"""Async SQLAlchemy 2.0 engine + session factory.

In the "ci" and "local" environments we use NullPool so that every connection
is created fresh. This is required on Windows because pytest-asyncio creates a
new event loop per test, and pooled asyncpg connections bound to a dead loop
cannot be reused. In "docker"/production, the default pooling is fine.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool

from apix.settings import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _pool_for_env(env: str) -> type:
    # NullPool in test/dev keeps each connection tied to its own loop.
    return NullPool if env in {"ci", "local"} else AsyncAdaptedQueuePool


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.env.db_url,
            pool_pre_ping=True,
            future=True,
            poolclass=_pool_for_env(settings.env.env),
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def session_dependency() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session per request."""
    async with get_sessionmaker()() as session:
        yield session
