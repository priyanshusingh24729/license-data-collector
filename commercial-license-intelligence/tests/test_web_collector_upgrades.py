"""
Tests for WebCollector Upgrades:
- robots.txt & Sitemap Discovery
- llms.txt First-Hop Discovery
- PDF Whitepaper Harvesting & Keyword Filtering
- Targeted Search & Dorking Queries
"""

import pytest
from unittest.mock import patch, MagicMock
from backend.collectors.web.sitemap_collector import SitemapCollector
from backend.collectors.web.llms_txt_collector import LlmsTxtCollector
from backend.collectors.web.pdf_harvester import PdfHarvester
from backend.collectors.web.web_collector import WebCollector
from backend.sources.discovery.query_builder import QueryBuilder


SAMPLE_ROBOTS_TXT = """User-agent: *
Disallow: /admin/
Disallow: /private/
Sitemap: https://example.com/sitemap.xml
"""

SAMPLE_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/</loc>
  </url>
  <url>
    <loc>https://example.com/pricing/</loc>
  </url>
  <url>
    <loc>https://example.com/legal/product-terms/</loc>
  </url>
  <url>
    <loc>https://example.com/blog/how-to-code/</loc>
  </url>
  <url>
    <loc>https://example.com/licensing/guide/</loc>
  </url>
</urlset>
"""

SAMPLE_LLMS_TXT = """# Example Software Documentation for LLMs

> Authoritative product terms and licensing information.

## Licensing and Governance
- [Commercial Product Terms](https://example.com/legal/commercial-terms): Complete enterprise licensing model and CAL rules.
- [EULA and End User License](https://example.com/eula.html): Standard user licensing agreement.
- [Technical API Docs](https://example.com/api): REST API documentation.
"""

SAMPLE_HTML_PAGE = """
<html>
<head><title>Enterprise Server Pricing</title></head>
<body>
  <h1>Server Deployment and Licensing</h1>
  <p>Read our documentation before ordering.</p>
  <ul>
    <li><a href="/docs/Licensing-Guide-2025.pdf">Download Licensing Guide (PDF)</a></li>
    <li><a href="https://cdn.example.com/eula-standard.pdf">Standard EULA</a></li>
    <li><a href="/marketing/brochure.pdf">Product Marketing Brochure</a></li>
    <li><a href="/press/annual-report-2024.pdf">Annual Report</a></li>
  </ul>
</body>
</html>
"""


def test_sitemap_collector_parsing():
    """Test extracting sitemap location from robots.txt and filtering licensing URLs from XML."""
    collector = SitemapCollector()

    with patch("httpx.Client.get") as mock_get:
        # Mock robots.txt response
        mock_robots_resp = MagicMock()
        mock_robots_resp.status_code = 200
        mock_robots_resp.text = SAMPLE_ROBOTS_TXT

        # Mock sitemap.xml response
        mock_sitemap_resp = MagicMock()
        mock_sitemap_resp.status_code = 200
        mock_sitemap_resp.content = SAMPLE_SITEMAP_XML.encode("utf-8")

        mock_get.side_effect = [mock_robots_resp, mock_sitemap_resp]

        urls = collector.discover_licensing_sitemap_urls("https://example.com")

        # Must discover licensing, pricing, and product-terms URLs
        assert any("pricing" in u for u in urls)
        assert any("product-terms" in u for u in urls)
        assert any("licensing/guide" in u for u in urls)
        # Must filter out irrelevant blog links
        assert not any("blog" in u for u in urls)


def test_llms_txt_collector_parsing():
    """Test probing llms.txt and extracting licensing markdown links."""
    collector = LlmsTxtCollector()

    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "text/plain"}
        mock_resp.text = SAMPLE_LLMS_TXT
        mock_get.return_value = mock_resp

        result = collector.discover("https://example.com")
        assert result.is_available is True
        assert result.url == "https://example.com/llms.txt"
        assert len(result.extracted_links) >= 2
        # Verify extracted links contain licensing URLs
        assert any("commercial-terms" in link[0] for link in result.extracted_links)
        assert any("eula" in link[0] for link in result.extracted_links)


def test_pdf_harvester_filtering():
    """Test PDF Harvester detects licensing PDFs and excludes brochures/reports."""
    harvester = PdfHarvester()
    found = harvester.find_licensing_pdf_links(SAMPLE_HTML_PAGE, base_url="https://example.com")

    # Should find Licensing-Guide-2025.pdf and eula-standard.pdf
    found_urls = [u[0] for u in found]
    assert any("Licensing-Guide-2025.pdf" in u for u in found_urls)
    assert any("eula-standard.pdf" in u for u in found_urls)

    # Should exclude marketing brochure and annual report
    assert not any("brochure.pdf" in u for u in found_urls)
    assert not any("annual-report" in u for u in found_urls)


def test_query_builder_targeted_dorking():
    """Test QueryBuilder generates advanced vendor dorking queries."""
    builder = QueryBuilder()
    queries = builder.build_queries(
        vendor="Oracle",
        product="Database",
        official_domain="oracle.com",
        max_queries=15
    )

    assert any('site:oracle.com Database ("licensing guide" OR "licensing model" OR "terms of service")' in q for q in queries)
    assert any('site:oracle.com Database ("per core" OR "per seat" OR "named user" OR "perpetual")' in q for q in queries)
    assert any('site:oracle.com filetype:pdf ("licensing brief" OR "product terms" OR "EULA")' in q for q in queries)


def test_web_collector_integration():
    """Test WebCollector discovers PDFs during page ingestion."""
    mock_http_client = MagicMock()
    mock_fetch_result = MagicMock()
    mock_fetch_result.status.value = "COLLECTED"
    from backend.models.enums import CollectionStatus
    mock_fetch_result.status = CollectionStatus.COLLECTED
    mock_fetch_result.final_url = "https://example.com/products/server"
    mock_fetch_result.text_content = SAMPLE_HTML_PAGE
    mock_fetch_result.content_bytes = SAMPLE_HTML_PAGE.encode("utf-8")
    mock_fetch_result.metadata = None
    mock_fetch_result.error_message = None
    mock_http_client.fetch.return_value = mock_fetch_result

    collector = WebCollector(http_client=mock_http_client)
    res = collector.collect("https://example.com/products/server", vendor="ExampleCorp")

    assert res.status == CollectionStatus.COLLECTED
    assert len(res.harvested_pdfs) >= 2
    assert any("Licensing-Guide-2025.pdf" in p for p in res.harvested_pdfs)
