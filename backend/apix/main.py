"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from apix import __version__
from apix.api.collect import router as collect_router
from apix.api.router import router as api_router
from apix.db import get_engine
from apix.logging import configure_logging, get_logger
from apix.settings import get_settings

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    log.info(
        "apix.startup",
        version=__version__,
        env=settings.env.env,
        routes=len(settings.basket.routes),
        sources=len(settings.sources.sources),
    )
    yield
    log.info("apix.shutdown")


app = FastAPI(
    title="APix",
    version=__version__,
    description="Real-time Airfare Price Index for India",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().env.cors_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(collect_router)


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    """Liveness + DB connectivity."""
    db_status = "ok"
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        log.error("healthz.db_failed", error=str(exc), exc_type=type(exc).__name__)
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": __version__,
        "db": db_status,
        "scheduler": "not_started",
    }
