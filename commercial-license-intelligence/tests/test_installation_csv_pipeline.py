"""
Test Suite for Isolated Installation CSV Processing Pipeline & Dual Tables.
Verifies:
1. Data isolation: Main application inventory (detected_applications) remains unchanged (163 records).
2. InstallationLicenseResult separate table stores machine-specific intelligence records (82 records).
3. API endpoints return isolated datasets for both Main Inventory and Machine Installation Results.
4. Export endpoints produce valid separate CSV files.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.inventory.processing.batch_csv_processor import BatchInstallationCSVProcessor
from backend.main import app


def test_isolated_csv_processing():
    """Verify processing the CSV populates the separate table without touching the main inventory."""
    db = SessionLocal()
    try:
        # Pre-check main inventory count
        main_baseline_count = db.query(DetectedApplication).count()
        assert main_baseline_count == 163, f"Expected 163 main inventory records, found {main_baseline_count}"

        # Run batch CSV processor on updated CSV
        csv_path = os.path.abspath("data/PF490A36_LAPTOP-TTASCMUO_Installation(1).csv")
        summary = BatchInstallationCSVProcessor.process_csv(csv_path, db_session=db)

        assert summary["total_input_records"] >= 80
        assert summary["final_machine_result_count"] >= 75

        # Verify main inventory count is STILL exactly 163 (STRICT DATA ISOLATION)
        main_after_count = db.query(DetectedApplication).count()
        assert main_after_count == 163, "Main inventory was modified during CSV processing!"

        # Verify separate table records
        isolated_records = db.query(InstallationLicenseResult).filter(
            InstallationLicenseResult.unique_id == "PF490A36_LAPTOP-TTASCMUO"
        ).all()
        assert len(isolated_records) == summary["final_machine_result_count"]

        # Check required fields on sample record
        sample = isolated_records[0]
        assert sample.unique_id == "PF490A36_LAPTOP-TTASCMUO"
        assert sample.hostname == "LAPTOP-TTASCMUO"
        assert sample.serial == "PF490A36"
        assert sample.raw_application_name is not None
        assert sample.classification is not None
        assert sample.reliability_score is not None
        assert sample.processed_at is not None

        # Verify Docker Desktop
        docker = next((r for r in isolated_records if "Docker Desktop" in r.raw_application_name), None)
        assert docker is not None
        assert docker.canonical_product == "Docker Desktop"
        assert docker.canonical_vendor == "Docker Inc."
        assert docker.classification == "COMMERCIAL"
        assert docker.reliability_score >= 90.0

        # Verify Go Programming Language
        go = next((r for r in isolated_records if "Go Programming Language" in r.raw_application_name), None)
        assert go is not None
        assert go.canonical_product == "Go Programming Language"
        assert go.classification == "OPEN_SOURCE"
        assert go.reliability_score >= 90.0

        # Verify ChatGPT
        chatgpt = next((r for r in isolated_records if "ChatGPT" in r.raw_application_name), None)
        assert chatgpt is not None
        assert chatgpt.canonical_product == "ChatGPT"
        assert chatgpt.classification == "FREE_AND_PAID"
        assert chatgpt.reliability_score >= 95.0

    finally:
        db.close()


def test_api_endpoints_dual_tables():
    """Verify separate API endpoints for main inventory and machine installation results."""
    client = TestClient(app)

    # 1. Main Application Inventory endpoint
    res_main = client.get("/api/inventory/main-applications")
    assert res_main.status_code == 200
    main_items = res_main.json()
    assert len(main_items) == 163

    # 2. Machine Installation Results endpoint
    res_mach = client.get("/api/inventory/installation-results?unique_id=PF490A36_LAPTOP-TTASCMUO")
    assert res_mach.status_code == 200
    mach_items = res_mach.json()
    assert len(mach_items) >= 75

    # 3. Main Application Inventory export
    res_main_export = client.get("/api/inventory/main-applications/export")
    assert res_main_export.status_code == 200
    assert "text/csv" in res_main_export.headers["content-type"]
    assert "main_application_inventory.csv" in res_main_export.headers["content-disposition"]
    main_lines = res_main_export.text.strip().split("\n")
    assert len(main_lines) <= 164 and len(main_lines) >= 150  # Header + deduplicated application records

    # 4. Machine Installation Results export
    res_mach_export = client.get("/api/inventory/installation-results/export?unique_id=PF490A36_LAPTOP-TTASCMUO")
    assert res_mach_export.status_code == 200
    assert "text/csv" in res_mach_export.headers["content-type"]
    assert "PF490A36_LAPTOP-TTASCMUO_installation_results.csv" in res_mach_export.headers["content-disposition"]
    mach_lines = res_mach_export.text.strip().split("\n")
    assert len(mach_lines) <= len(mach_items) + 1 and len(mach_lines) >= 70  # Header + deduplicated data rows
