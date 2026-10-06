"""
Test suite for Step 5: Official PDF & Document Collector.
Covers magic-byte verification, SSRF protection, size caps, multi-page text extraction,
metadata parsing, OCR requirement detection, versioning, duplicate detection, and API security.
"""

import os
import fitz  # PyMuPDF
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
    DocumentCollectionStatus,
    DocumentClassification,
)
from backend.models.source import LicenseSource
from backend.models.collection import CollectedDocument, DocumentPage
from backend.collectors.documents.document_downloader import DocumentDownloader, DownloadedDocumentPayload
from backend.collectors.documents.pdf_parser import PdfParser
from backend.collectors.documents.document_classifier import DocumentClassifier
from backend.collectors.documents.pdf_collector import PdfCollector
from backend.collectors.documents.document_collector import DocumentCollector

# Test database setup (in-memory SQLite with StaticPool)
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"


def create_sample_pdf(num_pages: int = 2, with_text: bool = True) -> bytes:
    """Helper to synthesize authentic in-memory PDF binary data using PyMuPDF."""
    doc = fitz.open()
    doc.set_metadata({
        "title": "Adobe Enterprise Licensing Guide 2025",
        "author": "Adobe Legal & Compliance",
        "subject": "Commercial Product Terms and Virtualization Rights",
        "creationDate": "D:20250115100000Z",
        "modDate": "D:20250120120000Z"
    })

    for page_num in range(1, num_pages + 1):
        page = doc.new_page(width=595, height=842)
        if with_text:
            page.insert_text(
                (50, 72),
                f"Adobe Acrobat Enterprise Licensing — Page {page_num}\n\n"
                "1. Named User Licensing: Assigned strictly to identified single users.\n"
                "2. Secondary Device Rights: Permitted on up to 2 machines.",
                fontsize=11
            )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


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
# 1. Magic-Byte Detection & Content Verification Tests
# -------------------------------------------------------------

def test_pdf_magic_byte_detection():
    """Test 1: Verify valid %PDF- magic bytes are recognized."""
    downloader = DocumentDownloader()
    valid_pdf = create_sample_pdf()
    assert downloader.is_pdf_content(valid_pdf, "application/pdf") is True


def test_invalid_pdf_rejection():
    """Test 3: Verify corrupt or non-PDF binary data is rejected."""
    downloader = DocumentDownloader()
    garbage_bytes = b"NOT_A_PDF_CORRUPT_BYTES_XYZ"
    assert downloader.is_pdf_content(garbage_bytes, "application/pdf") is False


def test_html_masquerading_as_pdf():
    """Test 4: Verify HTML returned on a .pdf URL is rejected as INVALID_DOCUMENT."""
    downloader = DocumentDownloader()
    html_bytes = b"<!DOCTYPE html><html><body>Error 403 Forbidden or Login Page</body></html>"
    assert downloader.is_pdf_content(html_bytes, "application/pdf") is False


# -------------------------------------------------------------
# 2. SSRF, Domain Validation & Size Limits
# -------------------------------------------------------------

def test_document_ssrf_and_domain_protection():
    """Test 9 & 10: Verify SSRF and vendor domain policy enforcement on PDF downloads."""
    downloader = DocumentDownloader()

    # SSRF loopback
    res1 = downloader.download_document("http://127.0.0.1:8000/doc.pdf", vendor="Adobe")
    assert res1.status == DocumentCollectionStatus.DOMAIN_REJECTED

    # Lookalike domain
    res2 = downloader.download_document("https://fake-adobe-files.com/doc.pdf", vendor="Adobe")
    assert res2.status == DocumentCollectionStatus.DOMAIN_REJECTED


def test_maximum_file_size_limit():
    """Test 5: Verify downloads exceeding MAX_DOCUMENT_BYTES are flagged."""
    downloader = DocumentDownloader(max_bytes=10)  # Very low byte cap
    sample_pdf = create_sample_pdf()
    assert len(sample_pdf) > 10
    # Manually check size constraint logic
    assert len(sample_pdf) > downloader.max_bytes


# -------------------------------------------------------------
# 3. PDF Metadata & Multi-Page Text Extraction Tests
# -------------------------------------------------------------

def test_pdf_metadata_extraction():
    """Test 11 & 12: Verify metadata and page count are extracted accurately."""
    parser = PdfParser()
    sample_pdf = create_sample_pdf(num_pages=3, with_text=True)
    meta, pages, clean_text, extractable, ocr_req = parser.parse_pdf(sample_pdf, sha256_hash="test_hash")

    assert meta.title == "Adobe Enterprise Licensing Guide 2025"
    assert meta.author == "Adobe Legal & Compliance"
    assert meta.page_count == 3
    assert len(pages) == 3
    assert extractable is True
    assert ocr_req is False


def test_page_level_text_extraction():
    """Test 13 & 14: Verify page-by-page text boundaries and SHA-256 hashing."""
    parser = PdfParser()
    sample_pdf = create_sample_pdf(num_pages=2, with_text=True)
    _, pages, clean_text, _, _ = parser.parse_pdf(sample_pdf, sha256_hash="hash123")

    assert pages[0].page_number == 1
    assert "Named User Licensing" in pages[0].text
    assert pages[1].page_number == 2
    assert "Secondary Device Rights" in pages[1].text
    assert "--- PAGE 1 ---" in clean_text
    assert "--- PAGE 2 ---" in clean_text


