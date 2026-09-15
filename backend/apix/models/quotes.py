"""The fare_quotes table â€” RAW, never mutated after insert (Â§6)."""

from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apix.models.base import Base, CreatedAtMixin, _enum_values

if TYPE_CHECKING:
    from apix.models.clean import CleanFare
    from apix.models.routes import Route
    from apix.models.runs import CollectionRun
    from apix.models.sources import Source


class DecompositionMethod(str, enum.Enum):
    PARSED = "parsed"
    PARTIAL = "partial"  # source exposed some components; rest modelled
    MODELLED = "modelled"
    NONE = "none"


class FareQuote(Base, CreatedAtMixin):
    __tablename__ = "fare_quotes"
    __table_args__ = (
        Index(
            "ix_fare_quotes_route_dep_window",
            "route_id",
            "departure_date",
            "advance_days",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    run_id: Mapped[int] = mapped_column(
        ForeignKey("collection_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    route_id: Mapped[int] = mapped_column(
        ForeignKey("routes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False)
    advance_days: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    carrier: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    flight_number: Mapped[str] = mapped_column(String(16), nullable=False)
    fare_class: Mapped[str] = mapped_column(String(32), nullable=False)

    base_fare: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    taxes: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    udf: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    convenience_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    total_fare: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, default="INR")

    is_sold_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    decomposition_method: Mapped[DecompositionMethod] = mapped_column(
        Enum(
            DecompositionMethod,
            name="decomposition_method_enum",
            native_enum=True,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    route: Mapped[Route] = relationship(back_populates="quotes", lazy="raise")
    source: Mapped[Source] = relationship(back_populates="quotes", lazy="raise")
    run: Mapped[CollectionRun] = relationship(back_populates="quotes", lazy="raise")
    clean_fare: Mapped[CleanFare | None] = relationship(
        back_populates="quote", uselist=False, lazy="raise"
    )
