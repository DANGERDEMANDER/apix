"""clean_fares — output of the cleaning pipeline, one row per accepted quote."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apix.models.base import Base, CreatedAtMixin

if TYPE_CHECKING:
    from apix.models.quotes import FareQuote
    from apix.models.routes import Route
    from apix.models.sources import Source


class CleanFare(Base, CreatedAtMixin):
    __tablename__ = "clean_fares"
    __table_args__ = (UniqueConstraint("quote_id", name="uq_clean_fares_quote_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    quote_id: Mapped[int] = mapped_column(
        ForeignKey("fare_quotes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    route_id: Mapped[int] = mapped_column(
        ForeignKey("routes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    collection_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    advance_days: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    base_fare: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_fare: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    is_outlier: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    outlier_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_imputed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    imputation_method: Mapped[str | None] = mapped_column(String(32), nullable=True)

    quote: Mapped[FareQuote] = relationship(back_populates="clean_fare", lazy="raise")
    route: Mapped[Route] = relationship(back_populates="clean_fares", lazy="raise")
    source: Mapped[Source] = relationship(back_populates="clean_fares", lazy="raise")
