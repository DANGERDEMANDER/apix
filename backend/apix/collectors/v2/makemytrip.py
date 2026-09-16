"""MakeMyTrip scraper — httpx + Selectolax.

Adapted from the open-source approach used in andrew-geeks/MakeMyTrip-scraper.
MakeMyTrip is a React SPA, so we try the mobile endpoint first.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

LOG = logging.getLogger("apix.collector.makemytrip")


async def search_fares(
    origin: str,
    destination: str,
    *,
    departure_date: str | None = None,
    max_results: int = 5,
) -> list[dict[str, Any]]:
    from datetime import date, timedelta

    import httpx
    from selectolax.parser import HTMLParser

    if not departure_date:
        departure_date = (date.today() + timedelta(days=30)).isoformat()

    url = (
        f"https://www.makemytrip.com/flight/search?"
        f"itinerary={origin}-{destination}-{departure_date}"
        f"&tripType=O&paxType=A-1_C-0_I-0&intl=false&cabinClass=E"
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-IN,en;q=0.9",
    }

    async with httpx.AsyncClient(follow_redirects=True, timeout=25) as c:
        r = await c.get(url, headers=headers)

    if r.status_code >= 400:
        raise RuntimeError(f"MakeMyTrip http {r.status_code}")

    tree = HTMLParser(r.text)

    fares: list[float] = []
    for node in tree.css("span, div"):
        text = (node.text() or "").strip()
        if "\u20b9" in text:
            digits = "".join(ch for ch in text if ch.isdigit())
            if digits:
                with contextlib.suppress(ValueError):
                    fares.append(float(digits))

    fares = sorted(set(fares))[:max_results]
    return [
        {
            "fare_inr": f,
            "currency": "INR",
            "departure_date": departure_date,
            "source": "MakeMyTrip",
        }
        for f in fares
    ]


def parse_makemytrip(payload: Any) -> list[float]:
    if isinstance(payload, dict):
        items = payload.get("fares") or []
    elif isinstance(payload, list):
        items = payload
    else:
        return []
    return [float(x["fare_inr"]) for x in items if isinstance(x, dict) and "fare_inr" in x]
