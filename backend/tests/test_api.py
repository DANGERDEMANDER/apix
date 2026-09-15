"""Integration tests for the Phase 6 API endpoints.

Every test uses the db_session fixture from conftest.py, which points at
apix_test. The session dependency of the FastAPI app is overridden to use
the same session.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apix.db import session_dependency
from apix.main import app
from apix.models.indices import Frequency, IndexStatus, IndexValue, Measure
from apix.models.routes import Route, WeightSource
from apix.models.runs import CollectionRun, RunMode, RunStatus


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """httpx.AsyncClient bound to the FastAPI app, with the test session injected."""

    async def _override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[session_dependency] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _seed_min_routes(session: AsyncSession) -> None:
    session.add(
        Route(
            origin_iata="DEL",
            destination_iata="BOM",
            label="DEL-BOM",
            dgca_pax_annual=8_500_000,
            weight=Decimal("1.000000"),
            weight_period="FY2024-25",
            weight_source=WeightSource.DGCA_SYNTHETIC,
            weight_source_note="test placeholder",
            is_active=True,
        )
    )
    session.add(
        CollectionRun(
            mode=RunMode.SYNTHETIC,
            started_at=datetime(2025, 9, 1, 6, 0, tzinfo=timezone.utc),
            finished_at=datetime(2025, 9, 1, 6, 5, tzinfo=timezone.utc),
            status=RunStatus.SUCCESS,
            quotes_collected=100,
            quotes_expected=100,
            blocked_sources=[],
            error_summary={},
            seed=42,
        )
    )
    await session.flush()


async def test_healthz(client: AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"ok", "degraded"}
    assert "version" in body


async def test_routes_empty(client: AsyncClient) -> None:
    r = await client.get("/api/v1/routes")
    assert r.status_code == 200
    body = r.json()
    assert body["routes"] == []
    assert body["meta"]["mode"] == "unknown"


async def test_routes_after_seed(client: AsyncClient, db_session: AsyncSession) -> None:
    await _seed_min_routes(db_session)
    await db_session.commit()

    r = await client.get("/api/v1/routes")
    assert r.status_code == 200
    body = r.json()
    assert len(body["routes"]) == 1
    assert body["routes"][0]["label"] == "DEL-BOM"
    assert body["meta"]["mode"] == "synthetic"


async def test_index_latest_no_data(client: AsyncClient) -> None:
    r = await client.get("/api/v1/index/latest?measure=base&frequency=daily")
    assert r.status_code == 200
    body = r.json()
    assert body["as_of"] is None
    assert body["value"] is None
    assert body["status"] == "no_data"


async def test_index_empty_range(client: AsyncClient) -> None:
    r = await client.get("/api/v1/index?measure=base&frequency=daily")
    assert r.status_code == 200
    body = r.json()
    assert body["points"] == []


async def test_contributions_404(client: AsyncClient) -> None:
    r = await client.get("/api/v1/index/2025-01-01/contributions")
    assert r.status_code == 404
    assert "error" in r.json()["detail"]


async def test_index_with_seeded_value(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_min_routes(db_session)
    db_session.add(
        IndexValue(
            date=date(2025, 9, 15),
            frequency=Frequency.DAILY,
            measure=Measure.BASE,
            value=Decimal("101.2345"),
            base_period="2025-09-01..2025-09-14",
            routes_included=1,
            weight_covered=Decimal("1.000000"),
            contributions={"DEL-BOM": 101.2345},
            status=IndexStatus.PUBLISHED,
            withheld_reason=None,
        )
    )
    await db_session.commit()

    r = await client.get("/api/v1/index?measure=base&frequency=daily")
    assert r.status_code == 200
    body = r.json()
    assert len(body["points"]) == 1
    assert body["points"][0]["date"] == "2025-09-15"
    assert body["base_period"] == "2025-09-01..2025-09-14"

    r2 = await client.get("/api/v1/index/latest?measure=base&frequency=daily")
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2["as_of"] == "2025-09-15"

    r3 = await client.get("/api/v1/index/2025-09-15/contributions")
    assert r3.status_code == 200
    b3 = r3.json()
    assert len(b3["contributions"]) == 1
    assert b3["contributions"][0]["route_label"] == "DEL-BOM"
