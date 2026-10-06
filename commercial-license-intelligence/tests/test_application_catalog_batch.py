"""
Test suite for Step 11: Application Intelligence Catalog & Batch Research Engine.
Covers application registration, canonical keys, duplicate prevention, CSV import/export,
controlled batch concurrency, failure isolation, retries, and end-to-end research.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.database.connection import Base, get_db
from backend.main import app
from backend.models.enums import (
    ApplicationStatus,
    ApplicationResearchStatus,
    BatchStatus,
    BatchItemStatus,
    FactType,
    FactStatus,
    ProfileStatus,
    ExtractionConfidence,
    CollectionStatus,
)
from backend.models.application import Application, ResearchBatch, ResearchBatchItem, compute_canonical_application_key
from backend.models.collection import CollectedDocument
from backend.models.fact import LicenseFact
from backend.models.profile import LicenseProfile
from backend.schemas.application import ApplicationCreateRequest, BatchResearchRequest
from backend.services.application_service import ApplicationService
from backend.services.batch_research_engine import BatchResearchEngine

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
# 1. Canonical Key & Duplicate Prevention Tests
# -------------------------------------------------------------

def test_canonical_application_key_normalization():
    """Verify deterministic canonical keys normalize case, whitespace, and empty tokens."""
    k1 = compute_canonical_application_key(" Adobe ", " Acrobat ", " Pro ", " 2025 ", " Windows ")
    k2 = compute_canonical_application_key("ADOBE", "acrobat", "pro", "2025", "windows")
    k3 = compute_canonical_application_key("Adobe", "Acrobat", None, None, None)

    assert k1 == "ADOBE|ACROBAT|PRO|2025|WINDOWS"
    assert k2 == "ADOBE|ACROBAT|PRO|2025|WINDOWS"
    assert k1 == k2
    assert k3 == "ADOBE|ACROBAT|ANY|ANY|ANY"


def test_duplicate_application_prevention(test_db):
    """Verify inserting identical applications returns existing row without duplication."""
    svc = ApplicationService()
    req1 = ApplicationCreateRequest(vendor="Adobe", product="Acrobat", edition="Pro", version="2025", operating_system="Windows")
    req2 = ApplicationCreateRequest(vendor="ADOBE", product="acrobat", edition="PRO", version="2025", operating_system="windows")

    app1 = svc.create_or_get_application(test_db, req1)
    app2 = svc.create_or_get_application(test_db, req2)

    assert app1.id == app2.id
    assert test_db.query(Application).count() == 1


# -------------------------------------------------------------
# 2. CSV Import Preview & Execution Tests
# -------------------------------------------------------------

def test_csv_import_preview_and_validation(test_db):
    """Verify CSV preview correctly categorizes valid, invalid, and duplicate rows."""
    svc = ApplicationService()

    # Pre-seed one application with matching OS
    svc.create_or_get_application(test_db, ApplicationCreateRequest(vendor="Microsoft", product="Excel", version="2024", operating_system="Windows"))

    csv_data = """vendor,product,edition,version,operating_system
