"""Index construction: the statistical core of APix (see build spec ?7).

Submodules:
  window_agg  ? ?7.1 window aggregation
  relative    ? ?7.2 price relative and base values
  weights     ? ?7.3 route weight normalisation
  engine      ? ?7.4 the index, with missing-route re-normalisation
"""

from __future__ import annotations

from apix.index.engine import IndexResult, IndexStatus, compute_index
from apix.index.relative import compute_base_value, price_relative
from apix.index.weights import normalise_weights
from apix.index.window_agg import WindowAggregate, aggregate_windows

__all__ = [
    "IndexResult",
    "IndexStatus",
    "WindowAggregate",
    "aggregate_windows",
    "compute_base_value",
    "compute_index",
    "normalise_weights",
    "price_relative",
]
