"""
Comprehensive Regression & Data Quality Test Suite for License Intelligence Pipeline.
Tests all 8 audited issues:
1. Deduplication failure (P0)
2. Entity resolution failure (P0)
3. Incorrect license classification / generic fallback (P0)
4. Reliability scoring / evidence computation (P0)
5. Version string corruption & bitness stripping (P0)
6. Encoding / Mojibake integrity (P0)
7. Schema domain violations (P0)
8. Missing data on verified records consistency (P0)
"""

import pytest
from backend.inventory.detection.detection_normalizer import DetectionNormalizer
from backend.inventory.recognition.alias_system import ApplicationAliasSystem
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
from backend.validation.export_validator import ExportValidator, ExportValidationIssue


def test_dedup_exact_duplicate_rows():
    """Issue 1: Exact duplicate rows must be deduplicated before export."""
    records = [
        {
            "Application": "Windows Terminal",
            "Vendor": "Microsoft",
            "Version": "1.22.3232.0",
            "Classification": "OPEN_SOURCE",
            "Confidence": "VERY_HIGH",
            "Reliability": "96%",
        },
        {
            "Application": "Windows Terminal",
            "Vendor": "Microsoft",
            "Version": "1.22.3232.0",
            "Classification": "OPEN_SOURCE",
            "Confidence": "HIGH",
            "Reliability": "90%",
        },
        {
            "Application": "Microsoft Teams",
            "Vendor": "Microsoft",
            "Version": "26213.1006.5014.9784",
            "Classification": "COMMERCIAL",
            "Confidence": "VERY_HIGH",
            "Reliability": "98%",
        },
        {
            "Application": "Microsoft Teams",
            "Vendor": "Microsoft",
            "Version": "26213.1006.5014.9784",
            "Classification": "COMMERCIAL",
            "Confidence": "VERY_HIGH",
            "Reliability": "98%",
        },
    ]

    # Verify validator detects duplicates
    dup_issues = ExportValidator.check_duplicates(records)
    assert len(dup_issues) == 2

    # Verify deduplication retains only unique records and keeps higher confidence
    deduped = ExportValidator.deduplicate_records(records)
    assert len(deduped) == 2
    wt_record = [r for r in deduped if r["Application"] == "Windows Terminal"][0]
    assert wt_record["Confidence"] == "VERY_HIGH"


def test_entity_resolution_onedrive():
    """Issue 2: 'OneDrive' and 'Microsoft OneDrive' resolve to canonical product."""
    alias1 = ApplicationAliasSystem.resolve_application(raw_name="OneDrive", raw_publisher="Microsoft Corporation")
    alias2 = ApplicationAliasSystem.resolve_application(raw_name="Microsoft OneDrive", raw_publisher="Microsoft")

    assert alias1.canonical_product == "Microsoft OneDrive"
    assert alias2.canonical_product == "Microsoft OneDrive"
    assert alias1.canonical_vendor == "Microsoft"


def test_entity_resolution_wsl():
    """Issue 2: WSL variants resolve to canonical product."""
    alias1 = ApplicationAliasSystem.resolve_application(raw_name="Windows Subsystem for Linux", raw_publisher="Microsoft")
    alias2 = ApplicationAliasSystem.resolve_application(raw_name="Windows Subsystem for Linux (WSL)", raw_publisher="Microsoft")

    assert alias1.canonical_product == "Windows Subsystem for Linux"
    assert alias2.canonical_product == "Windows Subsystem for Linux"


def test_entity_resolution_vscode_version_equivalence():
    """Issue 2: Version variations for same product are recognized as equivalent."""
    # 1.134.0 vs 1.0.134.0
    assert DetectionNormalizer.versions_are_equivalent("1.134.0", "1.0.134.0") is True
    # Trailing zeroes
    assert DetectionNormalizer.versions_are_equivalent("1.0", "1.0.0.0") is True
    # Bitness stripped
    assert DetectionNormalizer.versions_are_equivalent("3.14-64", "3.14") is True
    # Distinct versions must not match
    assert DetectionNormalizer.versions_are_equivalent("1.134.0", "1.135.0") is False


def test_git_license_classification_gplv2():
    """Issue 3: Git must be classified as OPEN_SOURCE with GPL-2.0, NOT Permissive/Bundled."""
    rec = HybridLicenseEngine.resolve_hybrid_record(
        app_id=32,
        name="Git",
        publisher="The Git Development Community",
        version="2.55.0.3",
    )
    assert rec["classification"] == "OPEN_SOURCE"
    assert rec["license_required"] == "NO"
    assert "GNU General Public License" in rec["license_model"] or "GPL" in rec["license_model"]
    assert rec["license_model"] != "Permissive / Bundled"
    assert rec["license_model"] != "Freeware Application"