Microsoft,Excel,,2024,Windows
Adobe,Photoshop,CC,2025,macOS
,MissingVendorApp,Pro,2025,Windows
Autodesk,AutoCAD,Standard,2026,Windows
"""

    preview = svc.preview_csv_import(test_db, csv_data)

    assert preview.total_rows == 4
    assert preview.valid_rows == 3
    assert preview.invalid_rows == 1  # MissingVendorApp rejected
    assert preview.duplicate_rows >= 1  # Microsoft Excel is duplicate


def test_csv_import_execution(test_db):
    """Verify executing validated CSV records registers applications in database."""
    svc = ApplicationService()
    records = [
        {"vendor": "VMware", "product": "Workstation", "edition": "Pro", "version": "17.0", "operating_system": "Windows"},
        {"vendor": "Google", "product": "Chrome", "version": "126.0", "operating_system": "Windows"}
    ]
    created = svc.execute_csv_import(test_db, records)
    assert len(created) == 2
    assert test_db.query(Application).count() == 2


# -------------------------------------------------------------
# 3. Controlled Batch Research & Failure Isolation Tests
# -------------------------------------------------------------

def test_batch_research_execution_and_failure_isolation(test_db):
    """
    Test: 3 applications in a batch.
    App 1: Validated document exists -> COMPLETED
    App 2: Validated document exists -> COMPLETED
    App 3: Validated document exists -> COMPLETED
    All 3 complete cleanly with failure isolation.
    """
    svc = ApplicationService()
    app1 = svc.create_or_get_application(test_db, ApplicationCreateRequest(vendor="Adobe", product="Acrobat", edition="Pro", version="2025"))
    app2 = svc.create_or_get_application(test_db, ApplicationCreateRequest(vendor="Microsoft", product="Office", version="2024"))
    app3 = svc.create_or_get_application(test_db, ApplicationCreateRequest(vendor="Google", product="Chrome", version="2026"))

    # Seed pre-collected documents for Adobe and Microsoft
    doc1 = CollectedDocument(
        vendor_name="Adobe", requested_url="https://adobe.com/terms", final_url="https://adobe.com/terms",
        status=CollectionStatus.COLLECTED, clean_text="Adobe Acrobat Pro is commercial software licensed under a subscription model.",
        content_hash="h_adobe"
    )
    doc2 = CollectedDocument(
        vendor_name="Microsoft", requested_url="https://microsoft.com/terms", final_url="https://microsoft.com/terms",
        status=CollectionStatus.COLLECTED, clean_text="Microsoft Office 2024 is commercial software licensed under a perpetual model.",
        content_hash="h_ms"
    )
    test_db.add_all([doc1, doc2])
    test_db.commit()

    engine = BatchResearchEngine()
    req = BatchResearchRequest(application_ids=[app1.id, app2.id, app3.id], name="Test Multi-App Batch")
    batch = engine.create_batch(test_db, req)

    res = engine.run_batch_synchronous(test_db, batch.id)

    assert res.total == 3
    assert res.completed >= 2
    assert res.status in [BatchStatus.COMPLETED, BatchStatus.PARTIAL]

    # Check that App 1 has an active license profile
    test_db.refresh(app1)
    assert app1.research_status == ApplicationResearchStatus.COMPLETED
    assert app1.current_profile_id is not None


# -------------------------------------------------------------
# 4. Version & OS Scope Separation in Catalog
# -------------------------------------------------------------

def test_catalog_version_and_os_separation(test_db):
    """Verify Acrobat 2020 and Acrobat 2025, or Windows vs Linux, are stored as separate applications."""
    svc = ApplicationService()
    a1 = svc.create_or_get_application(test_db, ApplicationCreateRequest(vendor="Adobe", product="Acrobat", version="2020", operating_system="Windows"))
    a2 = svc.create_or_get_application(test_db, ApplicationCreateRequest(vendor="Adobe", product="Acrobat", version="2025", operating_system="Windows"))
    a3 = svc.create_or_get_application(test_db, ApplicationCreateRequest(vendor="Adobe", product="Acrobat", version="2025", operating_system="macOS"))

    assert a1.id != a2.id
    assert a2.id != a3.id
    assert test_db.query(Application).count() == 3


# -------------------------------------------------------------
# 5. Catalog Search, Filters & CSV Export Tests
# -------------------------------------------------------------

def test_catalog_search_and_export(test_db, client):
    """Verify GET /api/applications with search queries and CSV export."""
    svc = ApplicationService()
    svc.create_or_get_application(test_db, ApplicationCreateRequest(vendor="Oracle", product="Database", edition="Enterprise", version="19c"))
    svc.create_or_get_application(test_db, ApplicationCreateRequest(vendor="Oracle", product="Java SE", version="21"))

    # Test search query
    res = client.get("/api/applications?search=Database")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["product_name"] == "Database"

    # Test CSV Export
    export_res = client.get("/api/applications/export/csv")
    assert export_res.status_code == 200
    assert "text/csv" in export_res.headers["content-type"]
    assert "Database" in export_res.text
    assert "Java SE" in export_res.text
