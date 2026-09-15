"""Backtest metrics: MAPE, Pearson r, Spearman rho, direction match."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestMetrics:
    n_months: int
    mape_pct: float
    pearson_r: float
    spearman_rho: float
    direction_match_pct: float


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2:
        return float("nan")
    mx, my = _mean(xs), _mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return float("nan")
    return num / (dx * dy)


def _rank(xs: list[float]) -> list[float]:
    """Average-rank, ties get the mean rank. 1-indexed."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2:
        return float("nan")
    return _pearson(_rank(xs), _rank(ys))


def compute_metrics(
    apix_monthly: list[float], dgca_monthly: list[float]
) -> BacktestMetrics:
    """Compute all four metrics on matched monthly series."""
    if len(apix_monthly) != len(dgca_monthly):
        raise ValueError("series lengths differ")
    n = len(apix_monthly)
    if n == 0:
        return BacktestMetrics(0, float("nan"), float("nan"), float("nan"), float("nan"))

    maes = [abs(a - d) / d for a, d in zip(apix_monthly, dgca_monthly, strict=True) if d != 0]
    mape = 100.0 * _mean(maes) if maes else float("nan")

    r = _pearson(apix_monthly, dgca_monthly)
    rho = _spearman(apix_monthly, dgca_monthly)

    if n >= 2:
        hits = 0
        for i in range(n - 1):
            da = apix_monthly[i + 1] - apix_monthly[i]
            dd = dgca_monthly[i + 1] - dgca_monthly[i]
            if (da >= 0) == (dd >= 0):
                hits += 1
        direction = 100.0 * hits / (n - 1)
    else:
        direction = float("nan")

    return BacktestMetrics(
        n_months=n,
        mape_pct=round(mape, 2) if not math.isnan(mape) else float("nan"),
        pearson_r=round(r, 4) if not math.isnan(r) else float("nan"),
        spearman_rho=round(rho, 4) if not math.isnan(rho) else float("nan"),
        direction_match_pct=round(direction, 1) if not math.isnan(direction) else float("nan"),
    )
