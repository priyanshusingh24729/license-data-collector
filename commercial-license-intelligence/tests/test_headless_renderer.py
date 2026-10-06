"""
Unit tests for HeadlessBrowserRenderer and SPA detection.
"""

import pytest
from backend.collectors.web.headless_renderer import HeadlessBrowserRenderer, is_spa_page


def test_is_spa_page_detection():
    # Empty root div (React / Next.js)
    spa_react = '<!DOCTYPE html><html><head></head><body><div id="root"></div><script src="/bundle.js"></script></body></html>'
    assert is_spa_page(spa_react) is True

    # Empty app div (Vue / Angular)
    spa_vue = '<!DOCTYPE html><html><head></head><body><div id="app"></div><script src="/app.js"></script></body></html>'
    assert is_spa_page(spa_vue) is True

    # JavaScript required message
    spa_msg = '<html><body><noscript>You need to enable JavaScript to run this app.</noscript></body></html>'
    assert is_spa_page(spa_msg) is True

    # Traditional static HTML with content
    static_html = """
    <html>
      <body>
        <h1>Apache HTTP Server</h1>
        <p>The Apache HTTP Server Project is an effort to develop and maintain an open-source HTTP server for modern operating systems including UNIX and Windows.</p>
        <p>Licensed under the Apache License, Version 2.0.</p>
      </body>
    </html>
    """
    assert is_spa_page(static_html) is False


def test_headless_renderer_initialization():
    renderer = HeadlessBrowserRenderer(timeout_seconds=5.0)
    assert renderer.timeout_seconds == 5.0
    assert "Mozilla" in renderer.user_agent
