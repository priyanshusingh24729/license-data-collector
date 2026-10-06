"""
Test suite for Step 4: Official Web Content Collector.
Covers SSRF prevention, URL validation, HTML cleaning, structural section & table parsing,
content hashing, PDF redirection (DOCUMENT_REQUIRES_STEP_5), HTTP error handling, and evidence storage.
"""

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.database.connection import Base, get_db
from backend.main import app
from backend.models.enums import CollectionStatus, ScopeType, SourceType, AuthorityLevel
from backend.models.source import LicenseSource
from backend.models.collection import CollectedDocument
from backend.collectors.web.url_policy import UrlPolicy
from backend.collectors.web.content_cleaner import ContentCleaner
from backend.collectors.web.content_parser import ContentParser
from backend.collectors.web.http_client import WebHttpClient, HttpFetchResult
from backend.collectors.web.web_collector import WebCollector, compute_content_hash

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
# 1. URL Policy & SSRF Protection Tests
# -------------------------------------------------------------

def test_ssrf_and_scheme_protection():
    """Verify UrlPolicy strictly blocks internal networks, metadata IPs, and non-http schemes."""
    policy = UrlPolicy()

    # Block non-HTTP schemes
    assert policy.validate_url("file:///etc/passwd")[1] == CollectionStatus.SSRF_REJECTED
    assert policy.validate_url("ftp://server.local/data")[1] == CollectionStatus.SSRF_REJECTED

    # Block localhost & loopback
    assert policy.validate_url("http://localhost:8000/admin")[1] == CollectionStatus.SSRF_REJECTED
    assert policy.validate_url("http://127.0.0.1:5432")[1] == CollectionStatus.SSRF_REJECTED
    assert policy.validate_url("http://[::1]:8080")[1] == CollectionStatus.SSRF_REJECTED

    # Block AWS/Azure/GCP metadata IP
    assert policy.validate_url("http://169.254.169.254/latest/meta-data")[1] == CollectionStatus.SSRF_REJECTED

    # Block Private LANs (10.0.0.0/8, 192.168.0.0/16, 172.16.0.0/12)
    assert policy.validate_url("http://10.0.0.1/internal")[1] == CollectionStatus.SSRF_REJECTED
    assert policy.validate_url("http://192.168.1.1/router")[1] == CollectionStatus.SSRF_REJECTED
    assert policy.validate_url("http://172.16.0.5/api")[1] == CollectionStatus.SSRF_REJECTED


def test_official_domain_policy_enforcement():
    """Verify vendor official domain checks permit genuine domains and reject unverified ones."""
    policy = UrlPolicy()

    # Permitted Adobe domains
    assert policy.validate_url("https://www.adobe.com/legal/terms.html", vendor="Adobe")[0] is True
    assert policy.validate_url("https://helpx.adobe.com/acrobat/licensing.html", vendor="Adobe")[0] is True

    # Reject lookalike domains
    valid, status, _ = policy.validate_url("https://adobe-cracks-free.com/terms.html", vendor="Adobe")
    assert valid is False
    assert status == CollectionStatus.DOMAIN_REJECTED


# -------------------------------------------------------------
# 2. HTML Cleaning & Structural Parsing Tests
# -------------------------------------------------------------

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Adobe Acrobat Commercial Terms of Service</title>
    <script src="tracking.js"></script>
    <style>.nav { color: red; }</style>
</head>
<body>
    <nav><ul><li><a href="/">Home</a></li><li><a href="/login">Login</a></li></ul></nav>
    <div id="cookie-banner" class="consent-dialog">Accept our cookies</div>
    
    <main>
        <h1>Adobe Acrobat Commercial Terms</h1>
        <p>These terms govern your commercial use of Adobe Acrobat.</p>
        
        <h2>Licensing Models</h2>
        <p>Adobe Acrobat is licensed under the following enterprise models:</p>
        <ul>
            <li>Named User Licensing: Assigned to an identified individual user.</li>
            <li>Shared Device Licensing: Deployed to lab and multi-user computer devices.</li>
        </ul>
        
        <h2>Virtualization & Cloud Deployment</h2>
        <p>Virtualization on multiplexed server environments requires dedicated user CALs.</p>
        
        <table>
            <caption>Licensing Metrics Matrix</caption>
            <thead>
                <tr><th>Edition</th><th>Metric</th><th>Secondary Device Rights</th></tr>
            </thead>
            <tbody>
                <tr><td>Acrobat Standard</td><td>Named User</td><td>Up to 2 devices</td></tr>
                <tr><td>Acrobat Pro</td><td>Named User</td><td>Up to 2 devices + Virtualization</td></tr>
            </tbody>
        </table>
    </main>
    
    <footer><p>&copy; 2025 Adobe. All rights reserved.</p></footer>
