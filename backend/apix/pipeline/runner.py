"""Run the full chain: load CSV, clean, index.

Uses whichever entry point actually exists in the target module. If a
stage fails to find anything, it returns the module's public functions
so we can see what to call instead.
"""
from __future__ import annotations

import importlib
import inspect as pyinspect
import logging
import os
from pathlib import Path
from typing import Any

from .loader import load_csv_to_db

LOG = logging.getLogger("apix.pipeline.runner")

REFERENCE_CSV = Path(os.environ.get("APIX_REFERENCE_CSV", "reference.csv"))

STAGES: list[tuple[str, list[str], list[str]]] = [
    (
        "clean",
        ["apix.cleaning.pipeline", "apix.cleaning", "apix.pipeline.clean"],
        ["run_cleaning", "clean_quotes", "clean_all", "clean", "run"],
    ),
    (
        "index",
        ["apix.index.service", "apix.index.engine", "apix.index"],
        [
            "build_indices",
            "run_index",
            "build_index",
            "recompute",
            "compute_index",
            "publish",
        ],
    ),
]


def _discover_entry(module_name: str, names: list[str]) -> tuple[Any | None, str]:
    try:
        mod = importlib.import_module(module_name)
    except ImportError as e:
        return None, f"cannot import {module_name}: {e}"

    for name in names:
        if hasattr(mod, name):
            return getattr(mod, name), f"{module_name}.{name}"

    public = [
        n for n, o in pyinspect.getmembers(mod, pyinspect.isfunction)
        if not n.startswith("_")
    ]
    return None, f"no matching entry point in {module_name}; available: {public}"


async def _call_entry(entry: Any, session: Any) -> Any:
    if pyinspect.iscoroutinefunction(entry):
        try:
            return await entry(session)
        except TypeError:
            return await entry()
    try:
        return entry(session)
    except TypeError:
        return entry()


async def run_full_pipeline() -> dict:
    from apix.db import get_sessionmaker

    summary: dict[str, Any] = {"steps": []}

    load_result = await load_csv_to_db(REFERENCE_CSV)
    summary["steps"].append({"step": "load_csv", **load_result})

    if load_result.get("loaded", 0) == 0:
        summary["stopped"] = "nothing loaded; skipping clean/index"
        return summary

    session_maker = get_sessionmaker()
    async with session_maker() as session:
        for stage_name, modules, entries in STAGES:
            entry = None
            via = None
            reason = None

            for mod_name in modules:
                entry, via = _discover_entry(mod_name, entries)
                if entry is not None:
                    break
                reason = via

            if entry is None:
                summary["steps"].append({
                    "step": stage_name, "ok": False, "reason": reason,
                })
                continue

            try:
                result = await _call_entry(entry, session)
                summary["steps"].append({
                    "step": stage_name,
                    "ok": True,
                    "via": via,
                    "result": str(result)[:200] if result is not None else None,
                })
            except Exception as e:
                LOG.exception("%s failed", stage_name)
                summary["steps"].append({
                    "step": stage_name,
                    "ok": False,
                    "via": via,
                    "error": f"{type(e).__name__}: {e}",
                })

    return summary


async def diagnose() -> dict:
    out: dict[str, Any] = {}
    for _name, modules, _entries in STAGES:
        for mod_name in modules:
            try:
                mod = importlib.import_module(mod_name)
                out[mod_name] = [
                    n for n, o in pyinspect.getmembers(mod, pyinspect.isfunction)
                    if not n.startswith("_")
                ]
            except ImportError as e:
                out[mod_name] = f"IMPORT ERROR: {e}"
    return out
