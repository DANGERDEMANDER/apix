"""daily_route_price — one row per (date, route) after window aggregation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, Numeric, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apix.models.base import Base, CreatedAtMixin

if TYPE_CHECKING:
    from apix.models.routes import Route


class DailyRoutePrice(Base, CreatedAtMixin):
    __tablename__ = "daily_route_price"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    route_id: Mapped[int] = mapped_column(
        ForeignKey("routes.id", ondelete="RESTRICT"), primary_key=True, index=True
    )

    avg_base_fare: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    avg_total_fare: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    n_quotes: Mapped[int] = mapped_column(Integer, nullable=False)
    n_windows_present: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    coverage_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    route: Mapped[Route] = relationship(back_populates="daily_prices", lazy="raise")
