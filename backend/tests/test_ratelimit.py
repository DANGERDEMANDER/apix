"""Tests for the per-domain token bucket rate limiter."""

from __future__ import annotations

import time

from apix.collectors.ratelimit import RateLimiter, backoff_seconds


async def test_rate_limiter_enforces_spacing() -> None:
    rl = RateLimiter()
    rl.configure("example.com", rate_limit_rpm=600, crawl_delay_s=0.1)
    start = time.monotonic()
    await rl.acquire("example.com")
    await rl.acquire("example.com")
    elapsed = time.monotonic() - start
    # At least crawl_delay_s must have elapsed between the two calls.
    assert elapsed >= 0.09


async def test_rate_limiter_bucket_limits_burst() -> None:
    rl = RateLimiter()
    # 60 rpm = 1 token/sec, burst = 1. Second call must wait ~1 sec.
    rl.configure("example.com", rate_limit_rpm=60, crawl_delay_s=0.0)
    start = time.monotonic()
    await rl.acquire("example.com")  # instant (bucket has 1 token)
    await rl.acquire("example.com")  # waits for refill
    elapsed = time.monotonic() - start
    assert elapsed >= 0.9


def test_backoff_within_range() -> None:
    for attempt in range(5):
        delay = backoff_seconds(attempt, base=1.0, cap=30.0)
        ceiling = min(30.0, 1.0 * (2**attempt))
        assert 0.0 <= delay <= ceiling


def test_backoff_caps_at_max() -> None:
    delay = backoff_seconds(attempt=10, base=1.0, cap=30.0)
    assert 0.0 <= delay <= 30.0
