"""IndiGo search-results parser.

IndiGo's site is a React SPA. The flight list is preloaded into
`window.__INITIAL_STATE__` as a JSON object alongside the page's JS bundle.
The parser reads that JSON; it does not scrape DOM nodes. That choice is
deliberate:

  - JSON keys are more stable than CSS selectors across redesigns.
  - The JSON is what the app itself trusts; there's no post-processing.
  - If the site ever stops embedding JSON, the parser raises ParseError
    with a clear message rather than silently returning zero quotes.

`decomposition_method` is set to "parsed" because IndiGo exposes base fare,
taxes, and UDF as separate fields. That is the meaningful distinction from
an OTA page, where the components are often folded into a single total.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import cast

from apix.collectors.base import ParseError, RawQuote

# The key whose value we want, looked for inside any <script> tag.
_STATE_KEY = "window.__INITIAL_STATE__"

# Fallback keys used by other IndiGo variants / older builds.
_FALLBACK_KEYS = ("window.__FLIGHT_DATA__", "window.__APOLLO_STATE__")

_SCRIPT_RE = re.compile(r"<script[^>]*>(.*?)</script>", re.DOTALL)


@dataclass(frozen=True)
class IndiGoFlight:
    flight_number: str
    fare_class: str
    base_fare: Decimal
    taxes: Decimal
    udf: Decimal | None
    total_fare: Decimal


def _extract_json_after(script_body: str, key: str) -> object | None:
    """Find `key = <json>` inside a script body and decode it."""
    idx = script_body.find(key)
    if idx < 0:
        return None
    after = script_body[idx + len(key) :].lstrip()
    if not after.startswith("="):
        return None
    after = after[1:].lstrip()
    try:
        # raw_decode stops at the end of the first valid JSON value,
        # so we don't have to balance braces ourselves.
        decoded = json.JSONDecoder().raw_decode(after)
    except json.JSONDecodeError:
        return None
    # raw_decode returns tuple[Any, int]; cast the first element to object
    # so mypy strict sees a concrete return type.
    return cast("object", decoded[0])


def _find_state(html: str) -> object | None:
    for script_match in _SCRIPT_RE.finditer(html):
        body = script_match.group(1)
        for key in (_STATE_KEY, *_FALLBACK_KEYS):
            obj = _extract_json_after(body, key)
            if obj is not None:
                return obj
    return None


def _flight_from_dict(raw: dict[str, object]) -> IndiGoFlight:
    def _dec(key: str) -> Decimal:
        v = raw.get(key)
        if v is None:
            raise ParseError(f"IndiGo flight missing {key!r}")
        try:
            return Decimal(str(v))
        except Exception as exc:
            raise ParseError(f"IndiGo fare {key} not a number: {v!r}") from exc

    fn = raw.get("flightNumber")
    fc = raw.get("fareClass", "ECONOMY")
    if not isinstance(fn, str) or not fn:
        raise ParseError("IndiGo flight missing flightNumber")
    udf_raw = raw.get("udf")
    udf = Decimal(str(udf_raw)) if udf_raw is not None else None

    return IndiGoFlight(
        flight_number=fn,
        fare_class=str(fc),
        base_fare=_dec("baseFare"),
        taxes=_dec("taxes"),
        udf=udf,
        total_fare=_dec("totalFare"),
    )


def parse_indigo_html(html: str) -> list[IndiGoFlight]:
    """Parse IndiGo search HTML into flight records. Raises ParseError."""
    state = _find_state(html)
    if state is None:
        raise ParseError(
            "could not find window.__INITIAL_STATE__ (or fallback key) " "in IndiGo HTML"
        )
    if not isinstance(state, dict):
        raise ParseError("IndiGo state root is not a JSON object")
    flights_raw = state.get("flights")
    if not isinstance(flights_raw, list):
        raise ParseError("IndiGo state has no 'flights' list")
    if not flights_raw:
        raise ParseError("IndiGo 'flights' list is empty")
    out: list[IndiGoFlight] = []
    for item in flights_raw:
        if not isinstance(item, dict):
            raise ParseError("IndiGo flight entry is not an object")
        out.append(_flight_from_dict(item))
    return out


class IndiGoParser:
    """Adapter between raw HTML and the collector's RawQuote contract."""

    name = "IndiGo"
    carrier = "6E"

    def parse(
        self,
        html: str,
        *,
        route_label: str,
        departure_date: date,
        advance_days: int,
        collected_at: datetime,
    ) -> list[RawQuote]:
        flights = parse_indigo_html(html)
        return [
            RawQuote(
                source_name=self.name,
                route_label=route_label,
                departure_date=departure_date,
                advance_days=advance_days,
                carrier=self.carrier,
                flight_number=f.flight_number,
                fare_class=f.fare_class,
                base_fare=f.base_fare,
                taxes=f.taxes,
                udf=f.udf,
                convenience_fee=Decimal("0.00"),
                total_fare=f.total_fare,
                is_sold_out=False,
                decomposition_method="parsed",
                collected_at=collected_at,
                raw_payload={
                    "flight_number": f.flight_number,
                    "fare_class": f.fare_class,
                    "source": "indigo-spa-json",
                },
            )
            for f in flights
        ]
