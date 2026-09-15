"""?7.3 ? route weight normalisation.

Weights come from routes.dgca_pax_annual, normalised across active routes
so they sum to exactly 1.0 at 6 decimal places (matching Numeric(8,6)).
The residual from rounding is assigned to the first route so the invariant
holds exactly, not just approximately.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal


def normalise_weights(raw: Mapping[int, int]) -> dict[int, Decimal]:
    """Return route_id -> weight, summing to exactly Decimal('1') at 6 dp.

    Arguments:
        raw: route_id -> dgca_pax_annual (a positive integer).

    Raises ValueError if raw is empty or the total is <= 0.
    """
    if not raw:
        raise ValueError("raw weights mapping is empty")
    total = Decimal(sum(raw.values()))
    if total <= 0:
        raise ValueError("sum of raw weights must be > 0")

    quant = Decimal("0.000001")
    rounded = {rid: (Decimal(p) / total).quantize(quant) for rid, p in raw.items()}

    residual = Decimal("1") - sum(rounded.values())
    first_key = next(iter(rounded))
    rounded[first_key] = rounded[first_key] + residual
    return rounded
