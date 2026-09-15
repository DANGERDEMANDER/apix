

"""The routes table â€” basket structure + DGCA-derived weights."""

from __future__ import annotations

import enum
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apix.models.base import Base, CreatedAtMixin, _enum_values

if TYPE_CHECKING:
    from apix.models.clean import CleanFare
    from apix.models.prices import DailyRoutePrice
    from apix.models.quotes import FareQuote


class WeightSource(str, enum.Enum):
    """Provenance of routes.weight. Never null â€” see METHODOLOGY.md Â§12."""

    DGCA_PUBLISHED = "dgca-published"
    DGCA_SYNTHETIC = "dgca-synthetic"


class Route(Base, CreatedAtMixin):
    __tablename__ = "routes"
    __table_args__ = (
        UniqueConstraint("origin_iata", "destination_iata", name="uq_routes_origin_dest"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    origin_iata: Mapped[str] = mapped_column(String(3), nullable=False)
    destination_iata: Mapped[str] = mapped_column(String(3), nullable=False)
    label: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)

    dgca_pax_annual: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    weight_period: Mapped[str] = mapped_column(String(16), nullable=False)

    # Provenance is a first-class column. The API and dashboard mark synthetic
    # weights visibly; we never present a placeholder as an official figure.
    weight_source: Mapped[WeightSource] = mapped_column(
        Enum(WeightSource, name="weight_source_enum", native_enum=True, values_callable=_enum_values),
        nullable=False,
    )
    weight_source_note: Mapped[str] = mapped_column(String(256), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    quotes: Mapped[list["FareQuote"]] = relationship(
        back_populates="route", lazy="raise"
    )
    clean_fares: Mapped[list["CleanFare"]] = relationship(
        back_populates="route", lazy="raise"
    )
    daily_prices: Mapped[list["DailyRoutePrice"]] = relationship(
        back_populates="route", lazy="raise"
    )