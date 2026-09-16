"""Per-domain token bucket rate limiter with exponential backoff + jitter."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    rate_per_sec: float
    burst: int
    tokens: float
    last_refill: float

    @classmethod
    def make(cls, rate_per_sec: float, burst: int) -> _Bucket:
        return cls(
            rate_per_sec=rate_per_sec,
            burst=burst,
            tokens=float(burst),
            last_refill=time.monotonic(),
        )

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(float(self.burst), self.tokens + elapsed * self.rate_per_sec)
        self.last_refill = now

    async def acquire(self) -> None:
        while True:
            self._refill()
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return
            deficit = 1.0 - self.tokens
            sleep_s = deficit / self.rate_per_sec
            await asyncio.sleep(sleep_s)


class RateLimiter:
    """One token bucket per domain, configured from sources.yaml.

    Two constraints are enforced per domain:
      - Token bucket with the configured requests-per-minute ceiling.
      - Minimum spacing between calls, derived from robots.txt Crawl-delay.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = {}
        self._min_interval: dict[str, float] = {}
        self._last_call: dict[str, float] = {}

    def configure(
        self,
        domain: str,
        rate_limit_rpm: int,
        crawl_delay_s: float,
    ) -> None:
        if rate_limit_rpm <= 0:
            raise ValueError("rate_limit_rpm must be > 0")
        rate_per_sec = rate_limit_rpm / 60.0
        # Burst = one second's worth of tokens, min 1. Prevents the bucket
        # from allowing a large burst that would trip a source's rate limiter.
        burst = max(1, int(round(rate_per_sec)))
        self._buckets[domain] = _Bucket.make(rate_per_sec=rate_per_sec, burst=burst)
        self._min_interval[domain] = max(crawl_delay_s, 0.0)
        self._last_call[domain] = 0.0

    async def acquire(self, domain: str) -> None:
        bucket = self._buckets.get(domain)
        if bucket is None:
            # Unconfigured domain: conservative fallback.
            await asyncio.sleep(6.0)
            return

        min_interval = self._min_interval.get(domain, 0.0)
        last = self._last_call.get(domain, 0.0)
        now = time.monotonic()
        since_last = now - last
        if since_last < min_interval:
            await asyncio.sleep(min_interval - since_last)

        await bucket.acquire()
        self._last_call[domain] = time.monotonic()


def backoff_seconds(attempt: int, base: float = 1.0, cap: float = 60.0) -> float:
    """Exponential backoff with full jitter. attempt is 0-indexed.

    Returns a value in [0, min(cap, base * 2**attempt)]. Full jitter avoids
    thundering-herd re-tries when multiple collectors hit a 429 together.
    """
    raw = min(cap, base * (2**attempt))
    return random.uniform(0.0, raw)
