"""Pydantic response schemas for the public API.

Every response includes a `meta` object with generated_at and mode so that
consumers can tell when a number was produced and whether it came from
synthetic, replay, or live collection.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from apix.models.indices import Frequency, IndexStatus, Measure


class Meta(BaseModel):
    """Attached to every API response."""

    generated_at: datetime
    mode: str
    data_quality: str | None = None


class IndexPoint(BaseModel):
    date: date
    value: Decimal | None
    weight_covered: Decimal
    routes_included: int
    status: IndexStatus
    withheld_reason: str | None = None


class IndexResponse(BaseModel):
    meta: Meta
    measure: Measure
    frequency: Frequency
    base_period: str
    points: list[IndexPoint]


class IndexLatestResponse(BaseModel):
    meta: Meta
    measure: Measure
    as_of: date | None
    value: Decimal | None
    weight_covered: Decimal | None
    routes_included: int | None
    status: IndexStatus


class RouteOut(BaseModel):
    id: int
    label: str
    origin_iata: str
    destination_iata: str
    dgca_pax_annual: int
    weight: Decimal
    weight_period: str
    weight_source: str
    weight_source_note: str
    is_active: bool


class RoutesResponse(BaseModel):
    meta: Meta
    routes: list[RouteOut]


class Contribution(BaseModel):
    route_label: str
    contribution_points: float


class ContributionsResponse(BaseModel):
    meta: Meta
    date: date
    measure: Measure
    contributions: list[Contribution]
    total: float


class BacktestMonthRow(BaseModel):
    month: str
    apix_value: float
    dgca_value: float
    apix_pct_of_base: float
    dgca_pct_of_base: float


class BacktestMetricsOut(BaseModel):
    n_months: int
    mape_pct: float
    pearson_r: float
    spearman_rho: float
    direction_match_pct: float


class BacktestResponse(BaseModel):
    meta: Meta
    rows: list[BacktestMonthRow]
    metrics: BacktestMetricsOut
    provenance_note: str
