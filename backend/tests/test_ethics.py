"""Tests for robots.txt compliance and the kill switch."""

from __future__ import annotations

import urllib.robotparser

import pytest

from apix.collectors.ethics import RobotsCache, kill_switch_engaged


@pytest.fixture
def cache() -> RobotsCache:
    return RobotsCache(user_agent="APix/0.1 (+https://github.com/DANGERDEMANDER/apix)")


async def test_robots_allows_when_absent(
    cache: RobotsCache, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_fetch(self: RobotsCache, key: str) -> urllib.robotparser.RobotFileParser:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(["User-agent: *", "Allow: /"])
        return rp

    monkeypatch.setattr(RobotsCache, "_fetch", fake_fetch)
    decision = await cache.check("https://example.com/search")
    assert decision.allowed is True
    assert decision.reason == "allowed"


async def test_robots_disallows(cache: RobotsCache, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(self: RobotsCache, key: str) -> urllib.robotparser.RobotFileParser:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(["User-agent: *", "Disallow: /search"])
        return rp

    monkeypatch.setattr(RobotsCache, "_fetch", fake_fetch)
    decision = await cache.check("https://example.com/search?q=1")
    assert decision.allowed is False
    assert "robots" in decision.reason.lower()


async def test_robots_crawl_delay_is_parsed(
    cache: RobotsCache, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_fetch(self: RobotsCache, key: str) -> urllib.robotparser.RobotFileParser:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(["User-agent: *", "Crawl-delay: 5", "Allow: /"])
        return rp

    monkeypatch.setattr(RobotsCache, "_fetch", fake_fetch)
    decision = await cache.check("https://example.com/")
    assert decision.crawl_delay_s == 5.0


def test_kill_switch_engaged_by_default() -> None:
    # APIX_COLLECTION_ENABLED defaults to false; kill switch is engaged.
    assert kill_switch_engaged() is True
