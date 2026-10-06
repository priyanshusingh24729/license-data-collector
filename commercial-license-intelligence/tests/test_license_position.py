"""
Test suite for Step 14: License Entitlement + License Position Engine.
Covers entitlement management, metric compatibility rules, consumption tracking,
position calculations, overdeployment reporting, and separation of installation from entitlement.
"""

from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.database.connection import Base, get_db
from backend.main import app
from backend.models.enums import (
    EntitlementType,
    EntitlementStatus,
    EntitlementSourceType,
    LicensePositionStatus,
    ProfileStatus,
    ExtractionConfidence,
    DetectedAppStatus,
)
from backend.models.application import Application
from backend.models.profile import LicenseProfile
from backend.models.inventory import Device, DetectedApplication
from backend.models.entitlement import (
    LicenseEntitlement,
    LicenseConsumption,
    LicensePosition,
    LicensePositionHistory,
)
from backend.entitlement.position_result import (
    EntitlementCreateRequest,
    ConsumptionCreateRequest,
)
from backend.entitlement.entitlement_service import EntitlementService
from backend.entitlement.consumption_service import ConsumptionService
from backend.entitlement.position_engine import LicensePositionEngine
from backend.entitlement.metric_rules import MetricRules

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
# 1. Critical Test: Named-User Entitlement (Installation != Consumption)
# -------------------------------------------------------------

def test_named_user_installation_does_not_infer_consumption(test_db):
    """
    Critical Test:
    - Application: Adobe Acrobat Pro 2025
    - License Profile: SUBSCRIPTION / NAMED_USER
    - Entitlement: 35 NAMED_USER
    - Known assigned users: 30
    - Endpoint Installations: 42 devices
    - Expected Position:
      Entitled: 35, Consumed: 30, Available: 5, Overdeployment: 0, Position: OVER_LICENSED_POSITION
      (The 42 installations MUST NOT be used as consumed named users).
    """
    # 1. Setup Catalog App & Profile
    prof = LicenseProfile(
        vendor_name="Adobe", product_name="Acrobat", edition="Pro", version="2025",
        license_model="SUBSCRIPTION", license_metric="NAMED_USER",
        profile_hash="hash_acrobat_named", profile_status=ProfileStatus.VALIDATED
    )
    test_db.add(prof)
    test_db.commit()

    app_cat = Application(
        vendor_name="Adobe", product_name="Acrobat", edition="Pro", version="2025",
        display_name="Adobe Acrobat Pro 2025",
        application_key="ADOBE|ACROBAT|PRO|2025|ANY",
        current_profile_id=prof.id
    )
    test_db.add(app_cat)
    test_db.commit()

    # 2. Add 42 endpoint installations
    dev = Device(device_key="DEV-CLUSTER-01")
    test_db.add(dev)
    test_db.commit()

    for i in range(42):
        det = DetectedApplication(
            device_id=dev.id,
            raw_name=f"Adobe Acrobat Pro #{i}",
            normalized_name="Adobe Acrobat Pro",
            resolved_application_id=app_cat.id,
            status=DetectedAppStatus.ACTIVE
        )
        test_db.add(det)
    test_db.commit()

    # 3. Register Entitlement: 35 NAMED_USER
    ent_svc = EntitlementService()
    ent_svc.create_entitlement(test_db, EntitlementCreateRequest(
        application_id=app_cat.id,
        vendor_name="Adobe",
        product_name="Acrobat",
        quantity=35.0,
        metric="NAMED_USER",
        entitlement_type=EntitlementType.SUBSCRIBED
    ))

    # 4. Register Measured Consumption: 30 assigned users
    con_svc = ConsumptionService()
    con_svc.record_consumption(test_db, ConsumptionCreateRequest(
        application_id=app_cat.id,
        consumption_metric="NAMED_USER",
        consumption_quantity=30.0,
        user_reference="ASSIGNED_POOL_30"
    ))

    # 5. Calculate Position
    engine = LicensePositionEngine()
    pos = engine.calculate_position(test_db, app_cat.id)

    assert pos.entitled_quantity == 35.0
    assert pos.consumed_quantity == 30.0
    assert pos.available_quantity == 5.0
    assert pos.overdeployment_quantity == 0.0
    assert pos.installed_devices_count == 42
    assert pos.position_status == LicensePositionStatus.OVER_LICENSED_POSITION


# -------------------------------------------------------------
# 2. Critical Test: Under-Licensed Overdeployment Reporting
# -------------------------------------------------------------

def test_under_licensed_position_calculation(test_db):
    """
    Critical Test:
    - Entitlement: 35 NAMED_USER
    - Consumed: 42 NAMED_USER
    - Expected:
      Available: 0, Overdeployment: 7, Position: UNDER_LICENSED_POSITION
      (Does NOT call it a legal violation).
    """
    app_cat = Application(
        vendor_name="Oracle", product_name="Database",
        application_key="ORACLE|DATABASE|ANY|ANY|ANY"
    )
    test_db.add(app_cat)
    test_db.commit()

    ent_svc = EntitlementService()
    ent_svc.create_entitlement(test_db, EntitlementCreateRequest(
        application_id=app_cat.id,
        vendor_name="Oracle", product_name="Database",
        quantity=35.0, metric="NAMED_USER"
    ))

    con_svc = ConsumptionService()
    con_svc.record_consumption(test_db, ConsumptionCreateRequest(
        application_id=app_cat.id,
        consumption_metric="NAMED_USER",
        consumption_quantity=42.0
    ))

    engine = LicensePositionEngine()
    pos = engine.calculate_position(test_db, app_cat.id)

    assert pos.entitled_quantity == 35.0
    assert pos.consumed_quantity == 42.0
    assert pos.available_quantity == 0.0
    assert pos.overdeployment_quantity == 7.0
    assert pos.position_status == LicensePositionStatus.UNDER_LICENSED_POSITION
    assert "overdeployment of 7 NAMED_USER" in pos.status_reason


