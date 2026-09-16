"""Per-source parsers. Each converts fetched HTML into RawQuotes."""

from __future__ import annotations

from apix.collectors.airlines.indigo import IndiGoParser

__all__ = ["IndiGoParser"]
