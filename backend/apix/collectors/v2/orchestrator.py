"""Orchestrates a collection run: spawns workers, emits events, writes CSV.

Writes each worker's rows to reference.csv as soon as that worker
finishes, so the UI sees the file grow during the run instead of
waiting for every route to complete.
"""

from __future__ import annotations

import asyncio
import csv
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

LOG = logging.getLogger("apix.collector.orchestrator")

# Resolve to an absolute path so subprocesses and reloads agree.
_default_csv = Path(__file__).resolve().parents[3] / "reference.csv"
REFERENCE_CSV = Path(os.environ.get("APIX_REFERENCE_CSV", str(_default_csv)))

LOG.info("reference.csv path: %s", REFERENCE_CSV)

SOURCE_TIMEOUT_S = 60


@dataclass
class ProgressEvent:
    job_id: str
    route: str
    tier: str
    status: str
    detail: str
    elapsed_ms: int


@dataclass
class QuoteRow:
    date: str
    route: str
    origin: str
    destination: str
    source: str
    tier: str
    fare_inr: float
    currency: str
    captured_at: str


# --- Atomic CSV writer -----------------------------------------


def _read_existing() -> list[dict]:
    if not REFERENCE_CSV.exists():
        return []
    with REFERENCE_CSV.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_atomic(rows: list[dict]) -> None:
    REFERENCE_CSV.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".reference.", suffix=".csv", dir=str(REFERENCE_CSV.parent))
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        with tmp_path.open("w", encoding="utf-8", newline="") as f:
            if not rows:
                return
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_path, REFERENCE_CSV)
        LOG.info("wrote %d rows to %s", len(rows), REFERENCE_CSV)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


# Lock so concurrent workers don't clobber each other's writes.
_write_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    global _write_lock
    if _write_lock is None or _write_lock._loop is not asyncio.get_running_loop():  # type: ignore[attr-defined]
        _write_lock = asyncio.Lock()
    return _write_lock


async def append_quotes(new_rows: list[QuoteRow]) -> None:
    """Append rows atomically. Safe to call from concurrent workers."""
    if not new_rows:
        return
    async with _get_lock():
        existing = _read_existing()
        existing.extend(asdict(r) for r in new_rows)
        _write_atomic(existing)


# --- Worker --------------------------------------------


async def _worker_api(
    job_id: str,
    route: dict,
    source: dict,
    queue: asyncio.Queue[ProgressEvent],
    semaphore: asyncio.Semaphore,
) -> list[QuoteRow]:
    label = route["label"]
    tier = source["name"].split()[0].lower()
    started = asyncio.get_event_loop().time()

    async def emit(status: str, detail: str) -> None:
        await queue.put(
            ProgressEvent(
                job_id,
                label,
                tier,
                status,
                detail,
                int((asyncio.get_event_loop().time() - started) * 1000),
            )
        )

    await emit("start", f"{source['name']} \u00b7 queued")

    needs_browser = source.get("needs_browser", False)

    async def call_search() -> list[dict]:
        return await source["search"](
            route["origin_iata"],
            route["destination_iata"],
        )

    try:
        if needs_browser:
            async with semaphore:
                await emit("start", f"{source['name']} \u00b7 browser acquired")
                fares = await asyncio.wait_for(call_search(), timeout=SOURCE_TIMEOUT_S)
        else:
            fares = await asyncio.wait_for(call_search(), timeout=SOURCE_TIMEOUT_S)

        rows = [
            QuoteRow(
                date=date.today().isoformat(),
                route=label,
                origin=route["origin_iata"],
                destination=route["destination_iata"],
                source=source["name"],
                tier=tier,
                fare_inr=float(f["fare_inr"]),
                currency=f.get("currency", "INR"),
                captured_at=datetime.utcnow().isoformat() + "Z",
            )
            for f in fares
        ]

        # Write immediately so the UI sees the CSV grow
        if rows:
            await append_quotes(rows)
            await emit("done", f"{len(rows)} fares \u00b7 csv updated")
        else:
            await emit("done", "0 fares (parser found nothing)")

        return rows

    except TimeoutError:
        await emit("error", f"timeout after {SOURCE_TIMEOUT_S}s")
        return []
    except Exception as e:
        await emit("error", f"{type(e).__name__}: {str(e)[:120]}")
        return []


# --- Main entry -----------------------------------------


async def run_collection(
    job_id: str,
    routes: list[dict],
    sources: list[dict],
    *,
    progress_queue: asyncio.Queue[ProgressEvent],
) -> list[QuoteRow]:
    # Fresh semaphore per run — avoids "bound to a dead loop" after reload.
    semaphore = asyncio.Semaphore(2)

    tasks = [
        _worker_api(job_id, route, source, progress_queue, semaphore)
        for route in routes
        for source in sources
    ]
    batches = await asyncio.gather(*tasks, return_exceptions=True)

    all_rows: list[QuoteRow] = []
    for b in batches:
        if isinstance(b, list):
            all_rows.extend(b)

    LOG.info("collection %s complete: %d quotes total", job_id, len(all_rows))
    return all_rows
