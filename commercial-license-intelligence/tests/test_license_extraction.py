"""
Test suite for Step 7: License Fact Extraction Engine.
Covers deterministic pattern extraction, evidence linking, product/edition/version validation,
confidence calculation, conflict detection, anti-hallucination tests, and database persistence.
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
from backend.models.fact import LicenseFact, LicenseEvidence, ExtractionRun
from backend.schemas.extraction import ExtractedFactCandidate
from backend.extraction.relevant_content_detector import RelevantContentDetector
from backend.extraction.fact_normalizer import FactNormalizer
from backend.extraction.confidence_engine import ConfidenceEngine
from backend.extraction.conflict_detector import ConflictDetector
from backend.extraction.evidence_extractor import EvidenceExtractor
from backend.extraction.license_extractor import LicenseExtractor

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
# 1. Deterministic Normalization & Taxonomy Tests
# -------------------------------------------------------------

def test_fact_normalization_rules():
    """Verify raw strings map into canonical taxonomy."""
    normalizer = FactNormalizer()

    assert normalizer.normalize(FactType.LICENSE_CLASSIFICATION, "commercial software") == "COMMERCIAL"
    assert normalizer.normalize(FactType.LICENSE_CLASSIFICATION, "free for personal use") == "FREEWARE"
    assert normalizer.normalize(FactType.LICENSE_CLASSIFICATION, "open source GPL-3.0") == "OPEN_SOURCE"

    assert normalizer.normalize(FactType.LICENSE_MODEL, "annual subscription") == "SUBSCRIPTION"
    assert normalizer.normalize(FactType.LICENSE_MODEL, "perpetual with active maintenance") == "PERPETUAL_WITH_MAINTENANCE"
    assert normalizer.normalize(FactType.LICENSE_MODEL, "floating network license") == "CONCURRENT"

    assert normalizer.normalize(FactType.LICENSE_METRIC, "named-user basis") == "NAMED_USER"
    assert normalizer.normalize(FactType.LICENSE_METRIC, "per core licensing") == "CORE"
    assert normalizer.normalize(FactType.LICENSE_METRIC, "per-device deployment") == "DEVICE"

    assert normalizer.normalize(FactType.LICENSE_REQUIRED, "license is required") == "TRUE"
    assert normalizer.normalize(FactType.LICENSE_REQUIRED, "free of charge / no license") == "FALSE"
    assert normalizer.normalize(FactType.LICENSE_REQUIRED, "random unrelated token") == "UNKNOWN"


# -------------------------------------------------------------
# 2. Mock Document Extraction Tests
# -------------------------------------------------------------

SAMPLE_DOCUMENT_TEXT = """
TITLE: Adobe Acrobat Enterprise Licensing Guide 2025

SECTION: Introduction
Adobe Acrobat Pro is proprietary software for professional PDF authoring and electronic signatures.

SECTION: Licensing Models & Metrics
Adobe Acrobat Pro is licensed under a subscription model.
Each named user requires a separate license.
Secondary device rights are permitted on up to 2 machines for the same identified user.

