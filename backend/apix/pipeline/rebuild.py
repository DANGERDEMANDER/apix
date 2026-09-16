"""End-to-end rebuild: CSV -> quotes -> clean -> index_points.

Introspects models at runtime so it works with whatever column names
the project actually has. Fills required columns with sensible
defaults so route/source auto-creation never fails on NOT NULL.
"""

from __future__ import annotations

import csv
import importlib
import inspect as pyinspect
import logging
import os
from collections.abc import Callable
from datetime import date as date_cls
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

LOG = logging.getLogger("apix.pipeline.rebuild")

REFERENCE_CSV = Path(
    os.environ.get(
        "APIX_REFERENCE_CSV",
        str(Path(__file__).resolve().parents[3] / "reference.csv"),
    )
)


# ─── Introspection helpers ──────────────────────────────────────


def _cols(model: Any) -> dict[str, Any]:
    from sqlalchemy import inspect as sa_inspect

    return {c.key: c for c in sa_inspect(model).columns}


def _required_cols(model: Any) -> list[str]:
    """Columns without default/nullable that must be supplied."""
    out = []
    for c in _cols(model).values():
        if c.primary_key:
            continue
        if c.nullable:
            continue
        if c.default is not None or c.server_default is not None:
            continue
        if c.foreign_keys:
            continue
        out.append(c.key)
    return out


def _default_for_col(col_name: str, col: Any) -> Any:
    """Best-effort value for a required column we didn't explicitly set."""
    # Enum types: try to introspect the values
    try:
        py_type = col.type.python_type
    except (AttributeError, NotImplementedError):
        py_type = None

    # Enum: pick first enum value
    if type(col.type).__name__ == "Enum" and hasattr(col.type, "enums"):
        enums = col.type.enums or []
        if enums:
            return enums[0]

    # Boolean
    if py_type is bool:
        return False
    # Integer
    if py_type is int:
        return 0
    # Float / Decimal
    if py_type in (float,):
        return 0.0
    if py_type and py_type.__name__ == "Decimal":
        return 0
    # Date / datetime
    if py_type is date_cls:
        return date_cls.today()
    if py_type is datetime:
        return datetime.now(timezone.utc)
    # Strings
    if py_type is str or py_type is None:
        n = col_name.lower()
        if "url" in n:
            return "https://example.com"
        if "name" in n or "slug" in n or "label" in n:
            return "unknown"
        if "code" in n:
            return "UNK"
        if "note" in n or "desc" in n:
            return ""
        if "version" in n:
            return "1"
        return "unknown"

    # Unknown — try a string, most things coerce
    return "unknown"


async def _count(session: Any, model: Any) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


# ─── Step 1: ensure routes exist ────────────────────────────────


async def _ensure_routes(session: Any, csv_rows: list[dict]) -> dict:
    from apix.models import Route

    cols = _cols(Route)
    route_col = next(
        (k for k in ("label", "code", "name", "route_label", "route_code") if k in cols),
        None,
    )
    if not route_col:
        return {"ok": False, "reason": f"no label/code column; cols={list(cols)}"}

    origin_col = next((k for k in ("origin_iata", "origin", "from_iata") if k in cols), None)
    dest_col = next((k for k in ("destination_iata", "destination", "to_iata") if k in cols), None)

    needed: dict[str, dict] = {}
    for r in csv_rows:
        label = (r.get("route") or "").strip()
        if not label:
            continue
        parts = label.split("-")
        needed[label] = {
            "origin": (r.get("origin") or (parts[0] if parts else "")).strip(),
            "destination": (r.get("destination") or (parts[1] if len(parts) > 1 else "")).strip(),
        }

    existing = {
        getattr(rt, route_col, None) for rt in (await session.execute(select(Route))).scalars()
    }
    existing.discard(None)

    created = 0
    for label, info in needed.items():
        if label in existing:
            continue

        payload: dict[str, Any] = {route_col: label}
        if origin_col:
            payload[origin_col] = info["origin"]
        if dest_col:
            payload[dest_col] = info["destination"]

        # Fill every remaining required column with a default
        for req in _required_cols(Route):
            if req in payload:
                continue
            payload[req] = _default_for_col(req, cols[req])

        session.add(Route(**payload))
        created += 1

    await session.flush()
    return {"ok": True, "created": created, "total": len(needed)}


