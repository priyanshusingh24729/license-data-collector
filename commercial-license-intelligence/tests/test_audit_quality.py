"""
Test suite for Step 15: License Intelligence Audit + Quality Dashboard.
Covers audit events, evidence lineage, profile field explanations, deterministic quality scoring,
critical field coverage, source freshness (stale source tracking), position explanations, and audit export.
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
    SourceType,
    AuthorityLevel,
    CollectionMethod,
    FactType,
    FactStatus,
    ExtractionConfidence,
    ProfileStatus,
    QualityCategory,
    QualityIssueType,
    AuditEventType,
    IssueStatus,
)
from backend.models.application import Application
from backend.models.profile import LicenseProfile
from backend.models.fact import LicenseFact, LicenseEvidence
from backend.models.source import LicenseSource
from backend.models.collection import CollectedDocument
from backend.models.monitoring import SourceMonitor
from backend.models.audit import AuditEvent, QualityIssue
from backend.audit.quality_engine import ApplicationQualityEngine
from backend.audit.evidence_lineage import EvidenceLineageService
from backend.audit.audit_service import AuditService
from backend.audit.quality_service import QualityService

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
# 1. Critical Audit Test: Multi-Hop Evidence Lineage
# -------------------------------------------------------------

def test_evidence_chain_and_field_explanation(test_db):
    """
    Critical Audit Test:
    Trace: Application -> License Profile (SUBSCRIPTION) -> Validated Fact -> Evidence -> Document -> Official Source.
    """
    # 1. Setup Source, Document, Fact, Profile, Application
    source = LicenseSource(
        source_name="Adobe Official Terms",
        vendor_name="Adobe",
        product_name="Acrobat",
        scope_identifier="Adobe Acrobat",
        source_url="https://adobe.com/terms",
        normalized_url="https://adobe.com/terms",
        authority_level=AuthorityLevel.OFFICIAL_VENDOR_TERMS,
        collection_method=CollectionMethod.WEB
    )
    test_db.add(source)
    test_db.commit()

    doc = CollectedDocument(
        source_id=source.id,
        vendor_name="Adobe",
        requested_url="https://adobe.com/terms",
        final_url="https://adobe.com/terms",
        clean_text="Adobe Acrobat is licensed on an annual subscription basis."
    )
    test_db.add(doc)
    test_db.commit()

    fact = LicenseFact(
        source_id=source.id,
        document_id=doc.id,
        vendor_name="Adobe",
        product_name="Acrobat",
        edition="Pro",
        version="2025",
        fact_type=FactType.LICENSE_MODEL,
        fact_value="SUBSCRIPTION",
        normalized_value="SUBSCRIPTION",
        status=FactStatus.VALIDATED,
        confidence=ExtractionConfidence.HIGH,
        confidence_score=0.95,
        page_number=4,
        evidence_text="licensed on an annual subscription basis",
        evidence_hash="hash_acrobat_sub_p4",
        verified_at=datetime.now(timezone.utc)
    )
    test_db.add(fact)
    test_db.commit()

    profile = LicenseProfile(
        vendor_name="Adobe",
        product_name="Acrobat",
        edition="Pro",
        version="2025",
        license_model="SUBSCRIPTION",
        license_metric="NAMED_USER",
        license_required="TRUE",
        license_classification="COMMERCIAL",
        profile_hash="hash_profile_adobe",
        profile_status=ProfileStatus.VALIDATED,
        overall_confidence=ExtractionConfidence.HIGH
    )
    test_db.add(profile)
    test_db.commit()

    app_cat = Application(
        vendor_name="Adobe",
        product_name="Acrobat",
        edition="Pro",
        version="2025",
        application_key="ADOBE|ACROBAT|PRO|2025|ANY",
        current_profile_id=profile.id
    )
    test_db.add(app_cat)
    test_db.commit()

    # 2. Lineage Test
    lineage_svc = EvidenceLineageService()
    chain = lineage_svc.get_evidence_chain_for_application(test_db, app_cat.id)

    assert chain.application_id == app_cat.id
    assert chain.sources_count >= 1
    assert chain.documents_count >= 1
    assert chain.validated_facts_count >= 1
    assert len(chain.lineage) >= 1
    assert chain.lineage[0]["source"]["name"] == "Adobe Official Terms"
    assert chain.lineage[0]["document"]["page_number"] == 4

    # 3. Field Explanation Test
    field_exp = lineage_svc.explain_profile_field(test_db, profile.id, "license_model")
    assert field_exp.field == "license_model"
    assert field_exp.value == "SUBSCRIPTION"
    assert len(field_exp.supporting_facts) == 1
    assert field_exp.supporting_facts[0].fact_id == fact.id
    assert field_exp.supporting_facts[0].evidence_text == "licensed on an annual subscription basis"


# -------------------------------------------------------------
# 2. Critical Quality Test: Quality Score & Incomplete Fields
# -------------------------------------------------------------

def test_deterministic_quality_score_and_coverage(test_db):
    """
    Critical Quality Test:
    Application has:
    LICENSE_REQUIRED = VALIDATED (+10)
    LICENSE_MODEL = VALIDATED (+10)
    LICENSE_METRIC = UNKNOWN (0)
    CLASSIFICATION = VALIDATED (+10)
    Coverage: 75%
    Expected: Quality score below 100, metric coverage flagged UNKNOWN.
    """
    source = LicenseSource(
        source_name="Acme Terms",
        vendor_name="Acme",
        product_name="Widget",
        scope_identifier="Acme Widget",
        source_url="https://acme.com/terms",
        normalized_url="https://acme.com/terms",
        authority_level=AuthorityLevel.OFFICIAL_VENDOR
    )
    test_db.add(source)
    test_db.commit()

    app_cat = Application(
        vendor_name="Acme",
        product_name="Widget",
        application_key="ACME|WIDGET|ANY|ANY|ANY"
    )
    test_db.add(app_cat)
    test_db.commit()

    # Add 3 validated facts (excluding LICENSE_METRIC)
    f1 = LicenseFact(source_id=source.id, vendor_name="Acme", product_name="Widget", fact_type=FactType.LICENSE_REQUIRED, fact_value="TRUE", normalized_value="TRUE", status=FactStatus.VALIDATED, confidence_score=0.9, evidence_text="Requires license.", evidence_hash="h1")
    f2 = LicenseFact(source_id=source.id, vendor_name="Acme", product_name="Widget", fact_type=FactType.LICENSE_MODEL, fact_value="SUBSCRIPTION", normalized_value="SUBSCRIPTION", status=FactStatus.VALIDATED, confidence_score=0.9, evidence_text="Subscription model.", evidence_hash="h2")
    f3 = LicenseFact(source_id=source.id, vendor_name="Acme", product_name="Widget", fact_type=FactType.LICENSE_CLASSIFICATION, fact_value="COMMERCIAL", normalized_value="COMMERCIAL", status=FactStatus.VALIDATED, confidence_score=0.9, evidence_text="Commercial software.", evidence_hash="h3")
    test_db.add_all([f1, f2, f3])
    test_db.commit()

    prof = LicenseProfile(
        vendor_name="Acme", product_name="Widget",
        license_required="TRUE", license_model="SUBSCRIPTION",
        license_metric="UNKNOWN", license_classification="COMMERCIAL",
        profile_hash="hash_profile_widget",
        profile_status=ProfileStatus.PARTIALLY_VALIDATED
    )
    test_db.add(prof)
    test_db.commit()
    app_cat.current_profile_id = prof.id
    test_db.commit()

    q_engine = ApplicationQualityEngine()
    q_res = q_engine.evaluate_application_quality(test_db, app_cat.id)

    assert q_res.critical_field_coverage_percent == 75.0
    assert q_res.license_metric_status == "UNKNOWN"
    assert q_res.quality_score < 100.0
    assert any("License Metric is UNKNOWN" in neg for neg in q_res.negative_factors)


# -------------------------------------------------------------
# 3. Critical Stale Test: Stale Source Tracking (Preserves Knowledge)
# -------------------------------------------------------------

def test_stale_source_preserves_validated_knowledge(test_db):
    """
    Critical Stale Test:
    Last source check: 120 days ago (Threshold: 90 days).
    Expected: Flagged STALE in quality report, but existing validated facts remain VALIDATED.
    """
    source = LicenseSource(
        source_name="Old Portal",
        vendor_name="LegacyCorp",
        product_name="LegacyApp",
        scope_identifier="LegacyCorp",
        source_url="https://legacy.com/terms",
        normalized_url="https://legacy.com/terms",
        authority_level=AuthorityLevel.OFFICIAL_VENDOR
    )
    test_db.add(source)
    test_db.commit()

    # Monitored 120 days ago
    check_date = datetime.now(timezone.utc) - timedelta(days=120)
    monitor = SourceMonitor(
        source_id=source.id,
        last_checked_at=check_date,
        last_content_hash="hash_legacy_120d"
    )
    test_db.add(monitor)

    fact = LicenseFact(
        source_id=source.id,
        vendor_name="LegacyCorp",
        product_name="LegacyApp",
        fact_type=FactType.LICENSE_MODEL,
        fact_value="PERPETUAL",
        normalized_value="PERPETUAL",
        status=FactStatus.VALIDATED,
        confidence_score=0.9,
        evidence_text="Licensed perpetually.",
        evidence_hash="hash_leg_120"
    )
    test_db.add(fact)

    app_cat = Application(
        vendor_name="LegacyCorp", product_name="LegacyApp",
        application_key="LEGACYCORP|LEGACYAPP|ANY|ANY|ANY"
    )
    test_db.add(app_cat)
    test_db.commit()

    q_engine = ApplicationQualityEngine(freshness_days=90)
    q_res = q_engine.evaluate_application_quality(test_db, app_cat.id)

    assert q_res.is_source_stale is True
    assert q_res.days_since_last_check >= 120

    # Verify fact remains VALIDATED
    test_db.refresh(fact)
    assert fact.status == FactStatus.VALIDATED
    assert fact.normalized_value == "PERPETUAL"


# -------------------------------------------------------------
# 4. Critical Position Test: Structured Explanation
# -------------------------------------------------------------

def test_structured_position_audit_explanation(test_db, client):
    """
    Critical Position Test:
    Entitlement: 35 NAMED_USER
    Consumption: 30 NAMED_USER
    Expected Explanation: 35 - 30 = 5 (Position: 5 AVAILABLE).
    """
    app_cat = Application(
        vendor_name="TestVendor", product_name="TestTool",
        application_key="TESTVENDOR|TESTTOOL|ANY|ANY|ANY"
    )
    test_db.add(app_cat)
    test_db.commit()

    from backend.entitlement.entitlement_service import EntitlementService
    from backend.entitlement.consumption_service import ConsumptionService
    from backend.entitlement.position_result import EntitlementCreateRequest, ConsumptionCreateRequest

    EntitlementService().create_entitlement(test_db, EntitlementCreateRequest(
        application_id=app_cat.id,
        vendor_name="TestVendor", product_name="TestTool",
        quantity=35.0, metric="NAMED_USER"
    ))
    ConsumptionService().record_consumption(test_db, ConsumptionCreateRequest(
        application_id=app_cat.id,
        consumption_metric="NAMED_USER",
        consumption_quantity=30.0
    ))

    # Test GET /api/audit/position/{id}
    res = client.get(f"/api/audit/position/{app_cat.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["entitled_quantity"] == 35.0
    assert data["consumed_quantity"] == 30.0
    assert data["available_quantity"] == 5.0
    assert "35 - 30 = 5" in data["calculation_formula"]
    assert data["position_status"] == "OVER_LICENSED_POSITION"


# -------------------------------------------------------------
# 5. Quality Issues Management & Audit CSV Export
# -------------------------------------------------------------

def test_quality_issues_and_audit_export(test_db, client):
    """Test scanning quality issues, resolving an issue, and exporting audit CSV."""
    app_cat = Application(
        vendor_name="IncompleteVendor", product_name="IncompleteTool",
        application_key="INCOMPLETE|TOOL|ANY|ANY|ANY"
    )
    test_db.add(app_cat)
    test_db.commit()

    q_svc = QualityService()
    issues = q_svc.scan_application_issues(test_db, app_cat.id)
    assert len(issues) >= 1

    # List issues API
    res_list = client.get(f"/api/quality/issues?application_id={app_cat.id}")
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1
    issue_id = res_list.json()[0]["id"]

    # Resolve issue API
    res_resolve = client.post(f"/api/quality/issues/{issue_id}/resolve")
    assert res_resolve.status_code == 200
    assert res_resolve.json()["status"] == "RESOLVED"

    # Export CSV API
    res_csv = client.get("/api/audit/export/csv")
    assert res_csv.status_code == 200
    assert "Application / Vendor" in res_csv.text
