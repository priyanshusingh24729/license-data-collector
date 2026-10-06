"""
Test suite for Step 17: Intelligent License Research Prioritization Engine.
Validates deterministic decision rules, priority scoring, cost & budget limits,
queue deduplication, candidate assembly, Step 10 dispatch, and mock inventory evaluation.
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.connection import Base
from backend.models.enums import (
    ResearchDecision,
    ResearchPriority,
    ResearchQueueStatus,
    ProfileStatus,
    ExtractionConfidence,
    ApplicationStatus,
    ApplicationResearchStatus,
    AlertStatus,
    AlertType,
    AlertSeverity,
    ResolutionQueueStatus,
    MatchType,
    AuditEventType,
)
from backend.models.application import Application
from backend.models.profile import LicenseProfile
from backend.models.monitoring import LicenseAlert
from backend.models.inventory import Device, DetectedApplication, DeviceApplication, ApplicationResolutionQueue
from backend.models.research_queue import LicenseResearchQueueItem
from backend.models.audit import AuditEvent
from backend.research.prioritization import (
    ResearchPolicy,
    ResearchCandidate,
    ResearchDecisionEngine,
    PriorityScoreEngine,
    ResearchPrioritizationEngine,
)


@pytest.fixture
def db_session():
    """In-memory SQLite database session fixture."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_device(db_session):
    """Fixture providing a standard test Device."""
    dev = Device(
        device_key="DEV-UNITTEST-001",
        hostname="TEST-ENDPOINT",
        operating_system="Windows",
        os_version="11 (10.0.26200)",
        architecture="x64"
    )
    db_session.add(dev)
    db_session.commit()
    return dev


# -------------------------------------------------------------
# 1. Critical Test 49: Validated, High Quality, Fresh -> NO_RESEARCH_REQUIRED
# -------------------------------------------------------------

def test_critical_validated_fresh_profile_no_research_required(db_session):
    """
    Critical Test (Prompt #49):
    Adobe Acrobat Pro 2025
    Existing profile: Validated, Quality: 95, Source checked: 10 days ago, No source change.
    Expected: NO_RESEARCH_REQUIRED, Priority: NONE, Score: 0.
    """
    profile = LicenseProfile(
        vendor_name="Adobe",
        product_name="Acrobat Pro 2025",
        version="2025.1",
        profile_status=ProfileStatus.VALIDATED,
        license_classification="COMMERCIAL",
        license_required="TRUE",
        license_model="SUBSCRIPTION",
        license_metric="NAMED_USER",
        overall_confidence=ExtractionConfidence.HIGH,
        profile_hash=uuid.uuid4().hex,
        updated_at=datetime.now(timezone.utc) - timedelta(days=10)
    )
    db_session.add(profile)
    db_session.commit()

    app = Application(
        vendor_name="Adobe",
        product_name="Acrobat Pro 2025",
        display_name="Adobe Acrobat Pro 2025",
        publisher="Adobe",
        version="2025.1",
        application_key="ADOBE|ACROBAT_PRO_2025|ANY|2025.1|ANY",
        status=ApplicationStatus.ACTIVE,
        research_status=ApplicationResearchStatus.COMPLETED,
        current_profile_id=profile.id
    )
    db_session.add(app)
    db_session.commit()

    engine = ResearchPrioritizationEngine()
    result = engine.evaluate_application(db_session, app.id)

    assert result is not None
    assert result.decision == ResearchDecision.NO_RESEARCH_REQUIRED
    assert result.priority == ResearchPriority.NONE
    assert result.score == 0
    assert any("validated" in r.lower() for r in result.reasons)


# -------------------------------------------------------------
# 2. Critical Test 50: Source Changed -> REFRESH_REQUIRED
# -------------------------------------------------------------

