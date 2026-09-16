"""Real-time collection progress via Server-Sent Events."""

from __future__ import annotations

import asyncio
import csv as _csv
import json
import logging
import uuid

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from apix.collectors.v2.orchestrator import (
    REFERENCE_CSV,
    ProgressEvent,
    run_collection,
)
from apix.collectors.v2.sources import SOURCES
from apix.pipeline.rebuild import rebuild_all
from apix.pipeline.runner import diagnose as _diagnose

LOG = logging.getLogger("apix.api.collect")

router = APIRouter(prefix="/api/v1/collect", tags=["collect"])

JOBS: dict[str, asyncio.Queue[ProgressEvent]] = {}
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()

DEFAULT_ROUTES = [
    {"label": "DEL-BOM", "origin_iata": "DEL", "destination_iata": "BOM"},
    {"label": "DEL-BLR", "origin_iata": "DEL", "destination_iata": "BLR"},
    {"label": "BOM-BLR", "origin_iata": "BOM", "destination_iata": "BLR"},
    {"label": "BOM-HYD", "origin_iata": "BOM", "destination_iata": "HYD"},
    {"label": "DEL-HYD", "origin_iata": "DEL", "destination_iata": "HYD"},
]


@router.post("/start")
async def start_collection() -> dict:
    job_id = uuid.uuid4().hex[:12]
    queue: asyncio.Queue[ProgressEvent] = asyncio.Queue()
    JOBS[job_id] = queue
    _task = asyncio.create_task(_run(job_id, DEFAULT_ROUTES, SOURCES, queue))
    _BACKGROUND_TASKS.add(_task)
    _task.add_done_callback(_BACKGROUND_TASKS.discard)
    return {"job_id": job_id, "routes": len(DEFAULT_ROUTES), "sources": len(SOURCES)}


async def _run(job_id, routes, sources, queue) -> None:
    try:
        await run_collection(job_id, routes, sources, progress_queue=queue)
    except Exception as e:
        LOG.exception("collection %s failed", job_id)
        await queue.put(
            ProgressEvent(
                job_id=job_id,
                route="",
                tier="",
                status="error",
                detail=str(e)[:160],
                elapsed_ms=0,
            )
        )
    finally:
        await queue.put(
            ProgressEvent(
                job_id=job_id,
                route="",
                tier="",
                status="__end__",
                detail="",
                elapsed_ms=0,
            )
        )


@router.get("/stream/{job_id}")
async def stream_progress(job_id: str):
    queue = JOBS.get(job_id)
    if not queue:
        return {"error": "unknown job"}

    async def event_gen():
        while True:
            event: ProgressEvent = await queue.get()
            if event.status == "__end__":
                yield {"event": "end", "data": "{}"}
                break
            yield {
                "event": "progress",
                "data": json.dumps(
                    {
                        "route": event.route,
                        "tier": event.tier,
                        "status": event.status,
                        "detail": event.detail,
                        "elapsed_ms": event.elapsed_ms,
                    }
                ),
            }

    return EventSourceResponse(event_gen())


@router.get("/preview")
async def preview_csv(limit: int = 50) -> dict:
    if not REFERENCE_CSV.exists():
        return {"rows": [], "total": 0, "path": str(REFERENCE_CSV), "exists": False}
    with REFERENCE_CSV.open("r", encoding="utf-8", newline="") as f:
        all_rows = list(_csv.DictReader(f))
    return {
        "rows": all_rows[-limit:],
        "total": len(all_rows),
        "path": str(REFERENCE_CSV),
        "exists": True,
    }


@router.post("/rebuild")
async def rebuild() -> dict:
    """CSV -> quotes -> clean -> index_points. Full chain, introspected."""
    return await rebuild_all()


@router.get("/diagnose")
async def pipeline_diagnose() -> dict:
    return await _diagnose()


@router.get("/db-state")
async def db_state() -> dict:
    """Counts in each pipeline table."""
    from sqlalchemy import func, select

    from apix.db import get_sessionmaker
    from apix.models import CleanPrice, FareQuote, IndexPoint, Route, Source

    async def _count(session, model):
        return (await session.execute(select(func.count()).select_from(model))).scalar_one()

    session_maker = get_sessionmaker()
    async with session_maker() as session:
        return {
            "routes": await _count(session, Route),
            "sources": await _count(session, Source),
            "quotes": await _count(session, FareQuote),
            "clean_prices": await _count(session, CleanPrice),
            "index_points": await _count(session, IndexPoint),
        }
