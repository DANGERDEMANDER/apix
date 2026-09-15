"""API routes (see build spec section 11).

Phase 6 Batch 1 covers:
  GET /api/v1/index
  GET /api/v1/index/latest
  GET /api/v1/routes
  GET /api/v1/index/{on_date}/contributions

Later batches will add /heatmap, /elasticity, /backtest, /quality/runs, and
/methodology.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apix.backtest.service import run_backtest
from apix.api.schemas import (
    BacktestMetricsOut,
    BacktestMonthRow,
    BacktestResponse,
    Contribution,
    ContributionsResponse,
    IndexLatestResponse,
    IndexPoint,
    IndexResponse,
    Meta,
    RouteOut,
    RoutesResponse,
)
from apix.db import session_dependency
from apix.models.indices import Frequency, IndexStatus, IndexValue, Measure
from apix.models.routes import Route
from apix.models.runs import CollectionRun

router = APIRouter(prefix="/api/v1", tags=["apix"])


async def _meta(session: AsyncSession) -> Meta:
    """Build the meta block for a response."""
    stmt = select(CollectionRun).order_by(CollectionRun.started_at.desc()).limit(1)
    last_run = (await session.execute(stmt)).scalar_one_or_none()
    return Meta(
        generated_at=datetime.now(timezone.utc),
        mode=last_run.mode.value if last_run is not None else "unknown",
        data_quality=None,
    )


@router.get("/index", response_model=IndexResponse)
async def list_index(
    session: Annotated[AsyncSession, Depends(session_dependency)],
    measure: Measure = Query(default=Measure.BASE),
    frequency: Frequency = Query(default=Frequency.DAILY),
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
) -> IndexResponse:
    """Index values in a date range, one row per (date, measure, frequency)."""
    stmt = select(IndexValue).where(
        IndexValue.measure == measure,
        IndexValue.frequency == frequency,
    )
    if from_ is not None:
        stmt = stmt.where(IndexValue.date >= from_)
    if to is not None:
        stmt = stmt.where(IndexValue.date <= to)
    stmt = stmt.order_by(IndexValue.date)

    rows = list((await session.execute(stmt)).scalars().all())
    base_period = rows[0].base_period if rows else ""

    return IndexResponse(
        meta=await _meta(session),
        measure=measure,
        frequency=frequency,
        base_period=base_period,
        points=[
            IndexPoint(
                date=r.date,
                value=r.value,
                weight_covered=r.weight_covered,
                routes_included=r.routes_included,
                status=r.status,
                withheld_reason=r.withheld_reason,
            )
            for r in rows
        ],
    )


@router.get("/index/latest", response_model=IndexLatestResponse)
async def latest_index(
    session: Annotated[AsyncSession, Depends(session_dependency)],
    measure: Measure = Query(default=Measure.BASE),
    frequency: Frequency = Query(default=Frequency.DAILY),
) -> IndexLatestResponse:
    """Most recent published value for a (measure, frequency) pair."""
    stmt = (
        select(IndexValue)
        .where(
            IndexValue.measure == measure,
            IndexValue.frequency == frequency,
            IndexValue.status == IndexStatus.PUBLISHED,
        )
        .order_by(IndexValue.date.desc())
        .limit(1)
    )
    r = (await session.execute(stmt)).scalar_one_or_none()

    return IndexLatestResponse(
        meta=await _meta(session),
        measure=measure,
        as_of=r.date if r else None,
        value=r.value if r else None,
        weight_covered=r.weight_covered if r else None,
        routes_included=r.routes_included if r else None,
        status=r.status if r else IndexStatus.NO_DATA,
    )


@router.get("/routes", response_model=RoutesResponse)
async def list_routes(
    session: Annotated[AsyncSession, Depends(session_dependency)],
    active_only: bool = Query(default=True),
) -> RoutesResponse:
    """The route basket, with weights and provenance."""
    stmt = select(Route).order_by(Route.label)
    if active_only:
        stmt = stmt.where(Route.is_active.is_(True))

    rows = list((await session.execute(stmt)).scalars().all())

    return RoutesResponse(
        meta=await _meta(session),
        routes=[
            RouteOut(
                id=r.id,
                label=r.label,
                origin_iata=r.origin_iata,
                destination_iata=r.destination_iata,
                dgca_pax_annual=r.dgca_pax_annual,
                weight=r.weight,
                weight_period=r.weight_period,
                weight_source=r.weight_source.value,
                weight_source_note=r.weight_source_note,
                is_active=r.is_active,
            )
            for r in rows
        ],
    )


@router.get(
    "/index/{on_date}/contributions",
    response_model=ContributionsResponse,
)
async def contributions_for_date(
    session: Annotated[AsyncSession, Depends(session_dependency)],
    on_date: date,
    measure: Measure = Query(default=Measure.BASE),
    frequency: Frequency = Query(default=Frequency.DAILY),
) -> ContributionsResponse:
    """Per-route contribution to the index on a given date."""
    stmt = select(IndexValue).where(
        IndexValue.date == on_date,
        IndexValue.measure == measure,
        IndexValue.frequency == frequency,
    )
    r = (await session.execute(stmt)).scalar_one_or_none()
    if r is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "not_found",
                    "message": f"no index value for {on_date}",
                    "field": "date",
                }
            },
        )

    contribs = [
        Contribution(route_label=label, contribution_points=float(pts))
        for label, pts in (r.contributions or {}).items()
    ]
    total = float(
        sum((Decimal(str(c.contribution_points)) for c in contribs), start=Decimal("0"))
    )

    return ContributionsResponse(
        meta=await _meta(session),
        date=r.date,
        measure=measure,
        contributions=contribs,
        total=total,
    )

@router.get("/backtest", response_model=BacktestResponse)
async def backtest(
    session: Annotated[AsyncSession, Depends(session_dependency)],
) -> BacktestResponse:
    """Monthly APix vs DGCA reference, with MAPE, Pearson r, Spearman rho,
    direction match (spec section 12 and section 15)."""
    result = await run_backtest(session)
    return BacktestResponse(
        meta=await _meta(session),
        rows=[
            BacktestMonthRow(
                month=r.month,
                apix_value=r.apix_value,
                dgca_value=r.dgca_value,
                apix_pct_of_base=r.apix_pct_of_base,
                dgca_pct_of_base=r.dgca_pct_of_base,
            )
            for r in result.rows
        ],
        metrics=BacktestMetricsOut(
            n_months=result.metrics.n_months,
            mape_pct=result.metrics.mape_pct,
            pearson_r=result.metrics.pearson_r,
            spearman_rho=result.metrics.spearman_rho,
            direction_match_pct=result.metrics.direction_match_pct,
        ),
        provenance_note=result.provenance_note,
    )
