"""apix CLI: seed, collect, index."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date

from apix.db import get_sessionmaker
from apix.logging import configure_logging, get_logger
from apix.seed.basket import seed_routes
from apix.seed.dgca import seed_dgca_reference
from apix.seed.sources import seed_sources

log = get_logger(__name__)


async def _seed_all() -> None:
    configure_logging()
    async with get_sessionmaker()() as session:
        n_routes = await seed_routes(session)
        n_sources = await seed_sources(session)
        n_dgca = await seed_dgca_reference(session)
        await session.commit()
    log.info(
        "apix.seed.done",
        routes=n_routes,
        sources=n_sources,
        dgca_reference_rows=n_dgca,
    )
    print(f"Seeded {n_routes} routes, {n_sources} sources, {n_dgca} DGCA rows.")


async def _collect_synthetic(from_date: date, to_date: date, seed: int | None) -> None:
    configure_logging()
    from apix.collectors.service import run_synthetic

    async with get_sessionmaker()() as session:
        report = await run_synthetic(session, from_date, to_date, seed)
        await session.commit()
    log.info(
        "apix.collect.done",
        mode="synthetic",
        run_id=report.run_id,
        quotes=report.quotes_collected,
        expected=report.quotes_expected,
        status=report.status,
    )
    print(
        f"Run {report.run_id}: {report.quotes_collected} quotes collected "
        f"of {report.quotes_expected} expected ({report.status})."
    )


async def _run_index(from_date: date, to_date: date) -> None:
    configure_logging()
    from apix.index.service import build_daily_prices, build_indices

    async with get_sessionmaker()() as session:
        n_prices = await build_daily_prices(session, from_date, to_date)
        await session.commit()
        n_daily, n_weekly, n_monthly = await build_indices(session, from_date, to_date)
        await session.commit()

    log.info(
        "apix.index.done",
        daily_route_price_rows=n_prices,
        daily=n_daily,
        weekly=n_weekly,
        monthly=n_monthly,
    )
    print(
        f"Daily prices: {n_prices} rows  |  "
        f"Index values: daily={n_daily} weekly={n_weekly} monthly={n_monthly}"
    )


async def _run_backtest() -> None:
    configure_logging()
    from apix.backtest.service import run_backtest

    async with get_sessionmaker()() as session:
        result = await run_backtest(session)

    if not result.rows:
        print(result.provenance_note)
        return

    m = result.metrics
    print("Monthly backtest: APix vs DGCA reference")
    print("-" * 60)
    for r in result.rows:
        print(f"  {r.month}   APix={r.apix_pct_of_base:7.2f}   DGCA={r.dgca_pct_of_base:7.2f}")
    print("-" * 60)
    print(f"  Months compared      : {m.n_months}")
    print(f"  MAPE                 : {m.mape_pct:.2f}%")
    print(f"  Pearson r            : {m.pearson_r}")
    print(f"  Spearman rho         : {m.spearman_rho}")
    print(f"  Direction match      : {m.direction_match_pct}%")
    print("-" * 60)
    print(f"  {result.provenance_note}")


def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO date: {s}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="apix")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("seed", help="Seed routes, sources, and DGCA reference")

    collect = sub.add_parser("collect", help="Collect fare quotes (synthetic mode by default)")
    collect.add_argument("--mode", choices=["synthetic"], default="synthetic")
    collect.add_argument("--from", dest="from_date", type=_parse_date, required=True)
    collect.add_argument("--to", dest="to_date", type=_parse_date, required=True)
    collect.add_argument("--seed", type=int, default=None)

    index = sub.add_parser("index", help="Compute APix index from collected quotes")
    index.add_argument("--from", dest="from_date", type=_parse_date, required=True)
    index.add_argument("--to", dest="to_date", type=_parse_date, required=True)

    sub.add_parser("backtest", help="Compare monthly APix against DGCA reference")

    args = parser.parse_args(argv)

    if args.cmd == "seed":
        asyncio.run(_seed_all())
        return 0
    if args.cmd == "collect":
        if args.from_date > args.to_date:
            parser.error("--from must be <= --to")
        asyncio.run(_collect_synthetic(args.from_date, args.to_date, args.seed))
        return 0
    if args.cmd == "index":
        if args.from_date > args.to_date:
            parser.error("--from must be <= --to")
        asyncio.run(_run_index(args.from_date, args.to_date))
        return 0
    if args.cmd == "backtest":
        asyncio.run(_run_backtest())
        return 0

    parser.error(f"unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