SECTION: Virtualization
Virtualization on multi-tenant server infrastructure requires dedicated user CALs.
"""

def test_mock_document_fact_extraction(test_db):
    """
    Test controlled mock document extraction:
    Extracts LICENSE_MODEL=SUBSCRIPTION, LICENSE_METRIC=NAMED_USER, LICENSE_REQUIRED=TRUE with evidence.
    """
    doc = CollectedDocument(
        vendor_name="Adobe",
        requested_url="https://www.adobe.com/terms.html",
        final_url="https://www.adobe.com/terms.html",
        status=CollectionStatus.COLLECTED,
        title="Adobe Acrobat Enterprise Licensing Guide 2025",
        clean_text=SAMPLE_DOCUMENT_TEXT,
        content_hash="mock_hash_adobe_123"
    )
    test_db.add(doc)
    test_db.commit()

    extractor = LicenseExtractor()
    facts = extractor.extract_from_document(test_db, doc.id, target_product="Acrobat")

    fact_map = {f.fact_type: f for f in facts}

    assert FactType.LICENSE_MODEL in fact_map
    assert fact_map[FactType.LICENSE_MODEL].normalized_value == "SUBSCRIPTION"
    assert "subscription" in fact_map[FactType.LICENSE_MODEL].evidence_text.lower()

    assert FactType.LICENSE_METRIC in fact_map
    assert fact_map[FactType.LICENSE_METRIC].normalized_value == "NAMED_USER"

    assert FactType.LICENSE_REQUIRED in fact_map
    assert fact_map[FactType.LICENSE_REQUIRED].normalized_value == "TRUE"

    assert FactType.SECONDARY_DEVICE_RIGHTS in fact_map
    assert fact_map[FactType.SECONDARY_DEVICE_RIGHTS].normalized_value == "ALLOWED"


# -------------------------------------------------------------
# 3. Anti-Hallucination & Guardrail Tests
# -------------------------------------------------------------

def test_anti_hallucination_evaluation_does_not_infer_subscription(test_db):
    """
    Test: 'Example Product is available for evaluation.'
    MUST NOT conclude LICENSE_MODEL = SUBSCRIPTION.
    Concludes TRIAL_AVAILABLE = TRUE.
    """
    doc = CollectedDocument(
        vendor_name="ExampleCorp",
        requested_url="https://example.com/eval.html",
        final_url="https://example.com/eval.html",
        status=CollectionStatus.COLLECTED,
        clean_text="Example Product is available for evaluation on Windows.",
        content_hash="hash_eval_456"
    )
    test_db.add(doc)
    test_db.commit()

    extractor = LicenseExtractor()
    facts = extractor.extract_from_document(test_db, doc.id, target_product="Example Product")
    fact_map = {f.fact_type: f for f in facts}

    assert FactType.LICENSE_MODEL not in fact_map
    assert FactType.TRIAL_AVAILABLE in fact_map
    assert fact_map[FactType.TRIAL_AVAILABLE].normalized_value == "TRUE"


def test_proprietary_classification_does_not_blindly_infer_license_required(test_db):
    """
    Test: 'Example Product is proprietary software.'
    Extracts LICENSE_CLASSIFICATION = PROPRIETARY.
    Does NOT infer LICENSE_REQUIRED = TRUE without explicit licensing text.
    """
    doc = CollectedDocument(
        vendor_name="SampleCorp",
        requested_url="https://sample.com/about.html",
        final_url="https://sample.com/about.html",
        status=CollectionStatus.COLLECTED,
        clean_text="Sample Product is proprietary software developed for Windows.",
        content_hash="hash_prop_789"
    )
    test_db.add(doc)
    test_db.commit()

    extractor = LicenseExtractor()
    facts = extractor.extract_from_document(test_db, doc.id, target_product="Sample Product")
    fact_map = {f.fact_type: f for f in facts}

    assert FactType.LICENSE_CLASSIFICATION in fact_map
    assert fact_map[FactType.LICENSE_CLASSIFICATION].normalized_value == "PROPRIETARY"
    assert FactType.LICENSE_REQUIRED not in fact_map  # Not inferred without proof


# -------------------------------------------------------------
# 4. Product Mismatch Rejection
# -------------------------------------------------------------

def test_wrong_product_evidence_rejected():
    """Verify evidence referring strictly to 'Photoshop' is rejected from product-scope when target is 'Acrobat'."""
    extractor = EvidenceExtractor()
    from backend.extraction.relevant_content_detector import RelevantContextBlock
    block = RelevantContextBlock(
        text="Adobe Photoshop is licensed under a subscription model.",
        matched_keywords=["subscription"],
        page_number=1,
        section_name="Photoshop Terms"
    )
    candidates = extractor.extract_candidates_from_block(
        block=block,
        target_vendor="Adobe",
        target_product="Acrobat"
    )
    # Because Photoshop does not match Acrobat, confidence product_matched is False and scope is Vendor-only
    for c in candidates:
        assert c.scope_value != "Acrobat"
        assert c.scope_type == ScopeType.VENDOR


# -------------------------------------------------------------
# 5. Conflict Detection Tests
# -------------------------------------------------------------

def test_conflicting_sources_detection():
    """Verify contradictory facts (SUBSCRIPTION vs PERPETUAL) are flagged as CONFLICT."""
    detector = ConflictDetector()

    cand1 = ExtractedFactCandidate(
        fact_type=FactType.LICENSE_MODEL,
        fact_value="subscription",
        normalized_value="SUBSCRIPTION",
        evidence_text="Source A says subscription",
        confidence=ExtractionConfidence.HIGH
    )
    cand2 = ExtractedFactCandidate(
        fact_type=FactType.LICENSE_MODEL,
        fact_value="perpetual",
        normalized_value="PERPETUAL",
        evidence_text="Source B says perpetual",
        confidence=ExtractionConfidence.HIGH
    )

    processed, conflicts = detector.detect_conflicts([cand1, cand2])

    assert len(conflicts) == 1
    assert conflicts[0].fact_type == FactType.LICENSE_MODEL
    assert "SUBSCRIPTION" in conflicts[0].values
    assert "PERPETUAL" in conflicts[0].values
    assert processed[0].status == FactStatus.CONFLICT
    assert processed[1].status == FactStatus.CONFLICT


# -------------------------------------------------------------
# 6. Confidence Engine Tests
# -------------------------------------------------------------

def test_confidence_scoring_tiers():
    """Verify deterministic confidence calculation."""
    engine = ConfidenceEngine()

    # Official vendor + exact product + exact edition + direct evidence -> VERY_HIGH
    score1, tier1 = engine.calculate_confidence(
        authority=AuthorityLevel.OFFICIAL_VENDOR,
        product_matched=True,
        edition_matched=True,
        version_matched=True,
        evidence_type=EvidenceType.DIRECT_STATEMENT
    )
    assert score1 >= 0.85
    assert tier1 == ExtractionConfidence.VERY_HIGH

    # Secondary source + product match only -> MEDIUM / LOW
    score2, tier2 = engine.calculate_confidence(
        authority=AuthorityLevel.TRUSTED_SECONDARY,
        product_matched=True,
        edition_matched=False,
        version_matched=False,
        evidence_type=EvidenceType.INFERRED
    )
    assert score2 < 0.70
    assert tier2 in [ExtractionConfidence.MEDIUM, ExtractionConfidence.LOW]


# -------------------------------------------------------------
# 7. Application Extraction & API Endpoint Tests
# -------------------------------------------------------------

def test_application_extraction_without_collected_sources_returns_no_evidence(test_db, client):
    """Test 26: Querying an application with no collected sources returns NO_EVIDENCE_AVAILABLE."""
    res = client.post("/api/extraction/application", json={
        "vendor": "NonExistentVendorXYZ",
        "product": "MysteryApp",
        "edition": "Enterprise",
        "version": "2025"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "NO_EVIDENCE_AVAILABLE"


def test_full_application_extraction_pipeline(test_db, client):
    """Test full application intelligence endpoint against pre-collected documents."""
    doc = CollectedDocument(
        vendor_name="Autodesk",
        requested_url="https://www.autodesk.com/legal/terms",
        final_url="https://www.autodesk.com/legal/terms",
        status=CollectionStatus.COLLECTED,
        title="Autodesk Commercial Terms",
        clean_text="AutoCAD is commercial software licensed under a named user subscription model.",
        content_hash="autodesk_hash_999"
    )
    test_db.add(doc)
    test_db.commit()

    res = client.post("/api/extraction/application", json={
        "vendor": "Autodesk",
        "product": "AutoCAD"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"
    assert data["classification"] == "COMMERCIAL"
    assert data["license_model"] == "SUBSCRIPTION"
    assert data["license_metric"] == "NAMED_USER"
    assert len(data["facts"]) >= 2
