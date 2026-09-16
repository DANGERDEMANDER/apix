"""Standalone Google Flights worker. Run as a subprocess.

This isolates Playwright from uvicorn's event loop, which on Windows
uses a SelectorEventLoop that cannot spawn subprocesses.
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta

from playwright.sync_api import sync_playwright
from selectolax.parser import HTMLParser


def scrape(origin: str, destination: str, departure_date: str, max_results: int) -> list[dict]:
    url = (
        f"https://www.google.com/travel/flights?"
        f"q=flights+from+{origin}+to+{destination}"
        f"+on+{departure_date}+oneway&curr=INR"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            viewport={"width": 1366, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2500)
            html = page.content()
        finally:
            browser.close()

    tree = HTMLParser(html)
    fares: list[float] = []
    for node in tree.css("span"):
        text = (node.text() or "").strip()
        if "\u20b9" in text or "INR" in text:
            digits = "".join(ch for ch in text if ch.isdigit())
            if digits:
                try:
                    fares.append(float(digits))
                except ValueError:
                    pass

    fares = sorted(set(fares))[:max_results]
    return [
        {
            "fare_inr": f,
            "currency": "INR",
            "departure_date": departure_date,
            "source": "Google Flights",
        }
        for f in fares
    ]


def main() -> None:
    if len(sys.argv) < 5:
        print("usage: _gf_worker ORIGIN DEST YYYY-MM-DD MAX", file=sys.stderr)
        sys.exit(2)

    origin, destination, dep_date, max_str = sys.argv[1:5]
    max_results = int(max_str)

    try:
        result = scrape(origin, destination, dep_date, max_results)
        print(json.dumps(result))
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
