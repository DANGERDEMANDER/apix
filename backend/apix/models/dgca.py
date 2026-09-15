"""dgca_reference — ground truth for the monthly backtest."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apix.models.base import Base, CreatedAtMixin

if TYPE_CHECKING:
    from apix.models.routes import Route


class DgcaReference(Base, CreatedAtMixin):
    __tablename__ = "dgca_reference"

    month: Mapped[date] = mapped_column(Date, primary_key=True)
    route_id: Mapped[int] = mapped_column(
        ForeignKey("routes.id", ondelete="RESTRICT"), primary_key=True, index=True
    )

    avg_fare: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    source_note: Mapped[str] = mapped_column(String(512), nullable=False)

    route: Mapped["Route"] = relationship(lazy="raise")