</body>
</html>
"""

def test_html_cleaning():
    """Verify ContentCleaner removes script, style, nav, cookie banners, and footer."""
    cleaner = ContentCleaner()
    soup = cleaner.clean_html(SAMPLE_HTML)

    assert soup.find("script") is None
    assert soup.find("style") is None
    assert soup.find("nav") is None
    assert soup.find("footer") is None
    assert soup.find(id="cookie-banner") is None
    assert soup.find("h1") is not None
    assert soup.find("table") is not None


def test_document_structural_parsing():
    """Verify ContentParser preserves sections, headings, lists, tables, and Markdown table output."""
    cleaner = ContentCleaner()
    parser = ContentParser()

    soup = cleaner.clean_html(SAMPLE_HTML)
    title, sections, tables, clean_text = parser.parse_document(soup)

    assert title == "Adobe Acrobat Commercial Terms of Service"
    assert len(sections) >= 3
    assert len(tables) == 1

    # Check Table Markdown formatting
    tbl = tables[0]
    assert "Edition" in tbl.headers
    assert "Metric" in tbl.headers
    assert len(tbl.rows) == 2
    assert "| Acrobat Pro | Named User | Up to 2 devices + Virtualization |" in tbl.markdown_repr

    # Check Clean Text formatting
    assert "TITLE: Adobe Acrobat Commercial Terms of Service" in clean_text
    assert "SECTION [H2]: Licensing Models" in clean_text
    assert "Named User Licensing" in clean_text


# -------------------------------------------------------------
# 3. Content Hashing & Determinism Tests
# -------------------------------------------------------------

def test_content_hash_consistency():
    """Verify SHA-256 content hashing is deterministic and immune to trivial whitespace changes."""
    text1 = "Adobe Acrobat Pro Licensing Terms.\nSection 1: Named User."
    text2 = "Adobe Acrobat  Pro   Licensing Terms. \n\n Section 1: Named User. "
    hash1 = compute_content_hash(text1)
    hash2 = compute_content_hash(text2)
    assert len(hash1) == 64
    assert hash1 == hash2


# -------------------------------------------------------------
# 4. WebCollector Execution & PDF Handling Tests
# -------------------------------------------------------------

class MockHttpClient(WebHttpClient):
    """Mock HTTP client returning predetermined test responses."""
    def __init__(self, response_map):
        super().__init__()
        self.response_map = response_map

    def fetch(self, url: str, vendor=None, expected_official_domain=None) -> HttpFetchResult:
        if url in self.response_map:
            return self.response_map[url]
        return HttpFetchResult(
            status=CollectionStatus.NOT_FOUND,
            status_code=404,
            final_url=url,
            error_message="Not found"
        )


def test_web_collector_html_collection():
    """Verify WebCollector successfully collects and structures HTML content."""
    mock_responses = {
        "https://www.adobe.com/legal/terms.html": HttpFetchResult(
            status=CollectionStatus.COLLECTED,
            status_code=200,
            content_bytes=SAMPLE_HTML.encode("utf-8"),
            text_content=SAMPLE_HTML,
            content_type="text/html; charset=utf-8",
            final_url="https://www.adobe.com/legal/terms.html"
        )
    }

    collector = WebCollector(http_client=MockHttpClient(mock_responses))
    result = collector.collect("https://www.adobe.com/legal/terms.html", vendor="Adobe")

    assert result.status == CollectionStatus.COLLECTED
    assert result.title == "Adobe Acrobat Commercial Terms of Service"
    assert result.content_hash is not None
    assert len(result.structured_sections) >= 3
    assert len(result.tables) == 1
    assert result.word_count > 20


def test_pdf_redirection_triggers_step5_status():
    """Verify that PDF responses are identified and flagged as DOCUMENT_REQUIRES_STEP_5."""
    mock_responses = {
        "https://www.adobe.com/licensing-guide.pdf": HttpFetchResult(
            status=CollectionStatus.DOCUMENT_REQUIRES_STEP_5,
            status_code=200,
            content_type="application/pdf",
            final_url="https://www.adobe.com/licensing-guide.pdf",
            error_message="Response is a PDF document. Deferred to Step 5 PDF Collector."
        )
    }

    collector = WebCollector(http_client=MockHttpClient(mock_responses))
    result = collector.collect("https://www.adobe.com/licensing-guide.pdf", vendor="Adobe")

    assert result.status == CollectionStatus.DOCUMENT_REQUIRES_STEP_5
    assert "Deferred to Step 5" in (result.error_message or "")


# -------------------------------------------------------------
# 5. Database Source Integration & API Tests
# -------------------------------------------------------------

def test_source_collection_database_persistence(test_db):
    """Verify collect_source saves CollectedDocument record and updates source last_checked_at."""
    source = LicenseSource(
        vendor_name="Adobe",
        product_name="Acrobat",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Adobe Acrobat",
        source_name="Adobe Terms",
        source_type=SourceType.OFFICIAL_TERMS,
        authority_level=AuthorityLevel.OFFICIAL_VENDOR,
        source_url="https://www.adobe.com/legal/terms.html",
        normalized_url="https://www.adobe.com/legal/terms.html",
        is_active=True,
    )
    test_db.add(source)
    test_db.commit()

    mock_responses = {
        "https://www.adobe.com/legal/terms.html": HttpFetchResult(
            status=CollectionStatus.COLLECTED,
            status_code=200,
            content_bytes=SAMPLE_HTML.encode("utf-8"),
            text_content=SAMPLE_HTML,
            content_type="text/html",
            final_url="https://www.adobe.com/legal/terms.html"
        )
    }

    collector = WebCollector(http_client=MockHttpClient(mock_responses))
    result = collector.collect_source(test_db, source.id)

    assert result.status == CollectionStatus.COLLECTED
    test_db.refresh(source)
    assert source.last_checked_at is not None

    # Check CollectedDocument in DB
    doc = test_db.query(CollectedDocument).filter(CollectedDocument.source_id == source.id).first()
    assert doc is not None
    assert doc.title == "Adobe Acrobat Commercial Terms of Service"
    assert doc.content_hash == result.content_hash


def test_collectors_api_endpoints(test_db, client):
    """Verify FastAPI collectors endpoints."""
    # Pre-insert a document
    doc = CollectedDocument(
        vendor_name="Microsoft",
        requested_url="https://www.microsoft.com/licensing/terms",
        final_url="https://www.microsoft.com/licensing/terms",
        status=CollectionStatus.COLLECTED,
        http_status=200,
        content_type="text/html",
        content_hash="abcd1234efgh5678",
        title="Microsoft Product Terms",
        clean_text="TITLE: Microsoft Product Terms\n\nSECTION: Universal Terms",
        structured_sections=[{"heading_level": "H1", "heading_text": "Universal Terms", "paragraphs": ["Terms text"]}],
        tables_data=[]
    )
    test_db.add(doc)
    test_db.commit()

    # List documents
    res = client.get("/api/collectors/web/documents", params={"vendor": "Microsoft"})
    assert res.status_code == 200
    docs = res.json()
    assert len(docs) == 1
    assert docs[0]["title"] == "Microsoft Product Terms"

    # Get single document by ID
    get_res = client.get(f"/api/collectors/web/documents/{doc.id}")
    assert get_res.status_code == 200
    detail = get_res.json()
    assert "Universal Terms" in detail["clean_text"]

    # Get by content hash
    hash_res = client.get(f"/api/collectors/web/documents/by-hash/{doc.content_hash}")
    assert hash_res.status_code == 200
    assert hash_res.json()["vendor_name"] == "Microsoft"
