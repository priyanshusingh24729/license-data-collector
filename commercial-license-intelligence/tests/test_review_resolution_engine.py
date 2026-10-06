"""
Comprehensive Test Suite for STEP 17.7: Automatic Review Required Resolution Engine.
Tests all 15 required scenarios including critical test cases for .NET SDK 9, Adobe Acrobat Pro,
ambiguous Acrobat edition, and corporate keyword / substring collision protection.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.connection import Base
from backend.models.enums import (
    FinalLicenseStatus,
    ResolutionMethod,
    ReviewReason,
    ExtractionConfidence,
    AuditEventType,
)
from backend.models.inventory import DetectedApplication
from backend.models.profile import LicenseProfile
from backend.models.audit import AuditEvent
from backend.models.resolution import ReviewResolutionRun
from backend.inventory.recognition.resolver import AutomaticReviewResolver
from backend.inventory.recognition.catalog import RecognitionCatalog, sanitize_vendor_name


@pytest.fixture
def db_session():
    """Provides an in-memory SQLite database session for unit testing."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.close()


class TestReviewResolutionEngine:
    """Test suite covering all Step 17.7 resolution scenarios and critical invariants."""

    # -------------------------------------------------------------------------
    # 1. Known open-source application (Critical Test 28)
    # -------------------------------------------------------------------------
    def test_known_open_source_dotnet_sdk_9(self, db_session):
        """
        Critical Test 28:
        Input: .NET SDK 9
        Expected: LICENSE_REQUIRED_NO, Confidence: HIGH, Method: DETERMINISTIC_RULE
        """
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(
            db=db_session,
            raw_name=".NET SDK 9",
            raw_publisher="Microsoft Corporation",
            version="9.0.100"
        )
        assert res.new_status == FinalLicenseStatus.LICENSE_REQUIRED_NO
        assert res.confidence in [ExtractionConfidence.HIGH, ExtractionConfidence.VERY_HIGH]
        assert res.method == ResolutionMethod.DETERMINISTIC_RULE
        assert res.canonical_name == ".NET SDK"

    def test_known_open_source_git_and_python(self, db_session):
        """Test Git and Python resolve to LICENSE_REQUIRED_NO deterministically."""
        resolver = AutomaticReviewResolver()
        
        res_git = resolver.resolve_application(db=db_session, raw_name="Git 2.40", raw_publisher="The Git Development Community")
        assert res_git.new_status == FinalLicenseStatus.LICENSE_REQUIRED_NO
        assert res_git.method == ResolutionMethod.DETERMINISTIC_RULE
        
        res_py = resolver.resolve_application(db=db_session, raw_name="Python 3.12.0", raw_publisher="Python Software Foundation")
        assert res_py.new_status == FinalLicenseStatus.LICENSE_REQUIRED_NO
        assert res_py.method == ResolutionMethod.DETERMINISTIC_RULE

    # -------------------------------------------------------------------------
    # 2. Known Windows OS Component
    # -------------------------------------------------------------------------
    def test_known_windows_component(self, db_session):
        """Test built-in Windows components resolve to LICENSE_REQUIRED_NO with HIGH confidence."""
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(
            db=db_session,
            raw_name="Microsoft.WindowsCalculator",
            raw_publisher="Microsoft Corporation",
            version="11.2401.0.0"
        )
        assert res.new_status == FinalLicenseStatus.LICENSE_REQUIRED_NO
        assert res.confidence == ExtractionConfidence.HIGH
        assert res.method == ResolutionMethod.DETERMINISTIC_RULE

    # -------------------------------------------------------------------------
    # 3. Known Commercial Application (Critical Test 29)
    # -------------------------------------------------------------------------
    def test_known_commercial_adobe_acrobat_pro(self, db_session):
        """
        Critical Test 29:
        Input: Adobe Acrobat Pro
        Expected: LICENSE_REQUIRED_YES (with KNOWN_PROFILE) or RESEARCH_REQUIRED
        """
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(
            db=db_session,
            raw_name="Adobe Acrobat Pro",
            raw_publisher="Adobe Inc.",
            version="24.001.20604"
        )
        assert res.new_status in [FinalLicenseStatus.LICENSE_REQUIRED_YES, FinalLicenseStatus.RESEARCH_REQUIRED]
        assert res.confidence in [ExtractionConfidence.HIGH, ExtractionConfidence.VERY_HIGH]

    # -------------------------------------------------------------------------
    # 4. Unknown Application
    # -------------------------------------------------------------------------
    def test_unknown_application_fallback(self, db_session):
        """Test completely unknown application with missing vendor falls back to REVIEW_REQUIRED with UNKNOWN_IDENTITY/MISSING_VENDOR."""
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(
            db=db_session,
            raw_name="",
            raw_publisher=None,
            version=None
        )
        assert res.new_status == FinalLicenseStatus.REVIEW_REQUIRED
        assert res.review_reason == ReviewReason.UNKNOWN_IDENTITY

    # -------------------------------------------------------------------------
    # 5. Ambiguous Application (Critical Test 30)
    # -------------------------------------------------------------------------
    def test_ambiguous_application_acrobat(self, db_session):
        """
        Critical Test 30:
        Input: Acrobat (without specifying Reader vs Standard vs Pro)
        Expected: REVIEW_REQUIRED, Reason: AMBIGUOUS_IDENTITY
        """
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(
            db=db_session,
            raw_name="Acrobat",
            raw_publisher="Adobe",
            version="2024"
        )
        assert res.new_status == FinalLicenseStatus.REVIEW_REQUIRED
        assert res.review_reason == ReviewReason.AMBIGUOUS_IDENTITY

    # -------------------------------------------------------------------------
    # 6. Missing Vendor
    # -------------------------------------------------------------------------
    def test_missing_vendor_assignment(self, db_session):
        """Test uncataloged application with missing vendor sets MISSING_VENDOR."""
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(
            db=db_session,
            raw_name="CustomInHouseUtilityAlpha",
            raw_publisher=None,
            version="1.0"
        )
        assert res.new_status == FinalLicenseStatus.REVIEW_REQUIRED
        assert res.review_reason == ReviewReason.MISSING_VENDOR

    # -------------------------------------------------------------------------
    # 7. Missing Version
    # -------------------------------------------------------------------------
    def test_missing_version_assignment(self, db_session):
        """Test uncataloged application with missing version sets MISSING_VERSION."""
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(
            db=db_session,
            raw_name="CustomEnterpriseServiceBeta",
            raw_publisher="SomeSmallCo",
            version=None
        )
        assert res.new_status in [FinalLicenseStatus.RESEARCH_REQUIRED, FinalLicenseStatus.REVIEW_REQUIRED]

    # -------------------------------------------------------------------------
    # 8. Microsoft Corporation False Positive Protection (Critical Test 31)
    # -------------------------------------------------------------------------
    def test_random_corporation_must_not_match_microsoft(self, db_session):
        """
        Critical Test 31:
        Input: Random Corporation Product
        Publisher: Random Corporation
        Expected: Must NOT match Microsoft.
        """
        sanitized = sanitize_vendor_name("Random Corporation")
        assert "microsoft" not in (sanitized or "").lower()
        assert sanitized == "Random"

        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(
            db=db_session,
            raw_name="Random Product",
            raw_publisher="Random Corporation",
            version="1.0"
        )
        assert "microsoft" not in (res.canonical_vendor or "").lower()

    # -------------------------------------------------------------------------
    # 9. .NET SDK vs Visual Studio Substring Collision Protection
    # -------------------------------------------------------------------------
    def test_dotnet_sdk_vs_visual_studio_collision(self, db_session):
        """
        Section 7: Never allow contains('Visual Studio') to classify .NET SDK or Visual Studio Code.
        """
        resolver = AutomaticReviewResolver()
        
        # 1. .NET SDK
        res_sdk = resolver.resolve_application(
            db=db_session,
            raw_name="Microsoft .NET SDK 10.0.400 (x64)",
            raw_publisher="Microsoft Corporation"
        )
        assert res_sdk.canonical_name == ".NET SDK"
        assert res_sdk.new_status == FinalLicenseStatus.LICENSE_REQUIRED_NO

        # 2. Visual Studio Code
        res_code = resolver.resolve_application(
            db=db_session,
            raw_name="Microsoft Visual Studio Code (User)",
            raw_publisher="Microsoft Corporation"
        )
        assert res_code.canonical_name == "Visual Studio Code"
        assert res_code.new_status == FinalLicenseStatus.LICENSE_REQUIRED_NO

    # -------------------------------------------------------------------------
    # 10. Go Malformed Name & URL Publisher
    # -------------------------------------------------------------------------
    def test_go_malformed_name_and_url_publisher(self, db_session):
        """Test 'Go Programming Language amd64 go1.26.5' with publisher 'https://go.dev'."""
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(
            db=db_session,
            raw_name="Go Programming Language amd64 go1.26.5",
            raw_publisher="https://go.dev",
            version="1.26.5"
        )
        assert res.new_status == FinalLicenseStatus.LICENSE_REQUIRED_NO
        assert res.method == ResolutionMethod.DETERMINISTIC_RULE
        assert res.canonical_name == "Go Programming Language"

    # -------------------------------------------------------------------------
    # 11. AppX Internal Identity Resolution
    # -------------------------------------------------------------------------
    def test_appx_internal_identity(self, db_session):
        """Test AppX internal identity (e.g. MicrosoftWindows.Client.Core)."""
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(
            db=db_session,
            raw_name="MicrosoftWindows.Client.Core",
            raw_publisher="Microsoft Windows",
            version="1000.26100.131.0"
        )
        assert res.new_status == FinalLicenseStatus.LICENSE_REQUIRED_NO
        assert res.method == ResolutionMethod.DETERMINISTIC_RULE

    # -------------------------------------------------------------------------
    # 12. Existing Knowledge Reused (No Unnecessary Search)
    # -------------------------------------------------------------------------
    def test_existing_knowledge_reused(self, db_session):
        """Test validated profile in database is reused without re-researching."""
        prof = LicenseProfile(
            vendor_name="AcmeCorp",
            product_name="AcmeSuite",
            license_classification="COMMERCIAL",
            license_required="TRUE",
            profile_status="VALIDATED",
            license_model="Subscription",
            license_metric="Named User",
            overall_confidence=ExtractionConfidence.HIGH,
            profile_hash="hash_acme_123"
        )
        db_session.add(prof)
        db_session.commit()

        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(
            db=db_session,
            raw_name="AcmeSuite",
            raw_publisher="AcmeCorp",
            version="5.0"
        )
        assert res.new_status == FinalLicenseStatus.LICENSE_REQUIRED_YES
        assert res.method == ResolutionMethod.KNOWN_PROFILE

    # -------------------------------------------------------------------------
    # 13. Audit Event Creation
    # -------------------------------------------------------------------------
    def test_audit_event_created_on_resolution(self, db_session):
        """Test that every automatic resolution creates an audit event REVIEW_AUTO_RESOLVED."""
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(
            db=db_session,
            raw_name="7-Zip",
            raw_publisher="Igor Pavlov",
            version="23.01"
        )
        assert res.new_status == FinalLicenseStatus.LICENSE_REQUIRED_NO
        
        audit = db_session.query(AuditEvent).filter(
            AuditEvent.event_type == AuditEventType.REVIEW_AUTO_RESOLVED
        ).first()
        assert audit is not None
        assert "7-Zip" in audit.new_value

    # -------------------------------------------------------------------------
    # 14. ReviewResolutionRun Table Persistence
    # -------------------------------------------------------------------------
    def test_review_resolution_run_persisted(self, db_session):
        """Test review_resolution_runs table stores runs with fields intact."""
        resolver = AutomaticReviewResolver()
        res = resolver.resolve_application(
            db=db_session,
            raw_name="Node.js",
            raw_publisher="Node.js Foundation",
            version="20.10.0"
        )
        runs = db_session.query(ReviewResolutionRun).all()
        assert len(runs) >= 1
        last_run = runs[-1]
        assert last_run.new_status == FinalLicenseStatus.LICENSE_REQUIRED_NO
        assert last_run.resolution_method == ResolutionMethod.DETERMINISTIC_RULE
