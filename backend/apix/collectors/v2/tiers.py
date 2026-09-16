"""Tiered fetch strategy: curl_cffi -> httpx+selectolax -> Patchright.

Each tier raises TierUnavailable if it can't handle the source, and the
orchestrator falls through to the next. Only Tier 2 costs real time.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

LOG = logging.getLogger("apix.collector.tiers")


@dataclass
class FetchResult:
    url: str
    status: int
    body: str
    tier: str           # "curl_cffi" | "httpx" | "patchright"
    elapsed_ms: int


class TierUnavailable(Exception):
    """Raised when a tier cannot handle the source and must escalate."""


# --- Tier 0: curl_cffi with TLS impersonation -------------------

async def fetch_tier0(url: str, *, timeout: float = 10.0) -> FetchResult:
    """Fast path. Bypasses TLS fingerprinting with Chrome impersonation."""
    from curl_cffi.requests import AsyncSession

    started = time.perf_counter()
    async with AsyncSession() as s:
        r = await s.get(
            url,
            impersonate="chrome124",
            timeout=timeout,
            allow_redirects=True,
        )
    elapsed = int((time.perf_counter() - started) * 1000)

    if r.status_code in (403, 429):
        raise TierUnavailable(f"tier0 blocked: {r.status_code}")
    if len(r.text) < 500:
        raise TierUnavailable("tier0 body too small; probably SPA")

    return FetchResult(url, r.status_code, r.text, "curl_cffi", elapsed)


# --- Tier 1: httpx + selectolax --------------------------------

async def fetch_tier1(url: str, *, timeout: float = 15.0) -> FetchResult:
    """Server-rendered pages with structured HTML."""
    import httpx

    started = time.perf_counter()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-IN,en;q=0.9",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as c:
        r = await c.get(url, headers=headers)
    elapsed = int((time.perf_counter() - started) * 1000)

    if r.status_code >= 400:
        raise TierUnavailable(f"tier1 http {r.status_code}")

    lower = r.text.lower()
    if "\u20b9" not in r.text and "inr" not in lower and "price" not in lower:
        raise TierUnavailable("tier1 body has no fare markers")

    return FetchResult(url, r.status_code, r.text, "httpx", elapsed)


# --- Tier 2: Patchright (undetected Playwright) -----------------

async def fetch_tier2(url: str, *, timeout: float = 30.0) -> FetchResult:
    """Full browser. Last resort for JS-heavy or bot-protected sources."""
    from patchright.async_api import async_playwright

    started = time.perf_counter()
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        ctx = await browser.new_context(
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await ctx.new_page()
        await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
        await page.wait_for_timeout(1500)
        body = await page.content()
        await browser.close()

    elapsed = int((time.perf_counter() - started) * 1000)
    return FetchResult(url, 200, body, "patchright", elapsed)


# --- The escalation ladder -------------------------------------

TierCallback = Callable[[str, str], Awaitable[None]]


async def fetch_with_escalation(
    url: str,
    *,
    on_tier: Optional[TierCallback] = None,
) -> FetchResult:
    """Try each tier in order. Emit a callback when escalating."""
    tiers: list[tuple[str, Callable[[str], Awaitable[FetchResult]]]] = [
        ("curl_cffi", fetch_tier0),
        ("httpx", fetch_tier1),
        ("patchright", fetch_tier2),
    ]
    last_error: Optional[Exception] = None

    for name, fn in tiers:
        try:
            if on_tier:
                await on_tier(name, "start")
            result = await fn(url)
            if on_tier:
                await on_tier(name, "success")
            return result
        except TierUnavailable as e:
            LOG.info("tier %s unavailable for %s: %s", name, url, e)
            last_error = e
            if on_tier:
                await on_tier(name, "escalate")
            continue
        except Exception as e:
            LOG.warning("tier %s error for %s: %s", name, url, e)
            last_error = e
            if on_tier:
                await on_tier(name, "error")
            continue

    raise RuntimeError(f"all tiers failed for {url}: {last_error}")
