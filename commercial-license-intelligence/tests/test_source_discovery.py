"""
Test suite for Step 3: Automatic Official License Source Discovery.
Covers query building, domain validation, search provider fallback, source ranking,
deduplication, run tracking, failure handling, and manual source protection.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.database.connection import Base, get_db
from backend.main import app
from backend.models.enums import (
    SourceType,
    AuthorityLevel,
    ScopeType,
    SourceOrigin,
    DomainValidationStatus,
    RelevanceTier,
    DiscoveryRunStatus,
)
from backend.models.source import LicenseSource
from backend.models.discovery import DiscoveryRun
from backend.schemas.discovery import DiscoveryTargetRequest
from backend.sources.discovery.query_builder import QueryBuilder
from backend.sources.discovery.domain_validator import DomainValidator
from backend.sources.discovery.search_provider import (
    SearchProvider,
    SearchResult,
    DevSearchProvider,
    NullSearchProvider,
)
from backend.sources.discovery.source_ranker import SourceRanker
from backend.sources.discovery.discovery_engine import SourceDiscoveryEngine

# Test database setup (in-memory SQLite with StaticPool)
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_db():
    """Creates a fresh test database with schema initialized."""
    test_engine = create_engine(
        SQLALCHEMY_TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(test_db):
    """Provides a FastAPI test client using the shared test database session."""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# -------------------------------------------------------------
# 1. Query Builder Tests
# -------------------------------------------------------------

def test_query_generation():
    """Test 1: Verify targeted discovery queries are generated for target parameters."""
    builder = QueryBuilder()
    queries = builder.build_queries(
        vendor="Adobe",
        product="Acrobat",
        edition="Pro",
        version="2025",
        os="Windows",
        official_domain="adobe.com",
        max_queries=10
    )
    assert len(queries) > 0
    assert len(queries) <= 10
    # Check that core terms and domain restrictions are generated
    assert any("Adobe Acrobat Pro 2025 product terms" in q for q in queries)
    assert any("site:adobe.com" in q for q in queries)


def test_generic_vendor_support():
    """Test 2: Verify query builder works generically for any vendor without hardcoding."""
    builder = QueryBuilder()
    queries = builder.build_queries(
        vendor="JetBrains",
        product="IntelliJ IDEA",
        edition="Ultimate",
        version="2024.1",
        official_domain="jetbrains.com"
    )
    assert any("JetBrains IntelliJ IDEA Ultimate 2024.1" in q for q in queries)
    assert any("site:jetbrains.com" in q for q in queries)


# -------------------------------------------------------------
# 2. Domain Validation Tests
# -------------------------------------------------------------

def test_official_domain_validation():
    """Test 3: Verify authentic official root domains and subdomains are validated."""
    validator = DomainValidator()

    # Exact root
    assert validator.validate_domain("https://adobe.com/legal/terms.html", "Adobe") == DomainValidationStatus.OFFICIAL
    assert validator.validate_domain("https://www.adobe.com/legal", "Adobe") == DomainValidationStatus.OFFICIAL

    # Known subdomains
    assert validator.validate_domain("https://helpx.adobe.com/acrobat/kb.html", "Adobe") == DomainValidationStatus.OFFICIAL
    assert validator.validate_domain("https://learn.microsoft.com/licensing", "Microsoft") == DomainValidationStatus.OFFICIAL


def test_non_official_domain_rejection():
    """Test 4: Verify lookalike, spoofed, or third-party domains are rejected as NOT_OFFICIAL."""
    validator = DomainValidator()

    # Lookalike domains containing vendor name
    assert validator.validate_domain("https://adobe-licensing-portal.com", "Adobe") == DomainValidationStatus.NOT_OFFICIAL
    assert validator.validate_domain("https://free-adobe-acrobat.net/terms", "Adobe") == DomainValidationStatus.NOT_OFFICIAL
    assert validator.validate_domain("https://adobe.com.fakeportal.org", "Adobe") == DomainValidationStatus.NOT_OFFICIAL
    assert validator.validate_domain("https://random-forum.com/thread/123", "Adobe") == DomainValidationStatus.NOT_OFFICIAL


# -------------------------------------------------------------
# 3. Source Ranking & Signal Relevance Tests
# -------------------------------------------------------------

def test_source_ranking():
    """Test 5: Verify source ranker computes scores, authority, and document classifications."""
    ranker = SourceRanker()
    (
        score,
        tier,
        authority,
        src_type,
        reasons,
        m_v,
        m_p,
        m_e,
        m_ver
    ) = ranker.rank_candidate(
        url="https://www.adobe.com/legal/licenses-terms.html",
        title="Adobe Product Specific Licensing Terms",
        snippet="Official enterprise licensing terms and virtualization rules for Adobe Acrobat.",
        vendor="Adobe",
        product="Acrobat",
        edition="Pro",
        version="2025",
        domain_status=DomainValidationStatus.OFFICIAL
    )
    assert score >= 80
    assert tier in [RelevanceTier.VERY_HIGH, RelevanceTier.HIGH]
    assert authority == AuthorityLevel.OFFICIAL_VENDOR
    assert src_type == SourceType.OFFICIAL_TERMS
    assert len(reasons) > 0


def test_exact_product_relevance():
    """Test 6: Verify matching product receives higher score than unrelated vendor product."""
    ranker = SourceRanker()
    score_acrobat, _, _, _, _, _, _, _, _ = ranker.rank_candidate(
        url="https://helpx.adobe.com/acrobat/kb/licensing.html",
        title="Adobe Acrobat Licensing Guide",
        snippet="Acrobat licensing information.",
        vendor="Adobe",
        product="Acrobat",
        edition=None,
        version=None,
        domain_status=DomainValidationStatus.OFFICIAL
    )

    score_photoshop, _, _, _, _, _, _, _, _ = ranker.rank_candidate(
        url="https://helpx.adobe.com/photoshop/kb/licensing.html",
        title="Adobe Photoshop Licensing Guide",
        snippet="Photoshop licensing information.",
        vendor="Adobe",
        product="Acrobat",
        edition=None,
        version=None,
        domain_status=DomainValidationStatus.OFFICIAL
    )

    assert score_acrobat > score_photoshop


def test_edition_and_version_relevance():
    """Test 7 & 8: Verify edition and version matching signals increase candidate score."""
    ranker = SourceRanker()
    score_with_version, _, _, _, _, _, _, m_edition, m_version = ranker.rank_candidate(
        url="https://helpx.adobe.com/acrobat/pro-2025-licensing.html",
        title="Adobe Acrobat Pro 2025 Deployment Licensing Guide",
        snippet="Acrobat Pro 2025 named user licenses.",
        vendor="Adobe",
        product="Acrobat",
        edition="Pro",
        version="2025",
        domain_status=DomainValidationStatus.OFFICIAL
    )
    assert m_edition is True
    assert m_version is True
    assert score_with_version >= 90


# -------------------------------------------------------------
# 4. Deduplication & Run Tracking Tests
# -------------------------------------------------------------

def test_duplicate_source_prevention_across_queries(test_db):
    """Test 9: Verify multiple queries returning the same URL result in single deduplicated record."""
    class CustomDuplicateProvider(SearchProvider):
        def is_available(self) -> bool:
            return True
        def search(self, query: str, num_results: int = 10) -> list:
            # Always return identical URL across every query
            return [
                SearchResult(
                    url="https://www.adobe.com/legal/licenses-terms.html",
                    title="Adobe Product Terms",
                    snippet="Official terms.",
                    engine="mock"
                )
            ]

    engine = SourceDiscoveryEngine(search_provider=CustomDuplicateProvider())
    req = DiscoveryTargetRequest(vendor="Adobe", product="Acrobat", max_queries=5)
    response = engine.run_discovery(test_db, req)

    assert response.sources_accepted == 1
    # Check database count for this vendor and URL
    count = test_db.query(LicenseSource).filter(
        LicenseSource.normalized_url == "https://www.adobe.com/legal/licenses-terms.html"
    ).count()
    assert count == 1


def test_discovery_run_tracking(test_db, client):
    """Test 10: Verify discovery run is tracked and logged in discovery_runs table."""
    req_payload = {
        "vendor": "Adobe",
        "product": "Acrobat",
        "edition": "Pro",
        "version": "2025",
        "os": "Windows",
        "max_queries": 5
    }
    res = client.post("/api/discovery/sources", json=req_payload)
    assert res.status_code == 200
    data = res.json()
    run_id = data["run_id"]
    assert run_id is not None

    # Check runs endpoint
    runs_res = client.get(f"/api/discovery/runs/{run_id}")
    assert runs_res.status_code == 200
    run_data = runs_res.json()
    assert run_data["vendor_name"] == "Adobe"
    assert run_data["product_name"] == "Acrobat"
    assert run_data["sources_found"] > 0
    assert run_data["status"] in ["COMPLETED", "REVIEW_REQUIRED"]


# -------------------------------------------------------------
# 5. Search Failure & Edge Case Handling Tests
# -------------------------------------------------------------

def test_missing_search_configuration_returns_status(test_db):
    """Test 11: When no search provider is available, return NO_SEARCH_PROVIDER status gracefully."""
    engine = SourceDiscoveryEngine(search_provider=NullSearchProvider())
    req = DiscoveryTargetRequest(vendor="Adobe", product="Acrobat")
    response = engine.run_discovery(test_db, req)

    assert response.status == DiscoveryRunStatus.NO_SEARCH_PROVIDER
    assert response.sources_accepted == 0
    assert "No search provider configured" in (response.message or "")


def test_search_failure_handling(test_db):
    """Test 12: When search provider raises an exception, handle cleanly without crash."""
    class FailingSearchProvider(SearchProvider):
        def is_available(self) -> bool:
            return True
        def search(self, query: str, num_results: int = 10) -> list:
            raise RuntimeError("External network connection timeout.")

    engine = SourceDiscoveryEngine(search_provider=FailingSearchProvider())
    req = DiscoveryTargetRequest(vendor="Adobe", product="Acrobat", max_queries=3)
    response = engine.run_discovery(test_db, req)

    assert response.status == DiscoveryRunStatus.NO_OFFICIAL_SOURCE_FOUND
    assert response.sources_accepted == 0


def test_no_official_source_scenario(test_db):
    """Test 13: When search results contain only non-official spam domains, reject them."""
    class SpamSearchProvider(SearchProvider):
        def is_available(self) -> bool:
            return True
        def search(self, query: str, num_results: int = 10) -> list:
            return [
                SearchResult(
                    url="https://warez-crack-download.net/adobe-license",
                    title="Free Adobe Acrobat Cracks",
                    snippet="Download free keygen",
                    engine="mock"
                )
            ]

    engine = SourceDiscoveryEngine(search_provider=SpamSearchProvider())
    req = DiscoveryTargetRequest(vendor="Adobe", product="Acrobat", max_queries=2)
    response = engine.run_discovery(test_db, req)

    assert response.status == DiscoveryRunStatus.NO_OFFICIAL_SOURCE_FOUND
    assert response.sources_accepted == 0
    assert response.sources_rejected == 1


# -------------------------------------------------------------
# 6. Existing Source Update & Manual Protection Tests
# -------------------------------------------------------------

def test_existing_source_update(test_db):
    """Test 14: Existing automatic source has its relevance score & timestamp updated."""
    # Pre-insert existing automatic source
    src = LicenseSource(
        vendor_name="Adobe",
        product_name="Acrobat",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Adobe Acrobat",
        source_name="Old Adobe Terms Title",
        source_type=SourceType.OFFICIAL_TERMS,
        authority_level=AuthorityLevel.OFFICIAL_VENDOR,
        source_url="https://www.adobe.com/legal/licenses-terms.html",
        normalized_url="https://www.adobe.com/legal/licenses-terms.html",
        is_active=True,
        source_origin=SourceOrigin.AUTOMATIC,
        relevance_score=50,
    )
    test_db.add(src)
    test_db.commit()

    engine = SourceDiscoveryEngine(search_provider=DevSearchProvider())
    req = DiscoveryTargetRequest(vendor="Adobe", product="Acrobat", max_queries=3)
    response = engine.run_discovery(test_db, req)

    # Check that it updated the existing source without creating a second record
    test_db.refresh(src)
    count = test_db.query(LicenseSource).filter(
        LicenseSource.normalized_url == "https://www.adobe.com/legal/licenses-terms.html"
    ).count()
    assert count == 1
    assert src.last_checked_at is not None


def test_manual_source_protection(test_db):
    """Test 15: Manually verified sources must NOT have their core attributes overwritten by discovery."""
    manual_src = LicenseSource(
        vendor_name="Adobe",
        product_name="Acrobat",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Adobe Acrobat",
        source_name="Curated Official Adobe Product Terms",
        description="Manually verified enterprise terms document by legal auditor.",
        source_type=SourceType.OFFICIAL_TERMS,
        authority_level=AuthorityLevel.OFFICIAL_VENDOR,
        source_url="https://www.adobe.com/legal/licenses-terms.html",
        normalized_url="https://www.adobe.com/legal/licenses-terms.html",
        is_active=True,
        source_origin=SourceOrigin.MANUAL,
        relevance_score=100,
    )
    test_db.add(manual_src)
    test_db.commit()

    engine = SourceDiscoveryEngine(search_provider=DevSearchProvider())
    req = DiscoveryTargetRequest(vendor="Adobe", product="Acrobat", max_queries=3)
    response = engine.run_discovery(test_db, req)

    test_db.refresh(manual_src)
    # Manual origin and verified description must remain intact
    assert manual_src.source_origin == SourceOrigin.MANUAL
    assert manual_src.source_name == "Curated Official Adobe Product Terms"
    assert manual_src.description == "Manually verified enterprise terms document by legal auditor."
    assert manual_src.last_checked_at is not None