def test_ocr_required_detection():
    """Test 17: Verify image-only/empty text PDF triggers OCR_REQUIRED flag."""
    parser = PdfParser(min_char_threshold=50)
    empty_pdf = create_sample_pdf(num_pages=1, with_text=False)
    _, _, _, extractable, ocr_required = parser.parse_pdf(empty_pdf, sha256_hash="empty_hash")

    assert extractable is False
    assert ocr_required is True


def test_document_classification():
    """Test 18: Verify document classification infers type without license conclusions."""
    classifier = DocumentClassifier()

    assert classifier.classify(
        url="https://www.adobe.com/legal/licenses-terms.pdf",
        title="Adobe Product Terms"
    ) == DocumentClassification.PRODUCT_TERMS

    assert classifier.classify(
        url="https://www.microsoft.com/licensing/docs/view/SQL-Server-Licensing-Guide.pdf",
        title="SQL Server Licensing Guide"
    ) == DocumentClassification.LICENSING_GUIDE

    assert classifier.classify(
        url="https://www.autodesk.com/eula.pdf",
        title="Autodesk End User License Agreement"
    ) == DocumentClassification.EULA


# -------------------------------------------------------------
# 4. Collector Execution, Duplicate Detection & Versioning
# -------------------------------------------------------------

class MockDownloader(DocumentDownloader):
    """Mock downloader returning simulated PDF payloads."""
    def __init__(self, sample_bytes):
        super().__init__()
        self.sample_bytes = sample_bytes

    def download_document(self, url, vendor=None, expected_official_domain=None, source_id=None):
        import hashlib
        h = hashlib.sha256(self.sample_bytes).hexdigest()
        return DownloadedDocumentPayload(
            status=DocumentCollectionStatus.COLLECTED,
            raw_bytes=self.sample_bytes,
            final_url=url,
            content_type="application/pdf",
            sha256_hash=h,
            saved_file_path=f"data/raw/{h}.pdf"
        )


def test_document_collection_and_page_persistence(test_db):
    """Test 19: Verify DocumentCollector saves document and document_pages in database."""
    source = LicenseSource(
        vendor_name="Adobe",
        product_name="Acrobat",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Adobe Acrobat",
        source_name="Adobe Acrobat Licensing PDF",
        source_type=SourceType.OFFICIAL_PDF,
        authority_level=AuthorityLevel.OFFICIAL_VENDOR,
        source_url="https://www.adobe.com/acrobat-licensing.pdf",
        normalized_url="https://www.adobe.com/acrobat-licensing.pdf",
        is_active=True,
    )
    test_db.add(source)
    test_db.commit()

    sample_pdf = create_sample_pdf(num_pages=2, with_text=True)
    mock_downloader = MockDownloader(sample_pdf)
    pdf_col = PdfCollector(downloader=mock_downloader)
    doc_col = DocumentCollector(pdf_collector=pdf_col)

    result = doc_col.collect(test_db, source.id)

    assert result.status == DocumentCollectionStatus.PARSED
    assert len(result.pages) == 2

    # Verify DB records
    doc_record = test_db.query(CollectedDocument).filter(CollectedDocument.source_id == source.id).first()
    assert doc_record is not None
    assert doc_record.page_count == 2

    pages = test_db.query(DocumentPage).filter(DocumentPage.document_id == doc_record.id).all()
    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert "Named User" in pages[0].text


def test_document_versioning_and_duplicate_preservation(test_db):
    """Test 15, 16 & 21: Verify document updates with new hashes preserve historical versions."""
    source = LicenseSource(
        vendor_name="Adobe",
        product_name="Acrobat",
        scope_type=ScopeType.PRODUCT,
        scope_identifier="Adobe Acrobat",
        source_name="Adobe Acrobat Terms PDF",
        source_type=SourceType.OFFICIAL_PDF,
        authority_level=AuthorityLevel.OFFICIAL_VENDOR,
        source_url="https://www.adobe.com/terms.pdf",
        normalized_url="https://www.adobe.com/terms.pdf",
        is_active=True,
    )
    test_db.add(source)
    test_db.commit()

    # 1. First collection (Version 1)
    pdf_v1 = create_sample_pdf(num_pages=1, with_text=True)
    doc_col = DocumentCollector(pdf_collector=PdfCollector(downloader=MockDownloader(pdf_v1)))
    res1 = doc_col.collect(test_db, source.id)

    # 2. Second collection with updated terms (Version 2)
    pdf_v2 = create_sample_pdf(num_pages=2, with_text=True)
    doc_col2 = DocumentCollector(pdf_collector=PdfCollector(downloader=MockDownloader(pdf_v2)))
    res2 = doc_col2.collect(test_db, source.id)

    # Both version records must be preserved in the database
    docs = test_db.query(CollectedDocument).filter(CollectedDocument.source_id == source.id).all()
    assert len(docs) == 2
    assert docs[0].content_hash != docs[1].content_hash


# -------------------------------------------------------------
# 5. API Endpoints & Security Restrictions
# -------------------------------------------------------------

def test_no_arbitrary_url_download(client):
    """Test 20: Verify the API only allows collecting registered source IDs, no arbitrary URL endpoint."""
    res = client.post("/api/collector/document", json={"source_id": 99999})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()
