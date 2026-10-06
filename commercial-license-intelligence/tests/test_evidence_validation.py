"""
Test suite for Step 8: Evidence Validation & License Intelligence Quality Engine.
Verifies multi-dimensional validation checks, quality scoring, anti-hallucination rules,
cross-product pollution protection, edition/version boundaries, and conflict handling.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.database.connection import Base, get_db
from backend.main import app
from backend.models.enums import (
    FactType,
    FactStatus,
    EvidenceType,
    ExtractionConfidence,
    AuthorityLevel,
    ScopeType,
    CollectionStatus,
)
from backend.models.source import LicenseSource
from backend.models.collection import CollectedDocument, DocumentPage
from backend.models.fact import LicenseFact, LicenseEvidence
from backend.models.validation import FactValidationRun
from backend.validation.evidence_validator import EvidenceValidator
from backend.validation.product_validator import ProductValidator
from backend.validation.edition_validator import EditionValidator
from backend.validation.version_validator import VersionValidator
from backend.validation.quality_engine import QualityEngine
from backend.validation.conflict_detector import ValidationConflictDetector
from backend.validation.fact_validator import FactValidator

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
# 1. Strong Evidence Validation Test
# -------------------------------------------------------------

def test_strong_evidence_becomes_validated(test_db):
    """
    Test: Official vendor document with exact product match, edition match, and direct statement
    becomes VALIDATED with HIGH/VERY_HIGH quality.
    """
    doc = CollectedDocument(
        vendor_name="Adobe",
        requested_url="https://www.adobe.com/acrobat/terms.html",
        final_url="https://www.adobe.com/acrobat/terms.html",
        status=CollectionStatus.COLLECTED,
        clean_text="Adobe Acrobat Pro is licensed on a named-user subscription basis.",
        content_hash="adobe_doc_hash_1"
    )
    test_db.add(doc)
    test_db.commit()

    fact = LicenseFact(
        vendor_name="Adobe",
        product_name="Acrobat",
        edition="Pro",
        version="2025",
        fact_type=FactType.LICENSE_MODEL,
        fact_value="subscription",
        normalized_value="SUBSCRIPTION",
        scope_type=ScopeType.PRODUCT,
        scope_value="Acrobat",
        document_id=doc.id,
        evidence_text="Adobe Acrobat Pro is licensed on a named-user subscription basis.",
        evidence_hash="ev_hash_1",
        status=FactStatus.EXTRACTED
    )
    test_db.add(fact)
    test_db.commit()

    validator = FactValidator()
    res = validator.validate_fact(test_db, fact, target_vendor="Adobe", target_product="Acrobat", target_edition="Pro", target_version="2025")

    assert res.status == FactStatus.VALIDATED
    assert res.quality in [ExtractionConfidence.VERY_HIGH, ExtractionConfidence.HIGH]
    assert res.checks.evidence_exists is True
    assert res.checks.evidence_text_matched is True
    assert res.checks.product_match is True
    assert res.checks.edition_match is True


# -------------------------------------------------------------
# 2. Missing / Fabricated Evidence Text Rejection
# -------------------------------------------------------------

def test_fabricated_evidence_text_is_rejected(test_db):
    """
    Test: LLM claims a fact with evidence text that does not exist in the source document.
    MUST be REJECTED with EVIDENCE_TEXT_NOT_FOUND.
    """
    doc = CollectedDocument(
        vendor_name="Microsoft",
        requested_url="https://www.microsoft.com/terms",
        final_url="https://www.microsoft.com/terms",
        status=CollectionStatus.COLLECTED,
        clean_text="This document discusses general support lifecycle policies.",
        content_hash="ms_doc_hash_2"
    )
    test_db.add(doc)
    test_db.commit()

    fact = LicenseFact(
        vendor_name="Microsoft",
        product_name="SQL Server",
        fact_type=FactType.LICENSE_METRIC,
        fact_value="CORE",
        normalized_value="CORE",
        document_id=doc.id,
        evidence_text="Fabricated sentence that does not exist in document: SQL Server is licensed per core.",
        evidence_hash="fake_hash",
        status=FactStatus.EXTRACTED
    )
    test_db.add(fact)
    test_db.commit()

    validator = FactValidator()
    res = validator.validate_fact(test_db, fact)

    assert res.status == FactStatus.REJECTED
    assert res.checks.evidence_text_matched is False
    assert any("EVIDENCE_TEXT_NOT_FOUND" in r for r in res.reasons)


# -------------------------------------------------------------
# 3. Anti-Hallucination & Weak Evidence Tests
# -------------------------------------------------------------

def test_weak_sign_in_evidence_cannot_validate_subscription(test_db):
    """
    Test: 'Users must sign in to access the application.'
    Must NOT become VALIDATED for LICENSE_MODEL = SUBSCRIPTION.
    Becomes REVIEW_REQUIRED with semantic failure reason.
    """
    doc = CollectedDocument(
        vendor_name="Adobe",
        requested_url="https://www.adobe.com/auth.html",
        final_url="https://www.adobe.com/auth.html",
        status=CollectionStatus.COLLECTED,
        clean_text="Users must sign in to access the application and view documents.",
        content_hash="sign_in_hash"
    )
    test_db.add(doc)
    test_db.commit()

    fact = LicenseFact(
        vendor_name="Adobe",
        product_name="Acrobat",
        edition="Pro",
        fact_type=FactType.LICENSE_MODEL,
        fact_value="subscription",
        normalized_value="SUBSCRIPTION",
        document_id=doc.id,
        evidence_text="Users must sign in to access the application and view documents.",
        evidence_hash="auth_hash",
        status=FactStatus.EXTRACTED
    )
    test_db.add(fact)
    test_db.commit()

    validator = FactValidator()
    res = validator.validate_fact(test_db, fact)

    assert res.status == FactStatus.REVIEW_REQUIRED
    assert any("INSUFFICIENT_EVIDENCE" in r for r in res.reasons)


# -------------------------------------------------------------
# 4. Cross-Product Pollution Rejection
# -------------------------------------------------------------

def test_cross_product_evidence_is_rejected(test_db):
    """
    Test: Fact for 'Adobe Acrobat Pro' with evidence exclusively from 'Adobe Photoshop'.
    Must be REJECTED.
    """
    doc = CollectedDocument(
        vendor_name="Adobe",
        requested_url="https://www.adobe.com/photoshop/terms.html",
        final_url="https://www.adobe.com/photoshop/terms.html",
        status=CollectionStatus.COLLECTED,
        clean_text="Adobe Photoshop is licensed under a creative cloud subscription plan.",
        content_hash="ps_hash"
    )
    test_db.add(doc)
    test_db.commit()

    fact = LicenseFact(
        vendor_name="Adobe",
        product_name="Acrobat",
        fact_type=FactType.LICENSE_MODEL,
        fact_value="subscription",
        normalized_value="SUBSCRIPTION",
        document_id=doc.id,
        evidence_text="Adobe Photoshop is licensed under a creative cloud subscription plan.",
        evidence_hash="ps_ev_hash",
        status=FactStatus.EXTRACTED
    )
    test_db.add(fact)
    test_db.commit()

    validator = FactValidator()
    res = validator.validate_fact(test_db, fact, target_product="Acrobat")

    assert res.status == FactStatus.REJECTED
    assert res.checks.product_match is False
    assert any("CROSS_PRODUCT_POLLUTION" in r for r in res.reasons)


# -------------------------------------------------------------
# 5. Edition Mismatch Validation
# -------------------------------------------------------------

def test_edition_mismatch_yields_review_required(test_db):
    """
    Test: Fact evaluated for 'Acrobat Pro', but evidence references 'Acrobat Reader'.
    Yields REVIEW_REQUIRED.
    """
    doc = CollectedDocument(
        vendor_name="Adobe",
        requested_url="https://www.adobe.com/reader/terms.html",
        final_url="https://www.adobe.com/reader/terms.html",
        status=CollectionStatus.COLLECTED,
        clean_text="Adobe Acrobat Reader is available free of charge for personal viewing.",
        content_hash="reader_hash"
    )
    test_db.add(doc)
    test_db.commit()

    fact = LicenseFact(
        vendor_name="Adobe",
        product_name="Acrobat",
        edition="Pro",
        fact_type=FactType.LICENSE_CLASSIFICATION,
        fact_value="FREEWARE",
        normalized_value="FREEWARE",
        document_id=doc.id,
        evidence_text="Adobe Acrobat Reader is available free of charge for personal viewing.",
        evidence_hash="reader_ev_hash",
        status=FactStatus.EXTRACTED
    )
    test_db.add(fact)
    test_db.commit()

    validator = FactValidator()
    res = validator.validate_fact(test_db, fact, target_edition="Pro")

    assert res.status == FactStatus.REVIEW_REQUIRED
    assert res.checks.edition_match is False


# -------------------------------------------------------------
# 6. Version Mismatch & Historical Preservation Tests
# -------------------------------------------------------------

def test_version_mismatch_yields_review_required(test_db):
    """
    Test: Target version 2025, but evidence explicitly references 2017 terms.
    Yields REVIEW_REQUIRED.
    """
    doc = CollectedDocument(
        vendor_name="Adobe",
        requested_url="https://www.adobe.com/acrobat-2017.html",
        final_url="https://www.adobe.com/acrobat-2017.html",
        status=CollectionStatus.COLLECTED,
        clean_text="Adobe Acrobat 2017 is licensed under a classic perpetual desktop license.",
        content_hash="acrobat_2017_hash"
    )
    test_db.add(doc)
    test_db.commit()

    fact = LicenseFact(
        vendor_name="Adobe",
        product_name="Acrobat",
        version="2017",
        fact_type=FactType.LICENSE_MODEL,
        fact_value="perpetual",
        normalized_value="PERPETUAL",
        document_id=doc.id,
        evidence_text="Adobe Acrobat 2017 is licensed under a classic perpetual desktop license.",
        evidence_hash="acrobat_2017_ev_hash",
        status=FactStatus.EXTRACTED
    )
    test_db.add(fact)
    test_db.commit()

    validator = FactValidator()
    res = validator.validate_fact(test_db, fact, target_version="2025")

    assert res.status == FactStatus.REVIEW_REQUIRED
    assert res.checks.version_match is False


# -------------------------------------------------------------
# 7. Unresolved Conflict Detection Test
# -------------------------------------------------------------

def test_unresolved_conflict_detection(test_db):
    """
    Test: Two sources give contradictory facts (SUBSCRIPTION vs PERPETUAL) for the exact same scope.
    Flags status as CONFLICT.
    """
    fact1 = LicenseFact(
        vendor_name="TestCorp",
        product_name="ToolApp",
        version="2025",
        fact_type=FactType.LICENSE_MODEL,
        fact_value="subscription",
        normalized_value="SUBSCRIPTION",
        evidence_text="ToolApp is licensed under a subscription model.",
        evidence_hash="t1_hash",
        status=FactStatus.EXTRACTED
    )
    fact2 = LicenseFact(
        vendor_name="TestCorp",
        product_name="ToolApp",
        version="2025",
        fact_type=FactType.LICENSE_MODEL,
        fact_value="perpetual",
        normalized_value="PERPETUAL",
        evidence_text="ToolApp is available under a perpetual license.",
        evidence_hash="t2_hash",
        status=FactStatus.EXTRACTED
    )
    test_db.add_all([fact1, fact2])
    test_db.commit()

    detector = ValidationConflictDetector()
    processed_facts, reports = detector.analyze_conflicts([fact1, fact2])

    assert len(reports) == 1
    assert reports[0]["fact_type"] == "LICENSE_MODEL"
    assert fact1.status == FactStatus.CONFLICT
    assert fact2.status == FactStatus.CONFLICT


# -------------------------------------------------------------
# 8. Validation Audit Runs & API Endpoint Tests
# -------------------------------------------------------------

def test_validation_audit_run_persisted(test_db, client):
    """Verify validation runs write audit records to fact_validation_runs table."""
    doc = CollectedDocument(
        vendor_name="VMware",
        requested_url="https://www.vmware.com/pricing",
        final_url="https://www.vmware.com/pricing",
        status=CollectionStatus.COLLECTED,
        clean_text="VMware vSphere is commercial software licensed under a core-based subscription model.",
        content_hash="vmware_hash"
    )
    test_db.add(doc)
    test_db.commit()

    fact = LicenseFact(
        vendor_name="VMware",
        product_name="vSphere",
        fact_type=FactType.LICENSE_MODEL,
        fact_value="SUBSCRIPTION",
        normalized_value="SUBSCRIPTION",
        document_id=doc.id,
        evidence_text="VMware vSphere is commercial software licensed under a core-based subscription model.",
        evidence_hash="vm_ev_hash",
        status=FactStatus.EXTRACTED
    )
    test_db.add(fact)
    test_db.commit()

    res = client.post(f"/api/validation/facts/{fact.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "VALIDATED"
    assert data["validator_version"] == "1.0.0"

    # Verify audit record in DB
    runs = test_db.query(FactValidationRun).filter(FactValidationRun.license_fact_id == fact.id).all()
    assert len(runs) >= 1
    assert runs[0].validation_status == FactStatus.VALIDATED


def test_application_quality_summary_api(test_db, client):
    """Test GET /api/validation/application returns high-level metrics and review queues."""
    doc = CollectedDocument(
        vendor_name="Oracle",
        requested_url="https://www.oracle.com/database/pricing",
        final_url="https://www.oracle.com/database/pricing",
        status=CollectionStatus.COLLECTED,
        clean_text="Oracle Database Enterprise Edition is commercial software licensed on a processor socket basis.",
        content_hash="oracle_hash"
    )
    test_db.add(doc)
    test_db.commit()

    fact = LicenseFact(
        vendor_name="Oracle",
        product_name="Database",
        edition="Enterprise",
        fact_type=FactType.LICENSE_METRIC,
        fact_value="SOCKET",
        normalized_value="SOCKET",
        document_id=doc.id,
        evidence_text="Oracle Database Enterprise Edition is commercial software licensed on a processor socket basis.",
        evidence_hash="ora_ev_hash",
        status=FactStatus.EXTRACTED
    )
    test_db.add(fact)
    test_db.commit()

    res = client.get("/api/validation/application?vendor=Oracle&product=Database&edition=Enterprise")
    assert res.status_code == 200
    data = res.json()
    assert data["total_facts"] == 1
    assert data["validated"] == 1
    assert data["review_required"] == 0