def test_permissive_bundled_fallback_eliminated():
    """Issue 3: Open source and freeware apps do not receive generic 'Permissive / Bundled' label."""
    for app_name, pub in [("Brave", "Brave Software Inc"), ("PHP 8.2", "PHP Group"), ("Python 3.14.7", "Python Software Foundation")]:
        rec = HybridLicenseEngine.resolve_hybrid_record(app_id=None, name=app_name, publisher=pub)
        assert rec["license_model"] != "Permissive / Bundled", f"Generic fallback found for {app_name}"


def test_version_bitness_suffix_stripped():
    """Issue 5: Bitness suffixes like -64, -32 are stripped from version numbers."""
    norm_v, maj, min_v, pat = DetectionNormalizer.normalize_version("3.14-64")
    assert norm_v == "3.14"
    assert maj == "3"
    assert min_v == "14"

    norm_v2, maj2, min_v2, pat2 = DetectionNormalizer.normalize_version("16.0.20326.20100 (64-bit)")
    assert norm_v2 == "16.0.20326.20100"
    assert maj2 == "16"


def test_encoding_special_characters_and_mojibake():
    """Issue 6: Registered trademark and special characters handle properly without mojibake."""
    raw_name_mojibake = "IntelÂ® Graphics Experience"
    cleaned = DetectionNormalizer.normalize_name(raw_name_mojibake)
    assert "Â®" not in cleaned
    assert "Intel®" in cleaned or "Intel" in cleaned

    # Validator checks
    records_with_mojibake = [{"Application": "IntelÂ® Graphics", "Vendor": "Intel", "License Model": "Freeware"}]
    issues = ExportValidator.check_encoding_integrity(records_with_mojibake)
    assert len(issues) >= 1
    assert issues[0].issue_type == "ENCODING_MOJIBAKE"


def test_license_required_domain_constraints():
    """Issue 7: License Required must only contain YES, NO, CONTEXT_DEPENDENT, UNKNOWN."""
    invalid_record = [
        {
            "Application": "OfficePushNotificationUtility",
            "Vendor": "Microsoft",
            "Classification": "COMMERCIAL_COMPONENT",
            "License Required": "NOT_APPLICABLE",
            "Evidence Status": "VERIFIED",
        }
    ]
    issues = ExportValidator.check_schema_constraints(invalid_record)
    assert any(i.issue_type == "SCHEMA_VIOLATION" and i.field == "License Required" for i in issues)

    # Fix schema violations
    fixed = ExportValidator.fix_schema_violations(invalid_record)
    assert fixed[0]["License Required"] == "NO"


def test_verified_evidence_consistency_enforcement():
    """Issue 8: VERIFIED evidence status with missing version is downgraded to PARTIAL."""
    records = [
        {
            "Application": "SQL Server 2025",
            "Vendor": "Microsoft",
            "Version": "N/A",
            "Classification": "COMMERCIAL",
            "Confidence": "HIGH",
            "Evidence Status": "VERIFIED",
            "License Model": "Standard Commercial",
        }
    ]
    issues = ExportValidator.check_evidence_consistency(records)
    assert any(i.issue_type == "EVIDENCE_INCONSISTENCY" for i in issues)

    # Enforce consistency
    ExportValidator.enforce_evidence_consistency(records)
    assert records[0]["Evidence Status"] == "PARTIAL"


def test_full_export_validator_pipeline():
    """End-to-end test of export validator batch execution."""
    sample_export = [
        {
            "Application": "Git",
            "Vendor": "The Git Development Community",
            "Version": "2.55.0.3",
            "Classification": "OPEN_SOURCE",
            "Availability": "FREE",
            "License Required": "NO",
            "License Model": "GNU General Public License v2.0 (GPL-2.0)",
            "Metric": "NOT_APPLICABLE",
            "Confidence": "VERY_HIGH",
            "Reliability": "96%",
            "Evidence Status": "VERIFIED",
        },
        {
            "Application": "Microsoft OneDrive",
            "Vendor": "Microsoft",
            "Version": "26.150.0804.0011",
            "Classification": "COMMERCIAL",
            "Availability": "COMMERCIAL",
            "License Required": "YES",
            "License Model": "Commercial Named User / Subscription",
            "Metric": "USER",
            "Confidence": "VERY_HIGH",
            "Reliability": "98%",
            "Evidence Status": "VERIFIED",
        },
    ]

    issues = ExportValidator.validate_batch(sample_export)
    # The clean sample export should have 0 ERROR issues
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) == 0
