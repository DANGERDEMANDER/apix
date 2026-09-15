"""Phase 2 acceptance tests for the synthetic fare generator."""

from __future__ import annotations

import statistics
from datetime import date, timedelta
from decimal import Decimal

from apix.collectors.festivals import load_festivals
from apix.collectors.synthetic import SyntheticConfig, build_collectors
from apix.settings import get_settings


def _collector(name: str = "IndiGo", seed: int = 42) -> object:
    settings = get_settings()
    festivals = load_festivals(settings.env.config_dir)
    return build_collectors((name,), SyntheticConfig(seed=seed), festivals)[0]


def _route_labels() -> tuple[str, ...]:
    return tuple(r.label for r in get_settings().basket.routes)


def test_seed_determinism() -> None:
    c1 = _collector(seed=42)
    c2 = _collector(seed=42)
    for label in _route_labels():
        q1 = c1.generate(label, date(2025, 6, 15), 15)
        q2 = c2.generate(label, date(2025, 6, 15), 15)
        assert q1 == q2, f"non-deterministic quote for {label}"


def test_different_seeds_differ() -> None:
    c1 = _collector(seed=42)
    c2 = _collector(seed=43)
    diffs = 0
    for label in _route_labels():
        q1 = c1.generate(label, date(2025, 6, 15), 15)
        q2 = c2.generate(label, date(2025, 6, 15), 15)
        if q1 != q2:
            diffs += 1
    assert diffs >= 5, "seeds 42 and 43 produced nearly identical output"


def test_lead_time_curve_monotone_decreasing_on_average() -> None:
    windows = get_settings().index.advance_windows_days
    departure = date(2025, 6, 15)
    means: dict[int, float] = {}

    for adv in windows:
        prices: list[float] = []
        for label in _route_labels():
            for src in ("IndiGo", "AirIndia", "MakeMyTrip"):
                c = _collector(src, seed=2026)
                q = c.generate(label, departure, adv)
                if q is not None and not q.is_sold_out and q.base_fare is not None:
                    prices.append(float(q.base_fare))
        means[adv] = statistics.mean(prices)

    ordered = [means[adv] for adv in sorted(windows)]
    for a, b in zip(ordered, ordered[1:]):
        assert a >= b, f"lead-time curve not decreasing: {means}"


def test_sold_out_fraction_in_band() -> None:
    windows = get_settings().index.advance_windows_days
    departure = date(2025, 7, 1)
    total = 0
    sold_out = 0

    for label in _route_labels():
        for src in ("IndiGo", "AirIndia", "MakeMyTrip", "Yatra"):
            for adv in windows:
                for day_offset in range(30):
                    d = departure + timedelta(days=day_offset)
                    c = _collector(src, seed=2026)
                    q = c.generate(label, d, adv)
                    total += 1
                    if q is not None and q.is_sold_out:
                        sold_out += 1

    frac = sold_out / total
    assert 0.02 <= frac <= 0.08, f"sold-out fraction {frac:.4f} outside [0.02, 0.08]"


def test_festival_surge_is_visible() -> None:
    route = "DEL-BOM"
    adv = 15
    c = _collector("IndiGo", seed=2026)

    festival_prices: list[float] = []
    baseline_prices: list[float] = []

    for i in range(-3, 4):
        d = date(2025, 10, 20) + timedelta(days=i)
        q = c.generate(route, d, adv)
        if q is not None and not q.is_sold_out and q.base_fare is not None:
            festival_prices.append(float(q.base_fare))

    for i in range(-3, 4):
        d = date(2025, 7, 20) + timedelta(days=i)
        q = c.generate(route, d, adv)
        if q is not None and not q.is_sold_out and q.base_fare is not None:
            baseline_prices.append(float(q.base_fare))

    festival_mean = statistics.mean(festival_prices)
    baseline_mean = statistics.mean(baseline_prices)
    assert festival_mean > baseline_mean * 1.15, (
        f"festival mean {festival_mean:.2f} not sufficiently above "
        f"baseline mean {baseline_mean:.2f}"
    )


def test_sold_out_quote_shape() -> None:
    c = _collector("IndiGo", seed=2026)
    found = False
    for day_offset in range(200):
        d = date(2025, 1, 1) + timedelta(days=day_offset)
        q = c.generate("DEL-BOM", d, 7)
        if q is None or not q.is_sold_out:
            continue
        found = True
        assert q.base_fare is None
        assert q.taxes is None
        assert q.udf is None
        assert q.total_fare == Decimal("0.00")
        assert q.decomposition_method == "none"
        break
    assert found, "no sold-out cell found in 200 attempts"


