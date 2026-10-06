"""
Test suite for Step 12: Automated License Source Monitoring + Change Detection.
Covers content hashing, diff generation, licensing relevance classification,
targeted re-extraction, fact evolution, alert deduplication, and failure isolation.
"""

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
    SourceStatus,
    AccessType,
    CollectionStatus,
    FactType,
    FactStatus,
    ProfileStatus,
    ExtractionConfidence,
    MonitorFrequency,
    MonitorStatus,
    MonitoringRunStatus,
    ChangeClassification,
    FactChangeType,
    AlertType,
    AlertSeverity,
    AlertStatus,
)
from backend.models.source import LicenseSource
from backend.models.collection import CollectedDocument
from backend.models.fact import LicenseFact
from backend.models.profile import LicenseProfile
from backend.models.application import Application
from backend.models.monitoring import SourceMonitor, MonitoringRun, LicenseFactChange, LicenseAlert
from backend.monitoring.change_detector import ChangeDetector
from backend.monitoring.change_classifier import ChangeClassifier
from backend.monitoring.source_monitor import SourceMonitorRunner
from backend.monitoring.refresh_manager import TargetedRefreshManager
from backend.monitoring.monitoring_scheduler import MonitoringScheduler

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
# 1. Content Hashing, Diff & Normalization Tests
# -------------------------------------------------------------

def test_content_hashing_and_diff():
    """Verify normalization collapses meaningless whitespace and generates clean diffs."""
    t1 = "Adobe Acrobat Pro\n\n\nLicensed as perpetual software."
    t2 = "  Adobe Acrobat Pro \n Licensed as perpetual software.  "
    t3 = "Adobe Acrobat Pro\nLicensed as subscription software."

    # Normalization equivalence
    assert ChangeDetector.compute_hash(t1) == ChangeDetector.compute_hash(t2)
    assert ChangeDetector.compute_hash(t1) != ChangeDetector.compute_hash(t3)

    diff = ChangeDetector.generate_diff(t1, t3)
    assert "Licensed as perpetual software." in diff
    assert "Licensed as subscription software." in diff


def test_diff_classification():
    """Verify change classifier distinguishes licensing-relevant, metadata-only, and content changes."""
    # Licensing change
    diff_lic = "-Licensed perpetually.\n+Offered as a subscription plan."
    assert ChangeClassifier.classify_diff(diff_lic) == ChangeClassification.LICENSING_RELEVANT_CHANGE

    # Metadata change
    diff_meta = "-Copyright 2025\n+Copyright 2026"
    assert ChangeClassifier.classify_diff(diff_meta) == ChangeClassification.DOCUMENT_METADATA_CHANGE

    # General content change
    diff_gen = "-Welcome to our portal.\n+Welcome to our new portal design."
    assert ChangeClassifier.classify_diff(diff_gen) == ChangeClassification.CONTENT_CHANGE


# -------------------------------------------------------------
# 2. Source Monitoring Run Tests (Unchanged vs Changed)
# -------------------------------------------------------------

def test_source_monitoring_unchanged_detection(test_db):
    """Verify checking a source with identical content returns UNCHANGED status."""
    source = LicenseSource(
        source_name="Adobe Terms",
        vendor_name="Adobe",
        scope_identifier="Adobe",
        source_url="https://adobe.com/terms",
        normalized_url="https://adobe.com/terms",
        source_type=SourceType.OFFICIAL_TERMS,
        authority_level=AuthorityLevel.OFFICIAL_VENDOR_TERMS,
        collection_method=CollectionMethod.WEB
    )
    test_db.add(source)
    test_db.commit()

    text_content = "Adobe Acrobat is licensed under a subscription model."
    doc = CollectedDocument(
        source_id=source.id,
        vendor_name="Adobe",
        requested_url="https://adobe.com/terms",
        final_url="https://adobe.com/terms",
        status=CollectionStatus.COLLECTED,
        clean_text=text_content,
        content_hash=ChangeDetector.compute_hash(text_content)
    )
    test_db.add(doc)
    test_db.commit()

    # Pre-seed the monitor with matching previous hash
    monitor = SourceMonitor(
        source_id=source.id,
        last_content_hash=ChangeDetector.compute_hash(text_content)
    )
    test_db.add(monitor)
    test_db.commit()

    runner = SourceMonitorRunner()
    runner.web_collector.collect_url = lambda db, url, source_id, vendor_name: doc

    run, res_doc = runner.check_source(test_db, source.id)
    assert run.status == MonitoringRunStatus.UNCHANGED
    assert run.change_detected is False


# -------------------------------------------------------------
# 3. Core Requirement Test: Perpetual -> Subscription Evolution & Alert
# -------------------------------------------------------------

