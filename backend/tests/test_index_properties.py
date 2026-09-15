"""§7.6 — property tests with Hypothesis for the index engine.

Four properties:
  1. Identity: if every P(i,t) == P(i,0), then APIx(t) == 100.0000 exactly.
  2. Scaling: if every route's price scales by k, then APIx(t) == 100k.
  3. Order-invariance: shuffling the dict order does not change the value.
  4. Weight normalisation sums to exactly 1 at 6 dp.
  5. Monotone in one route: raising any single route's price raises the index.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from apix.index.engine import IndexStatus, compute_index
from apix.index.weights import normalise_weights

_FIXED_WEIGHTS: dict[int, Decimal] = {
    1: Decimal("0.5"),
    2: Decimal("0.3"),
    3: Decimal("0.2"),
}
_LABELS: dict[int, str] = {1: "A", 2: "B", 3: "C"}
_TEST_DATE = date(2025, 9, 1)

_price = st.decimals(
    min_value=Decimal("1"),
    max_value=Decimal("100000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

_prices_dict = st.dictionaries(
    keys=st.integers(min_value=1, max_value=3),
    values=_price,
    min_size=3,
    max_size=3,
)

_slow_suppress = [HealthCheck.too_slow, HealthCheck.data_too_large]


@settings(suppress_health_check=_slow_suppress, deadline=None, max_examples=100)
@given(base=_prices_dict)
def test_identity_when_prices_equal_base(base: dict[int, Decimal]) -> None:
    """P(i,t) == P(i,0) for every route => APIx(t) == 100.0000 exactly."""
    r = compute_index(
        on_date=_TEST_DATE,
        route_prices=dict(base),
        base_values=dict(base),
        route_weights=_FIXED_WEIGHTS,
        route_labels=_LABELS,
    )
    assert r.status == IndexStatus.PUBLISHED
    assert r.value == Decimal("100.0000"), f"got {r.value}"


@settings(suppress_health_check=_slow_suppress, deadline=None, max_examples=100)
@given(
    base=_prices_dict,
    k=st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("100"),
        places=4,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_scaling(base: dict[int, Decimal], k: Decimal) -> None:
    """Every route's price scaled by k => APIx(t) == 100k."""
    scaled = {rid: p * k for rid, p in base.items()}
    r = compute_index(
        on_date=_TEST_DATE,
        route_prices=scaled,
        base_values=dict(base),
        route_weights=_FIXED_WEIGHTS,
        route_labels=_LABELS,
    )
    assert r.status == IndexStatus.PUBLISHED
    assert r.value is not None
    expected = (Decimal("100") * k).quantize(Decimal("0.0001"))
    assert r.value == expected, f"got {r.value}, expected {expected}"


@settings(suppress_health_check=_slow_suppress, deadline=None, max_examples=100)
@given(base=_prices_dict)
def test_order_invariance(base: dict[int, Decimal]) -> None:
    """Index is invariant to the order of routes."""
    r1 = compute_index(
        on_date=_TEST_DATE,
        route_prices={1: base[1], 2: base[2], 3: base[3]},
        base_values={1: base[1], 2: base[2], 3: base[3]},
        route_weights={1: Decimal("0.5"), 2: Decimal("0.3"), 3: Decimal("0.2")},
        route_labels=_LABELS,
    )
    r2 = compute_index(
        on_date=_TEST_DATE,
        route_prices={3: base[3], 1: base[1], 2: base[2]},
        base_values={3: base[3], 1: base[1], 2: base[2]},
        route_weights={3: Decimal("0.2"), 1: Decimal("0.5"), 2: Decimal("0.3")},
        route_labels=_LABELS,
    )
    assert r1.value == r2.value


@settings(suppress_health_check=_slow_suppress, deadline=None, max_examples=100)
@given(base=_prices_dict)
def test_monotone_in_one_route(base: dict[int, Decimal]) -> None:
    """Raising any single route's price raises the index, others fixed."""
    bump = max(Decimal("1"), base[1] * Decimal("0.01"))
    r1 = compute_index(
        on_date=_TEST_DATE,
        route_prices=dict(base),
        base_values=dict(base),
        route_weights=_FIXED_WEIGHTS,
        route_labels=_LABELS,
    )
    higher = dict(base)
    higher[1] = higher[1] + bump
    r2 = compute_index(
        on_date=_TEST_DATE,
        route_prices=higher,
        base_values=dict(base),
        route_weights=_FIXED_WEIGHTS,
        route_labels=_LABELS,
    )
    assert r1.value is not None and r2.value is not None
    assert r2.value > r1.value, f"{r1.value} -> {r2.value}"


@settings(deadline=None, max_examples=200)
@given(
    raw=st.dictionaries(
        keys=st.integers(min_value=1, max_value=20),
        values=st.integers(min_value=1, max_value=10_000_000),
        min_size=1,
        max_size=20,
    )
)
def test_weight_normalisation_sums_to_one(raw: dict[int, int]) -> None:
    w = normalise_weights(raw)
    total = sum(w.values(), start=Decimal("0"))
    assert abs(total - Decimal("1")) < Decimal("1e-9")
