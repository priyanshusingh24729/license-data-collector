"""
Unit & Integration Tests for SearxngSearchProvider and Search Provider Factory.
"""

import pytest
import httpx
from unittest.mock import MagicMock, patch

from backend.config.settings import Settings
from backend.sources.discovery.search_provider import (
    SearxngSearchProvider,
    ChainSearchProvider,
    DevSearchProvider,
    NullSearchProvider,
    SearchResult,
    get_search_provider,
)


def test_searxng_provider_availability():
    """Verify availability status based on presence of base_url."""
    p_valid = SearxngSearchProvider(base_url="http://127.0.0.1:8080")
    assert p_valid.is_available() is True

    p_empty = SearxngSearchProvider(base_url="")
    assert p_empty.is_available() is False

    with patch("backend.sources.discovery.search_provider.get_settings") as mock_settings:
        mock_settings.return_value = Settings(SEARXNG_BASE_URL="")
        p_none = SearxngSearchProvider(base_url=None)
        assert p_none.is_available() is False


def test_searxng_search_success_parsing():
    """Verify successful parsing and normalization of SearXNG JSON search response."""
    mock_searxng_response = {
        "query": "Docker Desktop licensing terms",
        "number_of_results": 2,
        "results": [
            {
                "title": "Docker Desktop Terms of Service",
                "url": "https://www.docker.com/legal/docker-software-end-user-license-agreement/",
                "content": "Docker Desktop requires a paid subscription (Pro, Team, Business) for companies with >250 employees or >$10M revenue.",
                "engine": "google",
                "score": 0.98,
            },
            {
                "title": "Docker FAQ",
                "url": "https://www.docker.com/pricing/faq/",
                "content": "Frequently asked questions regarding Docker Desktop commercial licensing.",
                "engine": "duckduckgo",
                "score": 0.91,
            },
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_searxng_response
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
        provider = SearxngSearchProvider(base_url="http://127.0.0.1:8080")
        results = provider.search("Docker Desktop licensing terms", num_results=5)

        assert len(results) == 2
        assert isinstance(results[0], SearchResult)
        assert results[0].url == "https://www.docker.com/legal/docker-software-end-user-license-agreement/"
        assert results[0].title == "Docker Desktop Terms of Service"
        assert "Docker Desktop requires a paid subscription" in results[0].snippet
        assert results[0].engine == "google"
        assert results[0].rank == 1

        assert results[1].rank == 2
        assert results[1].url == "https://www.docker.com/pricing/faq/"
        assert results[1].engine == "duckduckgo"


def test_searxng_search_parameters():
    """Verify search passes format=json, categories, engines, and query to GET request."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": []}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
        provider = SearxngSearchProvider(
            base_url="http://127.0.0.1:8080",
            categories="general,it",
            engines="google,bing,duckduckgo",
        )
        provider.search("PostgreSQL commercial terms", num_results=10)

        mock_get.assert_called_once()
        url = mock_get.call_args[0][0]
        params = mock_get.call_args[1].get("params", {})

        assert url == "http://127.0.0.1:8080/search"
        assert params["q"] == "PostgreSQL commercial terms"
        assert params["format"] == "json"
        assert params["categories"] == "general,it"
        assert params["engines"] == "google,bing,duckduckgo"


def test_searxng_search_domain_restriction():
    """Verify search_official_domain uses site: syntax in SearXNG query."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": []}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
        provider = SearxngSearchProvider(base_url="http://127.0.0.1:8080")
        provider.search_official_domain("commercial terms", domain="https://docker.com/legal", num_results=5)

        mock_get.assert_called_once()
        params = mock_get.call_args[1].get("params", {})
        assert params["q"] == "site:docker.com commercial terms"


def test_searxng_search_error_fallback_to_dev_provider():
    """Verify that when SearXNG is unavailable, provider falls back to DevSearchProvider."""
    fallback_mock = MagicMock(spec=DevSearchProvider)
    fallback_mock.search.return_value = [
        SearchResult(
            url="https://www.adobe.com/legal/licenses-terms.html",
            title="Adobe Product Specific Licensing Terms",
            snippet="Official enterprise licensing terms.",
            engine="dev_search_provider",
            rank=1,
        )
    ]

    with patch("httpx.Client.get", side_effect=httpx.ConnectError("Connection to SearXNG refused")):
        provider = SearxngSearchProvider(base_url="http://127.0.0.1:8080", fallback_provider=fallback_mock)
        results = provider.search("Adobe Acrobat licensing terms", num_results=5)

        assert len(results) == 1
        assert results[0].url == "https://www.adobe.com/legal/licenses-terms.html"
        fallback_mock.search.assert_called_once()


def test_get_search_provider_factory_resolution():
    """Verify factory returns resilient search provider (ChainSearchProvider or SearxngSearchProvider) when SEARCH_PROVIDER is set to SearXNG."""
    with patch("backend.sources.discovery.search_provider.get_settings") as mock_settings:
        mock_settings.return_value = Settings(
            SEARCH_PROVIDER="SearXNG",
            SEARXNG_BASE_URL="http://127.0.0.1:8080",
            ENABLE_DEV_SEARCH_FALLBACK=True,
        )
        provider = get_search_provider()
        assert isinstance(provider, (SearxngSearchProvider, ChainSearchProvider))
        assert provider.is_available() is True
