"""
Test suite for Step 9: License Knowledge Consolidation Engine.
Covers profile synthesis, version/edition scoping, conflict preservation,
profile versioning, content hashing, and evidence drill-down traceability.
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
    ProfileStatus,
    ExtractionConfidence,
    ScopeType,
    CollectionStatus,
)
from backend.models.source import LicenseSource
from backend.models.collection import CollectedDocument
from backend.models.fact import LicenseFact, LicenseEvidence
from backend.models.profile import LicenseProfile, LicenseProfileFact, ProfileVersion
from backend.consolidation.profile_consolidator import LicenseProfileConsolidator, compute_profile_hash

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
# 1. Single & Multiple Validated Fact Consolidation
# -------------------------------------------------------------

def test_fully_validated_profile_consolidation(test_db):
    """
    Test: Consolidating 4 critical validated facts produces a VALIDATED profile with HIGH confidence.
    """
    f1 = LicenseFact(
        vendor_name="Adobe", product_name="Acrobat", edition="Pro", version="2025",
        fact_type=FactType.LICENSE_CLASSIFICATION, fact_value="PROPRIETARY", normalized_value="PROPRIETARY",
        status=FactStatus.VALIDATED, confidence=ExtractionConfidence.HIGH, confidence_score=0.9,
        evidence_text="Adobe Acrobat Pro is proprietary software.", evidence_hash="f1_h"
    )
    f2 = LicenseFact(
        vendor_name="Adobe", product_name="Acrobat", edition="Pro", version="2025",
        fact_type=FactType.LICENSE_REQUIRED, fact_value="TRUE", normalized_value="TRUE",
        status=FactStatus.VALIDATED, confidence=ExtractionConfidence.HIGH, confidence_score=0.9,
        evidence_text="A valid license is required.", evidence_hash="f2_h"
    )
    f3 = LicenseFact(
        vendor_name="Adobe", product_name="Acrobat", edition="Pro", version="2025",
        fact_type=FactType.LICENSE_MODEL, fact_value="SUBSCRIPTION", normalized_value="SUBSCRIPTION",
        status=FactStatus.VALIDATED, confidence=ExtractionConfidence.VERY_HIGH, confidence_score=0.95,
        evidence_text="Licensed under a subscription plan.", evidence_hash="f3_h"
    )
    f4 = LicenseFact(
        vendor_name="Adobe", product_name="Acrobat", edition="Pro", version="2025",
        fact_type=FactType.LICENSE_METRIC, fact_value="NAMED_USER", normalized_value="NAMED_USER",
        status=FactStatus.VALIDATED, confidence=ExtractionConfidence.HIGH, confidence_score=0.9,
        evidence_text="Licensed on a named user basis.", evidence_hash="f4_h"
    )
    test_db.add_all([f1, f2, f3, f4])
    test_db.commit()

    consolidator = LicenseProfileConsolidator()
    profile = consolidator.consolidate_profile(test_db, "Adobe", "Acrobat", "Pro", "2025")

    assert profile.profile_status == ProfileStatus.VALIDATED
    assert profile.overall_confidence in [ExtractionConfidence.VERY_HIGH, ExtractionConfidence.HIGH]
    assert profile.license_classification == "PROPRIETARY"
    assert profile.license_required == "TRUE"
    assert profile.license_model == "SUBSCRIPTION"
    assert profile.license_metric == "NAMED_USER"
    assert profile.validated_fact_count == 4


# -------------------------------------------------------------
# 2. Conflicting Validated Facts Handling
# -------------------------------------------------------------

def test_conflicting_validated_facts_preserved_as_conflict(test_db):
    """
    Test: If two sources give contradictory validated facts (SUBSCRIPTION vs PERPETUAL)
    for identical scope, license_model becomes CONFLICT and profile_status becomes CONFLICT.
    """
    f1 = LicenseFact(
        vendor_name="ConflictCorp", product_name="AppX", edition="Standard", version="2025",
        fact_type=FactType.LICENSE_MODEL, fact_value="SUBSCRIPTION", normalized_value="SUBSCRIPTION",
        status=FactStatus.VALIDATED, confidence=ExtractionConfidence.HIGH, confidence_score=0.85,
        evidence_text="Source A: Subscription model.", evidence_hash="cf1_h"
    )
    f2 = LicenseFact(
        vendor_name="ConflictCorp", product_name="AppX", edition="Standard", version="2025",
        fact_type=FactType.LICENSE_MODEL, fact_value="PERPETUAL", normalized_value="PERPETUAL",
        status=FactStatus.VALIDATED, confidence=ExtractionConfidence.HIGH, confidence_score=0.85,
        evidence_text="Source B: Perpetual license.", evidence_hash="cf2_h"
    )
    test_db.add_all([f1, f2])
    test_db.commit()

    consolidator = LicenseProfileConsolidator()
    profile = consolidator.consolidate_profile(test_db, "ConflictCorp", "AppX", "Standard", "2025")

    assert profile.profile_status == ProfileStatus.CONFLICT
    assert profile.license_model == "CONFLICT"
    assert profile.explanations["LICENSE_MODEL"].conflicting_values == ["SUBSCRIPTION", "PERPETUAL"] or \
           profile.explanations["LICENSE_MODEL"].conflicting_values == ["PERPETUAL", "SUBSCRIPTION"]


# -------------------------------------------------------------
# 3. Version Scope Isolation (2020 vs 2025)
# -------------------------------------------------------------

def test_version_specific_profiles_remain_isolated(test_db):
    """
    Test: Acrobat Pro 2020 (PERPETUAL) and Acrobat Pro 2025 (SUBSCRIPTION) produce
    separate distinct profiles without flagging an artificial conflict.
    """
    f2020 = LicenseFact(
        vendor_name="Adobe", product_name="Acrobat", edition="Pro", version="2020",
        fact_type=FactType.LICENSE_MODEL, fact_value="PERPETUAL", normalized_value="PERPETUAL",
        status=FactStatus.VALIDATED, confidence=ExtractionConfidence.HIGH, confidence_score=0.9,
        evidence_text="Acrobat 2020 classic desktop perpetual license.", evidence_hash="v2020_h"
    )
    f2025 = LicenseFact(
        vendor_name="Adobe", product_name="Acrobat", edition="Pro", version="2025",
        fact_type=FactType.LICENSE_MODEL, fact_value="SUBSCRIPTION", normalized_value="SUBSCRIPTION",
        status=FactStatus.VALIDATED, confidence=ExtractionConfidence.HIGH, confidence_score=0.9,
        evidence_text="Acrobat 2025 named user subscription plan.", evidence_hash="v2025_h"
    )
    test_db.add_all([f2020, f2025])
    test_db.commit()

    consolidator = LicenseProfileConsolidator()
    p2020 = consolidator.consolidate_profile(test_db, "Adobe", "Acrobat", "Pro", "2020")
    p2025 = consolidator.consolidate_profile(test_db, "Adobe", "Acrobat", "Pro", "2025")

    assert p2020.license_model == "PERPETUAL"
    assert p2020.profile_status != ProfileStatus.CONFLICT

    assert p2025.license_model == "SUBSCRIPTION"
    assert p2025.profile_status != ProfileStatus.CONFLICT


# -------------------------------------------------------------
# 4. Unknown Facts & Partial Profiles
# -------------------------------------------------------------

def test_unknown_facts_remain_unknown_without_guessing(test_db):
    """
    Test: When only CLASSIFICATION is validated and MODEL/METRIC are missing,
    profile marks missing fields as UNKNOWN and status as PARTIALLY_VALIDATED.
    """
    f1 = LicenseFact(
        vendor_name="SampleCo", product_name="Tool",
        fact_type=FactType.LICENSE_CLASSIFICATION, fact_value="PROPRIETARY", normalized_value="PROPRIETARY",
        status=FactStatus.VALIDATED, confidence=ExtractionConfidence.HIGH, confidence_score=0.85,
        evidence_text="SampleCo Tool is proprietary software.", evidence_hash="sc_h"
    )
    test_db.add(f1)
    test_db.commit()

    consolidator = LicenseProfileConsolidator()
    profile = consolidator.consolidate_profile(test_db, "SampleCo", "Tool")

    assert profile.license_classification == "PROPRIETARY"
    assert profile.license_model == "UNKNOWN"
    assert profile.license_metric == "UNKNOWN"
    assert profile.license_required == "UNKNOWN"
    assert profile.profile_status == ProfileStatus.PARTIALLY_VALIDATED


# -------------------------------------------------------------
# 5. Profile Snapshotting & Version History Tests
# -------------------------------------------------------------

def test_profile_versioning_and_change_detection(test_db):
    """
    Test: Updating facts triggers a new profile_hash and stores a historical snapshot in profile_versions.
    """
    f1 = LicenseFact(
        vendor_name="EvolCo", product_name="EvolApp",
        fact_type=FactType.LICENSE_MODEL, fact_value="PERPETUAL", normalized_value="PERPETUAL",
        status=FactStatus.VALIDATED, confidence=ExtractionConfidence.HIGH, confidence_score=0.85,
        evidence_text="Initial release: Perpetual.", evidence_hash="ev1_h"
    )
    test_db.add(f1)
    test_db.commit()

    consolidator = LicenseProfileConsolidator()
    p1 = consolidator.consolidate_profile(test_db, "EvolCo", "EvolApp")
    initial_hash = p1.profile_hash

    # Now add a new validated metric fact
    f2 = LicenseFact(
        vendor_name="EvolCo", product_name="EvolApp",
        fact_type=FactType.LICENSE_METRIC, fact_value="NAMED_USER", normalized_value="NAMED_USER",
        status=FactStatus.VALIDATED, confidence=ExtractionConfidence.HIGH, confidence_score=0.85,
        evidence_text="Assigned per named user.", evidence_hash="ev2_h"
    )
    test_db.add(f2)
    test_db.commit()

    p2 = consolidator.consolidate_profile(test_db, "EvolCo", "EvolApp")
    assert p2.profile_hash != initial_hash

    history = consolidator.get_profile_history(test_db, p2.id)
    assert len(history) >= 2


# -------------------------------------------------------------
# 6. API Endpoints Test
# -------------------------------------------------------------

def test_profile_api_endpoints(test_db, client):
    """Test POST /api/profiles/application and GET /api/profiles/{id}."""
    f1 = LicenseFact(
        vendor_name="Autodesk", product_name="Maya",
        fact_type=FactType.LICENSE_MODEL, fact_value="SUBSCRIPTION", normalized_value="SUBSCRIPTION",
        status=FactStatus.VALIDATED, confidence=ExtractionConfidence.HIGH, confidence_score=0.9,
        evidence_text="Autodesk Maya is available as a subscription.", evidence_hash="maya_h"
    )
    test_db.add(f1)
    test_db.commit()

    # Generate profile via API
    res = client.post("/api/profiles/application", json={
        "vendor": "Autodesk",
        "product": "Maya"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["vendor"] == "Autodesk"
    assert data["product"] == "Maya"
    assert data["license_model"] == "SUBSCRIPTION"

    pid = data["id"]
    # Retrieve detail
    get_res = client.get(f"/api/profiles/{pid}")
    assert get_res.status_code == 200
    detail = get_res.json()
    assert len(detail["supporting_facts"]) >= 1
    assert "subscription" in detail["supporting_facts"][0]["evidence_text"].lower()
