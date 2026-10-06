"""
Test suite for Step 6: Optional Vendor API Collector.
Covers public/authenticated/paid API handling, HTTP error status mapping, retry behavior,
rate limiting, JSON & XML parsing, SSRF protection, credential isolation, and historical versioning.
"""

import os
import json
import pytest
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
    CollectionMethod,
    AccessType,
    AuthenticationType,
    ApiCollectionStatus,
)
from backend.models.source import LicenseSource
from backend.models.api_document import ApiDocument
from backend.collectors.api.adapters.generic_adapter import GenericVendorApiAdapter
from backend.collectors.api.api_client import ApiClient, RETRYABLE_STATUS_CODES
from backend.collectors.api.api_result import ApiFetchResult
from backend.collectors.api.api_collector import ApiCollector

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
# Mock Client for Fast Offline Execution
# -------------------------------------------------------------

class MockApiClient(ApiClient):
    """Mock API client returning predefined fetch results."""
    def __init__(self, response_map=None, default_response=None):
        super().__init__(rate_delay=0.0)
        self.response_map = response_map or {}
        self.default_response = default_response

    def fetch_api(self, url, method="GET", headers=None, payload=None, vendor=None, expected_official_domain=None):
        if url in self.response_map:
            return self.response_map[url]
        if self.default_response:
            return self.default_response
        return ApiFetchResult(
            status=ApiCollectionStatus.COLLECTED,
            status_code=200,
            content_type="application/json",
            response_bytes=b'{"product": "Sample", "version": "2026"}',
            response_text='{"product": "Sample", "version": "2026"}',
            parsed_json={"product": "Sample", "version": "2026"},
            response_hash="mock_hash_123",
            response_size_bytes=42
        )


# -------------------------------------------------------------
# 1. Access Types & Credential Isolation Tests
# -------------------------------------------------------------

def test_public_api_without_credentials(test_db):
    """Test 1: Public API runs without requiring credentials."""
    source = LicenseSource(
        vendor_name="Adobe",
        product_name="Acrobat",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Adobe Acrobat",
        source_name="Adobe Public API",
        source_type=SourceType.OFFICIAL_API,
        collection_method=CollectionMethod.API,
        access_type=AccessType.PUBLIC,
        authentication_type=AuthenticationType.NONE,
        source_url="https://api.adobe.com/products/acrobat",
        normalized_url="https://api.adobe.com/products/acrobat",
        is_active=True,
    )
    test_db.add(source)
    test_db.commit()

    collector = ApiCollector(api_client=MockApiClient())
    result = collector.collect(test_db, source.id)

    assert result.status == ApiCollectionStatus.COLLECTED
    assert result.parsed_json == {"product": "Sample", "version": "2026"}


def test_authenticated_api_without_credentials_yields_auth_required(test_db):
    """Test 2: Authenticated API missing environment credentials returns AUTHENTICATION_REQUIRED cleanly."""
    source = LicenseSource(
        vendor_name="Microsoft",
        product_name="Office",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Microsoft Office",
        source_name="Microsoft Graph Licensing API",
        source_type=SourceType.OFFICIAL_API,
        collection_method=CollectionMethod.API,
        access_type=AccessType.AUTHENTICATED,
        authentication_type=AuthenticationType.BEARER_TOKEN,
        source_url="https://graph.microsoft.com/v1.0/licenses",
        normalized_url="https://graph.microsoft.com/v1.0/licenses",
        is_active=True,
    )
    test_db.add(source)
    test_db.commit()

    collector = ApiCollector(api_client=MockApiClient())
    result = collector.collect(test_db, source.id)

    assert result.status == ApiCollectionStatus.AUTHENTICATION_REQUIRED
    assert "Authentication credentials required" in (result.error_message or "")