# ─── Step 2: ensure sources exist ───────────────────────────────


async def _ensure_sources(session: Any, csv_rows: list[dict]) -> dict:
    from apix.models import Source

    cols = _cols(Source)
    name_col = next(
        (k for k in ("name", "slug", "code", "key") if k in cols),
        None,
    )
    if not name_col:
        return {"ok": False, "reason": f"no name/slug column; cols={list(cols)}"}

    # Figure out sensible enum values by source name
    kind_col = cols.get("kind")
    kind_value_for: dict[str, str] = {}
    if kind_col is not None and type(kind_col.type).__name__ == "Enum":
        enum_values = list(kind_col.type.enums or [])
        # Heuristic mapping
        for r in csv_rows:
            src = (r.get("source") or "").strip()
            if not src:
                continue
            lower = src.lower()
            if (
                "google" in lower
                and "scrape" in enum_values
                or "makemytrip" in lower
                and "scrape" in enum_values
            ):
                kind_value_for[src] = "scrape"
            elif "amadeus" in lower and "api" in enum_values or "api" in enum_values:
                kind_value_for[src] = "api"
            elif enum_values:
                kind_value_for[src] = enum_values[0]

    needed = {(r.get("source") or "").strip() for r in csv_rows if r.get("source")}
    existing = {
        getattr(s, name_col, None) for s in (await session.execute(select(Source))).scalars()
    }
    existing.discard(None)

    created = 0
    for name in needed:
        if name in existing:
            continue

        payload: dict[str, Any] = {name_col: name}

        # Prefer explicit kind mapping
        if kind_col is not None and name in kind_value_for:
            payload["kind"] = kind_value_for[name]

        # Fill every remaining required column with a default
        for req in _required_cols(Source):
            if req in payload:
                continue
            payload[req] = _default_for_col(req, cols[req])

        session.add(Source(**payload))
        created += 1

    await session.flush()
    return {"ok": True, "created": created, "total": len(needed)}


# ─── Step 3: load CSV into quotes ───────────────────────────────


async def _load_quotes(session: Any, csv_rows: list[dict]) -> dict:
    from apix.models import FareQuote, Route, Source

    fq_cols = _cols(FareQuote)
    rt_cols = _cols(Route)
    src_cols = _cols(Source)

    route_col = next((k for k in ("label", "code", "name") if k in rt_cols), None)
    src_col = next((k for k in ("name", "slug", "code") if k in src_cols), None)

    price_col = next(
        (k for k in ("fare_inr", "fare", "price", "amount", "raw_fare", "value") if k in fq_cols),
        None,
    )
    date_col = next(
        (k for k in ("observed_date", "date", "quote_date", "day") if k in fq_cols),
        None,
    )
    ts_col = next(
        (k for k in ("captured_at", "observed_at", "collected_at", "fetched_at") if k in fq_cols),
        None,
    )

    if not price_col:
        return {"ok": False, "reason": f"no price column; fq_cols={list(fq_cols)}"}

    route_map = {
        getattr(rt, route_col, None): rt for rt in (await session.execute(select(Route))).scalars()
    }
    source_map = {
        getattr(s, src_col, None): s for s in (await session.execute(select(Source))).scalars()
    }

    inserted = 0
    skipped_reasons: dict[str, int] = {}

    def _skip(reason: str) -> None:
        skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1

    for r in csv_rows:
        try:
            fare = float(r.get("fare_inr") or r.get("fare") or r.get("price") or 0)
        except (TypeError, ValueError):
            _skip("bad_fare")
            continue
        if fare <= 0:
            _skip("zero_fare")
            continue

        label = (r.get("route") or "").strip()
        rt = route_map.get(label)
        if not rt:
            _skip("unknown_route")
            continue

        src_name = (r.get("source") or "").strip()
        s = source_map.get(src_name)
        if not s:
            _skip("unknown_source")
            continue

        payload: dict[str, Any] = {}
        if "route_id" in fq_cols:
            payload["route_id"] = rt.id
        if "source_id" in fq_cols:
            payload["source_id"] = s.id

        # Fill every remaining required column with a default
        for req in _required_cols(FareQuote):
            if req in payload:
                continue
            payload[req] = _default_for_col(req, fq_cols[req])

        # Overrides with real values
        payload[price_col] = fare
        if date_col:
            try:
                payload[date_col] = date_cls.fromisoformat(
                    r.get("date") or date_cls.today().isoformat()
                )
            except ValueError:
                payload[date_col] = date_cls.today()
        if ts_col:
            try:
                payload[ts_col] = datetime.fromisoformat(
                    (r.get("captured_at") or datetime.now(timezone.utc).isoformat()).replace(
                        "Z", "+00:00"
                    )
                )
            except ValueError:
                payload[ts_col] = datetime.now(timezone.utc)
        if "currency" in fq_cols:
            payload["currency"] = r.get("currency") or "INR"
        if "tier" in fq_cols:
            payload["tier"] = r.get("tier") or "api"

        session.add(FareQuote(**payload))
        inserted += 1

    await session.flush()
    return {
        "ok": True,
        "inserted": inserted,
        "skipped": sum(skipped_reasons.values()),
        "skip_reasons": skipped_reasons,
    }


