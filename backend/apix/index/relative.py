"""§7.2 — price relative: R(i,t) = P(i,t) / P(i,0)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal


def price_relative(p_it: Decimal, p_i0: Decimal) -> Decimal:
    """Return R(i,t) = P(i,t) / P(i,0).

    Raises ValueError if p_i0 <= 0 (a base value must be strictly positive).
    """
    if p_i0 <= 0:
        raise ValueError(f"p_i0 must be > 0, got {p_i0}")
    return p_it / p_i0


def compute_base_value(prices: Sequence[Decimal], min_days: int) -> Decimal | None:
    """P(i,0): arithmetic mean of P(i,t) over the base period.

    Returns None if fewer than min_days prices are available — the route is
    then excluded from the index entirely (it has no anchor).
    """
    if len(prices) < min_days:
        return None
    if not prices:
        return None
    total = sum(prices, start=Decimal("0"))
    return total / Decimal(len(prices))