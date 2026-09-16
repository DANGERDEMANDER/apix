"""Playwright browser session, one per collection run.

Stock Playwright + Firefox. No anti-detection tooling, no stealth patches,
no CAPTCHA solving. When a source serves a challenge page, the fetch raises
BlockedError and the caller falls back to replay mode.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    ViewportSize,
    async_playwright,
)

_VIEWPORT: ViewportSize = {"width": 1366, "height": 900}


class PlaywrightSession:
    """One browser process per session. Reuses a single context across pages."""

    def __init__(
        self,
        user_agent: str,
        *,
        headless: bool = True,
        navigation_timeout_ms: int = 30_000,
    ) -> None:
        self._user_agent = user_agent
        self._headless = headless
        self._timeout_ms = navigation_timeout_ms
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> Self:
        pw = await async_playwright().start()
        browser = await pw.firefox.launch(headless=self._headless)
        context = await browser.new_context(
            user_agent=self._user_agent,
            viewport=_VIEWPORT,
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            java_script_enabled=True,
        )
        context.set_default_navigation_timeout(self._timeout_ms)
        self._pw = pw
        self._browser = browser
        self._context = context
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._pw is not None:
            await self._pw.stop()
            self._pw = None

    async def fetch_html(
        self,
        url: str,
        *,
        wait_for_selector: str | None = None,
    ) -> str:
        """Navigate to url and return the rendered HTML."""
        ctx = self._context
        if ctx is None:
            raise RuntimeError(
                "session not started; use `async with PlaywrightSession(...)`"
            )
        page: Page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            if wait_for_selector is not None:
                await page.wait_for_selector(
                    wait_for_selector, timeout=self._timeout_ms
                )
            return await page.content()
        finally:
            await page.close()