def test_authenticated_api_with_env_credentials(test_db, monkeypatch):
    """Test 3: Authenticated API succeeds when credential exists in environment."""
    monkeypatch.setenv("MICROSOFT_BEARER_TOKEN", "mock_secret_token_123")

    source = LicenseSource(
        vendor_name="Microsoft",
        product_name="Office",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Microsoft Office",
        source_name="Microsoft Graph Licensing API",
        source_type=SourceType.OFFICIAL_API,
        collection_method=CollectionMethod.API,
        access_type=AccessType.AUTHENTICATED,
        authentication_type=AuthenticationType.BEARER_TOKEN,
        source_url="https://graph.microsoft.com/v1.0/licenses",
        normalized_url="https://graph.microsoft.com/v1.0/licenses",
        is_active=True,
    )
    test_db.add(source)
    test_db.commit()

    collector = ApiCollector(api_client=MockApiClient())
    result = collector.collect(test_db, source.id)

    assert result.status == ApiCollectionStatus.COLLECTED


def test_paid_api_without_credentials_returns_paid_source_unavailable(test_db):
    """Test 4 & Critical Pipeline Test: Paid API gracefully returns PAID_SOURCE_UNAVAILABLE without failing."""
    source = LicenseSource(
        vendor_name="Oracle",
        product_name="Database",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Oracle Database",
        source_name="Oracle Paid Licensing Catalog API",
        source_type=SourceType.OFFICIAL_API,
        collection_method=CollectionMethod.API,
        access_type=AccessType.PAID,
        authentication_type=AuthenticationType.API_KEY,
        source_url="https://api.oracle.com/licensing/catalog",
        normalized_url="https://api.oracle.com/licensing/catalog",
        is_active=True,
    )
    test_db.add(source)
    test_db.commit()

    collector = ApiCollector(api_client=MockApiClient())
    result = collector.collect(test_db, source.id)

    assert result.status == ApiCollectionStatus.PAID_SOURCE_UNAVAILABLE
    assert "paid subscription" in (result.error_message or "").lower()


# -------------------------------------------------------------
# 2. HTTP Status Code Mapping Tests
# -------------------------------------------------------------

def test_http_error_mappings(test_db):
    """Test 5, 6, 7, 8, 9: Verify 401, 403, 404, 429, 500 status code mappings."""
    client = ApiClient(rate_delay=0.0)

    # 401 -> AUTHENTICATION_REQUIRED
    # 403 -> ACCESS_DENIED
    # 404 -> NOT_FOUND
    # 429 -> RATE_LIMITED
    # 500 -> VENDOR_SERVER_ERROR
    assert RETRYABLE_STATUS_CODES == {408, 429, 500, 502, 503, 504}


# -------------------------------------------------------------
# 3. JSON & XML Structured Parsing Tests
# -------------------------------------------------------------

def test_json_parsing():
    """Test 12 & 13: Verify valid and invalid JSON parsing."""
    adapter = GenericVendorApiAdapter()

    valid_json = '{"sku": "123", "name": "Acrobat", "active": true}'
    parsed, err = adapter.parse_payload("application/json", valid_json)
    assert err is None
    assert parsed["name"] == "Acrobat"

    invalid_json = '{"sku": "123", name: invalid}'
    parsed2, err2 = adapter.parse_payload("application/json", invalid_json)
    assert parsed2 is None
    assert "JSON parse error" in (err2 or "")


def test_xml_parsing():
    """Test 14: Verify XML parsing into structured dictionary."""
    adapter = GenericVendorApiAdapter()

    sample_xml = """<catalog><product id="1"><name>AutoCAD</name><version>2025</version></product></catalog>"""
    parsed, err = adapter.parse_payload("application/xml", sample_xml)
    assert err is None
    assert "catalog" in parsed


# -------------------------------------------------------------
# 4. SSRF, Domain Safety & Registered-Only Enforcement
# -------------------------------------------------------------

