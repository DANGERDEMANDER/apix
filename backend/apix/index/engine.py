"""?7.4 ? the index, with explicit missing-route re-normalisation.

    APIx(t) = 100 ? [ ?_{i ? present} w_i ? R(i,t) ] / [ ?_{i ? present} w_i ]

Missing route handling:
  - Do NOT drop a missing route and sum the remaining weights ? that biases
    the index toward whichever routes were successfully scraped.
  - Instead re-normalise the weights over routes present on day t.
  - Store weight_covered = ?_{i ? present} w_i.
  - If weight_covered < min_coverage (default 0.70), withhold: do not publish
    a number. Return status = insufficient_coverage.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

_DEFAULT_MIN_COVERAGE = Decimal("0.70")


class IndexStatus(str, enum.Enum):
    PUBLISHED = "published"
    INSUFFICIENT_COVERAGE = "insufficient_coverage"
    NO_DATA = "no_data"


@dataclass(frozen=True)
class IndexResult:
    """One index value (or withholding) for a given date."""

    date: date
    value: Decimal | None
    weight_covered: Decimal
    routes_included: int
    status: IndexStatus
    withheld_reason: str | None = None
    contributions: dict[str, float] = field(default_factory=dict)


def compute_index(
    *,
    on_date: date,
    route_prices: Mapping[int, Decimal | None],
    base_values: Mapping[int, Decimal],
    route_weights: Mapping[int, Decimal],
    route_labels: Mapping[int, str],
    min_coverage: Decimal = _DEFAULT_MIN_COVERAGE,
) -> IndexResult:
    """Compute the index for one date.

    Arguments:
        on_date: the collection date t.
        route_prices: route_id -> P(i,t) for that day, or None if missing.
        base_values: route_id -> P(i,0), must be > 0 for every present route.
        route_weights: route_id -> w_i. Must already sum to 1.0.
        route_labels: route_id -> label (used as the contributions dict key).
        min_coverage: withhold if weight_covered < this value.

    Returns:
        IndexResult with status = published (value set) or
        insufficient_coverage / no_data (value = None).
    """
    # Routes that have both a price today and a base value to divide by.
    present: list[int] = []
    for rid, p in route_prices.items():
        if p is None:
            continue
        if rid not in base_values:
            continue
        if base_values[rid] <= 0:
            continue
        if rid not in route_weights:
            continue
        present.append(rid)

    if not present:
        return IndexResult(
            date=on_date,
            value=None,
            weight_covered=Decimal("0"),
            routes_included=0,
            status=IndexStatus.NO_DATA,
            withheld_reason="no routes with both price and base value",
        )

    weight_covered = sum((route_weights[rid] for rid in present), start=Decimal("0"))

    if weight_covered < min_coverage:
        return IndexResult(
            date=on_date,
            value=None,
            weight_covered=weight_covered,
            routes_included=len(present),
            status=IndexStatus.INSUFFICIENT_COVERAGE,
            withheld_reason=(f"weight_covered={weight_covered} below threshold {min_coverage}"),
        )

    # Numerator: ? w_i ? R(i,t), then divide by weight_covered.
    numerator = Decimal("0")
    for rid in present:
        r = route_prices[rid]
        assert r is not None  # guaranteed by the filter above
        relative = r / base_values[rid]
        numerator += route_weights[rid] * relative

    value = (Decimal("100") * numerator / weight_covered).quantize(Decimal("0.0001"))

    # Contributions: each route's point contribution to the index. The sum of
    # contributions equals the index value.
    contributions: dict[str, float] = {}
    for rid in present:
        r = route_prices[rid]
        assert r is not None
        relative = r / base_values[rid]
        contribution = Decimal("100") * route_weights[rid] * relative / weight_covered
        label = route_labels.get(rid, f"route_{rid}")
        contributions[label] = float(contribution.quantize(Decimal("0.0001")))

    return IndexResult(
        date=on_date,
        value=value,
        weight_covered=weight_covered,
        routes_included=len(present),
        status=IndexStatus.PUBLISHED,
        withheld_reason=None,
        contributions=contributions,
    )