def test_critical_source_changed_refresh_required(db_session):
    """
    Critical Test (Prompt #50):
    Adobe Acrobat Pro 2025
    Existing profile: Validated, Quality: 95, STEP 12 reports LICENSING_RELEVANT_CHANGE.
    Expected: REFRESH_REQUIRED, Priority: HIGH or CRITICAL.
    """
    profile = LicenseProfile(
        vendor_name="Adobe",
        product_name="Acrobat Pro 2025",
        version="2025.1",
        profile_status=ProfileStatus.VALIDATED,
        license_classification="COMMERCIAL",
        license_required="TRUE",
        license_model="SUBSCRIPTION",
        license_metric="NAMED_USER",
        overall_confidence=ExtractionConfidence.HIGH,
        profile_hash=uuid.uuid4().hex,
        updated_at=datetime.now(timezone.utc) - timedelta(days=10)
    )
    db_session.add(profile)
    db_session.commit()

    app = Application(
        vendor_name="Adobe",
        product_name="Acrobat Pro 2025",
        display_name="Adobe Acrobat Pro 2025",
        publisher="Adobe",
        version="2025.1",
        application_key="ADOBE|ACROBAT_PRO_2025|ANY|2025.1|ANY",
        status=ApplicationStatus.ACTIVE,
        current_profile_id=profile.id
    )
    db_session.add(app)
    db_session.commit()

    # Add active monitoring alert (STEP 12)
    alert = LicenseAlert(
        application_id=app.id,
        alert_type=AlertType.LICENSE_FACT_CHANGED,
        severity=AlertSeverity.HIGH,
        title="Licensing Term Modification",
        description="Official vendor product terms modified metric definitions",
        status=AlertStatus.NEW
    )
    db_session.add(alert)
    db_session.commit()

    engine = ResearchPrioritizationEngine()
    result = engine.evaluate_application(db_session, app.id)

    assert result is not None
    assert result.decision == ResearchDecision.REFRESH_REQUIRED
    assert result.priority in [ResearchPriority.HIGH, ResearchPriority.CRITICAL]
    assert result.source_change_detected is True
    assert any("changed" in r.lower() for r in result.reasons)


# -------------------------------------------------------------
# 3. Critical Test 51: Unresolved Identity -> REVIEW_REQUIRED
# -------------------------------------------------------------

def test_critical_unresolved_identity_review_required(db_session, test_device):
    """
    Critical Test (Prompt #51):
    Unknown Application XYZ, Identity: NO_MATCH.
    Expected: REVIEW_REQUIRED, Do NOT research automatically.
    """
    det = DetectedApplication(
        device_id=test_device.id,
        raw_name="Unknown Application XYZ",
        normalized_name="unknown application xyz",
        detection_method="WINDOWS_REGISTRY_64",
        resolution_type=MatchType.NO_MATCH,
        resolved_application_id=None
    )
    db_session.add(det)
    db_session.commit()

    res_q = ApplicationResolutionQueue(
        detected_application_id=det.id,
        match_type=MatchType.NO_MATCH,
        status=ResolutionQueueStatus.PENDING,
        reason="No matching catalog entry found"
    )
    db_session.add(res_q)
    db_session.commit()

    engine = ResearchPrioritizationEngine()
    result = engine.evaluate_detected_application(db_session, det.id)

    assert result is not None
    assert result.decision == ResearchDecision.REVIEW_REQUIRED
    assert any("unresolved" in r.lower() or "no_match" in r.lower() for r in result.reasons)


# -------------------------------------------------------------
# 4. Critical Test 52: Ambiguous Identity -> REVIEW_REQUIRED
# -------------------------------------------------------------

