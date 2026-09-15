"""The sources table â€” airlines and OTAs the collector knows about."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apix.models.base import Base, CreatedAtMixin, _enum_values

if TYPE_CHECKING:
    from apix.models.clean import CleanFare
    from apix.models.quotes import FareQuote


class SourceKind(str, enum.Enum):
    AIRLINE = "airline"
    OTA = "ota"


class Source(Base, CreatedAtMixin):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    kind: Mapped[SourceKind] = mapped_column(
        Enum(SourceKind, name="source_kind_enum", native_enum=True, values_callable=_enum_values),
        nullable=False,
    )
    base_url: Mapped[str] = mapped_column(String(256), nullable=False)

    rate_limit_rpm: Mapped[int] = mapped_column(Integer, nullable=False)
    crawl_delay_s: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)

    robots_last_checked: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    robots_allows_target: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    quotes: Mapped[list[FareQuote]] = relationship(back_populates="source", lazy="raise")
    clean_fares: Mapped[list[CleanFare]] = relationship(back_populates="source", lazy="raise")
