"""FareCollector ABC and the RawQuote intermediate type."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class RawQuote:
    """One fare quote as returned by a collector, before DB insertion.

    Field order matters: dataclass fields without defaults must come before
    any field with a default. `collected_at` is required (no default) so it
    sits above `currency`, which has a default.
    """

    source_name: str
    route_label: str
    departure_date: date
    advance_days: int
    carrier: str
    flight_number: str
    fare_class: str
    base_fare: Decimal | None
    taxes: Decimal | None
    udf: Decimal | None
    convenience_fee: Decimal | None
    total_fare: Decimal
    collected_at: datetime

    currency: str = "INR"
    is_sold_out: bool = False
    decomposition_method: str = "parsed"
    raw_payload: dict[str, Any] = field(default_factory=dict)


class FareCollector(ABC):
    """Interface every collector implements.

    One collector instance represents one source (an airline site or an
    OTA). The `collect` method is called once per (route, departure_date,
    advance_days) cell and returns zero or more quotes for that cell.
    """

    name: str

    @abstractmethod
    async def collect(
        self,
        route_label: str,
        departure_date: date,
        advance_days: int,
    ) -> list[RawQuote]:
        """Return zero or more quotes for this cell."""
        raise NotImplementedError