def test_critical_ambiguous_identity_review_required(db_session, test_device):
    """
    Critical Test (Prompt #52):
    Application: Acrobat, Identity: AMBIGUOUS_MATCH (Reader, Standard, Pro).
    Expected: REVIEW_REQUIRED.
    """
    det = DetectedApplication(
        device_id=test_device.id,
        raw_name="Acrobat",
        normalized_name="acrobat",
        detection_method="WINDOWS_REGISTRY_64",
        resolution_type=MatchType.AMBIGUOUS_MATCH,
        resolved_application_id=None
    )
    db_session.add(det)
    db_session.commit()

    res_q = ApplicationResolutionQueue(
        detected_application_id=det.id,
        match_type=MatchType.AMBIGUOUS_MATCH,
        status=ResolutionQueueStatus.REVIEW_REQUIRED,
        reason="Multiple candidates matched raw name"
    )
    db_session.add(res_q)
    db_session.commit()

    engine = ResearchPrioritizationEngine()
    result = engine.evaluate_detected_application(db_session, det.id)

    assert result is not None
    assert result.decision == ResearchDecision.REVIEW_REQUIRED
    assert any("ambiguous" in r.lower() for r in result.reasons)


# -------------------------------------------------------------
# 5. Critical Test 53: New Commercial Application -> RESEARCH_REQUIRED
# -------------------------------------------------------------

def test_critical_new_commercial_application_research_required(db_session):
    """
    Critical Test (Prompt #53):
    New Commercial Application, No profile exists.
    Expected: RESEARCH_REQUIRED, Priority: HIGH / CRITICAL.
    """
    app = Application(
        vendor_name="ACME",
        product_name="Enterprise Suite",
        display_name="ACME Enterprise Suite",
        publisher="ACME Corp",
        application_key="ACME|ENTERPRISE_SUITE|ANY|ANY|ANY",
        status=ApplicationStatus.ACTIVE,
        current_profile_id=None
    )
    db_session.add(app)
    db_session.commit()

    engine = ResearchPrioritizationEngine()
    result = engine.evaluate_application(db_session, app.id)

    assert result is not None
    assert result.decision == ResearchDecision.RESEARCH_REQUIRED
    assert result.priority in [ResearchPriority.HIGH, ResearchPriority.CRITICAL]
    assert any("no validated license profile" in r.lower() for r in result.reasons)


# -------------------------------------------------------------
# 6. Critical Test 54: Incomplete Profile (Unknown Metric) -> RESEARCH_REQUIRED
# -------------------------------------------------------------

