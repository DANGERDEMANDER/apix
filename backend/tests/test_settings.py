"""Assert the three config/*.yaml files load into the expected shape."""

from __future__ import annotations

from apix.settings import get_settings


def test_basket_has_ten_routes() -> None:
    s = get_settings()
    assert len(s.basket.routes) == 10
    labels = {r.label for r in s.basket.routes}
    # The six routes named explicitly in SIH 2026 PS 26056 must all be present.
    required = {"DEL-BOM", "DEL-BLR", "BOM-BLR", "DEL-CCU", "BLR-HYD", "MAA-DEL"}
    missing = required - labels
    assert not missing, f"PS-named routes missing from basket: {sorted(missing)}"


def test_sources_has_eleven_entries() -> None:
    s = get_settings()
    names = {src.name for src in s.sources.sources}
    expected_airlines = {"IndiGo", "AirIndia", "AirIndiaExpress", "AkasaAir", "SpiceJet"}
    expected_otas = {
        "MakeMyTrip",
        "Yatra",
        "EaseMyTrip",
        "Cleartrip",
        "Ixigo",
        "Goibibo",
    }
    assert expected_airlines <= names, "missing PS-named airlines"
    assert expected_otas <= names, "missing PS-named OTAs"
    assert "Vistara" not in names, "Vistara merged into Air India in 2024-25"


def test_index_config_is_consistent() -> None:
    s = get_settings()
    idx = s.index
    assert idx.advance_windows_days == [1, 7, 15, 30, 45]
    assert abs(sum(idx.window_weights.values()) - 1.0) < 1e-9
    assert abs(sum(idx.window_weights_prior.values()) - 1.0) < 1e-9
    assert idx.window_weights_source == "prior"
    assert idx.calibration_metadata is None
    assert idx.window_weights == idx.window_weights_prior


def test_operational_thresholds() -> None:
    s = get_settings()
    assert s.index.min_publishable_coverage == 0.70
    assert s.index.route_suspension_days == 7
    assert s.index.max_imputation_share == 0.10
    assert s.index.min_fare_inr < s.index.max_fare_inr
