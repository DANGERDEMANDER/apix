"""Tiered HTTP fetch with escalation.

Every live fetch goes through the ethics check and the rate limiter first.
If those refuse, the fetch is refused - no escalation path exists around them.

Tier 1: plain httpx GET. No browser-like headers. Cheapest. Use when the
        source returns clean HTML for non-browser User-Agents.
Tier 2: httpx GET with a browser-like header set (User-Agent, Accept,
        Accept-Language, Accept-Encoding, Sec-Fetch-*). Handles most sites
        that do a shallow UA check.
Tier 3: Playwright with a real browser context. Reserved for pages that
        require JavaScript execution. Deliberately not implemented in this
        batch; the class raises a clear error naming the missing tier so the
        caller knows the request was not silently dropped.
Tier 4: CAPTCHA solving via a third-party API. Deliberately not implemented
        and documented as a rejected capability in ETHICS.md.

Escalation rules:
  - 200 + clean body => return at whatever tier produced it.
  - 401/403 => escalate to the next tier, no retry at the current tier.
  - 429 => single retry at the same tier after exponential backoff with
           jitter; if the retry is also 429, escalate.
  - 200 + known challenge marker in the body => treat as blocked, escalate.

The escalation path is capped at Tier 2 in this batch. Tier 3 raises
NotImplementedError with a message naming the batch where it will land.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from apix.collectors.base import BlockedError, RateLimitedError
from apix.collectors.ethics import RobotsCache, kill_switch_engaged
from apix.collectors.live.session import PlaywrightSession
from apix.collectors.ratelimit import RateLimiter, backoff_seconds

_BROWSER_HEADERS: dict[str, str] = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9," "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# HTML substrings that mean "you were served a challenge, not the real page".
# Presence of any of these converts a 200 into a blocked response that
# escalates instead of being returned as valid HTML.
_CHALLENGE_MARKERS: tuple[str, ...] = (
    "just a moment",
    "cf-challenge",
    "cf_chl_opt",
    "checking your browser",
    "please verify you are a human",
    "enable javascript and cookies",
)


@dataclass(frozen=True)
class FetchedPage:
    """Result of a successful fetch. Only returned when the body looks real."""

    url: str
    status: int
    html: str
    tier: int
    fetched_at: datetime


def _looks_like_challenge(body: str) -> bool:
    lower = body.lower()
    return any(marker in lower for marker in _CHALLENGE_MARKERS)


def _is_success(response: httpx.Response) -> bool:
    if response.status_code != 200:
        return False
    return not _looks_like_challenge(response.text)


class TieredFetcher:
    """One fetcher per collection run. Reuses ethics + rate limit state."""

    def __init__(
        self,
        user_agent: str,
        ethics: RobotsCache,
        ratelimit: RateLimiter,
        *,
        timeout_s: float = 15.0,
        playwright_session_factory: Callable[[], PlaywrightSession] | None = None,
    ) -> None:
        self._user_agent = user_agent
        self._ethics = ethics
        self._ratelimit = ratelimit
        self._timeout_s = timeout_s
        self._session_factory = playwright_session_factory

    async def _preflight(self, url: str) -> str:
        """Kill switch + robots + rate-limit gate. Returns the domain."""
        if kill_switch_engaged():
            from apix.collectors.base import KillSwitchError

            raise KillSwitchError("live collection disabled (APIX_COLLECTION_ENABLED=false)")
        decision = await self._ethics.check(url)
        if not decision.allowed:
            from apix.collectors.base import RobotsDisallowedError

            raise RobotsDisallowedError(f"{decision.reason}: {url}")
        domain = urlparse(url).netloc
        await self._ratelimit.acquire(domain)
        return domain

    async def _get(
        self,
        url: str,
        headers: dict[str, str],
    ) -> httpx.Response:
        async with httpx.AsyncClient(
            headers=headers,
            timeout=self._timeout_s,
            follow_redirects=True,
        ) as client:
            return await client.get(url)

    async def _tier1_plain(self, url: str) -> httpx.Response:
        return await self._get(url, {"User-Agent": self._user_agent})

    async def _tier2_browser_headers(self, url: str) -> httpx.Response:
        headers = {"User-Agent": self._user_agent, **_BROWSER_HEADERS}
        return await self._get(url, headers)

    async def _tier3_playwright(self, url: str) -> FetchedPage:
        """Render the page in a real browser. Stock Playwright + Firefox.

        Raises BlockedError when no session factory is configured, since
        Tier 3 is an opt-in capability (the caller must supply a session).
        """
        if self._session_factory is None:
            raise BlockedError(
                f"tier 3 requested for {url} but no playwright_session_factory "
                "configured; caller must inject one"
            )
        async with self._session_factory() as session:
            html = await session.fetch_html(url)
            if _looks_like_challenge(html):
                raise BlockedError(f"tier 3 received a challenge page from {url}")
            return FetchedPage(
                url=url,
                status=200,
                html=html,
                tier=3,
                fetched_at=datetime.now(timezone.utc),
            )

    async def fetch(self, url: str) -> FetchedPage:
        """Fetch a page, escalating as needed. Raises on unrecoverable block."""
        domain = await self._preflight(url)
        now = datetime.now(timezone.utc)

        # ---- Tier 1: plain httpx ----
        try:
            r1 = await self._tier1_plain(url)
        except httpx.HTTPError:
            r1 = None

        if r1 is not None and _is_success(r1):
            return FetchedPage(url=url, status=r1.status_code, html=r1.text, tier=1, fetched_at=now)

        # ---- Retry at tier 1 on 429 after backoff ----
        if r1 is not None and r1.status_code == 429:
            await asyncio.sleep(backoff_seconds(attempt=0, base=1.0, cap=30.0))
            await self._ratelimit.acquire(domain)
            try:
                r1b = await self._tier1_plain(url)
                if _is_success(r1b):
                    return FetchedPage(
                        url=url,
                        status=r1b.status_code,
                        html=r1b.text,
                        tier=1,
                        fetched_at=datetime.now(timezone.utc),
                    )
            except httpx.HTTPError:
                pass

        # ---- Tier 2: browser-like headers ----
        await self._ratelimit.acquire(domain)
        try:
            r2 = await self._tier2_browser_headers(url)
        except httpx.HTTPError as exc:
            raise BlockedError(f"tier 2 HTTP error for {url}: {exc}") from exc

        if _is_success(r2):
            return FetchedPage(
                url=url,
                status=r2.status_code,
                html=r2.text,
                tier=2,
                fetched_at=datetime.now(timezone.utc),
            )

        if r2.status_code == 429:
            raise RateLimitedError(f"429 from {url} after tier-1 retry and tier-2")

        # Tier 3 (Playwright) if a session factory is configured.
        if self._session_factory is not None:
            await self._ratelimit.acquire(domain)
            return await self._tier3_playwright(url)

        raise BlockedError(
            f"tier 1 returned {getattr(r1, 'status_code', 'HTTPError')}, "
            f"tier 2 returned {r2.status_code} for {url}; "
            "no playwright_session_factory configured for tier 3"
        )
