"""Google Flights scraper.

Runs the Playwright work in a subprocess so it is not affected by
uvicorn's Windows event-loop policy. The subprocess prints JSON to
stdout; we parse and return it.
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

LOG = logging.getLogger("apix.collector.google_flights")

WORKER_MODULE = "apix.collectors.v2._gf_worker"
WORKER_TIMEOUT_S = 60


def _run_worker(
    origin: str,
    destination: str,
    departure_date: str,
    max_results: int,
) -> list[dict[str, Any]]:
    """Blocking. Runs in a thread via run_in_executor."""
    # Prefer running the module by file path, so cwd doesn't matter
    worker_path = Path(__file__).parent / "_gf_worker.py"

    try:
        result = subprocess.run(
            [
                sys.executable,
                str(worker_path),
                origin,
                destination,
                departure_date,
                str(max_results),
            ],
            capture_output=True,
            text=True,
            timeout=WORKER_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"worker timeout after {WORKER_TIMEOUT_S}s") from e

    if result.returncode != 0:
        stderr = (result.stderr or "").strip().splitlines()
        detail = stderr[-1] if stderr else f"exit {result.returncode}"
        raise RuntimeError(f"worker failed: {detail[:200]}")

    try:
        parsed = json.loads(result.stdout)
        if not isinstance(parsed, list):
            raise RuntimeError(f"worker output not a list: {type(parsed).__name__}")
        return parsed
    except json.JSONDecodeError as e:
        raise RuntimeError(f"worker output not JSON: {e}; raw={result.stdout[:200]}") from e


async def search_fares(
    origin: str,
    destination: str,
    *,
    departure_date: str | None = None,
    max_results: int = 5,
) -> list[dict[str, Any]]:
    if not departure_date:
        departure_date = (date.today() + timedelta(days=30)).isoformat()

    loop = asyncio.get_running_loop()
    fares = await loop.run_in_executor(
        None,
        functools.partial(_run_worker, origin, destination, departure_date, max_results),
    )
    LOG.info("gf %s->%s parsed %d fares", origin, destination, len(fares))
    return fares


def parse_google_flights(payload: Any) -> list[float]:
    if isinstance(payload, dict):
        items = payload.get("fares") or []
    elif isinstance(payload, list):
        items = payload
    else:
        return []
    return [float(x["fare_inr"]) for x in items if isinstance(x, dict) and "fare_inr" in x]
