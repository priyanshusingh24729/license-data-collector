"""
Unit and Integration Tests for Step 19: License Data Quality Hardening.
Tests:
1. Exact 6-component reliability scoring and anti-gaming floors.
2. Reliability bands classification.
3. Automated contradiction detection and issue persistence.
4. Specific validation of the 10 target applications.
5. Audit event creation.
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.connection import Base
from backend.models.enums import (
    LicenseClassificationValue,
    AvailabilityModel,
    LicenseRequirement,
    LicenseMetricValue,
    ReliabilityBand,
    DataQualityStatus,
    ContradictionSeverity,
    SourceAuthorityTier,
    EvidenceType,
    FinalLicenseStatus,
)
from backend.models.profile import LicenseProfile
from backend.models.inventory import DetectedApplication
from backend.models.data_quality import DataQualityIssue
from backend.models.audit import AuditEvent
from backend.validation.reliability_score import ReliabilityScoreEngine, ReliabilityBreakdown
from backend.validation.contradiction_detector import DataContradictionDetector
from backend.inventory.recognition.catalog import RecognitionCatalog
from backend.inventory.recognition.resolver import AutomaticReviewResolver
from backend.research.evidence_pipeline import EvidenceResearchPipeline


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


class TestReliabilityScoreEngineStep19:
    """Tests for 6-component scoring and floor rules (Parts 6–16)."""

    def test_ideal_perfect_evidence_score(self):
        """Tier 1 EULA + Direct Statement + Exact Scope + Clean Validation + Recent Freshness -> VERY_HIGH (100)."""
        breakdown = ReliabilityScoreEngine.calculate_reliability(
            has_exact_identity=True,
            is_vendor_matched=True,
            has_exact_version=True,
            identity_tier="EXACT_VENDOR_CONFIRMED",
            source_type="EULA",
            evidence_directness_tier="DIRECT_STATEMENT",
            scope_tier="EXACT_ALL",
            validation_tier="CLEAN",
            published_at=datetime.now(timezone.utc),
            has_evidence=True,
        )
        assert breakdown.identity_quality_score == 25.0
        assert breakdown.source_authority_score == 20.0
        assert breakdown.evidence_directness_score == 25.0
        assert breakdown.product_scope_score == 15.0
        assert breakdown.classification_score == 10.0
        assert breakdown.license_validation_score == 5.0
        assert breakdown.overall == 100.0
        assert breakdown.band == ReliabilityBand.VERY_HIGH

    def test_weights_calculation_exact(self):
        """Validates weights across 6 score components."""
        breakdown = ReliabilityScoreEngine.calculate_reliability(
            identity_tier="EXACT_VENDOR_CONFIRMED",
            source_type="DOCS",
            evidence_directness_tier="STRONG_AVAILABILITY",
            scope_tier="EXACT_ALL",
            classification_valid=True,
            license_metric_valid=True,
            has_evidence=True,
        )
        assert breakdown.overall >= 80.0
        assert breakdown.band in (ReliabilityBand.HIGH, ReliabilityBand.VERY_HIGH)

    def test_floor_cap_when_source_or_evidence_missing(self):
        """Part 16 Rule: If source authority = 0 or evidence directness = 0, overall reliability cannot exceed 60."""
        breakdown = ReliabilityScoreEngine.calculate_reliability(
            identity_tier="EXACT_VENDOR_CONFIRMED",  # 100
            source_type="NONE",                      # 0
            evidence_directness_tier="DIRECT_STATEMENT", # 100
            scope_tier="EXACT_ALL",                  # 100
            validation_tier="CLEAN",                 # 100
            has_evidence=True,
        )
        assert breakdown.source_authority_score == 0.0
        assert breakdown.overall <= 60.0

    def test_floor_cap_when_no_evidence_exists(self):
        """Part 16 Rule: If no evidence exists, reliability must not exceed 50."""
        breakdown = ReliabilityScoreEngine.calculate_reliability(
            identity_tier="EXACT_VENDOR_CONFIRMED",
            source_type="NONE",
            evidence_directness_tier="NONE",
            has_evidence=False,
        )
        assert breakdown.overall <= 50.0

    def test_reliability_bands(self):
        """Part 15: VERY_HIGH (95-100), HIGH (80-94), MEDIUM (60-79), LOW (40-59), VERY_LOW (0-39)."""
        assert ReliabilityScoreEngine.get_reliability_band(97.0) == ReliabilityBand.VERY_HIGH
        assert ReliabilityScoreEngine.get_reliability_band(85.0) == ReliabilityBand.HIGH
        assert ReliabilityScoreEngine.get_reliability_band(70.0) == ReliabilityBand.MEDIUM
        assert ReliabilityScoreEngine.get_reliability_band(45.0) == ReliabilityBand.LOW
        assert ReliabilityScoreEngine.get_reliability_band(25.0) == ReliabilityBand.VERY_LOW


class TestContradictionDetectorStep19:
    """Tests for automated contradiction detector (Parts 22–24)."""

    def test_open_source_with_user_metric_flagged(self, test_db):
        """OPEN_SOURCE + USER metric -> CRITICAL CONFLICT."""
        issues, status = DataContradictionDetector.audit_and_persist_issues(
            db=test_db,
            application_id=1,
            app_name=".NET SDK",
            vendor_name="Microsoft",
            classification="OPEN_SOURCE",
            availability="FREE",
            requirement="NO",
            metric="USER",
        )
        assert status == DataQualityStatus.CONFLICT
        assert any(i.issue_type == "CONTRADICTION_OPEN_SOURCE_METRIC" for i in issues)

    def test_os_bundled_with_core_metric_flagged(self, test_db):
        """OS_BUNDLED + CORE metric -> CONFLICT."""
        issues, status = DataContradictionDetector.audit_and_persist_issues(
            db=test_db,
            application_id=2,
            app_name="Windows Calculator",
            vendor_name="Microsoft Windows",
            classification="OS_BUNDLED",
            availability="BUNDLED",
            requirement="NO",
            metric="CORE",
        )
        assert status == DataQualityStatus.CONFLICT
        assert any(i.issue_type == "CONTRADICTION_OS_BUNDLED_METRIC" for i in issues)

    def test_sql_server_core_evidence_with_user_metric_flagged(self, test_db):
        """SQL Server + CORE evidence + USER metric -> CRITICAL CONFLICT."""
        issues, status = DataContradictionDetector.audit_and_persist_issues(
            db=test_db,
            application_id=3,
            app_name="Microsoft SQL Server",
            vendor_name="Microsoft",
            classification="COMMERCIAL",
            availability="FREE_AND_PAID",
            requirement="YES",
            metric="USER",
            evidence_text="SQL Server requires per core licensing",
            has_evidence=True,
        )
        assert status == DataQualityStatus.CONFLICT
        assert any(i.issue_type == "CONTRADICTION_SQL_SERVER_CORE_METRIC" for i in issues)

    def test_free_and_paid_with_no_requirement_flagged(self, test_db):
        """FREE_AND_PAID + requirement NO -> NEEDS_REVIEW."""
        issues, status = DataContradictionDetector.audit_and_persist_issues(
            db=test_db,
            application_id=4,
            app_name="Antigravity",
            vendor_name="Google",
            classification="FREE_AND_PAID",
            availability="FREE_AND_PAID",
            requirement="NO",
            metric="USER",
            has_evidence=True,
        )
        assert any(i.issue_type == "CONTRADICTION_FREE_AND_PAID_REQUIREMENT" for i in issues)

    def test_commercial_component_with_yes_standalone_flagged(self, test_db):
        """COMMERCIAL_COMPONENT + standalone requirement YES -> CONFLICT/NEEDS_REVIEW."""
        issues, status = DataContradictionDetector.audit_and_persist_issues(
            db=test_db,
            application_id=5,
            app_name="OfficePushNotificationUtility",
            vendor_name="Microsoft",
            classification="COMMERCIAL_COMPONENT",
            availability="BUNDLED",
            requirement="YES",
            metric="NOT_APPLICABLE",
            parent_product="Microsoft 365 Apps",
            has_evidence=True,
        )
        assert any(i.issue_type == "CONTRADICTION_COMPONENT_STANDALONE_LICENSE" for i in issues)

    def test_generic_per_user_device_default_flagged(self, test_db):
        """Legacy generic 'Per User / Device' metric -> flagged."""
        issues, status = DataContradictionDetector.audit_and_persist_issues(
            db=test_db,
            application_id=6,
            app_name="Unknown Tool",
            vendor_name="Vendor X",
            classification="COMMERCIAL",
            availability="PAID_ONLY",
            requirement="YES",
            metric="Per User / Device",
            has_evidence=True,
        )
        assert any(i.issue_type == "GENERIC_METRIC_DEFAULT_DETECTED" for i in issues)


class TestTarget10ApplicationsValidationStep19:
    """Explicit verification of the 10 target validation applications (Part 31)."""

    def test_01_antigravity(self, test_db):
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(test_db, raw_name="Antigravity", raw_publisher="Google")
        assert res.classification == "FREE_AND_PAID"
        assert res.availability == "FREE_AND_PAID"
        assert res.license_requirement == "CONTEXT_DEPENDENT"
        assert res.license_metric == "USER"
        assert res.reliability_score >= 80.0

    def test_02_antigravity_ide_user(self, test_db):
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(test_db, raw_name="Antigravity IDE (User)", raw_publisher="Google")
        assert res.classification == "FREE_AND_PAID"
        assert res.availability == "FREE_AND_PAID"
        assert res.license_requirement == "CONTEXT_DEPENDENT"
        assert res.license_metric == "USER"

    def test_03_docker_desktop(self, test_db):
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(test_db, raw_name="Docker Desktop", raw_publisher="Docker")
        assert res.classification == "COMMERCIAL"
        assert res.availability == "FREE_AND_PAID"
        assert res.license_requirement == "CONTEXT_DEPENDENT"
        assert res.license_metric == "USER"

    def test_04_microsoft_sql_server(self, test_db):
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(test_db, raw_name="Microsoft SQL Server 2022", raw_publisher="Microsoft")
        assert res.classification == "COMMERCIAL"
        assert res.license_requirement == "YES"
        assert res.license_metric == "CORE"
        assert res.reliability_score >= 80.0

    def test_05_microsoft_dotnet_sdk(self, test_db):
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(test_db, raw_name="Microsoft .NET SDK 9.0", raw_publisher="Microsoft")
        assert res.classification == "OPEN_SOURCE"
        assert res.availability == "FREE"
        assert res.license_requirement == "NO"
        assert res.license_metric == "NOT_APPLICABLE"

    def test_06_nodejs(self, test_db):
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(test_db, raw_name="Node.js", raw_publisher="OpenJS Foundation")
        assert res.classification == "OPEN_SOURCE"
        assert res.license_requirement == "NO"
        assert res.license_metric == "NOT_APPLICABLE"

    def test_07_go(self, test_db):
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(test_db, raw_name="Go Programming Language", raw_publisher="Google")
        assert res.classification == "OPEN_SOURCE"
        assert res.license_requirement == "NO"
        assert res.license_metric == "NOT_APPLICABLE"

    def test_08_windows_calculator(self, test_db):
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(test_db, raw_name="Microsoft.WindowsCalculator", raw_publisher="Microsoft Windows")
        assert res.classification == "OS_BUNDLED"
        assert res.availability == "BUNDLED"
        assert res.license_requirement == "NO"
        assert res.license_metric == "NOT_APPLICABLE"

    def test_09_windows_photos(self, test_db):
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(test_db, raw_name="Microsoft.WindowsPhotos", raw_publisher="Microsoft Windows")
        assert res.classification == "OS_BUNDLED"
        assert res.availability == "BUNDLED"
        assert res.license_requirement == "NO"
        assert res.license_metric == "NOT_APPLICABLE"

    def test_10_office_push_notification_utility(self, test_db):
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(test_db, raw_name="OfficePushNotificationUtility", raw_publisher="Microsoft")
        assert res.classification == "COMMERCIAL_COMPONENT"
        assert res.parent_product == "Microsoft 365 Apps"
        assert res.license_requirement == "NOT_APPLICABLE"
        assert res.license_metric == "NOT_APPLICABLE"


class TestAuditAndProvenanceStep19:
    """Tests audit logging and data preservation."""

    def test_audit_event_logged_on_resolution(self, test_db):
        resolver = AutomaticReviewResolver()
        resolver.resolve_application(test_db, raw_name=".NET SDK", raw_publisher="Microsoft")
        audit = test_db.query(AuditEvent).filter(AuditEvent.event_type == "REVIEW_AUTO_RESOLVED").first()
        assert audit is not None
        assert "OPEN_SOURCE" in audit.new_value
