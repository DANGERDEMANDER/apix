"""Deterministic synthetic fare generator for APix.

Produces realistic-looking fare quotes from a fixed seed. Same seed + same
collection window => byte-identical output. Used as the default mode so the
demo works without touching any live site.

Behaviour modelled:
  - Exponential lead-time curve: fares rise as departure approaches.
  - Day-of-week effect: Fri/Sun departure premiums.
  - Festival surges: from config/calendar.yaml, with linear falloff.
  - Carrier-level positioning: each source has a multiplicative offset.
  - Multiplicative daily noise.
  - Occasional sold-out cells.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from apix.collectors.base import RawQuote
from apix.collectors.festivals import Festival, festival_multiplier

_CARRIER_BY_SOURCE: dict[str, str] = {
    "IndiGo": "6E",
    "AirIndia": "AI",
    "AirIndiaExpress": "IX",
    "AkasaAir": "QP",
    "SpiceJet": "SG",
}

_OTA_CARRIER_POOL: tuple[str, ...] = ("6E", "AI", "IX", "QP", "SG")

_BASE_FARE_INR: dict[str, int] = {
    "DEL-BOM": 5200,
    "DEL-BLR": 5600,
    "BOM-BLR": 4800,
    "DEL-CCU": 5000,
    "BLR-HYD": 3200,
    "MAA-DEL": 5400,
    "DEL-HYD": 4800,
    "BOM-HYD": 4200,
    "DEL-AMD": 4400,
    "BLR-CCU": 5200,
}

_SOURCE_OFFSET: dict[str, float] = {
    "IndiGo": 0.98,
    "AirIndia": 1.08,
    "AirIndiaExpress": 0.95,
    "AkasaAir": 0.96,
    "SpiceJet": 0.94,
    "MakeMyTrip": 1.03,
    "Yatra": 1.04,
    "EaseMyTrip": 1.02,
    "Cleartrip": 1.05,
    "Ixigo": 1.03,
    "Goibibo": 1.04,
}

_DOW_MULT: dict[int, float] = {
    0: 1.00,
    1: 0.98,
    2: 1.00,
    3: 1.01,
    4: 1.10,
    5: 1.02,
    6: 1.08,
}


@dataclass(frozen=True)
class SyntheticConfig:
    seed: int
    sold_out_prob: float = 0.045
    noise_pct: float = 0.05
    lead_time_lambda: float = 0.008
    tax_rate: float = 0.05
    udf_inr: int = 249


def _cell_rng(seed: int, *parts: str | int) -> random.Random:
    key = "|".join(str(p) for p in (seed, *parts)).encode("utf-8")
    h = hashlib.sha256(key).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def _lead_time_multiplier(advance_days: int, lam: float) -> float:
    return math.exp(-lam * (advance_days - 1))


def _synthetic_collected_at(departure_date: date, advance_days: int) -> datetime:
    """Deterministic collection timestamp for a synthetic quote."""
    collection_date = departure_date - timedelta(days=advance_days)
    return datetime.combine(collection_date, time(6, 0), tzinfo=UTC)


def _to_decimal(x: float) -> Decimal:
    return Decimal(str(round(x, 2)))


class SyntheticCollector:
    """One instance per source. Deterministic given the same seed."""

    name: str

    def __init__(
        self,
        name: str,
        config: SyntheticConfig,
        festivals: tuple[Festival, ...],
    ) -> None:
        self.name = name
        self._cfg = config
        self._festivals = festivals

    def _pick_carrier(self, route_label: str, departure_date: date, advance_days: int) -> str:
        fixed = _CARRIER_BY_SOURCE.get(self.name)
        if fixed is not None:
            return fixed
        rng = _cell_rng(
            self._cfg.seed,
            self.name,
            route_label,
            departure_date.isoformat(),
            advance_days,
            "carrier",
        )
        return rng.choice(_OTA_CARRIER_POOL)

    @staticmethod
    def _flight_number(rng: random.Random) -> str:
        return f"{rng.randint(100, 9999)}"

    def generate(
        self,
        route_label: str,
        departure_date: date,
        advance_days: int,
    ) -> RawQuote | None:
        cfg = self._cfg
        base = _BASE_FARE_INR.get(route_label)
        if base is None:
            raise ValueError(f"no base fare for route {route_label}")

        rng = _cell_rng(
            cfg.seed,
            self.name,
            route_label,
            departure_date.isoformat(),
            advance_days,
            "quote",
        )

        if rng.random() < cfg.sold_out_prob:
            return RawQuote(
                source_name=self.name,
                route_label=route_label,
                departure_date=departure_date,
                advance_days=advance_days,
                carrier=self._pick_carrier(route_label, departure_date, advance_days),
                flight_number=self._flight_number(rng),
                fare_class="economy",
                base_fare=None,
                taxes=None,
                udf=None,
                convenience_fee=None,
                total_fare=Decimal("0.00"),
                collected_at=_synthetic_collected_at(departure_date, advance_days),
                is_sold_out=True,
                decomposition_method="none",
                raw_payload={"synthetic": True, "seed": cfg.seed, "sold_out": True},
            )

        price = float(base)
        price *= _SOURCE_OFFSET.get(self.name, 1.0)
        price *= _DOW_MULT[departure_date.weekday()]
        price *= _lead_time_multiplier(advance_days, cfg.lead_time_lambda)
        price *= festival_multiplier(departure_date, self._festivals)
        noise = 1.0 + rng.uniform(-cfg.noise_pct, cfg.noise_pct)
        price *= noise

        base_fare = _to_decimal(price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        taxes = (base_fare * Decimal(str(cfg.tax_rate))).quantize(Decimal("0.01"))
        udf = Decimal(cfg.udf_inr)
        convenience = Decimal("0.00")
        total = (base_fare + taxes + udf + convenience).quantize(Decimal("0.01"))

        return RawQuote(
            source_name=self.name,
            route_label=route_label,
            departure_date=departure_date,
            advance_days=advance_days,
            carrier=self._pick_carrier(route_label, departure_date, advance_days),
            flight_number=self._flight_number(rng),
            fare_class="economy",
            base_fare=base_fare,
            taxes=taxes,
            udf=udf,
            convenience_fee=convenience,
            total_fare=total,
            collected_at=_synthetic_collected_at(departure_date, advance_days),
            is_sold_out=False,
            decomposition_method="modelled",
            raw_payload={
                "synthetic": True,
                "seed": cfg.seed,
                "base_inr": base,
                "noise": round(noise, 4),
            },
        )


def build_collectors(
    source_names: tuple[str, ...],
    config: SyntheticConfig,
    festivals: tuple[Festival, ...],
) -> list[SyntheticCollector]:
    return [SyntheticCollector(name, config, festivals) for name in source_names]
