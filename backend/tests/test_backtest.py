"""Backtest metrics unit tests."""

from __future__ import annotations

import math

from apix.backtest.metrics import compute_metrics


def test_perfect_agreement() -> None:
    a = [100.0, 102.0, 105.0, 103.0]
    d = [100.0, 102.0, 105.0, 103.0]
    m = compute_metrics(a, d)
    assert m.n_months == 4
    assert m.mape_pct == 0.0
    assert m.pearson_r == 1.0
    assert m.spearman_rho == 1.0
    assert m.direction_match_pct == 100.0


def test_perfect_inverse() -> None:
    # Perfectly collinear inverse: d = -2*a + 330
    a = [100.0, 105.0, 110.0, 115.0]
    d = [130.0, 120.0, 110.0, 100.0]
    m = compute_metrics(a, d)
    assert m.pearson_r == -1.0
    assert m.spearman_rho == -1.0
    assert m.direction_match_pct == 0.0


def test_constant_dgca_no_divide_by_zero() -> None:
    """All DGCA values equal -> correlation undefined, not a crash."""
    a = [100.0, 102.0, 104.0]
    d = [100.0, 100.0, 100.0]
    m = compute_metrics(a, d)
    assert math.isnan(m.pearson_r) or m.pearson_r == 0.0
    assert m.mape_pct == m.mape_pct  # not NaN


def test_direction_match_mixed() -> None:
    a = [100.0, 101.0, 99.0, 100.0]
    d = [100.0, 100.5, 99.5, 101.0]
    m = compute_metrics(a, d)
    # direction of changes: (+,+), (-,-), (+,+) -> 3 of 3 match
    assert m.direction_match_pct == 100.0


def test_mismatched_lengths_raise() -> None:
    import pytest

    with pytest.raises(ValueError):
        compute_metrics([100.0, 101.0], [100.0])
