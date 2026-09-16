"""Replay mode: load recorded HTML from fixtures/ and run real parsers.

No network is touched in replay mode. Fixtures are committed to the repo
and reviewed before commit (no cookies, no tokens, no personal data).

Fixture path convention:
    fixtures/<source_slug>/<route_slug>_<advance_days>d.html

where source_slug is the source name lowercased with non-alphanumerics
replaced by underscores.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Protocol

from apix.collectors.airlines.indigo import IndiGoParser
from apix.collectors.base import ParseError, RawQuote

_FIXTURES_ROOT = Path(__file__).resolve().parents[3] / "fixtures"


class _Parser(Protocol):
    name: str
    carrier: str

    def parse(
        self,
        html: str,
        *,
        route_label: str,
        departure_date: date,
        advance_days: int,
        collected_at: datetime,
    ) -> list[RawQuote]: ...


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _fixture_path(source_name: str, route_label: str, advance_days: int) -> Path:
    return _FIXTURES_ROOT / _slug(source_name) / f"{route_label.lower()}_{advance_days}d.html"


_PARSERS: dict[str, type[_Parser]] = {
    "IndiGo": IndiGoParser,
}


class ReplayCollector:
    """Reads recorded HTML and returns quotes. No network."""

    def __init__(self, source_name: str) -> None:
        if source_name not in _PARSERS:
            raise ValueError(
                f"no parser registered for {source_name!r}; " f"known: {sorted(_PARSERS)}"
            )
        self.name = source_name
        self._parser = _PARSERS[source_name]()

    def collect_from_fixture(
        self,
        route_label: str,
        advance_days: int,
        *,
        collected_at: datetime,
    ) -> list[RawQuote]:
        """Load the fixture, parse it, and return RawQuotes."""
        path = _fixture_path(self.name, route_label, advance_days)
        if not path.is_file():
            raise FileNotFoundError(
                f"replay fixture not found: {path} "
                f"(route={route_label}, advance_days={advance_days})"
            )
        html = path.read_text(encoding="utf-8")
        departure = (collected_at + timedelta(days=advance_days)).date()
        try:
            return self._parser.parse(
                html,
                route_label=route_label,
                departure_date=departure,
                advance_days=advance_days,
                collected_at=collected_at,
            )
        except ParseError:
            raise
        except Exception as exc:
            raise ParseError(f"replay parser failed on {path}: {exc}") from exc


def list_registered_sources() -> list[str]:
    return sorted(_PARSERS)
