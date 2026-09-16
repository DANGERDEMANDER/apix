"""Tests for replay mode (no network)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from apix.collectors.base import RawQuote
from apix.collectors.replay import (
    ReplayCollector,
    list_registered_sources,
)


def test_registered_sources_includes_indigo() -> None:
    assert "IndiGo" in list_registered_sources()


def test_replay_collector_reads_fixture() -> None:
    c = ReplayCollector("IndiGo")
    quotes = c.collect_from_fixture(
        route_label="DEL-BOM",
        advance_days=15,
        collected_at=datetime(2025, 9, 1, 6, 0, tzinfo=timezone.utc),
    )
    assert len(quotes) == 3
    assert all(isinstance(q, RawQuote) for q in quotes)
    assert all(q.source_name == "IndiGo" for q in quotes)
    assert all(q.advance_days == 15 for q in quotes)


def test_replay_missing_fixture_raises() -> None:
    c = ReplayCollector("IndiGo")
    with pytest.raises(FileNotFoundError, match="replay fixture not found"):
        c.collect_from_fixture(
            route_label="XXX-YYY",
            advance_days=15,
            collected_at=datetime(2025, 9, 1, 6, 0, tzinfo=timezone.utc),
        )


def test_replay_unknown_source_raises() -> None:
    with pytest.raises(ValueError, match="no parser registered"):
        ReplayCollector("NotASource")


def test_departure_date_derived_from_collected_at() -> None:
    c = ReplayCollector("IndiGo")
    quotes = c.collect_from_fixture(
        route_label="DEL-BOM",
        advance_days=15,
        collected_at=datetime(2025, 9, 1, 6, 0, tzinfo=timezone.utc),
    )
    assert quotes[0].departure_date == date(2025, 9, 16)
