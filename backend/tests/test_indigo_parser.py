"""Tests for the IndiGo parser against a recorded fixture."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from apix.collectors.airlines.indigo import (
    IndiGoParser,
    parse_indigo_html,
)
from apix.collectors.base import ParseError

_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "indigo" / "del-bom_15d.html"


def _load_fixture() -> str:
    return _FIXTURE.read_text(encoding="utf-8")


def test_fixture_exists() -> None:
    assert _FIXTURE.is_file(), f"fixture missing: {_FIXTURE}"


def test_parse_returns_three_flights() -> None:
    flights = parse_indigo_html(_load_fixture())
    assert len(flights) == 3


def test_parse_extracts_fares_correctly() -> None:
    flights = parse_indigo_html(_load_fixture())
    f0 = flights[0]
    assert f0.flight_number == "6E 1234"
    assert f0.fare_class == "ECONOMY"
    assert f0.base_fare == Decimal("4280")
    assert f0.taxes == Decimal("512")
    assert f0.udf == Decimal("249")
    assert f0.total_fare == Decimal("5041")


def test_parse_raises_on_empty_html() -> None:
    with pytest.raises(ParseError, match="could not find"):
        parse_indigo_html("<html><body>Nothing here</body></html>")


def test_parse_raises_on_missing_flights_key() -> None:
    html = "<html><script>window.__INITIAL_STATE__ = {};</script></html>"
    with pytest.raises(ParseError, match="no 'flights' list"):
        parse_indigo_html(html)


def test_parse_raises_on_bad_fare() -> None:
    html = """
    <html><script>
    window.__INITIAL_STATE__ = {
      "flights": [
        {"flightNumber": "6E 1", "baseFare": "not-a-number",
         "taxes": 1, "totalFare": 2}
      ]
    };
    </script></html>
    """
    with pytest.raises(ParseError, match="not a number"):
        parse_indigo_html(html)


def test_indigo_parser_returns_raw_quotes() -> None:
    parser = IndiGoParser()
    quotes = parser.parse(
        _load_fixture(),
        route_label="DEL-BOM",
        departure_date=date(2025, 9, 16),
        advance_days=15,
        collected_at=datetime(2025, 9, 1, 6, 0, tzinfo=timezone.utc),
    )
    assert len(quotes) == 3
    for q in quotes:
        assert q.source_name == "IndiGo"
        assert q.carrier == "6E"
        assert q.route_label == "DEL-BOM"
        assert q.advance_days == 15
        assert q.decomposition_method == "parsed"
        assert q.is_sold_out is False
    # first quote has the parsed breakdown
    q0 = quotes[0]
    assert q0.base_fare == Decimal("4280")
    assert q0.taxes == Decimal("512")
    assert q0.udf == Decimal("249")
    assert q0.total_fare == Decimal("5041")
