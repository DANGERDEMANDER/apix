"""Shared test fixtures.

Uses a dedicated apix_test database so pytest never touches the dev
database. The APIX_DB_URL env var is overridden at module scope, before
any apix import reads get_settings().
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

_REPO_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("APIX_CONFIG_DIR", str(_REPO_ROOT / "config"))
os.environ.setdefault("APIX_ENV", "ci")

# Force tests onto apix_test. This must run before any apix module is
# imported, so it lives above the apix imports below.
_TEST_DB_URL = os.environ.get(
    "APIX_TEST_DB_URL",
    "postgresql+asyncpg://apix:apix@127.0.0.1:5432/apix_test",
)
os.environ["APIX_DB_URL"] = _TEST_DB_URL

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return _REPO_ROOT


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator["AsyncSession"]:
    """Create all tables in apix_test, yield a session, drop all tables."""
    from apix.db import get_engine, get_sessionmaker
    from apix.models import Base

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_maker = get_sessionmaker()
    async with session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()
