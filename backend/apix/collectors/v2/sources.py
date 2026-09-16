"""Source registry.

Only Google Flights is enabled while we stabilise the pipeline. The
MakeMyTrip entry is commented out because its httpx path hits a React
SPA shell with no server-rendered fares; re-enable once a real parser
is written.
"""

from __future__ import annotations

from typing import Any

from .google_flights import search_fares as gf_search


def _gf_parser(payload: Any) -> list[float]:
    from .google_flights import parse_google_flights

    return parse_google_flights(payload)


SOURCES: list[dict] = [
    {
        "name": "Google Flights",
        "kind": "api",
        "needs_browser": True,
        "search": gf_search,
        "parser": _gf_parser,
    },
    # --- disabled: needs a real SPA-aware parser ---
    # {
    #     "name": "MakeMyTrip",
    #     "kind": "api",
    #     "needs_browser": False,
    #     "search": mmt_search,
    #     "parser": _mmt_parser,
    # },
]
