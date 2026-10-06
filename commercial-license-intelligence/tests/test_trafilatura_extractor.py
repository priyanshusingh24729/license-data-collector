"""
Unit tests for TrafilaturaExtractor in backend/collectors/web/trafilatura_extractor.py.
Verifies extraction of noise-free Markdown with table formatting intact,
stripping navigation bars, cookie consent banners, and footers.
"""

import pytest
from backend.collectors.web.trafilatura_extractor import TrafilaturaExtractor, TrafilaturaExtractionResult

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Docker Desktop Commercial License Terms</title>
</head>
<body>
    <header>
        <nav>
            <a href="/">Home</a>
            <a href="/products">Products</a>
            <a href="/contact">Contact</a>
        </nav>
    </header>
    <div id="cookie-banner" class="cookie-consent">
        <p>We use cookies to improve your experience. Accept all cookies.</p>
    </div>
    <main>
        <h1>Docker Desktop Commercial Terms</h1>
        <p>Docker Desktop is free for small businesses (fewer than 250 employees and less than $10 million in annual revenue), personal use, education, and non-commercial open source projects.</p>
        <p>Commercial use in larger enterprises requires a paid subscription per user per month.</p>
        <table>
            <thead>
                <tr>
                    <th>Tier</th>
                    <th>Price</th>
                    <th>License Model</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Personal</td>
                    <td>Free</td>
                    <td>Non-Commercial</td>
                </tr>
                <tr>
                    <td>Pro</td>
                    <td>$5 / user / mo</td>
                    <td>Commercial Named User</td>
                </tr>
                <tr>
                    <td>Business</td>
                    <td>$24 / user / mo</td>
                    <td>Enterprise Commercial</td>
                </tr>
            </tbody>
        </table>
    </main>
    <footer>
        <p>&copy; 2026 Docker Inc. All rights reserved. Privacy Policy.</p>
    </footer>
</body>
</html>
"""


def test_trafilatura_extracts_clean_markdown_and_tables():
    result = TrafilaturaExtractor.extract(SAMPLE_HTML, base_url="https://www.docker.com/legal")
    assert result.is_success is True
    assert "Docker Desktop" in result.markdown_content
    assert "Commercial use in larger enterprises requires a paid subscription" in result.markdown_content
    # Navigation and cookie banners should be stripped
    assert "Accept all cookies" not in result.markdown_content
    # Table should be preserved
    assert "Personal" in result.markdown_content
    assert "Pro" in result.markdown_content
    assert result.tables_found >= 1


def test_trafilatura_empty_html_handling():
    result = TrafilaturaExtractor.extract("")
    assert result.is_success is False
    assert result.markdown_content == ""
    assert result.char_count == 0
