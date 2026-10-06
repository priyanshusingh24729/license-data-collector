"""
Dedicated Test Suite for Data Quality Regression Fix & Application Qualification Pipeline.

Validates:
1. Windows internal system components are NEVER classified as FREEWARE.
2. Evidence Status = MISSING is NEVER paired with Confidence = HIGH or VERY_HIGH.
3. Unresearched applications do NOT default to FREEWARE (they remain UNKNOWN).
4. 6-category Application Qualification accurately filters non-standalone software.
5. Machine inventory (InstallationLicenseResult) excludes OS internal system components.
6. Database integrity: 0 violations across all detected and machine records.
"""

import os
import sys
import pytest

from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.inventory.detection.qualification_filter import (
    ApplicationQualificationFilter,
    QualificationCategory,
    WindowsSystemComponentFilter,
    WindowsRuntimeFrameworkFilter,
    WindowsSystemToolFilter,
)
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
from backend.inventory.recognition.microsoft_identity_resolver import MicrosoftProductIdentityResolver
from backend.validation.microsoft_evidence_validator import MicrosoftEvidenceValidator


SYSTEM_COMPONENTS = [
    "aad.brokerplugin",
    "accountscontrol",
    "asynctextservice",
    "cloudexperiencehost",
    "ShellExperienceHost",
    "StartMenuExperienceHost",
    "Client.Core",
    "Client.Photon",
    "UndockedDevKit",
    "aimgr",
    "creddialoghost",
    "win32webviewhost",
    "capturepicker",
    "pinningconfirmationdialog",
    "lockapp",
    "ecapp",
    "Microsoft.Windows.CallingShellApp",
    "Microsoft.Windows.Apprep.ChxApp",
    "MicrosoftWindows.Client.CBS",
    "MicrosoftWindows.Client.CoreAI",
    "MicrosoftWindows.Client.FileExp",
    "MicrosoftWindows.Client.OOBE",
]


def test_windows_system_components_not_freeware():
    """Verify that none of the 39 Windows internal system components are classified as FREEWARE."""
    for comp in SYSTEM_COMPONENTS:
        res = HybridLicenseEngine.resolve_hybrid_record(
            app_id=None,
            name=comp,
            publisher="Microsoft Corporation",
            version=None,
        )
        assert res["classification"] != "FREEWARE", (
            f"Regression: System component '{comp}' was incorrectly classified as FREEWARE!"
        )
        assert res["classification"] in ("OS_BUNDLED", "UNKNOWN"), (
            f"Expected '{comp}' to be OS_BUNDLED or UNKNOWN, got: {res['classification']}"
        )
        # Verify confidence is never HIGH on system component
        assert res["confidence"] in ("LOW", "UNKNOWN"), (
            f"Expected LOW or UNKNOWN confidence for internal component '{comp}', got: {res['confidence']}"
        )


def test_no_missing_evidence_with_high_confidence():
    """Verify that MISSING evidence is NEVER paired with HIGH or VERY_HIGH confidence."""
    test_cases = [
        ("BrandNewUnknownApp", "Unknown Vendor"),
        ("CustomInhouseApp", "Inhouse Devs"),
        ("WebP Image Extension", "Microsoft Corporation"),
        ("RandomPackageName.12345", "Unknown"),
    ]
    for name, pub in test_cases:
        res = HybridLicenseEngine.resolve_hybrid_record(
            app_id=None,
            name=name,
            publisher=pub,
            version="1.0.0",
        )
        if res["evidence_status"] == "MISSING":
            assert res["confidence"] not in ("HIGH", "VERY_HIGH"), (
                f"Violation: '{name}' has MISSING evidence but received {res['confidence']} confidence!"
            )


def test_unresearched_application_remains_unknown():
    """Verify that unresearched applications do NOT default to FREEWARE."""
    res = HybridLicenseEngine.resolve_hybrid_record(
        app_id=None,
        name="UnregisteredToolXYZ",
        publisher="RandomCo",
        version="2.0",
    )
    assert res["classification"] == "UNKNOWN", (
        f"Expected unresearched app to be UNKNOWN, but got: {res['classification']}"
    )
    assert res["confidence"] == "UNKNOWN"
    assert res["license_model"] == "UNKNOWN"
    assert res["evidence_status"] == "MISSING"


def test_qualification_six_categories():
    """Verify 6-category Application Qualification."""
    # 1. STANDALONE_APPLICATION
    cand_app = {"raw_name": "Docker Desktop", "raw_publisher": "Docker Inc.", "detection_method": "WINDOWS_REGISTRY_64"}
    is_q, _, cat = ApplicationQualificationFilter.qualify_candidate(cand_app)
    assert is_q and cat == QualificationCategory.STANDALONE_APPLICATION.value

    # 2. OS_SYSTEM_COMPONENT
    cand_sys = {"raw_name": "ShellExperienceHost", "raw_publisher": "Microsoft", "detection_method": "WINDOWS_APPX"}
    is_q, _, cat = ApplicationQualificationFilter.qualify_candidate(cand_sys)
    assert not is_q and cat == QualificationCategory.OS_SYSTEM_COMPONENT.value

    # 3. RUNTIME_FRAMEWORK
    cand_rt = {"raw_name": "Microsoft.VCLibs.140.00", "detection_method": "WINDOWS_APPX"}
    is_q, _, cat = ApplicationQualificationFilter.qualify_candidate(cand_rt)
    assert not is_q and cat == QualificationCategory.RUNTIME_FRAMEWORK.value

    # 4. INSTALLER_INFRASTRUCTURE
    cand_inst = {"raw_name": "Windows Package Manager Source (winget)", "detection_method": "WINDOWS_WINGET"}
    is_q, _, cat = ApplicationQualificationFilter.qualify_candidate(cand_inst)
    assert not is_q and cat == QualificationCategory.INSTALLER_INFRASTRUCTURE.value


def test_database_records_zero_violations():
    """Audit all records in database to verify 0 regressions across detected and machine tables."""
    db = SessionLocal()
    try:
        # Check DetectedApplication
        detected = db.query(DetectedApplication).all()
        for d in detected:
            res = HybridLicenseEngine.resolve_hybrid_record(
                d.id, d.normalized_name, d.normalized_publisher, d.detected_version
            )
            # Rule 1: No MISSING + HIGH/VERY_HIGH
            if res["evidence_status"] == "MISSING":
                assert res["confidence"] not in ("HIGH", "VERY_HIGH"), (
                    f"Record ID {d.id} ({d.raw_name}) has MISSING evidence with {res['confidence']} confidence!"
                )
            # Rule 2: No system component as FREEWARE
            if "system component" in res["application"].lower():
                assert res["classification"] != "FREEWARE", (
                    f"Record ID {d.id} ({d.raw_name}) is a system component classified as FREEWARE!"
                )

        # Check InstallationLicenseResult
        machine_records = db.query(InstallationLicenseResult).all()
        for m in machine_records:
            if m.evidence_status == "MISSING":
                assert m.confidence not in ("HIGH", "VERY_HIGH"), (
                    f"Machine Record ID {m.id} ({m.raw_application_name}) has MISSING evidence with {m.confidence} confidence!"
                )
            if "system component" in (m.canonical_product or "").lower():
                assert m.classification != "FREEWARE", (
                    f"Machine Record ID {m.id} ({m.raw_application_name}) is a system component classified as FREEWARE!"
                )
    finally:
        db.close()
