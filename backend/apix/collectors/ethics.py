"""robots.txt compliance, per-domain policy, and the global kill switch.

Every live fetch goes through `RobotsCache.check()`. If robots.txt disallows
the path, or the kill switch is engaged, the fetch is refused and the attempt
is logged with a reason.

Per RFC 9309:
  - Absence of robots.txt => allow all.
  - Network error fetching robots.txt => refuse (fail closed, not open).
  - Crawl-delay is honoured when present.
"""

from __future__ import annotations

import urllib.robotparser
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from apix.settings import get_settings


@dataclass(frozen=True)
class RobotsDecision:
    allowed: bool
    reason: str
    crawl_delay_s: float | None
    checked_at: datetime


class RobotsCache:
    """Fetch and cache robots.txt per scheme+netloc with a TTL."""

    def __init__(self, user_agent: str, ttl_seconds: int = 3600) -> None:
        self._user_agent = user_agent
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[urllib.robotparser.RobotFileParser, datetime]] = {}

    @staticmethod
    def _key(url: str) -> str:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}"

    async def _fetch(self, key: str) -> urllib.robotparser.RobotFileParser:
        rp = urllib.robotparser.RobotFileParser()
        robots_url = f"{key}/robots.txt"
        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": self._user_agent},
                timeout=10.0,
                follow_redirects=True,
            ) as client:
                r = await client.get(robots_url)
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                else:
                    # No robots.txt -> RFC 9309 says allow by default.
                    rp.parse(["User-agent: *", "Allow: /"])
        except httpx.HTTPError:
            # Network error fetching robots.txt -> refuse rather than guess.
            rp.parse(["User-agent: *", "Disallow: /"])
        return rp

    async def check(self, url: str) -> RobotsDecision:
        key = self._key(url)
        now = datetime.now(timezone.utc)
        entry = self._cache.get(key)
        if entry is None or (now - entry[1]).total_seconds() > self._ttl:
            rp = await self._fetch(key)
            self._cache[key] = (rp, now)
        else:
            rp = entry[0]

        allowed = rp.can_fetch(self._user_agent, url)
        reason = "allowed" if allowed else "disallowed by robots.txt"
        delay = rp.crawl_delay(self._user_agent)
        crawl_delay_s = float(delay) if delay is not None else None
        return RobotsDecision(
            allowed=allowed,
            reason=reason,
            crawl_delay_s=crawl_delay_s,
            checked_at=now,
        )


def kill_switch_engaged() -> bool:
    """True when the operator has disabled live collection.

    Reads APIX_COLLECTION_ENABLED. Defaults to False (disabled), so the kill
    switch is engaged unless an operator explicitly turns collection on.
    """
    return not get_settings().env.collection_enabled