# ─── Step 4: run cleaning / index stages ────────────────────────


async def _run_stage(
    stage_name: str, module_names: list[str], entries: list[str], session: Any
) -> dict:
    entry: Callable[..., Any] | None = None
    via = ""

    for mod_name in module_names:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        for name in entries:
            if hasattr(mod, name):
                entry = getattr(mod, name)
                via = f"{mod_name}.{name}"
                break
        if entry:
            break

    if entry is None:
        return {"ok": False, "reason": f"no matching function in {module_names}"}

    sig = pyinspect.signature(entry)
    params = list(sig.parameters.keys())

    async def _try(*args, **kwargs):
        if pyinspect.iscoroutinefunction(entry):
            return await entry(*args, **kwargs)
        return entry(*args, **kwargs)

    last_err: Exception | None = None
    for call in (lambda: _try(session), lambda: _try()):
        try:
            result = await call()
            return {"ok": True, "via": via, "signature": params, "result": str(result)[:200]}
        except TypeError as e:
            last_err = e
            continue
        except Exception as e:
            return {
                "ok": False,
                "via": via,
                "signature": params,
                "error": f"{type(e).__name__}: {e}",
            }

    return {
        "ok": False,
        "via": via,
        "signature": params,
        "error": f"all call shapes failed: {last_err}",
    }


# ─── Main entry ─────────────────────────────────────────────────


async def rebuild_all() -> dict:
    from apix.db import get_sessionmaker

    out: dict[str, Any] = {"csv": str(REFERENCE_CSV)}

    if not REFERENCE_CSV.exists():
        out["error"] = "reference.csv not found"
        return out

    with REFERENCE_CSV.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    out["csv_rows"] = len(rows)

    if not rows:
        out["error"] = "csv is empty"
        return out

    session_maker = get_sessionmaker()

    async with session_maker() as session:
        out["routes"] = await _ensure_routes(session, rows)
        out["sources"] = await _ensure_sources(session, rows)
        await session.commit()

    async with session_maker() as session:
        out["quotes"] = await _load_quotes(session, rows)
        await session.commit()

    async with session_maker() as session:
        out["clean"] = await _run_stage(
            "clean",
            ["apix.cleaning.pipeline", "apix.cleaning"],
            ["run_cleaning", "clean_quotes", "clean_all"],
            session,
        )
        await session.commit()

    async with session_maker() as session:
        out["index"] = await _run_stage(
            "index",
            ["apix.index.service", "apix.index.engine"],
            ["build_indices", "run_index", "build_index", "compute_index"],
            session,
        )
        await session.commit()

    out["totals"] = await _counts(session_maker)
    return out


async def _counts(session_maker) -> dict:
    """Count rows in each pipeline model."""
    import apix.models as m

    models = {
        "routes": "Route",
        "sources": "Source",
        "quotes": "FareQuote",
        "clean_fares": "CleanFare",
        "daily_prices": "DailyRoutePrice",
        "index_values": "IndexValue",
        "dgca_refs": "DgcaReference",
    }

    out: dict[str, Any] = {}
    async with session_maker() as session:
        for label, cls_name in models.items():
            cls = getattr(m, cls_name, None)
            if cls is None:
                out[label] = f"missing class {cls_name}"
                continue
            try:
                out[label] = await _count(session, cls)
            except Exception as e:
                out[label] = f"error: {type(e).__name__}: {e}"
    return out
