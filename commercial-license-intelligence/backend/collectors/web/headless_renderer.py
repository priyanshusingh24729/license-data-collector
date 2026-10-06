"""
Headless Browser Renderer for Client-Side JavaScript SPAs.
Provides dynamic page rendering fallback using Playwright headless Chromium
for Single Page Applications (e.g., vendor pricing calculators, modern docs).
"""

import re
import logging
from typing import Optional

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)

# Heuristics for detecting Single Page Applications / empty shells
SPA_CONTAINER_PATTERNS = [
    re.compile(r'<div\s+id=["\'](?:root|app|__next|__nuxt|app-root)["\']\s*>\s*</div>', re.IGNORECASE),
    re.compile(r'<div\s+id=["\']root["\']\s*>\s*<noscript>.*?</noscript>\s*</div>', re.IGNORECASE | re.DOTALL),
    re.compile(r'You need to enable JavaScript to run this app', re.IGNORECASE),
    re.compile(r'JavaScript is required to view this site', re.IGNORECASE),
    re.compile(r'please enable javascript in your browser', re.IGNORECASE),
]


def is_spa_page(html: str) -> bool:
    """
    Determines whether an HTML document appears to be an empty or unrendered
    JavaScript Single Page Application (SPA) shell.
    """
    if not html:
        return False

    # Check for empty root container patterns
    for pattern in SPA_CONTAINER_PATTERNS:
        if pattern.search(html):
            return True

    # Check for minimal body with heavy scripts (< 400 non-tag chars with > 2 script tags)
    text_content = re.sub(r'<[^>]+>', ' ', html)
    text_length = len(" ".join(text_content.split()))
    script_count = len(re.findall(r'<script', html, re.IGNORECASE))

    if text_length < 350 and script_count >= 2:
        return True

    return False


class HeadlessBrowserRenderer:
    """
    Headless Chromium renderer backed by Playwright.
    Executes client-side JavaScript to render modern SPAs into fully hydrated HTML.
    """

    def __init__(self, timeout_seconds: Optional[float] = None):
        settings = get_settings()
        self.timeout_seconds = timeout_seconds or getattr(settings, "HEADLESS_BROWSER_TIMEOUT_SECONDS", 15.0)
        self.user_agent = getattr(
            settings,
            "WEB_COLLECTOR_USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )

    def render(self, url: str, wait_for_selector: Optional[str] = None) -> Optional[str]:
        """
        Navigates to the specified URL using headless Chromium, waits for DOM and dynamic
        content rendering, and returns the rendered HTML.
        
        Falls back safely and returns None if browser execution encounters an error.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("Playwright is not installed. Headless browser fallback unavailable.")
            return None

        timeout_ms = int(self.timeout_seconds * 1000)
        logger.info(f"[HeadlessRenderer] Rendering SPA URL: {url} (timeout: {self.timeout_seconds}s)")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ]
                )
                try:
                    context = browser.new_context(
                        user_agent=self.user_agent,
                        viewport={"width": 1280, "height": 800},
                        bypass_csp=True,
                    )
                    page = context.new_page()

                    # Navigate to target page
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

                    # Wait for specific selector if requested
                    if wait_for_selector:
                        try:
                            page.wait_for_selector(wait_for_selector, timeout=min(timeout_ms, 5000))
                        except Exception:
                            pass

                    # Wait a brief moment for dynamic client-side hydration
                    try:
                        page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 4000))
                    except Exception:
                        pass

                    rendered_html = page.content()
                    logger.info(f"[HeadlessRenderer] Successfully rendered dynamic HTML for {url} ({len(rendered_html)} bytes)")
                    return rendered_html
                finally:
                    browser.close()
        except Exception as exc:
            logger.warning(f"[HeadlessRenderer] Failed to render {url} via headless browser: {exc}")
            return None