# -------------------------------------------------------------
# 3. Critical Test: Unknown Entitlement Position
# -------------------------------------------------------------

def test_unknown_entitlement_returns_unknown_position(test_db):
    """
    Critical Test:
    - Entitlement: UNKNOWN (0 registered)
    - Consumed: 42
    - Expected Position: UNKNOWN_POSITION (Must NOT output -42).
    """
    app_cat = Application(
        vendor_name="JetBrains", product_name="IntelliJ IDEA",
        application_key="JETBRAINS|INTELLIJ IDEA|ANY|ANY|ANY"
    )
    test_db.add(app_cat)
    test_db.commit()

    con_svc = ConsumptionService()
    con_svc.record_consumption(test_db, ConsumptionCreateRequest(
        application_id=app_cat.id,
        consumption_metric="USER",
        consumption_quantity=42.0
    ))

    engine = LicensePositionEngine()
    pos = engine.calculate_position(test_db, app_cat.id)

    assert pos.position_status == LicensePositionStatus.UNKNOWN_POSITION
    assert pos.entitled_quantity is None
    assert pos.available_quantity is None
    assert pos.overdeployment_quantity is None
    assert "Entitlement quantity is not available" in pos.status_reason


# -------------------------------------------------------------
# 4. Critical Test: Metric Mismatch Handled
# -------------------------------------------------------------

def test_metric_mismatch_not_calculable(test_db):
    """
    Critical Test:
    - Entitlement metric: 35 NAMED_USER
    - Consumption metric: 42 DEVICE
    - Expected Position: NOT_CALCULABLE with METRIC_MISMATCH reason.
    """
    app_cat = Application(
        vendor_name="Atlassian", product_name="Jira",
        application_key="ATLASSIAN|JIRA|ANY|ANY|ANY"
    )
    test_db.add(app_cat)
    test_db.commit()

    ent_svc = EntitlementService()
    ent_svc.create_entitlement(test_db, EntitlementCreateRequest(
        application_id=app_cat.id,
        vendor_name="Atlassian", product_name="Jira",
        quantity=35.0, metric="NAMED_USER"
    ))

    con_svc = ConsumptionService()
    con_svc.record_consumption(test_db, ConsumptionCreateRequest(
        application_id=app_cat.id,
        consumption_metric="DEVICE",
        consumption_quantity=42.0
    ))

    engine = LicensePositionEngine()
    pos = engine.calculate_position(test_db, app_cat.id)

    assert pos.position_status == LicensePositionStatus.NOT_CALCULABLE
    assert "METRIC_MISMATCH" in pos.status_reason


# -------------------------------------------------------------
# 5. Expired Entitlements Handling
# -------------------------------------------------------------

def test_expired_entitlement_excluded(test_db):
    """Verify entitlements whose end_date is in the past are marked EXPIRED and excluded from available pool."""
    app_cat = Application(
        vendor_name="VMware", product_name="vSphere",
        application_key="VMWARE|VSPHERE|ANY|ANY|ANY"
    )
    test_db.add(app_cat)
    test_db.commit()

    past_date = datetime.now(timezone.utc) - timedelta(days=30)
    ent_svc = EntitlementService()
    ent_svc.create_entitlement(test_db, EntitlementCreateRequest(
        application_id=app_cat.id,
        vendor_name="VMware", product_name="vSphere",
        quantity=50.0, metric="CORE",
        license_end_date=past_date
    ))

    # All active entitlements are expired
    engine = LicensePositionEngine()
    pos = engine.calculate_position(test_db, app_cat.id)

    assert pos.position_status == LicensePositionStatus.UNKNOWN_POSITION


# -------------------------------------------------------------
# 6. Device Metric Derivation & History Snapshots
# -------------------------------------------------------------

def test_device_metric_derivation_and_history_snapshots(test_db, client):
    """
    Test:
    - Application with DEVICE metric automatically derives consumption from 3 active installations.
    - Historical snapshots recorded in license_position_history.
    """
    app_cat = Application(
        vendor_name="Acme", product_name="CAD Tool",
        application_key="ACME|CAD TOOL|ANY|ANY|ANY"
    )
    dev = Device(device_key="DEV-CAD-01")
    test_db.add_all([app_cat, dev])
    test_db.commit()

    for i in range(3):
        test_db.add(DetectedApplication(
            device_id=dev.id,
            raw_name="CAD Tool",
            normalized_name="CAD Tool",
            resolved_application_id=app_cat.id,
            status=DetectedAppStatus.ACTIVE
        ))
    test_db.commit()

    # Create Entitlement: 5 DEVICE
    client.post("/api/entitlements", json={
        "application_id": app_cat.id,
        "vendor_name": "Acme",
        "product_name": "CAD Tool",
        "quantity": 5.0,
        "metric": "DEVICE",
        "entitlement_type": "PURCHASED"
    })

    # Calculate Position
    calc_res = client.post(f"/api/license-position/{app_cat.id}/calculate")
    assert calc_res.status_code == 200
    data = calc_res.json()
    assert data["entitled_quantity"] == 5.0
    assert data["consumed_quantity"] == 3.0
    assert data["available_quantity"] == 2.0
    assert data["position_status"] == "OVER_LICENSED_POSITION"

    # Verify History endpoint
    hist_res = client.get(f"/api/license-position/{app_cat.id}/history")
    assert hist_res.status_code == 200
    assert len(hist_res.json()) >= 1
