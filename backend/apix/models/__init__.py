"""SQLAlchemy 2.0 typed ORM models for APix.

Import order matters for Alembic autogenerate: every model must be imported
here so that Base.metadata sees all tables before migrations run.
"""

from __future__ import annotations

from apix.models.base import Base
from apix.models.clean import CleanFare
from apix.models.dgca import DgcaReference
from apix.models.indices import IndexBaseValue, IndexValue
from apix.models.prices import DailyRoutePrice
from apix.models.quotes import FareQuote
from apix.models.routes import Route
from apix.models.runs import CollectionRun
from apix.models.sources import Source

__all__ = [
    "Base",
    "CleanFare",
    "CollectionRun",
    "DailyRoutePrice",
    "DgcaReference",
    "FareQuote",
    "IndexBaseValue",
    "IndexValue",
    "Route",
    "Source",
]
