"""Orchestrate a collection run: create a collection_runs row, iterate cells,
insert fare_quotes rows, finalise the run.

Mode-agnostic plumbing between the collector layer and the DB. Synthetic
mode is implemented now; replay and live will follow the same insertion path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apix.collectors.base import RawQuote
from apix.collectors.festivals import load_festivals
from apix.collectors.synthetic import SyntheticConfig, build_collectors
from apix.models.quotes import DecompositionMethod, FareQuote
from apix.models.routes import Route
from apix.models.runs import CollectionRun, RunMode, RunStatus
from apix.models.sources import Source
from apix.settings import get_settings

_DEFAULT_SEED = 20260916


@dataclass(frozen=True)
class RunReport:
    run_id: int
    quotes_collected: int
    quotes_expected: int
    status: str
    blocked_sources: tuple[str, ...] = ()


async def _lookup_routes(session: AsyncSession) -> dict[str, Route]:
    rows = (await session.execute(select(Route))).scalars().all()
    return {r.label: r for r in rows}


async def _lookup_sources(session: AsyncSession) -> dict[str, Source]:
    rows = (await session.execute(select(Source))).scalars().all()
    return {s.name: s for s in rows}


def _to_decomposition(method: str) -> DecompositionMethod:
    return DecompositionMethod(method)


def _collected_at_for(quote: RawQuote) -> datetime:
    """Deterministic collection timestamp derived from the cell, not now()."""
    day = quote.departure_date - timedelta(days=quote.advance_days)
    return datetime.combine(day, time(6, 0), tzinfo=UTC)


async def _insert_quote(
    session: AsyncSession,
    run_id: int,
    route: Route,
    source: Source,
    quote: RawQuote,
) -> None:
    session.add(
        FareQuote(
            run_id=run_id,
            route_id=route.id,
            source_id=source.id,
            collected_at=_collected_at_for(quote),
            departure_date=quote.departure_date,
            advance_days=quote.advance_days,
            carrier=quote.carrier,
            flight_number=quote.flight_number,
            fare_class=quote.fare_class,
            base_fare=quote.base_fare,
            taxes=quote.taxes,
            udf=quote.udf,
            convenience_fee=quote.convenience_fee,
            total_fare=quote.total_fare,
            currency=quote.currency,
            is_sold_out=quote.is_sold_out,
            decomposition_method=_to_decomposition(quote.decomposition_method),
            raw_payload=quote.raw_payload,
        )
    )


async def run_synthetic(
    session: AsyncSession,
    from_date: date,
    to_date: date,
    seed: int | None = None,
) -> RunReport:
    """Backfill [from_date, to_date] with synthetic quotes."""
    settings = get_settings()
    cfg = SyntheticConfig(seed=seed if seed is not None else _DEFAULT_SEED)

    festivals = load_festivals(settings.env.config_dir)
    source_names = tuple(s.name for s in settings.sources.sources)
    collectors = build_collectors(source_names, cfg, festivals)

    routes = await _lookup_routes(session)
    sources = await _lookup_sources(session)

    if not routes:
        raise RuntimeError("no routes in DB - run apix seed first")
    if not sources:
        raise RuntimeError("no sources in DB - run apix seed first")

    run = CollectionRun(
        mode=RunMode.SYNTHETIC,
        started_at=datetime.now(UTC),
        status=RunStatus.RUNNING,
        quotes_collected=0,
        quotes_expected=0,
        blocked_sources=[],
        error_summary={},
        seed=cfg.seed,
    )
    session.add(run)
    await session.flush()

    collected = 0
    expected = 0

    d = from_date
    while d <= to_date:
        for collector in collectors:
            for route_label, route in routes.items():
                for adv in settings.index.advance_windows_days:
                    expected += 1
                    q = collector.generate(
                        route_label=route_label,
                        departure_date=d + timedelta(days=adv),
                        advance_days=adv,
                    )
                    if q is None:
                        continue
                    await _insert_quote(session, run.id, route, sources[collector.name], q)
                    collected += 1
        d = d + timedelta(days=1)

    run.finished_at = datetime.now(UTC)
    run.quotes_collected = collected
    run.quotes_expected = expected
    run.status = RunStatus.SUCCESS if collected > 0 else RunStatus.FAILED
    await session.flush()

    return RunReport(
        run_id=run.id,
        quotes_collected=collected,
        quotes_expected=expected,
        status=run.status.value,
    )


# ---------------------------------------------------------------------------
# Replay mode
# ---------------------------------------------------------------------------


async def run_replay(
    session: AsyncSession,
    *,
    source_name: str,
    collection_date: date,
    advance_days: int,
) -> RunReport:
    """Load one recorded fixture, parse it, insert quotes into fare_quotes."""
    from datetime import datetime, timezone

    from apix.collectors.replay import ReplayCollector
    from apix.models.runs import RunMode

    collector = ReplayCollector(source_name)
    routes = await _lookup_routes(session)
    sources = await _lookup_sources(session)
    if not routes:
        raise RuntimeError("no routes in DB - run apix seed first")
    if source_name not in sources:
        raise RuntimeError(f"unknown source {source_name!r}")

    run = CollectionRun(
        mode=RunMode.REPLAY,
        started_at=datetime.now(timezone.utc),
        status=RunStatus.RUNNING,
        quotes_collected=0,
        quotes_expected=len(routes),
        blocked_sources=[],
        error_summary={},
        seed=None,
        notes=f"replay: {source_name} advance_days={advance_days}",
    )
    session.add(run)
    await session.flush()

    collected = 0
    for route_label, route in routes.items():
        try:
            quotes = collector.collect_from_fixture(
                route_label=route_label,
                advance_days=advance_days,
                collected_at=datetime.combine(
                    collection_date,
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                ),
            )
        except FileNotFoundError:
            continue
        except Exception as exc:
            run.error_summary[route_label] = str(exc)
            continue
        for q in quotes:
            await _insert_quote(session, run.id, route, sources[source_name], q)
            collected += 1

    run.finished_at = datetime.now(timezone.utc)
    run.quotes_collected = collected
    run.status = RunStatus.SUCCESS if collected > 0 else RunStatus.PARTIAL
    await session.flush()

    return RunReport(
        run_id=run.id,
        quotes_collected=collected,
        quotes_expected=len(routes),
        status=run.status.value,
    )
