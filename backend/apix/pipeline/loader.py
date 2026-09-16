"""Load reference.csv into the quotes table.

Uses SQLAlchemy introspection so it adapts to whatever column names the
FareQuote model actually uses. On failure it prints the real columns so
you know exactly what to align.
"""

from __future__ import annotations

import csv
import logging
from datetime import date as date_cls
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select

LOG = logging.getLogger("apix.pipeline.loader")

# Columns we'll try, in priority order, when mapping CSV to FareQuote.
PRICE_CANDIDATES = ["fare_inr", "fare", "price", "amount", "raw_fare", "value"]
DATE_CANDIDATES = ["captured_at", "observed_at", "collected_at", "fetched_at", "inserted_at"]
DAY_CANDIDATES = ["date", "observed_date", "quote_date", "day"]
SOURCE_NAME_CANDIDATES = ["name", "slug", "code", "key"]


def _pick(row: dict, keys: list[str], default: Any = None) -> Any:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return default


def _columns(model: Any) -> set[str]:
    return {c.key for c in sa_inspect(model).columns}


async def load_csv_to_db(csv_path: Path) -> dict:
    """Idempotently load rows from `csv_path` into the quotes table."""
    from apix.db import get_sessionmaker
    from apix.models import FareQuote, Route, Source

    fq_cols = _columns(FareQuote)
    src_cols = _columns(Source)
    rt_cols = _columns(Route)

    LOG.info("FareQuote columns: %s", sorted(fq_cols))
    LOG.info("Source columns: %s", sorted(src_cols))
    LOG.info("Route columns: %s", sorted(rt_cols))

    if not csv_path.exists():
        return {
            "loaded": 0,
            "skipped": 0,
            "reason": "csv not found",
            "farequote_columns": sorted(fq_cols),
        }

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return {"loaded": 0, "skipped": 0, "reason": "csv empty"}

    # route lookup — try label, then code, then name
    route_key = next(
        (k for k in ("label", "code", "name", "route_label", "route_code") if k in rt_cols),
        None,
    )
    source_key = next((k for k in SOURCE_NAME_CANDIDATES if k in src_cols), None)

    if not route_key:
        return {
            "loaded": 0,
            "skipped": len(rows),
            "reason": f"Route model has no label/code column. columns={sorted(rt_cols)}",
        }
    if not source_key:
        return {
            "loaded": 0,
            "skipped": len(rows),
            "reason": f"Source model has no name/slug column. columns={sorted(src_cols)}",
        }

    inserted = 0
    skipped = 0
    skipped_reasons: dict[str, int] = {}

    def _skip(reason: str) -> None:
        nonlocal skipped
        skipped += 1
        skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1

    session_maker = get_sessionmaker()
    async with session_maker() as session:
        # Build lookup maps
        route_map: dict[str, Any] = {}
        for r in (await session.execute(select(Route))).scalars():
            val = getattr(r, route_key, None)
            if val:
                route_map[str(val)] = r

        source_map: dict[str, Any] = {}
        for s in (await session.execute(select(Source))).scalars():
            val = getattr(s, source_key, None)
            if val:
                source_map[str(val)] = s

        for raw in rows:
            fare_raw = _pick(raw, ["fare_inr", "fare", "price", "amount"])
            try:
                fare = float(fare_raw) if fare_raw is not None else 0.0
            except (TypeError, ValueError):
                _skip("bad_fare")
                continue
            if fare <= 0:
                _skip("zero_fare")
                continue

            route_label = raw.get("route") or raw.get("label") or ""
            route = route_map.get(route_label)
            if not route:
                _skip("unknown_route")
                continue

            src_name = raw.get("source") or "unknown"
            source = source_map.get(src_name)
            if not source:
                source = Source(**{source_key: src_name})
                session.add(source)
                await session.flush()
                source_map[src_name] = source

            captured_raw = _pick(raw, ["captured_at", "observed_at"])
            if captured_raw:
                try:
                    captured = datetime.fromisoformat(str(captured_raw).replace("Z", "+00:00"))
                except ValueError:
                    captured = datetime.now(timezone.utc)
            else:
                captured = datetime.now(timezone.utc)

            day_raw = raw.get("date")
            try:
                day = date_cls.fromisoformat(day_raw) if day_raw else date_cls.today()
            except ValueError:
                day = date_cls.today()

            # Build a payload using ONLY columns that actually exist on FareQuote
            payload: dict[str, Any] = {}
            candidate_values = {
                "route_id": getattr(route, "id", None),
                "source_id": getattr(source, "id", None),
                "currency": raw.get("currency") or "INR",
                "tier": raw.get("tier") or "api",
                "captured_at": captured,
                "observed_at": captured,
                "date": day,
                "observed_date": day,
            }
            for k, v in candidate_values.items():
                if k in fq_cols and v is not None:
                    payload[k] = v
            for price_col in PRICE_CANDIDATES:
                if price_col in fq_cols:
                    payload[price_col] = fare
                    break

            if "route_id" not in payload or "source_id" not in payload:
                _skip("missing_fk_columns")
                continue
            if not any(p in payload for p in PRICE_CANDIDATES):
                _skip("missing_price_column")
                continue

            session.add(FareQuote(**payload))
            inserted += 1

        await session.commit()

    return {
        "loaded": inserted,
        "skipped": skipped,
        "total_rows": len(rows),
        "skip_reasons": skipped_reasons,
        "farequote_columns": sorted(fq_cols),
    }