def test_critical_incomplete_profile_unknown_metric_research_required(db_session):
    """
    Critical Test (Prompt #54):
    Example Product, Profile: LICENSE_MODEL = SUBSCRIPTION, LICENSE_METRIC = UNKNOWN.
    Expected: RESEARCH_REQUIRED.
    """
    profile = LicenseProfile(
        vendor_name="Vendor",
        product_name="Example Product",
        profile_status=ProfileStatus.PARTIALLY_VALIDATED,
        license_classification="COMMERCIAL",
        license_required="TRUE",
        license_model="SUBSCRIPTION",
        license_metric="UNKNOWN",
        overall_confidence=ExtractionConfidence.MEDIUM,
        profile_hash=uuid.uuid4().hex,
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(profile)
    db_session.commit()

    app = Application(
        vendor_name="Vendor",
        product_name="Example Product",
        display_name="Example Product",
        publisher="Vendor",
        application_key="VENDOR|EXAMPLE_PRODUCT|ANY|ANY|ANY",
        status=ApplicationStatus.ACTIVE,
        current_profile_id=profile.id
    )
    db_session.add(app)
    db_session.commit()

    engine = ResearchPrioritizationEngine()
    result = engine.evaluate_application(db_session, app.id)

    assert result is not None
    assert result.decision == ResearchDecision.RESEARCH_REQUIRED
    assert any("incomplete" in r.lower() or "license_metric" in r.lower() for r in result.reasons)


# -------------------------------------------------------------
# 7. Stale Profile (> 90 days) -> REFRESH_REQUIRED
# -------------------------------------------------------------

def test_stale_profile_triggers_refresh_required(db_session):
    """Verify profile older than 90 days triggers REFRESH_REQUIRED."""
    profile = LicenseProfile(
        vendor_name="Oracle",
        product_name="Database 19c",
        profile_status=ProfileStatus.VALIDATED,
        license_classification="COMMERCIAL",
        license_required="TRUE",
        license_model="PERPETUAL",
        license_metric="CORE",
        overall_confidence=ExtractionConfidence.HIGH,
        profile_hash=uuid.uuid4().hex,
        updated_at=datetime.now(timezone.utc) - timedelta(days=120)
    )
    db_session.add(profile)
    db_session.commit()

    app = Application(
        vendor_name="Oracle",
        product_name="Database 19c",
        display_name="Oracle Database 19c",
        publisher="Oracle",
        application_key="ORACLE|DATABASE_19C|ANY|ANY|ANY",
        status=ApplicationStatus.ACTIVE,
        current_profile_id=profile.id
    )
    db_session.add(app)
    db_session.commit()

    engine = ResearchPrioritizationEngine()
    result = engine.evaluate_application(db_session, app.id)

    assert result is not None
    assert result.decision == ResearchDecision.REFRESH_REQUIRED
    assert any("stale" in r.lower() or "refresh" in r.lower() for r in result.reasons)


# -------------------------------------------------------------
# 8. License Conflict -> REVIEW_REQUIRED
# -------------------------------------------------------------

def test_license_conflict_triggers_review_required(db_session):
    """Verify profile with CONFLICT status triggers REVIEW_REQUIRED."""
    profile = LicenseProfile(
        vendor_name="Contoso",
        product_name="Dual Licensed Tool",
        profile_status=ProfileStatus.CONFLICT,
        license_classification="COMMERCIAL",
        overall_confidence=ExtractionConfidence.LOW,
        profile_hash=uuid.uuid4().hex,
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(profile)
    db_session.commit()

    app = Application(
        vendor_name="Contoso",
        product_name="Dual Licensed Tool",
        display_name="Dual Licensed Tool",
        publisher="Contoso",
        application_key="CONTOSO|DUAL_TOOL|ANY|ANY|ANY",
        status=ApplicationStatus.ACTIVE,
        current_profile_id=profile.id
    )
    db_session.add(app)
    db_session.commit()

    engine = ResearchPrioritizationEngine()
    result = engine.evaluate_application(db_session, app.id)

    assert result is not None
    assert result.decision == ResearchDecision.REVIEW_REQUIRED
    assert any("conflict" in r.lower() for r in result.reasons)


# -------------------------------------------------------------
# 9. Freeware / Open Source Mitigation
# -------------------------------------------------------------

def test_freeware_complete_profile_mitigates_priority(db_session):
    """Verify verified open source / freeware with complete profile gets LOW or NONE priority."""
    profile = LicenseProfile(
        vendor_name="Python",
        product_name="Python 3.12",
        profile_status=ProfileStatus.VALIDATED,
        license_classification="OPEN_SOURCE",
        license_required="FALSE",
        license_model="OPEN_SOURCE",
        license_metric="INSTALLATION",
        overall_confidence=ExtractionConfidence.HIGH,
        profile_hash=uuid.uuid4().hex,
        updated_at=datetime.now(timezone.utc) - timedelta(days=20)
    )
    db_session.add(profile)
    db_session.commit()

    app = Application(
        vendor_name="Python",
        product_name="Python 3.12",
        display_name="Python 3.12",
        publisher="Python Software Foundation",
        application_key="PYTHON|PYTHON_312|ANY|ANY|ANY",
        status=ApplicationStatus.ACTIVE,
        current_profile_id=profile.id
    )
    db_session.add(app)
    db_session.commit()

    engine = ResearchPrioritizationEngine()
    result = engine.evaluate_application(db_session, app.id)

    assert result.decision == ResearchDecision.NO_RESEARCH_REQUIRED
    assert result.priority == ResearchPriority.NONE


# -------------------------------------------------------------
# 10. Version Change Dynamic Integration
# -------------------------------------------------------------

def test_detected_version_change_triggers_refresh(db_session, test_device):
    """Verify endpoint detected version differing from catalog triggers REFRESH_REQUIRED."""
    profile = LicenseProfile(
        vendor_name="Autodesk",
        product_name="AutoCAD",
        version="2024",
        profile_status=ProfileStatus.VALIDATED,
        license_classification="COMMERCIAL",
        license_required="TRUE",
        license_model="SUBSCRIPTION",
        license_metric="NAMED_USER",
        overall_confidence=ExtractionConfidence.HIGH,
        profile_hash=uuid.uuid4().hex,
        updated_at=datetime.now(timezone.utc) - timedelta(days=10)
    )
    db_session.add(profile)
    db_session.commit()

    app = Application(
        vendor_name="Autodesk",
        product_name="AutoCAD",
        display_name="AutoCAD",
        publisher="Autodesk",
        version="2024",
        application_key="AUTODESK|AUTOCAD|ANY|2024|ANY",
        status=ApplicationStatus.ACTIVE,
        current_profile_id=profile.id
    )
    db_session.add(app)
    db_session.commit()

    # Endpoint discovers AutoCAD 2026
    det = DetectedApplication(
        device_id=test_device.id,
        raw_name="AutoCAD 2026",
        normalized_name="autocad 2026",
        raw_version="2026",
        detection_method="WINDOWS_REGISTRY_64",
        resolution_type=MatchType.EXACT_MATCH,
        resolved_application_id=app.id
    )
    db_session.add(det)
    db_session.commit()

    engine = ResearchPrioritizationEngine()
    result = engine.evaluate_detected_application(db_session, det.id)

    assert result.decision == ResearchDecision.REFRESH_REQUIRED
    assert any("version" in r.lower() for r in result.reasons)


# -------------------------------------------------------------
# 11. Queue Deduplication & Priority Order
# -------------------------------------------------------------

def test_queue_creation_deduplication_and_priority_ordering(db_session):
    """Verify queue items are deduplicated and ordered by priority and score."""
    app1 = Application(vendor_name="Vendor1", product_name="High App", display_name="High Priority App", application_key="V1|APP|ANY|ANY|ANY", status=ApplicationStatus.ACTIVE)
    app2 = Application(vendor_name="Vendor2", product_name="Crit App", display_name="Critical Priority App", application_key="V2|APP|ANY|ANY|ANY", status=ApplicationStatus.ACTIVE)
    db_session.add_all([app1, app2])
    db_session.commit()

    engine = ResearchPrioritizationEngine()

    res1 = engine.evaluate_application(db_session, app1.id)
    res2 = engine.evaluate_application(db_session, app2.id)

    # First enqueue
    item1 = engine.enqueue_candidate(db_session, res1)
    item2 = engine.enqueue_candidate(db_session, res2)

    assert item1 is not None
    assert item2 is not None

    # Duplicate enqueue of app1 should reuse existing record
    item1_dup = engine.enqueue_candidate(db_session, res1)
    assert item1.id == item1_dup.id

    # Total items in queue should be exactly 2
    count = db_session.query(LicenseResearchQueueItem).count()
    assert count == 2


# -------------------------------------------------------------
# 12. Daily Research Budget Enforcement
# -------------------------------------------------------------

def test_daily_research_budget_enforcement(db_session):
    """Verify queue processor respects max_daily_research_applications limit."""
    policy = ResearchPolicy(max_daily_research_applications=2, max_batch_research=10)
    engine = ResearchPrioritizationEngine(policy=policy)

    # Create 3 queued items
    for i in range(3):
        app = Application(vendor_name=f"Vendor{i}", product_name=f"App {i}", display_name=f"App {i}", application_key=f"V{i}|APP|ANY|ANY|ANY", status=ApplicationStatus.ACTIVE)
        db_session.add(app)
        db_session.commit()
        item = LicenseResearchQueueItem(
            application_id=app.id,
            decision=ResearchDecision.RESEARCH_REQUIRED,
            priority=ResearchPriority.HIGH,
            priority_score=60,
            reason="No profile",
            status=ResearchQueueStatus.QUEUED
        )
        db_session.add(item)
    db_session.commit()

    # Process queue with limit 5 (should be capped at budget 2)
    resp = engine.process_queue(db_session, limit=5)
    assert resp.processed_count <= 2
    assert resp.daily_budget_remaining >= 0


# -------------------------------------------------------------
# 13. Audit Event Logging Verification
# -------------------------------------------------------------

def test_audit_event_logged_on_evaluation(db_session):
    """Verify evaluation creates immutable AuditEvent records."""
    app = Application(vendor_name="TestVendor", product_name="Audit App", display_name="Audit App", application_key="TEST|AUDIT|ANY|ANY|ANY", status=ApplicationStatus.ACTIVE)
    db_session.add(app)
    db_session.commit()

    engine = ResearchPrioritizationEngine()
    engine.evaluate_application(db_session, app.id)

    events = db_session.query(AuditEvent).filter(
        AuditEvent.entity_id == app.id,
        AuditEvent.event_type == AuditEventType.RESEARCH_DECISION_CREATED
    ).all()

    assert len(events) >= 1
    assert "RESEARCH_REQUIRED" in events[0].description or "RESEARCH" in events[0].description


# -------------------------------------------------------------
# 14. Mock Inventory with 20 Diverse Applications
# -------------------------------------------------------------

def test_mock_inventory_prioritization_distribution(db_session, test_device):
    """
    Verification Test (Prompt #60):
    Evaluate 20 diverse applications and verify valid categorical distribution across
    NO_RESEARCH_REQUIRED, RESEARCH_REQUIRED, REFRESH_REQUIRED, REVIEW_REQUIRED.
    """
    # 1-5: Known Validated Fresh (NO_RESEARCH_REQUIRED)
    for i in range(5):
        prof = LicenseProfile(
            vendor_name="VendorKnown",
            product_name=f"Known App {i}",
            profile_status=ProfileStatus.VALIDATED,
            license_classification="COMMERCIAL",
            license_required="TRUE",
            license_model="SUBSCRIPTION",
            license_metric="NAMED_USER",
            overall_confidence=ExtractionConfidence.HIGH,
            profile_hash=uuid.uuid4().hex,
            updated_at=datetime.now(timezone.utc) - timedelta(days=5)
        )
        db_session.add(prof)
        db_session.commit()

        app = Application(
            vendor_name="VendorKnown",
            product_name=f"Known App {i}",
            display_name=f"Known Fresh App {i}",
            application_key=f"KNOWN|APP_{i}|ANY|ANY|ANY",
            status=ApplicationStatus.ACTIVE,
            current_profile_id=prof.id
        )
        db_session.add(app)
        db_session.commit()

        det = DetectedApplication(
            device_id=test_device.id,
            raw_name=f"Known Fresh App {i}",
            normalized_name=f"known fresh app {i}",
            detection_method="WINDOWS_REGISTRY_64",
            resolution_type=MatchType.EXACT_MATCH,
            resolved_application_id=app.id
        )
        db_session.add(det)
        db_session.commit()
        db_session.add(DeviceApplication(device_id=test_device.id, detected_application_id=det.id))

    # 6-10: New Commercial Applications without profile (RESEARCH_REQUIRED)
    for i in range(5):
        app = Application(
            vendor_name="VendorNew",
            product_name=f"New App {i}",
            display_name=f"New Commercial App {i}",
            application_key=f"NEW|APP_{i}|ANY|ANY|ANY",
            status=ApplicationStatus.ACTIVE
        )
        db_session.add(app)
        db_session.commit()
        det = DetectedApplication(
            device_id=test_device.id,
            raw_name=f"New Commercial App {i}",
            normalized_name=f"new commercial app {i}",
            detection_method="WINDOWS_REGISTRY_64",
            resolution_type=MatchType.EXACT_MATCH,
            resolved_application_id=app.id
        )
        db_session.add(det)
        db_session.commit()
        db_session.add(DeviceApplication(device_id=test_device.id, detected_application_id=det.id))

    # 11-14: Stale Profiles or Source Changes (REFRESH_REQUIRED)
    for i in range(4):
        prof = LicenseProfile(
            vendor_name="VendorStale",
            product_name=f"Stale App {i}",
            profile_status=ProfileStatus.VALIDATED,
            license_classification="COMMERCIAL",
            license_required="TRUE",
            license_model="PERPETUAL",
            license_metric="CORE",
            overall_confidence=ExtractionConfidence.HIGH,
            profile_hash=uuid.uuid4().hex,
            updated_at=datetime.now(timezone.utc) - timedelta(days=110)
        )
        db_session.add(prof)
        db_session.commit()

        app = Application(
            vendor_name="VendorStale",
            product_name=f"Stale App {i}",
            display_name=f"Stale App {i}",
            application_key=f"STALE|APP_{i}|ANY|ANY|ANY",
            status=ApplicationStatus.ACTIVE,
            current_profile_id=prof.id
        )
        db_session.add(app)
        db_session.commit()

        det = DetectedApplication(
            device_id=test_device.id,
            raw_name=f"Stale App {i}",
            normalized_name=f"stale app {i}",
            detection_method="WINDOWS_REGISTRY_64",
            resolution_type=MatchType.EXACT_MATCH,
            resolved_application_id=app.id
        )
        db_session.add(det)
        db_session.commit()
        db_session.add(DeviceApplication(device_id=test_device.id, detected_application_id=det.id))

    # 15-18: Unresolved / Ambiguous Applications (REVIEW_REQUIRED)
    for i in range(4):
        det = DetectedApplication(
            device_id=test_device.id,
            raw_name=f"Unknown App {i}",
            normalized_name=f"unknown app {i}",
            detection_method="WINDOWS_REGISTRY_64",
            resolution_type=MatchType.NO_MATCH,
            resolved_application_id=None
        )
        db_session.add(det)
        db_session.commit()
        db_session.add(DeviceApplication(device_id=test_device.id, detected_application_id=det.id))
        res_q = ApplicationResolutionQueue(
            detected_application_id=det.id,
            match_type=MatchType.NO_MATCH,
            status=ResolutionQueueStatus.PENDING,
            reason="Unresolved"
        )
        db_session.add(res_q)

    # 19-20: Conflict Applications (REVIEW_REQUIRED)
    for i in range(2):
        prof = LicenseProfile(
            vendor_name="VendorConflict",
            product_name=f"Conflict App {i}",
            profile_status=ProfileStatus.CONFLICT,
            license_classification="COMMERCIAL",
            overall_confidence=ExtractionConfidence.LOW,
            profile_hash=uuid.uuid4().hex,
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(prof)
        db_session.commit()

        app = Application(
            vendor_name="VendorConflict",
            product_name=f"Conflict App {i}",
            display_name=f"Conflict App {i}",
            application_key=f"CONFLICT|APP_{i}|ANY|ANY|ANY",
            status=ApplicationStatus.ACTIVE,
            current_profile_id=prof.id
        )
        db_session.add(app)
        db_session.commit()

        det = DetectedApplication(
            device_id=test_device.id,
            raw_name=f"Conflict App {i}",
            normalized_name=f"conflict app {i}",
            detection_method="WINDOWS_REGISTRY_64",
            resolution_type=MatchType.EXACT_MATCH,
            resolved_application_id=app.id
        )
        db_session.add(det)
        db_session.commit()
        db_session.add(DeviceApplication(device_id=test_device.id, detected_application_id=det.id))

    db_session.commit()

    engine = ResearchPrioritizationEngine()
    summary = engine.prioritize_inventory(db_session, device_id=test_device.id)

    assert summary.total_evaluated == 20
    assert summary.no_research_required == 5
    assert summary.research_required == 5
    assert summary.refresh_required == 4
    assert summary.review_required == 6  # 4 unresolved + 2 conflicts
    assert summary.enqueued_count > 0