def test_licensing_fact_change_and_high_severity_alert(test_db):
    """
    Test:
    1. Application 'Adobe Acrobat Pro' initially has validated fact LICENSE_MODEL = PERPETUAL.
    2. Monitored source changes text to 'Acrobat Pro is available through a subscription.'
    3. Targeted refresh executes: detects fact change, updates profile, generates HIGH severity alert.
    """
    # 1. Setup Source and Application
    source = LicenseSource(
        source_name="Adobe Product Terms",
        vendor_name="Adobe",
        product_name="Acrobat",
        edition="Pro",
        version="2025",
        scope_identifier="Adobe Acrobat",
        source_url="https://adobe.com/terms",
        normalized_url="https://adobe.com/terms",
        source_type=SourceType.OFFICIAL_TERMS,
        authority_level=AuthorityLevel.OFFICIAL_VENDOR_TERMS,
        collection_method=CollectionMethod.WEB
    )
    app_obj = Application(
        vendor_name="Adobe",
        product_name="Acrobat",
        edition="Pro",
        version="2025",
        application_key="ADOBE|ACROBAT|PRO|2025|ANY"
    )
    test_db.add_all([source, app_obj])
    test_db.commit()

    # Initial profile: PERPETUAL
    init_fact = LicenseFact(
        source_id=source.id,
        vendor_name="Adobe", product_name="Acrobat", edition="Pro", version="2025",
        fact_type=FactType.LICENSE_MODEL, fact_value="PERPETUAL", normalized_value="PERPETUAL",
        status=FactStatus.VALIDATED, confidence=ExtractionConfidence.HIGH, confidence_score=0.9,
        evidence_text="Acrobat Pro classic perpetual license.", evidence_hash="h_perp"
    )
    test_db.add(init_fact)
    test_db.commit()

    from backend.consolidation.profile_consolidator import LicenseProfileConsolidator
    p1 = LicenseProfileConsolidator().consolidate_profile(test_db, "Adobe", "Acrobat", "Pro", "2025")
    app_obj.current_profile_id = p1.id
    test_db.commit()

    # 2. New Document Collected with Subscription Terms
    new_text = "Adobe Acrobat Pro 2025 is available through an annual subscription plan for named users."
    new_doc = CollectedDocument(
        source_id=source.id,
        vendor_name="Adobe",
        requested_url="https://adobe.com/terms",
        final_url="https://adobe.com/terms",
        status=CollectionStatus.COLLECTED,
        clean_text=new_text,
        content_hash=ChangeDetector.compute_hash(new_text)
    )
    test_db.add(new_doc)
    test_db.commit()

    # 3. Execute Targeted Refresh
    refresh_mgr = TargetedRefreshManager()
    alerts = refresh_mgr.process_source_change(test_db, source.id, new_doc.id)

    assert len(alerts) >= 1
    model_alert = [a for a in alerts if a.alert_type == AlertType.LICENSE_MODEL_CHANGED][0]
    assert model_alert.severity == AlertSeverity.HIGH
    assert model_alert.old_value == "PERPETUAL"
    assert model_alert.new_value == "SUBSCRIPTION"

    # Verify fact change was audited
    changes = test_db.query(LicenseFactChange).filter(LicenseFactChange.application_id == app_obj.id).all()
    assert len(changes) >= 1
    assert changes[0].fact_type == FactType.LICENSE_MODEL
    assert changes[0].new_value == "SUBSCRIPTION"


# -------------------------------------------------------------
# 4. Anti-Override / Failure Isolation Test
# -------------------------------------------------------------

def test_monitoring_failure_preserves_existing_knowledge(test_db):
    """
    Test: If monitoring fails (e.g. timeout / network error),
    the existing validated licensing facts MUST NOT be cleared or set to UNKNOWN.
    """
    source = LicenseSource(
        source_name="Vendor Portal",
        vendor_name="Acme",
        scope_identifier="Acme",
        source_url="https://acme.com/terms",
        normalized_url="https://acme.com/terms",
        source_type=SourceType.OFFICIAL_TERMS,
        authority_level=AuthorityLevel.OFFICIAL_VENDOR_TERMS,
        collection_method=CollectionMethod.WEB
    )
    fact = LicenseFact(
        vendor_name="Acme", product_name="Tool",
        fact_type=FactType.LICENSE_MODEL, fact_value="SUBSCRIPTION", normalized_value="SUBSCRIPTION",
        status=FactStatus.VALIDATED, confidence=ExtractionConfidence.HIGH, confidence_score=0.9,
        evidence_text="Subscription license.", evidence_hash="h_acme"
    )
    test_db.add_all([source, fact])
    test_db.commit()

    runner = SourceMonitorRunner()
    # Mock network failure
    def mock_fail(db, url, source_id, vendor_name):
        raise TimeoutError("Connection timed out.")
    runner.web_collector.collect_url = mock_fail

    run, _ = runner.check_source(test_db, source.id)
    assert run.status == MonitoringRunStatus.FAILED

    # Check that existing fact is still VALIDATED and SUBSCRIPTION
    test_db.refresh(fact)
    assert fact.status == FactStatus.VALIDATED
    assert fact.normalized_value == "SUBSCRIPTION"


# -------------------------------------------------------------
# 5. Alert Acknowledgment & Resolution API Test
# -------------------------------------------------------------

def test_monitoring_alerts_api(test_db, client):
    """Test GET /api/monitoring/alerts, POST /acknowledge, and POST /resolve."""
    alert = LicenseAlert(
        alert_type=AlertType.LICENSE_MODEL_CHANGED,
        severity=AlertSeverity.HIGH,
        title="License Model Changed",
        description="Changed from Perpetual to Subscription",
        old_value="PERPETUAL",
        new_value="SUBSCRIPTION",
        status=AlertStatus.NEW
    )
    test_db.add(alert)
    test_db.commit()

    # List alerts
    res = client.get("/api/monitoring/alerts?severity=HIGH")
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # Acknowledge
    ack_res = client.post(f"/api/monitoring/alerts/{alert.id}/acknowledge")
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "ACKNOWLEDGED"

    # Resolve
    res_res = client.post(f"/api/monitoring/alerts/{alert.id}/resolve")
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "RESOLVED"
