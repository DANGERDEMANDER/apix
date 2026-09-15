"""Load config/basket.yaml into the routes table."""

from __future__ import annotations

import csv
from decimal import Decimal, getcontext
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apix.models.routes import Route, WeightSource
from apix.settings import get_settings

getcontext().prec = 28

_DGCA_CSV = Path("data/dgca/route_pax.csv")

_SYNTHETIC_PAX: dict[str, int] = {
    "DEL-BOM": 8_500_000,
    "DEL-BLR": 5_200_000,
    "BOM-BLR": 4_800_000,
    "DEL-CCU": 3_500_000,
    "BLR-HYD": 3_100_000,
    "MAA-DEL": 2_900_000,
    "DEL-HYD": 4_200_000,
    "BOM-HYD": 2_800_000,
    "DEL-AMD": 2_500_000,
    "BLR-CCU": 2_100_000,
}


def _load_real_pax_csv(path: Path) -> dict[str, int] | None:
    if not path.is_file():
        return None
    out: dict[str, int] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            out[row["label"].strip()] = int(row["dgca_pax_annual"])
    return out or None


def _normalise_weights(pax: dict[str, int]) -> dict[str, Decimal]:
    """Return weights that sum to EXACTLY Decimal('1') at 6 dp.

    Rounding each weight to 6 decimals (matching Numeric(8,6)) leaves a small
    residual. Assign that residual to the first route so the sum is exact and
    the invariant test can assert equality to 1e-9.
    """
    total = Decimal(sum(pax.values()))
    if total <= 0:
        raise ValueError("sum of dgca_pax_annual must be > 0")

    quant = Decimal("0.000001")
    rounded = {label: (Decimal(p) / total).quantize(quant) for label, p in pax.items()}
    residual = Decimal("1") - sum(rounded.values())
    first = next(iter(rounded))
    rounded[first] = rounded[first] + residual
    return rounded


async def seed_routes(session: AsyncSession) -> int:
    settings = get_settings()

    real_pax = _load_real_pax_csv(_DGCA_CSV)
    if real_pax is not None:
        pax = real_pax
        source = WeightSource.DGCA_PUBLISHED
        note = f"Loaded from {_DGCA_CSV}"
    else:
        pax = {r.label: _SYNTHETIC_PAX[r.label] for r in settings.basket.routes}
        source = WeightSource.DGCA_SYNTHETIC
        note = (
            "Synthetic placeholder pending real DGCA data. "
            "See METHODOLOGY.md Phase 5 prerequisites."
        )

    weights = _normalise_weights(pax)

    existing = {r.label: r for r in (await session.execute(select(Route))).scalars().all()}

    written = 0
    for r in settings.basket.routes:
        if r.label not in weights:
            raise ValueError(f"no DGCA pax figure for route {r.label}")
        row = existing.get(r.label)
        if row is None:
            row = Route(
                origin_iata=r.origin,
                destination_iata=r.destination,
                label=r.label,
                dgca_pax_annual=pax[r.label],
                weight=weights[r.label],
                weight_period=settings.basket.weight_period,
                weight_source=source,
                weight_source_note=note,
                is_active=True,
            )
            session.add(row)
        else:
            row.dgca_pax_annual = pax[r.label]
            row.weight = weights[r.label]
            row.weight_period = settings.basket.weight_period
            row.weight_source = source
            row.weight_source_note = note
        written += 1

    await session.flush()
    return written
