"""Declarative base + shared column mixins."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

# Alembic picks up this naming convention so constraint names are stable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class CreatedAtMixin:
    """Every table has created_at TIMESTAMP NOT NULL DEFAULT now() (Â§6)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


def utcnow() -> datetime:
    """Timezone-aware UTC now. Rule 8 forbids naive datetimes."""
    return datetime.now(timezone.utc)

def _enum_values(enum_cls: type) -> list[str]:
    """Use .value instead of .name for SQLAlchemy Enum serialization."""
    return [e.value for e in enum_cls]