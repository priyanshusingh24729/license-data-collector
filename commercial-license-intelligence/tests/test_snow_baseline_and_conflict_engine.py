"""
Comprehensive test suite verifying the Snow Authoritative Baseline Enrichment
and Conflict Detection Layer across all 10 representative business cases:

1. Snow and our intelligence agree (Commercial)
2. Snow and our intelligence agree (Free/Open Source)
3. Snow and our intelligence disagree (Freemium: Docker Desktop)
4. Snow and our intelligence disagree (Trial software)
5. Snow value is NULL and reliable evidence exists (Metric Enrichment)
6. Snow value is NULL and no reliable evidence exists (Never fabricated)
7. Freeware
8. Commercial software
9. Open-source software with an identifiable SPDX license
10. Software whose licensing depends on edition, version, deployment, or commercial usage
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from backend.inventory.upload.bulk_upload_processor import BulkUploadProcessor
from backend.validation.consensus_engine import (
    ConsensusVerificationEngine,
    ConsensusVerificationResult,
)
from backend.inventory.export.standardized_inventory_exporter import (
    StandardizedInventoryExporter,
)
from backend.validation.spdx_taxonomy import SPDXTaxonomyService


def test_case_1_snow_intelligence_agree_commercial():
    """Case 1: Snow (0 = YES) and our intelligence (YES) agree on commercial software."""
    snow_baseline = {
        "NoLicenseRequired": "0",
        "Metric": "Installations",
        "IsEndOfLife": "0",
        "IsEndOfSupport": "0",
    }
    res = ConsensusVerificationEngine.verify_and_synthesize(
        raw_name="Oracle Database 19c Enterprise Edition",
        raw_vendor="Oracle Corporation",
        raw_version="19.0.0",
        snow_baseline=snow_baseline,
    )
    assert res.license_required == "YES"
    assert res.conflict_status == "CONFIRMED"
    assert "SNOW_AUTHORITATIVE_BASELINE" in res.resolution_notes


def test_case_2_snow_intelligence_agree_free_open_source():
    """Case 2: Snow (1 = NO) and our intelligence (NO) agree on open-source software."""
    snow_baseline = {
        "NoLicenseRequired": "1",
        "Metric": "No license required",
        "IsEndOfLife": "0",
        "IsEndOfSupport": "0",
    }
    res = ConsensusVerificationEngine.verify_and_synthesize(
        raw_name="7-Zip 23.01",
        raw_vendor="Igor Pavlov",
        raw_version="23.01",
        catalog_record={
            "classification": "OPEN_SOURCE",
            "license_required": "NO",
            "license_model": "GNU LGPL-2.1-or-later",
            "metric": "No License Required",
        },
        snow_baseline=snow_baseline,
    )
    assert res.license_required == "NO"
    assert res.conflict_status == "CONFIRMED"
    assert res.spdx_id is not None  # LGPL-2.1 or similar


def test_case_3_snow_intelligence_disagree_freemium():
    """
    Case 3: Snow (1 = NO) but our intelligence detects commercial subscription required (YES)
    for Docker Desktop. Snow's value MUST be preserved, and flagged as a discrepancy.
    """
    snow_baseline = {
        "NoLicenseRequired": "1",  # Snow legacy says free
        "Metric": "NULL",
    }
    res = ConsensusVerificationEngine.verify_and_synthesize(
        raw_name="Docker Desktop 4.25.0",
        raw_vendor="Docker Inc.",
        raw_version="4.25.0",
        snow_baseline=snow_baseline,
    )
    # Consensus engine detects conflict
    assert res.conflict_status == "DISCREPANCY_FLAGGED"
    assert res.consensus_status == "REVIEW_RECOMMENDED"
    assert "Snow Baseline specifies NoLicenseRequired=1 (NO)" in res.resolution_notes


def test_case_4_snow_intelligence_disagree_trial():
    """
    Case 4: Snow has 1 (NO) for evaluation/trial software, but intelligence detects trial requirement.
    Snow's baseline is preserved, flagged as DISCREPANCY_FLAGGED.
    """
    snow_baseline = {
        "NoLicenseRequired": "1",
        "Metric": "No license required",
    }
    res = ConsensusVerificationEngine.verify_and_synthesize(
        raw_name="RecoveryFIX for Lotus Notes to Outlook 1 Trial",
        raw_vendor="RecoveryFIX",
        raw_version="1.0",
        catalog_record={
            "classification": "TRIAL",
            "license_required": "YES",
            "license_model": "Trial / Evaluation",
            "evidence_quote": "Trial version is strictly for evaluation purposes.",
        },
        snow_baseline=snow_baseline,
    )
    assert res.conflict_status == "DISCREPANCY_FLAGGED"
    assert res.consensus_status == "REVIEW_RECOMMENDED"


def test_case_5_snow_metric_null_evidence_exists():
    """Case 5: Snow Metric is NULL/empty, but verified intelligence exists to enrich it."""
    snow_baseline = {
        "NoLicenseRequired": "0",
        "Metric": "NULL",  # Missing metric gap
    }
    res = ConsensusVerificationEngine.verify_and_synthesize(
        raw_name="Microsoft 365 Apps for enterprise",
        raw_vendor="Microsoft Corporation",
        raw_version="16.0",
        catalog_record={
            "classification": "COMMERCIAL",
            "license_required": "YES",
            "license_model": "Per User Subscription",
            "metric": "Users",
            "evidence_source": "Official Microsoft Corporation Documentation",
        },
        snow_baseline=snow_baseline,
    )
    assert res.metric == "Users"
    assert res.conflict_status == "ENRICHED"


def test_case_6_snow_metric_null_no_evidence_never_fabricated():
    """Case 6: Snow Metric is NULL/empty, and no reliable evidence exists -> left blank/UNKNOWN."""
    snow_baseline = {
        "NoLicenseRequired": "0",
        "Metric": "NULL",
    }
    res = ConsensusVerificationEngine.verify_and_synthesize(
        raw_name="Unidentified Proprietary In-House Module 1.0",
        raw_vendor="Custom Vendor Corp",
        raw_version="1.0",
        catalog_record={
            "classification": "UNKNOWN",
            "license_required": "UNKNOWN",
            "license_model": "",
            "metric": "",
        },
        snow_baseline=snow_baseline,
    )
    assert res.metric == "UNKNOWN"
    assert res.license_required == "UNKNOWN"


def test_case_7_freeware():
    """Case 7: Pure freeware software with no commercial fees."""
    snow_baseline = {
        "NoLicenseRequired": "1",
        "Metric": "No license required",
    }
    res = ConsensusVerificationEngine.verify_and_synthesize(
        raw_name="Windows Calculator",
        raw_vendor="Microsoft Corporation",
        raw_version="11.0",
        catalog_record={
            "classification": "FREEWARE",
            "license_required": "NO",
            "license_model": "Freeware",
            "metric": "No License Required",
        },
        snow_baseline=snow_baseline,
    )
    assert res.license_required == "NO"
    assert res.classification == "FREEWARE"
    assert res.conflict_status == "CONFIRMED"


def test_case_8_pure_commercial_software():
    """Case 8: Pure commercial software requiring license purchase."""
    snow_baseline = {
        "NoLicenseRequired": "0",
        "Metric": "Installations",
    }
    res = ConsensusVerificationEngine.verify_and_synthesize(
        raw_name="VMware vSphere Enterprise Plus",
        raw_vendor="Broadcom / VMware",
        raw_version="8.0",
        catalog_record={
            "classification": "COMMERCIAL",
            "license_required": "YES",
            "license_model": "Per Core Subscription",
            "metric": "Processor Cores",
        },
        snow_baseline=snow_baseline,
    )
    assert res.license_required == "YES"
    assert res.classification == "COMMERCIAL"
    assert res.conflict_status == "CONFIRMED"


def test_case_9_open_source_with_valid_spdx():
    """Case 9: Open-source software with standardized SPDX identifier."""
    snow_baseline = {
        "NoLicenseRequired": "1",
        "Metric": "No license required",
    }
    res = ConsensusVerificationEngine.verify_and_synthesize(
        raw_name="Python 3.11.4",
        raw_vendor="Python Software Foundation",
        raw_version="3.11.4",
        catalog_record={
            "classification": "OPEN_SOURCE",
            "license_required": "NO",
            "license_model": "Python-2.0",
            "metric": "No License Required",
        },
        snow_baseline=snow_baseline,
    )
    assert res.license_required == "NO"
    assert res.classification == "OPEN_SOURCE"
    assert res.spdx_id == "PSF-2.0"
    assert res.conflict_status == "CONFIRMED"


def test_case_10_edition_dependent_licensing():
    """Case 10: Licensing depends on edition (SQL Server Express vs Enterprise)."""
    # 10A: Express edition -> Free
    res_express = ConsensusVerificationEngine.verify_and_synthesize(
        raw_name="Microsoft SQL Server 2019 Express",
        raw_vendor="Microsoft Corporation",
        raw_version="2019",
        snow_baseline={"NoLicenseRequired": "1", "Metric": "No license required"},
    )
    assert res_express.canonical_edition.upper() == "EXPRESS"
    assert res_express.license_required == "NO"
    assert res_express.classification in ("FREEWARE", "FREE", "COMMERCIAL_COMPONENT")

    # 10B: Enterprise edition -> Commercial Paid
    res_enterprise = ConsensusVerificationEngine.verify_and_synthesize(
        raw_name="Microsoft SQL Server 2019 Enterprise",
        raw_vendor="Microsoft Corporation",
        raw_version="2019",
        snow_baseline={"NoLicenseRequired": "0", "Metric": "Processor Cores"},
    )
    assert res_enterprise.canonical_edition.upper() == "ENTERPRISE"
    assert res_enterprise.license_required == "YES"
    assert res_enterprise.classification == "COMMERCIAL"


def test_bulk_upload_processor_preserves_snow_baseline():
    """
    Tests end-to-end processing of a DataFrame with Snow baseline data.
    Verifies:
    - Snow's original NoLicenseRequired is strictly preserved.
    - Discrepancies are flagged without overwriting Snow's value.
    - Enriched metrics are populated when Snow metric was NULL.
    """
    df = pd.DataFrame([
        {
            "App_ID": "1001",
            "Name": "Oracle Database Enterprise",
            "NoLicenseRequired": "0",
            "Metric": "Installations",
            "IsEndOfLife": "0",
            "IsEndOfSupport": "0",
        },
        {
            "App_ID": "1002",
            "Name": "Docker Desktop 4.25",
            "Version": "4.25.0",
            "NoLicenseRequired": "1",  # Snow says free
            "Metric": "NULL",
            "IsEndOfLife": "0",
            "IsEndOfSupport": "0",
        },
        {
            "App_ID": "1003",
            "Name": "Microsoft 365 Apps",
            "NoLicenseRequired": "0",
            "Metric": "NULL",  # Snow has NULL metric
            "IsEndOfLife": "0",
            "IsEndOfSupport": "0",
        },
        {
            "App_ID": "1004",
            "Name": "7-Zip 23.01",
            "NoLicenseRequired": "1",
            "Metric": "No license required",
            "IsEndOfLife": "0",
            "IsEndOfSupport": "0",
        }
    ])

    col_map = {
        "application": "Name",
        "vendor": None,
        "version": "Version",
        "hostname": None,
        "no_license_required": "NoLicenseRequired",
        "metric": "Metric",
        "is_end_of_life": "IsEndOfLife",
        "is_end_of_support": "IsEndOfSupport",
        "app_id": "App_ID",
    }

    upload_id = "test_snow_baseline_preservation_001"
    summary = BulkUploadProcessor.process_upload_dataframe(
        upload_id=upload_id,
        file_name="srs_apps_sample.csv",
        file_type="CSV",
        df=df,
        column_mapping=col_map,
    )

    from backend.database.connection import SessionLocal
    from backend.models.inventory_upload import UploadLicenseResult

    db = SessionLocal()
    try:
        results = db.query(UploadLicenseResult).filter(UploadLicenseResult.upload_id == upload_id).order_by(UploadLicenseResult.row_index).all()
        assert len(results) == 4

        # Row 1: Oracle -> Snow 0 (YES) + Intel YES -> CONFIRMED
        r1 = results[0]
        assert r1.license_required == "YES"
        assert r1.metric == "Installations"
        assert r1.conflict_status == "CONFIRMED"

        # Row 2: Docker Desktop -> Snow 1 (NO) + Intel YES -> Snow 1 PRESERVED, DISCREPANCY_FLAGGED
        r2 = results[1]
        assert r2.license_required == "NO"  # Strictly preserved Snow baseline!
        assert r2.conflict_status == "DISCREPANCY_FLAGGED"
        assert r2.consensus_status == "REVIEW_RECOMMENDED"
        assert "AUDIT DISCREPANCY" in r2.override_reason

        # Row 3: M365 -> Snow 0 (YES), Metric NULL -> ENRICHED
        r3 = results[2]
        assert r3.license_required == "YES"
        assert r3.metric in ("Users", "Installations", "Devices")
        assert r3.conflict_status in ("ENRICHED", "CONFIRMED")

        # Row 4: 7-Zip -> Snow 1 (NO) + Intel NO -> CONFIRMED
        r4 = results[3]
        assert r4.license_required == "NO"
        assert r4.metric == "No license required"
        assert r4.conflict_status == "CONFIRMED"

    finally:
        # Cleanup test records
        from backend.models.inventory_upload import InventoryUpload, InventoryUploadRow
        db.query(UploadLicenseResult).filter(UploadLicenseResult.upload_id == upload_id).delete()
        db.query(InventoryUploadRow).filter(InventoryUploadRow.upload_id == upload_id).delete()
        db.query(InventoryUpload).filter(InventoryUpload.upload_id == upload_id).delete()
        db.commit()
        db.close()