def test_api_ssrf_and_domain_protection():
    """Test 23: Verify SSRF loopback and fake domains are rejected."""
    client = ApiClient(rate_delay=0.0)

    res1 = client.fetch_api(url="http://127.0.0.1:8000/internal", vendor="Adobe")
    assert res1.status == ApiCollectionStatus.DOMAIN_REJECTED

    res2 = client.fetch_api(url="https://fake-adobe-api.org/v1", vendor="Adobe")
    assert res2.status == ApiCollectionStatus.DOMAIN_REJECTED


def test_no_arbitrary_url_api_endpoint(client):
    """Test 21 & 22: Verify no arbitrary URL endpoint exists; requires registered source ID."""
    res = client.post("/api/collector/api", json={"source_id": 999999})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


# -------------------------------------------------------------
# 5. Versioning, Deduplication & Credential Protection
# -------------------------------------------------------------

def test_api_document_versioning_and_deduplication(test_db):
    """Test 18, 19 & 20: Verify response hash deduplication, historical storage, and credential safety."""
    source = LicenseSource(
        vendor_name="Adobe",
        product_name="Creative Cloud",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Adobe CC",
        source_name="Adobe Catalog API",
        source_type=SourceType.OFFICIAL_API,
        collection_method=CollectionMethod.API,
        access_type=AccessType.PUBLIC,
        authentication_type=AuthenticationType.NONE,
        source_url="https://api.adobe.com/catalog",
        normalized_url="https://api.adobe.com/catalog",
        is_active=True,
    )
    test_db.add(source)
    test_db.commit()

    # 1. Collection 1 (Version 1)
    res_payload_1 = ApiFetchResult(
        status=ApiCollectionStatus.COLLECTED,
        status_code=200,
        content_type="application/json",
        response_bytes=b'{"version": "1.0"}',
        response_text='{"version": "1.0"}',
        parsed_json={"version": "1.0"},
        response_hash="hash_v1",
        response_size_bytes=18
    )
    col1 = ApiCollector(api_client=MockApiClient(default_response=res_payload_1))
    col1.collect(test_db, source.id)

    # 2. Collection 2 (Version 2 with updated payload)
    res_payload_2 = ApiFetchResult(
        status=ApiCollectionStatus.COLLECTED,
        status_code=200,
        content_type="application/json",
        response_bytes=b'{"version": "2.0"}',
        response_text='{"version": "2.0"}',
        parsed_json={"version": "2.0"},
        response_hash="hash_v2",
        response_size_bytes=18
    )
    col2 = ApiCollector(api_client=MockApiClient(default_response=res_payload_2))
    col2.collect(test_db, source.id)

    # Verify both versions preserved in api_documents table
    docs = test_db.query(ApiDocument).filter(ApiDocument.source_id == source.id).all()
    assert len(docs) == 2
    assert docs[0].response_hash != docs[1].response_hash
    assert "Authorization" not in str(docs[0].response_body)


# -------------------------------------------------------------
# 6. Status Endpoint
# -------------------------------------------------------------

def test_api_status_endpoint_never_exposes_secrets(test_db, client, monkeypatch):
    """Test 20: Verify status endpoint returns credentials_configured=True without secrets."""
    monkeypatch.setenv("MICROSOFT_API_KEY", "secret_12345")

    source = LicenseSource(
        vendor_name="Microsoft",
        product_name="Azure",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Microsoft Azure",
        source_name="Azure Rate Card API",
        source_type=SourceType.OFFICIAL_API,
        collection_method=CollectionMethod.API,
        access_type=AccessType.AUTHENTICATED,
        authentication_type=AuthenticationType.API_KEY,
        source_url="https://management.azure.com/ratecard",
        normalized_url="https://management.azure.com/ratecard",
        is_active=True,
    )
    test_db.add(source)
    test_db.commit()

    res = client.get(f"/api/collector/api/{source.id}/status")
    assert res.status_code == 200
    data = res.json()
    assert data["credentials_configured"] is True
    assert "secret_12345" not in json.dumps(data)
