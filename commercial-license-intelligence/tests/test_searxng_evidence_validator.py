"""
Unit tests for SearxngEvidenceValidator in backend/validation/searxng_evidence_validator.py.
"""

import pytest
from unittest.mock import MagicMock, patch
from backend.validation.searxng_evidence_validator import SearxngEvidenceValidator, SearxngValidationEvidence
from backend.sources.discovery.search_provider import SearchResult
from backend.collectors.web.collection_result import WebCollectionResult, TableData


def test_validate_application_commercial():
    mock_search_results = [
        SearchResult(
            url="https://www.docker.com/legal/docker-software-end-user-license-agreement/",
            title="Docker Desktop Terms of Service",
            snippet="Docker Desktop is free for small businesses. Commercial use requires a paid subscription.",
            engine="google",
            rank=1,
        )
    ]

    mock_collection = WebCollectionResult(
        requested_url="https://www.docker.com/legal/docker-software-end-user-license-agreement/",
        final_url="https://www.docker.com/legal/docker-software-end-user-license-agreement/",
        vendor="Docker Inc.",
        status="COLLECTED",
        title="Docker Software End User License Agreement",
        clean_text="Commercial use requires a paid subscription per user per month. Small business free tier available.",
        markdown_content="# Docker Terms\nCommercial use requires a paid subscription.\n| Plan | Price |\n|---|---|\n| Pro | $5 |",
        tables=[TableData(headers=["Plan", "Price"], rows=[["Pro", "$5"]], markdown_repr="| Plan | Price |\n|---|---|\n| Pro | $5 |")],
    )

    with patch("backend.validation.searxng_evidence_validator.get_search_provider") as mock_get_provider, \
         patch("backend.collectors.web.web_collector.WebCollector.collect", return_value=mock_collection):

        mock_provider = MagicMock()
        mock_provider.search.return_value = mock_search_results
        mock_get_provider.return_value = mock_provider

        ev = SearxngEvidenceValidator.validate_application(
            app_name="Docker Desktop",
            vendor="Docker Inc.",
            version="4.87.0",
            scrape_page=True,
        )

        assert ev.application == "Docker Desktop"
        assert ev.classification in ("COMMERCIAL", "FREE_AND_PAID")
        assert ev.evidence_status == "VERIFIED"
        assert ev.evidence_url == "https://www.docker.com/legal/docker-software-end-user-license-agreement/"
        assert ev.confidence == "VERY_HIGH"
        assert len(ev.scraped_tables) >= 1


def test_validate_and_enrich_hybrid_record():
    mock_search_results = [
        SearchResult(
            url="https://www.autodesk.com/company/terms-of-use/en/general-terms",
            title="Autodesk General Terms of Use",
            snippet="Master software licensing agreement and commercial conditions for Autodesk desktop and cloud subscriptions.",
            engine="bing",
            rank=1,
        )
    ]

    mock_collection = WebCollectionResult(
        requested_url="https://www.autodesk.com/company/terms-of-use/en/general-terms",
        final_url="https://www.autodesk.com/company/terms-of-use/en/general-terms",
        vendor="Autodesk",
        status="COLLECTED",
        clean_text="Autodesk commercial named user subscription licensing rules.",
    )

    with patch("backend.validation.searxng_evidence_validator.get_search_provider") as mock_get_provider, \
         patch("backend.collectors.web.web_collector.WebCollector.collect", return_value=mock_collection):

        mock_provider = MagicMock()
        mock_provider.search.return_value = mock_search_results
        mock_get_provider.return_value = mock_provider

        raw_record = {
            "application": "AutoCAD",
            "vendor": "Autodesk",
            "version": "2026",
            "classification": "UNKNOWN",
            "availability": "UNKNOWN",
            "license_required": "UNKNOWN",
            "license_model": "UNKNOWN",
            "evidence_status": "MISSING",
        }

        enriched = SearxngEvidenceValidator.validate_and_enrich(
            h_rec=raw_record,
            raw_name="AutoCAD",
            raw_vendor="Autodesk",
            raw_version="2026",
        )

        assert enriched["classification"] == "COMMERCIAL"
        assert enriched["license_required"] == "YES"
        assert enriched["evidence_status"] == "VERIFIED"
        assert enriched["source_url"] == "https://www.autodesk.com/company/terms-of-use/en/general-terms"
        assert enriched["evidence_url"] == "https://www.autodesk.com/company/terms-of-use/en/general-terms"
