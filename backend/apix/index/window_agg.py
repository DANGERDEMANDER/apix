"""§7.1 — window aggregation: quotes -> one price per route per day."""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------
#
# For route i on collection date t, aggregate across advance windows using
# booking-profile weights v_w:
#
#     P(i,t) = Σ_w  v_w × median{ clean base fares for (i, t, window w) }
#
# Use median within a window (robust to a single bad source), weighted mean
# across windows. If a window has zero accepted quotes, re-normalise v over
# the windows that are present. If no windows are present, return None.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WindowAggregate:
    """Result of aggregating one route's quotes across advance windows."""

    price: Decimal
    windows_present: tuple[int, ...]
    n_quotes: int
    weights_used: dict[int, Decimal]


def _median_decimal(values: Sequence[Decimal]) -> Decimal:
    """Median of a list of Decimals, using Decimal arithmetic throughout."""
    if not values:
        raise ValueError("median of empty sequence")
    if len(values) == 1:
        return values[0]
    # statistics.median returns the average of the two middle values for even
    # length; we recompute that in Decimal to avoid float drift.
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 1:
        return sorted_vals[mid]
    return (sorted_vals[mid - 1] + sorted_vals[mid]) / Decimal("2")


def aggregate_windows(
    quotes_by_window: Mapping[int, Sequence[Decimal]],
    window_weights: Mapping[int, Decimal],
    *,
    min_quotes_per_window: int = 1,
) -> WindowAggregate | None:
    """Aggregate one route's quotes for one collection date into P(i,t).

    Arguments:
        quotes_by_window: advance_days -> sequence of accepted base fares.
        window_weights: advance_days -> weight v_w. Must sum to 1.0.
        min_quotes_per_window: window is considered present only if it has at
            least this many quotes. Default 1.

    Returns None if no window has enough quotes.
    """
    if abs(sum(window_weights.values()) - Decimal("1")) > Decimal("1e-9"):
        raise ValueError("window_weights must sum to 1.0")

    present: dict[int, Decimal] = {}
    total_quotes = 0

    for adv, vals in quotes_by_window.items():
        if len(vals) < min_quotes_per_window:
            continue
        if adv not in window_weights:
            continue
        present[adv] = _median_decimal(list(vals))
        total_quotes += len(vals)

    if not present:
        return None

    # Re-normalise weights over the windows that are present.
    present_weight_sum = sum(window_weights[adv] for adv in present)
    if present_weight_sum <= 0:
        return None

    effective_weights = {
        adv: window_weights[adv] / present_weight_sum for adv in present
    }

    price = sum(
        (effective_weights[adv] * present[adv] for adv in present),
        start=Decimal("0"),
    )

    return WindowAggregate(
        price=price,
        windows_present=tuple(sorted(present)),
        n_quotes=total_quotes,
        weights_used=effective_weights,
    )