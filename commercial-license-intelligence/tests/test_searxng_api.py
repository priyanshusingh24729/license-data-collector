"""
Tests for SearXNG Backend API Endpoints (/api/discovery/search/status and /api/discovery/search/query).
"""

import pytest
import httpx
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.sources.discovery.search_provider import SearchResult

client = TestClient(app)


def test_search_status_online():
    """Verify /api/discovery/search/status reports online when SearXNG responds."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("backend.api.discovery.httpx.Client") as mock_client_cls:
        instance = mock_client_cls.return_value.__enter__.return_value
        instance.get.return_value = mock_resp

        res = client.get("/api/discovery/search/status")
        assert res.status_code == 200
        data = res.json()
        assert data["provider"] == "SearXNG"
        assert data["is_online"] is True
        assert "online" in data["status_message"].lower()


def test_search_status_offline():
    """Verify /api/discovery/search/status reports offline when connection refused."""
    with patch("backend.api.discovery.httpx.Client") as mock_client_cls:
        instance = mock_client_cls.return_value.__enter__.return_value
        instance.get.side_effect = httpx.ConnectError("Connection refused")

        res = client.get("/api/discovery/search/status")
        assert res.status_code == 200
        data = res.json()
        assert data["is_online"] is False
        assert data["fallback_available"] is True
        assert "offline" in data["status_message"].lower()


def test_search_query_endpoint():
    """Verify /api/discovery/search/query executes search and returns results."""
    mock_results = [
        SearchResult(
            url="https://www.docker.com/legal/docker-software-end-user-license-agreement/",
            title="Docker Desktop Terms of Service",
            snippet="Docker Desktop commercial license conditions.",
            engine="google",
            rank=1,
        )
    ]

    mock_provider = MagicMock()
    mock_provider.search.return_value = mock_results

    with patch("backend.api.discovery.get_search_provider", return_value=mock_provider):
        payload = {
            "query": "Docker Desktop licensing",
            "num_results": 3,
            "categories": "general,it",
        }
        res = client.post("/api/discovery/search/query", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["query"] == "Docker Desktop licensing"
        assert data["total_results"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["url"] == "https://www.docker.com/legal/docker-software-end-user-license-agreement/"
        assert data["results"][0]["engine"] == "google"


def test_search_query_endpoint_fallback_chain():
    """Verify /api/discovery/search/query routes through ChainSearchProvider fallback."""
    mock_fallback_results = [
        SearchResult(
            url="https://www.yacy.net/legal/license",
            title="YaCy Licensing",
            snippet="YaCy decentralized search engine terms.",
            engine="yacy",
            rank=1,
        )
    ]
    mock_provider = MagicMock()
    mock_provider.search.return_value = mock_fallback_results

    with patch("backend.api.discovery.get_search_provider", return_value=mock_provider):
        payload = {
            "query": "YaCy decentralized search licensing",
            "num_results": 1,
        }
        res = client.post("/api/discovery/search/query", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["total_results"] == 1
        assert data["results"][0]["engine"] == "yacy"
        assert "yacy" in data["provider_used"].lower()
