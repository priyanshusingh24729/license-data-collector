"""
Test suite for Step 13: Application Detection + Identity Resolution Layer.
Covers endpoint ingestion, publisher/name/version normalization, exact/normalized matches,
ambiguity handling in the human review queue, multi-device installation tracking,
license profile connection, and separation of detection from entitlement.
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
    DeviceStatus,
    DetectedAppStatus,
    DetectionMethod,
    MatchType,
    ResolutionQueueStatus,
    ExtractionConfidence,
    FactType,
    FactStatus,
    ProfileStatus,
)
from backend.models.application import Application, compute_canonical_application_key
from backend.models.profile import LicenseProfile
from backend.models.inventory import Device, DetectedApplication, DeviceApplication, ApplicationResolutionQueue
from backend.inventory.detection.detection_normalizer import DetectionNormalizer
from backend.inventory.detection.match_confidence import MatchConfidenceCalculator
from backend.inventory.detection.matching_engine import MatchingEngine
from backend.inventory.detection.identity_resolver import IdentityResolver
from backend.inventory.detection.inventory_ingestor import InventoryIngestor
from backend.inventory.detection.detection_result import (
    InventoryIngestRequest,
    DeviceIngestPayload,
    ApplicationIngestItem,
    ManualResolveRequest,
)

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
# 1. Normalization Tests (Name, Publisher, Version)
# -------------------------------------------------------------

def test_detection_normalizations():
    """Verify name, publisher, and version normalization algorithms."""
    # Name normalization
    assert DetectionNormalizer.normalize_name("Adobe Acrobat Pro (64-bit)") == "Adobe Acrobat Pro"
    assert DetectionNormalizer.normalize_name("Microsoft Office 2024 Setup") == "Microsoft Office 2024"
    assert DetectionNormalizer.normalize_name("VMware Workstation Pro [x64]") == "VMware Workstation Pro"

    # Publisher normalization
    assert DetectionNormalizer.normalize_publisher("Adobe Inc.") == "Adobe"
    assert DetectionNormalizer.normalize_publisher("Adobe Systems Incorporated") == "Adobe"
    assert DetectionNormalizer.normalize_publisher("Microsoft Corporation") == "Microsoft"

    # Version normalization
    raw_v, maj, min_v, pat = DetectionNormalizer.normalize_version("25.001.204xx")
    assert maj == "25"
    assert min_v == "001"
    assert pat == "20400"


# -------------------------------------------------------------
# 2. Exact & Normalized Match Ingestion Tests
# -------------------------------------------------------------

def test_exact_and_normalized_matching(test_db):
    """
    Test:
    1. Pre-seed Application Catalog with 'Adobe Acrobat Pro', 'Adobe', 'Pro', '2025', 'Windows'.
    2. Endpoint reports 'Adobe Acrobat Pro (64-bit)', 'Adobe Inc.', '25.001'.
    3. Ingestion auto-resolves with NORMALIZED_MATCH and links to catalog ID.
    """
    app_cat = Application(
        vendor_name="Adobe",
        product_name="Acrobat",
        edition="Pro",
        version="2025",
        operating_system="Windows",
        display_name="Adobe Acrobat Pro 2025",
        application_key="ADOBE|ACROBAT|PRO|2025|WINDOWS"
    )
    test_db.add(app_cat)
    test_db.commit()

    ingestor = InventoryIngestor()
    req = InventoryIngestRequest(
        device=DeviceIngestPayload(
            device_key="DEV-LAPTOP-01",
            hostname="FINANCE-LAPTOP",
            operating_system="Windows",
            os_version="11"
        ),
        applications=[
            ApplicationIngestItem(
                name="Adobe Acrobat Pro (64-bit)",
                publisher="Adobe Inc.",
                version="25.001",
                install_location="C:\\Program Files\\Adobe"
            )
        ]
    )

    res = ingestor.ingest_inventory(test_db, req)
    assert res.total_reported == 1
    assert res.resolved_count == 1
    assert res.applications[0].resolved_application_id == app_cat.id
    assert res.applications[0].resolution_type in [MatchType.NORMALIZED_MATCH, MatchType.EXACT_MATCH]


# -------------------------------------------------------------
# 3. Ambiguity Guard Test (Acrobat vs Reader vs Pro)
# -------------------------------------------------------------

def test_ambiguous_detection_handling(test_db):
    """
    Test:
    1. Catalog contains 'Acrobat Reader', 'Acrobat Standard', and 'Acrobat Pro'.
    2. Device reports bare name 'Acrobat' with no edition.
    3. Result MUST be AMBIGUOUS_MATCH, not auto-resolved, and sent to resolution queue.
    """
    app1 = Application(vendor_name="Adobe", product_name="Acrobat Reader", application_key="ADOBE|ACROBAT READER|ANY|ANY|ANY")
    app2 = Application(vendor_name="Adobe", product_name="Acrobat Standard", application_key="ADOBE|ACROBAT STANDARD|ANY|ANY|ANY")
    app3 = Application(vendor_name="Adobe", product_name="Acrobat Pro", application_key="ADOBE|ACROBAT PRO|ANY|ANY|ANY")
    test_db.add_all([app1, app2, app3])
    test_db.commit()

    ingestor = InventoryIngestor()
    req = InventoryIngestRequest(
        device=DeviceIngestPayload(device_key="DEV-02", hostname="HR-LAPTOP"),
        applications=[
            ApplicationIngestItem(name="Acrobat", publisher="Adobe")
        ]
    )

    res = ingestor.ingest_inventory(test_db, req)
    assert res.resolved_count == 0
    assert res.unresolved_count == 1
    assert res.applications[0].resolution_type == MatchType.AMBIGUOUS_MATCH
    assert res.applications[0].resolved_application_id is None

    # Check review queue entries
    queue_items = test_db.query(ApplicationResolutionQueue).all()
    assert len(queue_items) >= 2


# -------------------------------------------------------------
# 4. Multi-Device Tracking & Installation Counting
# -------------------------------------------------------------

def test_multi_device_installation_counting(test_db):
    """
    Test:
    1. Application 'Microsoft Office 2024' registered in catalog.
    2. Ingested from Device 1, Device 2, Device 3.
    3. Device 1 reports twice -> last_seen_at updated, no duplicate rows.
    4. Installed count is 3 across distinct devices.
    """
    app_cat = Application(
        vendor_name="Microsoft",
        product_name="Office",
        version="2024",
        application_key="MICROSOFT|OFFICE|ANY|2024|ANY"
    )
    test_db.add(app_cat)
    test_db.commit()

    ingestor = InventoryIngestor()
    item = ApplicationIngestItem(name="Microsoft Office", publisher="Microsoft", version="2024")

    # Ingest Device 1 (first time)
    ingestor.ingest_inventory(test_db, InventoryIngestRequest(
        device=DeviceIngestPayload(device_key="DEV-A"), applications=[item]
    ))
    # Ingest Device 1 (second time - duplicate check)
    ingestor.ingest_inventory(test_db, InventoryIngestRequest(
        device=DeviceIngestPayload(device_key="DEV-A"), applications=[item]
    ))
    # Ingest Device 2 & 3
    ingestor.ingest_inventory(test_db, InventoryIngestRequest(
        device=DeviceIngestPayload(device_key="DEV-B"), applications=[item]
    ))
    ingestor.ingest_inventory(test_db, InventoryIngestRequest(
        device=DeviceIngestPayload(device_key="DEV-C"), applications=[item]
    ))

    # Verify total detected installations for this resolved application
    count = test_db.query(DetectedApplication).filter(
        DetectedApplication.resolved_application_id == app_cat.id,
        DetectedApplication.status == DetectedAppStatus.ACTIVE
    ).count()

    assert count == 3
    assert test_db.query(Device).count() == 3


# -------------------------------------------------------------
# 5. Separation of Detection from Entitlement
# -------------------------------------------------------------

def test_license_intelligence_connected_without_inferring_entitlement(test_db, client):
    """
    Test:
    GET /api/inventory/applications shows 'SUBSCRIPTION / NAMED_USER' as License Intelligence,
    along with 'installed_count = 1', but does NOT imply compliance or entitlement.
    """
    profile = LicenseProfile(
        vendor_name="Autodesk", product_name="AutoCAD",
        license_model="SUBSCRIPTION", license_metric="NAMED_USER",
        license_classification="COMMERCIAL", license_required="TRUE",
        profile_hash="hash_autocad", profile_status=ProfileStatus.VALIDATED
    )
    test_db.add(profile)
    test_db.commit()

    app_cat = Application(
        vendor_name="Autodesk", product_name="AutoCAD",
        application_key="AUTODESK|AUTOCAD|ANY|ANY|ANY",
        current_profile_id=profile.id
    )
    test_db.add(app_cat)
    test_db.commit()

    # Ingest detection
    ingestor = InventoryIngestor()
    ingestor.ingest_inventory(test_db, InventoryIngestRequest(
        device=DeviceIngestPayload(device_key="DEV-ENG-01"),
        applications=[ApplicationIngestItem(name="AutoCAD", publisher="Autodesk")]
    ))

    res = client.get("/api/inventory/applications?vendor=Autodesk")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["installed_count"] == 1
    assert data[0]["license_model"] == "SUBSCRIPTION"
    assert data[0]["license_metric"] == "NAMED_USER"


# -------------------------------------------------------------
# 6. Manual Review Queue Resolution API
# -------------------------------------------------------------

def test_manual_resolution_api(test_db, client):
    """Test manual acceptance of candidate via POST /api/inventory/resolve/{queue_id}."""
    app_cat = Application(
        vendor_name="Quest", product_name="ActiveRoles",
        application_key="QUEST|ACTIVEROLES|ANY|ANY|ANY"
    )
    device = Device(device_key="DEV-SRV-01")
    test_db.add_all([app_cat, device])
    test_db.commit()

    det = DetectedApplication(
        device_id=device.id,
        raw_name="ActiveRoles Server",
        normalized_name="ActiveRoles Server"
    )
    test_db.add(det)
    test_db.commit()

    q_item = ApplicationResolutionQueue(
        detected_application_id=det.id,
        candidate_application_id=app_cat.id,
        match_type=MatchType.FUZZY_MATCH,
        match_score=65.0,
        status=ResolutionQueueStatus.PENDING
    )
    test_db.add(q_item)
    test_db.commit()

    res = client.post(f"/api/inventory/resolve/{q_item.id}", json={
        "accepted_application_id": app_cat.id,
        "action": "ACCEPTED"
    })
    assert res.status_code == 200
    assert res.json()["status"] == "ACCEPTED"

    test_db.refresh(det)
    assert det.resolved_application_id == app_cat.id
    assert det.resolution_type == MatchType.MANUAL_MATCH
