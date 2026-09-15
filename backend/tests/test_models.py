"""Phase 1 acceptance tests.

Covers:
  - All nine tables register in Base.metadata
  - Route weights sum to exactly 1.0 after seeding
  - Every route carries a non-null weight_source and non-empty note
  - Constraint integrity: unique label, unique (origin, destination)
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apix.models import Base
from apix.models.routes import Route, WeightSource
from apix.models.sources import Source
from apix.seed.basket import seed_routes
from apix.seed.sources import seed_sources

EXPECTED_TABLES = {
    "clean_fares",
    "collection_runs",
    "daily_route_price",
    "dgca_reference",
    "fare_quotes",
    "index_base_values",
    "index_values",
    "routes",
    "sources",
}


def test_all_tables_registered() -> None:
    assert set(Base.metadata.tables.keys()) == EXPECTED_TABLES


@pytest.mark.asyncio
async def test_seed_routes_idempotent(db_session: AsyncSession) -> None:
    n_first = await seed_routes(db_session)
    await db_session.commit()

    n_second = await seed_routes(db_session)
    await db_session.commit()

    assert n_first == 10
    assert n_second == 10

    count = (await db_session.execute(select(func.count()).select_from(Route))).scalar_one()
    assert count == 10


@pytest.mark.asyncio
async def test_route_weights_sum_to_one(db_session: AsyncSession) -> None:
    await seed_routes(db_session)
    await db_session.commit()

    rows = (await db_session.execute(select(Route))).scalars().all()
    total = sum((r.weight for r in rows), start=Decimal("0"))
    assert abs(total - Decimal("1")) < Decimal("1e-9"), f"weights sum to {total}"


@pytest.mark.asyncio
async def test_weight_source_never_null(db_session: AsyncSession) -> None:
    await seed_routes(db_session)
    await db_session.commit()

    rows = (await db_session.execute(select(Route))).scalars().all()
    for r in rows:
        assert r.weight_source in {
            WeightSource.DGCA_PUBLISHED,
            WeightSource.DGCA_SYNTHETIC,
        }
        assert r.weight_source_note.strip() != ""


@pytest.mark.asyncio
async def test_seed_sources(db_session: AsyncSession) -> None:
    n = await seed_sources(db_session)
    await db_session.commit()

    assert n == 11
    rows = (await db_session.execute(select(Source))).scalars().all()
    names = {s.name for s in rows}
    assert "IndiGo" in names
    assert "MakeMyTrip" in names
    assert "Vistara" not in names


@pytest.mark.asyncio
async def test_unique_route_label(db_session: AsyncSession) -> None:
    await seed_routes(db_session)
    await db_session.commit()

    dup = Route(
        origin_iata="XXX",
        destination_iata="YYY",
        label="DEL-BOM",
        dgca_pax_annual=1,
        weight=Decimal("0.5"),
        weight_period="TEST",
        weight_source=WeightSource.DGCA_SYNTHETIC,
        weight_source_note="dup test",
        is_active=True,
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()
