"""?7 ? index construction service.

Reads fare_quotes. Writes:
  - daily_route_price    (?7.1)
  - index_base_values    (?7.2, P(i,0) per route per measure)
  - index_values         (?7.4 daily, ?7.5 weekly and monthly)

Public API:
    build_daily_prices(session, from_date, to_date) -> int
    build_indices(session, from_date, to_date) -> int

build_daily_prices must run before build_indices.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from apix.index.engine import IndexResult, IndexStatus, compute_index
from apix.index.relative import compute_base_value
from apix.index.weights import normalise_weights
from apix.index.window_agg import aggregate_windows
from apix.models.indices import Frequency, IndexBaseValue, IndexValue, Measure
from apix.models.prices import DailyRoutePrice
from apix.models.quotes import FareQuote
from apix.models.routes import Route
from apix.settings import get_settings

MeasureStr = Literal["base", "total"]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _bounds(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    """[start, end) UTC bounds for a collection-date range."""
    start = datetime.combine(from_date, time(0, 0), tzinfo=UTC)
    end = datetime.combine(to_date + timedelta(days=1), time(0, 0), tzinfo=UTC)
    return start, end


async def _load_active_routes(session: AsyncSession) -> dict[int, Route]:
    rows = (await session.execute(select(Route).where(Route.is_active.is_(True)))).scalars().all()
    return {r.id: r for r in rows}


async def _load_quotes(session: AsyncSession, from_date: date, to_date: date) -> list[FareQuote]:
    start, end = _bounds(from_date, to_date)
    stmt = select(FareQuote).where(
        FareQuote.collected_at >= start,
        FareQuote.collected_at < end,
        FareQuote.is_sold_out.is_(False),
    )
    return list((await session.execute(stmt)).scalars().all())


async def _load_daily_prices(
    session: AsyncSession, from_date: date, to_date: date
) -> list[DailyRoutePrice]:
    stmt = (
        select(DailyRoutePrice)
        .where(
            DailyRoutePrice.date >= from_date,
            DailyRoutePrice.date <= to_date,
        )
        .order_by(DailyRoutePrice.date, DailyRoutePrice.route_id)
    )
    return list((await session.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# ?7.1 ? daily_route_price
# ---------------------------------------------------------------------------


async def build_daily_prices(session: AsyncSession, from_date: date, to_date: date) -> int:
    """Aggregate fare_quotes into daily_route_price for the range.

    Idempotent: existing rows in [from_date, to_date] are replaced.
    """
    settings = get_settings()
    window_weights = {k: Decimal(str(v)) for k, v in settings.index.window_weights.items()}
    total_windows = len(settings.index.advance_windows_days)

    routes = await _load_active_routes(session)
    if not routes:
        raise RuntimeError("no active routes ? run apix seed first")

    quotes = await _load_quotes(session, from_date, to_date)

    base_bucket: dict[tuple[date, int], dict[int, list[Decimal]]] = defaultdict(
        lambda: defaultdict(list)
    )
    total_bucket: dict[tuple[date, int], dict[int, list[Decimal]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for q in quotes:
        coll_date = q.collected_at.date()
        key = (coll_date, q.route_id)
        if q.base_fare is not None:
            base_bucket[key][q.advance_days].append(q.base_fare)
        if q.total_fare is not None:
            total_bucket[key][q.advance_days].append(q.total_fare)

    await session.execute(
        delete(DailyRoutePrice).where(
            DailyRoutePrice.date >= from_date,
            DailyRoutePrice.date <= to_date,
        )
    )

    keys = set(base_bucket.keys()) | set(total_bucket.keys())
    written = 0
    for coll_date, route_id in keys:
        base_agg = aggregate_windows(base_bucket.get((coll_date, route_id), {}), window_weights)
        total_agg = aggregate_windows(total_bucket.get((coll_date, route_id), {}), window_weights)
        if base_agg is None or total_agg is None:
            continue
        windows_present = max(len(base_agg.windows_present), len(total_agg.windows_present))
        coverage_pct = (
            Decimal(windows_present) / Decimal(total_windows) * Decimal("100")
        ).quantize(Decimal("0.01"))
        n_quotes = base_agg.n_quotes + total_agg.n_quotes

        session.add(
            DailyRoutePrice(
                date=coll_date,
                route_id=route_id,
                avg_base_fare=base_agg.price.quantize(Decimal("0.01")),
                avg_total_fare=total_agg.price.quantize(Decimal("0.01")),
                n_quotes=n_quotes,
                n_windows_present=windows_present,
                coverage_pct=coverage_pct,
            )
        )
        written += 1

    await session.flush()
    return written


# ---------------------------------------------------------------------------
# ?7.2 ? index_base_values
# ---------------------------------------------------------------------------


async def _write_base_values(
    session: AsyncSession,
    base_start: date,
    base_end: date,
    measure: Measure,
) -> dict[int, Decimal]:
    """Compute and write P(i,0) per route for one measure."""
    settings = get_settings()
    min_days = settings.index.base_period_min_route_days
    base_period_label = f"{base_start.isoformat()}..{base_end.isoformat()}"

    prices = await _load_daily_prices(session, base_start, base_end)

    per_route: dict[int, list[Decimal]] = defaultdict(list)
    for p in prices:
        val = p.avg_base_fare if measure == Measure.BASE else p.avg_total_fare
        per_route[p.route_id].append(val)

    await session.execute(
        delete(IndexBaseValue).where(
            IndexBaseValue.measure == measure,
            IndexBaseValue.base_period == base_period_label,
        )
    )

    result: dict[int, Decimal] = {}
    for route_id, vals in per_route.items():
        p_i0 = compute_base_value(vals, min_days=min_days)
        if p_i0 is None:
            continue
        result[route_id] = p_i0
        session.add(
            IndexBaseValue(
                route_id=route_id,
                measure=measure,
                base_period=base_period_label,
                p_i0=p_i0.quantize(Decimal("0.0001")),
                n_base_days=len(vals),
                computed_at=datetime.now(UTC),
            )
        )
    await session.flush()
    return result


# ---------------------------------------------------------------------------
# ?7.4 ? daily index_values
# ---------------------------------------------------------------------------


async def _write_index_value(
    session: AsyncSession,
    result: IndexResult,
    frequency: Frequency,
    measure: Measure,
    base_period_label: str,
) -> None:
    session.add(
        IndexValue(
            date=result.date,
            frequency=frequency,
            measure=measure,
            value=result.value,
            base_period=base_period_label,
            routes_included=result.routes_included,
            weight_covered=result.weight_covered.quantize(Decimal("0.000001")),
            contributions=result.contributions,
            status=result.status,
            withheld_reason=result.withheld_reason,
        )
    )


async def _compute_daily(
    session: AsyncSession,
    from_date: date,
    to_date: date,
    base_values_by_measure: dict[Measure, dict[int, Decimal]],
    base_period_label: str,
) -> dict[Measure, dict[date, IndexResult]]:
    settings = get_settings()
    routes = await _load_active_routes(session)
    route_weights = normalise_weights({r.id: r.dgca_pax_annual for r in routes.values()})
    route_labels = {r.id: r.label for r in routes.values()}

    prices = await _load_daily_prices(session, from_date, to_date)
    prices_by_date: dict[date, dict[int, tuple[Decimal, Decimal]]] = defaultdict(dict)
    for p in prices:
        prices_by_date[p.date][p.route_id] = (p.avg_base_fare, p.avg_total_fare)

    await session.execute(
        delete(IndexValue).where(
            IndexValue.date >= from_date,
            IndexValue.date <= to_date,
        )
    )

    daily: dict[Measure, dict[date, IndexResult]] = {
        Measure.BASE: {},
        Measure.TOTAL: {},
    }

    min_cov = Decimal(str(settings.index.min_publishable_coverage))

    for d in sorted(prices_by_date.keys()):
        for m in (Measure.BASE, Measure.TOTAL):
            if not base_values_by_measure.get(m):
                continue
            idx = 0 if m == Measure.BASE else 1
            route_prices = {rid: pair[idx] for rid, pair in prices_by_date[d].items()}
            result = compute_index(
                on_date=d,
                route_prices=route_prices,
                base_values=base_values_by_measure[m],
                route_weights=route_weights,
                route_labels=route_labels,
                min_coverage=min_cov,
            )
            daily[m][d] = result
            await _write_index_value(session, result, Frequency.DAILY, m, base_period_label)

    return daily


# ---------------------------------------------------------------------------
# ?7.5 ? weekly and monthly
# ---------------------------------------------------------------------------


def _iso_week_key(d: date) -> tuple[int, int]:
    y, w, _ = d.isocalendar()
    return (y, w)


def _month_key(d: date) -> tuple[int, int]:
    return (d.year, d.month)


async def _write_weekly(
    session: AsyncSession,
    daily: dict[date, IndexResult],
    measure: Measure,
    base_period_label: str,
    min_days: int = 5,
) -> int:
    weeks: dict[tuple[int, int], list[IndexResult]] = defaultdict(list)
    for d, r in daily.items():
        weeks[_iso_week_key(d)].append(r)

    written = 0
    for _, results in weeks.items():
        published = [
            r for r in results if r.status == IndexStatus.PUBLISHED and r.value is not None
        ]
        if len(published) < min_days:
            continue
        mean_value = (
            sum((r.value for r in published if r.value is not None), start=Decimal("0"))
            / Decimal(len(published))
        ).quantize(Decimal("0.0001"))
        mean_cov = (
            sum((r.weight_covered for r in published), start=Decimal("0")) / Decimal(len(published))
        ).quantize(Decimal("0.000001"))
        # Assign the value to the last day of the week for lack of a separate
        # week-key column; the DEMO_SCRIPT will explain this representation.
        ref_date = max(r.date for r in published)
        session.add(
            IndexValue(
                date=ref_date,
                frequency=Frequency.WEEKLY,
                measure=measure,
                value=mean_value,
                base_period=base_period_label,
                routes_included=sum(r.routes_included for r in published) // len(published),
                weight_covered=mean_cov,
                contributions={},
                status=IndexStatus.PUBLISHED,
                withheld_reason=None,
            )
        )
        written += 1
    return written


async def _write_monthly(
    session: AsyncSession,
    daily: dict[date, IndexResult],
    measure: Measure,
    base_period_label: str,
    min_days: int = 20,
) -> int:
    months: dict[tuple[int, int], list[IndexResult]] = defaultdict(list)
    for d, r in daily.items():
        months[_month_key(d)].append(r)

    written = 0
    for _, results in months.items():
        published = [
            r for r in results if r.status == IndexStatus.PUBLISHED and r.value is not None
        ]
        if len(published) < min_days:
            continue
        mean_value = (
            sum((r.value for r in published if r.value is not None), start=Decimal("0"))
            / Decimal(len(published))
        ).quantize(Decimal("0.0001"))
        mean_cov = (
            sum((r.weight_covered for r in published), start=Decimal("0")) / Decimal(len(published))
        ).quantize(Decimal("0.000001"))
        ref_date = max(r.date for r in published)
        session.add(
            IndexValue(
                date=ref_date,
                frequency=Frequency.MONTHLY,
                measure=measure,
                value=mean_value,
                base_period=base_period_label,
                routes_included=sum(r.routes_included for r in published) // len(published),
                weight_covered=mean_cov,
                contributions={},
                status=IndexStatus.PUBLISHED,
                withheld_reason=None,
            )
        )
        written += 1
    return written


# ---------------------------------------------------------------------------
# public: build_indices
# ---------------------------------------------------------------------------


async def build_indices(
    session: AsyncSession,
    from_date: date,
    to_date: date,
) -> tuple[int, int, int]:
    """Compute base values and index values. Returns (daily, weekly, monthly) counts."""
    settings = get_settings()
    base_days = settings.index.base_period_days
    base_end = from_date + timedelta(days=base_days - 1)
    base_period_label = f"{from_date.isoformat()}..{base_end.isoformat()}"

    base_values_by_measure: dict[Measure, dict[int, Decimal]] = {}
    for m in (Measure.BASE, Measure.TOTAL):
        base_values_by_measure[m] = await _write_base_values(session, from_date, base_end, m)

    daily = await _compute_daily(
        session, from_date, to_date, base_values_by_measure, base_period_label
    )

    n_daily = sum(len(v) for v in daily.values())
    n_weekly = 0
    n_monthly = 0
    for m in (Measure.BASE, Measure.TOTAL):
        n_weekly += await _write_weekly(session, daily[m], m, base_period_label)
        n_monthly += await _write_monthly(session, daily[m], m, base_period_label)

    await session.flush()
    return n_daily, n_weekly, n_monthly
