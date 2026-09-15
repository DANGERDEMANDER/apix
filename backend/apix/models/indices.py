"""index_values and index_base_values.

index_values carries status and withheld_reason â€” Â§7.4 requires a "withheld"
marker, but Â§6's schema had no column for it. Added here per the plan we
agreed before Phase 1.
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apix.models.base import Base, CreatedAtMixin, _enum_values

if TYPE_CHECKING:
    from apix.models.routes import Route


class Frequency(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class Measure(str, enum.Enum):
    BASE = "base"
    TOTAL = "total"


class IndexStatus(str, enum.Enum):
    PUBLISHED = "published"
    INSUFFICIENT_COVERAGE = "insufficient_coverage"
    NO_DATA = "no_data"


class IndexValue(Base, CreatedAtMixin):
    __tablename__ = "index_values"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    frequency: Mapped[Frequency] = mapped_column(
        Enum(Frequency, name="frequency_enum", native_enum=True, values_callable=_enum_values), primary_key=True
    )
    measure: Mapped[Measure] = mapped_column(
        Enum(Measure, name="measure_enum", native_enum=True, values_callable=_enum_values), primary_key=True
    )

    value: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    base_period: Mapped[str] = mapped_column(String(64), nullable=False)
    routes_included: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    weight_covered: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    contributions: Mapped[dict[str, float]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    status: Mapped[IndexStatus] = mapped_column(
        Enum(IndexStatus, name="index_status_enum", native_enum=True, values_callable=_enum_values), nullable=False
    )
    withheld_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)


class IndexBaseValue(Base, CreatedAtMixin):
    """Stores P(i,0) per route per measure per base period (Â§7.2)."""

    __tablename__ = "index_base_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    route_id: Mapped[int] = mapped_column(
        ForeignKey("routes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    measure: Mapped[Measure] = mapped_column(
        Enum(Measure, name="measure_enum", native_enum=True, values_callable=_enum_values), nullable=False
    )
    base_period: Mapped[str] = mapped_column(String(64), nullable=False)

    p_i0: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    n_base_days: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    route: Mapped["Route"] = relationship(lazy="raise")