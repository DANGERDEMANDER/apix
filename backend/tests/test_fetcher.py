"""Tests for the tiered fetcher. All network is monkeypatched."""

from __future__ import annotations

import urllib.robotparser

import httpx
import pytest

from apix.collectors.base import BlockedError, RobotsDisallowedError
from apix.collectors.ethics import RobotsCache
from apix.collectors.live.fetcher import TieredFetcher, _looks_like_challenge
from apix.collectors.ratelimit import RateLimiter


def _allow_all_robots(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(self: RobotsCache, key: str) -> urllib.robotparser.RobotFileParser:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(["User-agent: *", "Allow: /"])
        return rp

    monkeypatch.setattr(RobotsCache, "_fetch", fake_fetch)


def _block_all_robots(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(self: RobotsCache, key: str) -> urllib.robotparser.RobotFileParser:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(["User-agent: *", "Disallow: /"])
        return rp

    monkeypatch.setattr(RobotsCache, "_fetch", fake_fetch)


def _fake_response(status: int, text: str) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=text.encode("utf-8"),
        headers={"content-type": "text/html; charset=utf-8"},
        request=httpx.Request("GET", "https://example.com/"),
    )


@pytest.fixture
def fetcher(monkeypatch: pytest.MonkeyPatch) -> TieredFetcher:
    _allow_all_robots(monkeypatch)
    # Force collection_enabled = true so the kill switch does not fire.
    from apix.settings import EnvSettings, get_settings

    real = get_settings()
    fake_env = EnvSettings(collection_enabled=True, enable_live=True)
    fake = real.model_copy(update={"env": fake_env})
    monkeypatch.setattr("apix.collectors.ethics.get_settings", lambda: fake)
    ethics = RobotsCache(user_agent="APix/0.1 (+https://example.com)")
    rl = RateLimiter()
    rl.configure("example.com", rate_limit_rpm=6000, crawl_delay_s=0.0)
    return TieredFetcher("APix/0.1", ethics, rl)


def test_challenge_marker_detection() -> None:
    assert _looks_like_challenge("Checking your browser before accessing")
    assert _looks_like_challenge("Just a moment...")
    assert not _looks_like_challenge("<html><body>Fare: 5000</body></html>")


async def test_tier1_success_returns_immediately(
    fetcher: TieredFetcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(self: httpx.AsyncClient, url: str) -> httpx.Response:
        return _fake_response(200, "<html><body>Fare: 5000</body></html>")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    page = await fetcher.fetch("https://example.com/search")
    assert page.tier == 1
    assert "Fare: 5000" in page.html


async def test_tier2_escalation_on_403(
    fetcher: TieredFetcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    call_count = {"n": 0}

    async def fake_get(self: httpx.AsyncClient, url: str) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _fake_response(403, "Forbidden")
        return _fake_response(200, "<html>Fare: 4800</html>")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    page = await fetcher.fetch("https://example.com/search")
    assert page.tier == 2
    assert "Fare: 4800" in page.html


async def test_blocked_raises_when_both_tiers_fail(
    fetcher: TieredFetcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(self: httpx.AsyncClient, url: str) -> httpx.Response:
        return _fake_response(403, "Forbidden")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    with pytest.raises(BlockedError, match="tier 3"):
        await fetcher.fetch("https://example.com/search")


def _enable_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force APIX_COLLECTION_ENABLED=true so the kill switch does not fire."""
    from apix.settings import EnvSettings, get_settings

    real = get_settings()
    fake_env = EnvSettings(collection_enabled=True, enable_live=True)
    fake = real.model_copy(update={"env": fake_env})
    monkeypatch.setattr("apix.collectors.ethics.get_settings", lambda: fake)


async def test_robots_disallowed_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_collection(monkeypatch)
    _block_all_robots(monkeypatch)
    ethics = RobotsCache(user_agent="APix/0.1")
    rl = RateLimiter()
    rl.configure("example.com", rate_limit_rpm=6000, crawl_delay_s=0.0)
    f = TieredFetcher("APix/0.1", ethics, rl)
    with pytest.raises(RobotsDisallowedError):
        await f.fetch("https://example.com/search")


# ---------------------------------------------------------------------------
# Tier-3 (Playwright) tests. A fake session is injected so no real browser
# launches during the test run.
# ---------------------------------------------------------------------------


class _FakeSession:
    """Stand-in for PlaywrightSession. Returns canned HTML."""

    def __init__(self, html: str) -> None:
        self._html = html
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> _FakeSession:
        self.entered = True
        return self

    async def __aexit__(self, *_args: object) -> None:
        self.exited = True

    async def fetch_html(self, url: str, **_: object) -> str:
        return self._html


async def test_tier3_used_when_tier2_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_all_robots(monkeypatch)
    from apix.settings import EnvSettings, get_settings

    real = get_settings()
    fake_env = EnvSettings(collection_enabled=True, enable_live=True)
    fake = real.model_copy(update={"env": fake_env})
    monkeypatch.setattr("apix.collectors.ethics.get_settings", lambda: fake)

    async def fake_get(self: httpx.AsyncClient, url: str) -> httpx.Response:
        return _fake_response(403, "Forbidden")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    created: list[_FakeSession] = []

    def factory() -> _FakeSession:
        s = _FakeSession("<html><body>Fare: 4777</body></html>")
        created.append(s)
        return s

    ethics = RobotsCache(user_agent="APix/0.1")
    rl = RateLimiter()
    rl.configure("example.com", rate_limit_rpm=6000, crawl_delay_s=0.0)
    f = TieredFetcher("APix/0.1", ethics, rl, playwright_session_factory=factory)  # type: ignore[arg-type]

    page = await f.fetch("https://example.com/search")
    assert page.tier == 3
    assert "Fare: 4777" in page.html
    assert len(created) == 1
    assert created[0].entered is True
    assert created[0].exited is True


async def test_tier3_challenge_page_raises_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_all_robots(monkeypatch)
    from apix.settings import EnvSettings, get_settings

    real = get_settings()
    fake_env = EnvSettings(collection_enabled=True, enable_live=True)
    fake = real.model_copy(update={"env": fake_env})
    monkeypatch.setattr("apix.collectors.ethics.get_settings", lambda: fake)

    async def fake_get(self: httpx.AsyncClient, url: str) -> httpx.Response:
        return _fake_response(403, "Forbidden")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    def factory() -> _FakeSession:
        return _FakeSession("<html><title>Just a moment...</title></html>")

    ethics = RobotsCache(user_agent="APix/0.1")
    rl = RateLimiter()
    rl.configure("example.com", rate_limit_rpm=6000, crawl_delay_s=0.0)
    f = TieredFetcher("APix/0.1", ethics, rl, playwright_session_factory=factory)  # type: ignore[arg-type]

    with pytest.raises(BlockedError, match="tier 3"):
        await f.fetch("https://example.com/search")


async def test_tier3_not_configured_raises_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_all_robots(monkeypatch)
    from apix.settings import EnvSettings, get_settings

    real = get_settings()
    fake_env = EnvSettings(collection_enabled=True, enable_live=True)
    fake = real.model_copy(update={"env": fake_env})
    monkeypatch.setattr("apix.collectors.ethics.get_settings", lambda: fake)

    async def fake_get(self: httpx.AsyncClient, url: str) -> httpx.Response:
        return _fake_response(403, "Forbidden")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    ethics = RobotsCache(user_agent="APix/0.1")
    rl = RateLimiter()
    rl.configure("example.com", rate_limit_rpm=6000, crawl_delay_s=0.0)
    f = TieredFetcher("APix/0.1", ethics, rl)  # no factory

    with pytest.raises(BlockedError, match="no playwright_session_factory"):
        await f.fetch("https://example.com/search")
