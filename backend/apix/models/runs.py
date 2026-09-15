"""The collection_runs table â€” one row per collection attempt."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apix.models.base import Base, CreatedAtMixin, _enum_values

if TYPE_CHECKING:
    from apix.models.quotes import FareQuote


class RunMode(str, enum.Enum):
    LIVE = "live"
    REPLAY = "replay"
    SYNTHETIC = "synthetic"


class RunStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class CollectionRun(Base, CreatedAtMixin):
    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    mode: Mapped[RunMode] = mapped_column(
        Enum(RunMode, name="run_mode_enum", native_enum=True, values_callable=_enum_values), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status_enum", native_enum=True, values_callable=_enum_values), nullable=False
    )

    quotes_collected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quotes_expected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked_sources: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    error_summary: Mapped[dict[str, str]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    seed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)

    quotes: Mapped[list["FareQuote"]] = relationship(
        back_populates="run", lazy="raise"
    )