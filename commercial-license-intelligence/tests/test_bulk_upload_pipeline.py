"""
Comprehensive unit and integration test suite for Bulk CSV/Excel Software Inventory Uploads & Processing.
Tests:
- Automatic column mapping detection and confidence scoring
- CSV & Excel file parsing and previewing
- Small inventory (89 rows) processing
- Large-scale inventory canonical grouping and research cache reuse
- Strict database isolation from baseline tables
- CSV & Excel exports
- FastAPI REST API endpoints
"""

import os
import io
import csv
import json
import pytest
import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.connection import SessionLocal, engine, Base
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.models.inventory_upload import InventoryUpload, InventoryUploadRow, UploadLicenseResult
from backend.inventory.processing.column_mapper import ColumnMapper
from backend.inventory.processing.bulk_upload_service import BulkInventoryUploadService


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_column_mapper_heuristics():
    """Tests column mapper with various header synonym combinations."""
    headers_1 = ["Software Name", "Publisher", "Product Version", "Computer Name", "Install Date"]
    mapping_1 = ColumnMapper.auto_detect_columns(headers_1)
    
    assert mapping_1["application"] == "Software Name"
    assert mapping_1["vendor"] == "Publisher"
    assert mapping_1["version"] == "Product Version"
    assert mapping_1["hostname"] == "Computer Name"
    assert mapping_1["install_date"] == "Install Date"

    confidence_1 = ColumnMapper.calculate_confidence(headers_1, mapping_1)
    assert confidence_1["is_valid"] is True
    assert confidence_1["confidence"] == "HIGH"

    # Test with minimal columns (only application name)
    headers_2 = ["Display Name"]
    mapping_2 = ColumnMapper.auto_detect_columns(headers_2)
    assert mapping_2["application"] == "Display Name"
    assert mapping_2["vendor"] is None
    assert mapping_2["version"] is None

    confidence_2 = ColumnMapper.calculate_confidence(headers_2, mapping_2)
    assert confidence_2["is_valid"] is True


def test_column_mapper_row_extraction():
    """Tests row data extraction with missing or null fields."""
    mapping = {
        "application": "App",
        "vendor": "Mfr",
        "version": "Ver",
        "hostname": "PC",
    }
    raw_row = {
        "App": "Google Chrome",
        "Mfr": "Google LLC",
        "Ver": "120.0.0.0",
        "PC": "WORKSTATION-01",
    }
    extracted = ColumnMapper.extract_row_data(raw_row, mapping, row_index=1)
    assert extracted["raw_application"] == "Google Chrome"
    assert extracted["raw_vendor"] == "Google LLC"
    assert extracted["raw_version"] == "120.0.0.0"
    assert extracted["hostname"] == "WORKSTATION-01"

    # With missing optional values
    raw_row_empty = {
        "App": "Docker Desktop",
        "Mfr": "N/A",
        "Ver": "",
        "PC": None,
    }
    extracted_empty = ColumnMapper.extract_row_data(raw_row_empty, mapping, row_index=2)
    assert extracted_empty["raw_application"] == "Docker Desktop"
    assert extracted_empty["raw_vendor"] is None
    assert extracted_empty["raw_version"] is None
    assert extracted_empty["hostname"] == "UNKNOWN_HOST"


def test_preview_csv_and_excel():
    """Tests file preview functionality for CSV and Excel formats."""
    # 1. Create in-memory CSV
    csv_rows = [
        {"Application Name": "Google Chrome", "Vendor": "Google", "Version": "118.0", "Hostname": "PC1"},
        {"Application Name": "Docker Desktop", "Vendor": "Docker", "Version": "4.25", "Hostname": "PC1"},
        {"Application Name": "Python 3.11", "Vendor": "Python", "Version": "3.11.4", "Hostname": "PC2"},
    ]
    csv_buf = io.StringIO()
    writer = csv.DictWriter(csv_buf, fieldnames=list(csv_rows[0].keys()))
    writer.writeheader()
    writer.writerows(csv_rows)
    csv_bytes = csv_buf.getvalue().encode("utf-8")

    preview_csv = BulkInventoryUploadService.preview_file(csv_bytes, "test_inv.csv")
    assert preview_csv["file_type"] == "CSV"
    assert preview_csv["total_rows"] == 3
    assert preview_csv["detected_mapping"]["application"] == "Application Name"
    assert len(preview_csv["sample_rows"]) == 3

    # 2. Create in-memory Excel
    excel_df = pd.DataFrame(csv_rows)
    excel_buf = io.BytesIO()
    with pd.ExcelWriter(excel_buf, engine="openpyxl") as xw:
        excel_df.to_excel(xw, index=False)
    excel_bytes = excel_buf.getvalue()

    preview_excel = BulkInventoryUploadService.preview_file(excel_bytes, "test_inv.xlsx")
    assert preview_excel["file_type"] == "XLSX"
    assert preview_excel["total_rows"] == 3
    assert preview_excel["detected_mapping"]["application"] == "Application Name"


def test_small_inventory_processing_and_isolation():
    """
    Tests processing an 89-row inventory CSV and validates strict database isolation
    from detected_applications and installation_license_results baseline tables.
    """
    db = SessionLocal()
    try:
        baseline_da_count_before = db.query(DetectedApplication).count()
        baseline_ilr_count_before = db.query(InstallationLicenseResult).count()

        # Build 89 rows of diverse software inventory across 10 machines
        sample_apps = [
            ("Google Chrome", "Google", "120.0.6099.130"),
            ("Microsoft Visual Studio Code", "Microsoft", "1.85.1"),
            ("Docker Desktop", "Docker Inc.", "4.26.1"),
            ("Python 3.12.1", "Python Software Foundation", "3.12.1"),
            ("Git", "The Git Development Community", "2.43.0"),
            ("Node.js", "Node.js Foundation", "20.10.0"),
            ("Brave", "Brave Software Inc", "1.61.100"),
            ("Microsoft Teams", "Microsoft", "23320.3021.2567.4799"),
            ("Microsoft Edge", "Microsoft", "120.0.2210.91"),
        ]

        csv_rows = []
        for i in range(89):
            app_tuple = sample_apps[i % len(sample_apps)]
            host_name = f"ENDPOINT-MACHINE-{ (i % 10) + 1:02d}"
            csv_rows.append({
                "Software": app_tuple[0],
                "Publisher": app_tuple[1],
                "Version": app_tuple[2],
                "Device Name": host_name,
            })

        csv_buf = io.StringIO()
        writer = csv.DictWriter(csv_buf, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)
        csv_bytes = csv_buf.getvalue().encode("utf-8")

        column_mapping = {
            "application": "Software",
            "vendor": "Publisher",
            "version": "Version",
            "hostname": "Device Name",
        }

        # Run upload processing job synchronously
        summary = BulkInventoryUploadService.start_upload_job(
            file_bytes=csv_bytes,
            file_name="small_inventory_89.csv",
            column_mapping=column_mapping,
            run_async=False,
            db_session=db,
        )

        assert summary is not None
        upload_id = summary["upload_id"]
        assert summary["total_raw_rows"] == 89
        assert summary["unique_machines"] == 10
        assert summary["resolved_records"] > 0

        # Check isolated results in database
        results = BulkInventoryUploadService.get_upload_results(upload_id=upload_id, limit=200, db_session=db)
        assert len(results) == summary["total_qualified_rows"]
        assert len(results) > 0

        # Verify classifications exist
        classes = {r["classification"] for r in results}
        assert "FREEWARE" in classes or "OPEN_SOURCE" in classes or "COMMERCIAL" in classes

        # STRICT ISOLATION ASSERTION: Baseline tables must NOT be modified
        baseline_da_count_after = db.query(DetectedApplication).count()
        baseline_ilr_count_after = db.query(InstallationLicenseResult).count()

        assert baseline_da_count_after == baseline_da_count_before, "detected_applications baseline was modified!"
        assert baseline_ilr_count_after == baseline_ilr_count_before, "installation_license_results table was modified!"

        # Test export generation (Standardized 14-column schema)
        csv_export = BulkInventoryUploadService.export_results_csv(upload_id=upload_id, db_session=db)
        assert "App_ID" in csv_export
        assert "Normalized_Application" in csv_export
        assert "OSType" in csv_export

        # Test legacy export when explicitly requested
        csv_legacy = BulkInventoryUploadService.export_results_csv(upload_id=upload_id, db_session=db, legacy=True)
        assert "Hostname" in csv_legacy
        assert "Canonical Product" in csv_legacy
        assert "Classification" in csv_legacy

        excel_export = BulkInventoryUploadService.export_results_excel(upload_id=upload_id, db_session=db)
        assert len(excel_export) > 1000

    finally:
        db.close()


def test_large_inventory_canonical_caching():
    """
    Tests processing a 1,000-row inventory where Google Chrome appears on 200 machines,
    Docker on 200 machines, Git on 200 machines, etc.
    Verifies that research is deduplicated and canonical knowledge is reused.
    """
    db = SessionLocal()
    try:
        sample_apps = [
            ("Google Chrome", "Google", "120.0.0.0"),
            ("Docker Desktop", "Docker Inc.", "4.26.0"),
            ("Git", "Git Community", "2.40.0"),
            ("Node.js", "Node.js Foundation", "20.0.0"),
            ("Microsoft Edge", "Microsoft", "120.0.0.0"),
        ]

        csv_rows = []
        for i in range(1000):
            app_tuple = sample_apps[i % len(sample_apps)]
            host_name = f"WORKSTATION-{ (i // 5) + 1:04d}"
            csv_rows.append({
                "Program Name": app_tuple[0],
                "Company": app_tuple[1],
                "Release Version": app_tuple[2],
                "Machine ID": host_name,
            })

        csv_buf = io.StringIO()
        writer = csv.DictWriter(csv_buf, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)
        csv_bytes = csv_buf.getvalue().encode("utf-8")

        column_mapping = {
            "application": "Program Name",
            "vendor": "Company",
            "version": "Release Version",
            "hostname": "Machine ID",
        }

        summary = BulkInventoryUploadService.start_upload_job(
            file_bytes=csv_bytes,
            file_name="large_simulated_1000.csv",
            column_mapping=column_mapping,
            run_async=False,
            db_session=db,
        )

        assert summary["total_raw_rows"] == 1000
        assert summary["unique_machines"] == 200
        # 1,000 raw rows should aggregate into only 5 unique canonical applications!
        assert summary["unique_applications"] == 5
        assert summary["cache_hits"] >= 5
        assert summary["total_qualified_rows"] == 1000

    finally:
        db.close()


def test_api_upload_endpoints():
    """Tests the FastAPI upload endpoints (/preview, /start, /jobs, /results, /export)."""
    client = TestClient(app)

    csv_content = (
        "Application,Vendor,Version,Hostname\n"
        "Google Chrome,Google,120.0.0,HOST-A\n"
        "Docker Desktop,Docker,4.25.0,HOST-A\n"
        "Python 3.12,PSF,3.12.0,HOST-B\n"
    ).encode("utf-8")

    # 1. Preview Endpoint
    preview_res = client.post(
        "/api/inventory/upload/preview",
        files={"file": ("inventory.csv", csv_content, "text/csv")},
    )
    assert preview_res.status_code == 200
    pdata = preview_res.json()
    assert pdata["total_rows"] == 3
    assert pdata["detected_mapping"]["application"] == "Application"

    # 2. Start Job Endpoint
    start_res = client.post(
        "/api/inventory/upload/start",
        files={"file": ("inventory.csv", csv_content, "text/csv")},
        data={"column_mapping": json.dumps(pdata["detected_mapping"])},
    )
    assert start_res.status_code == 202
    job_info = start_res.json()
    upload_id = job_info["upload_id"]
    assert upload_id.startswith("UP_")

    # 3. Jobs List Endpoint
    jobs_res = client.get("/api/inventory/upload/jobs")
    assert jobs_res.status_code == 200
    jobs_list = jobs_res.json()
    assert any(j["upload_id"] == upload_id for j in jobs_list)

    # 4. Job Progress Endpoint
    prog_res = client.get(f"/api/inventory/upload/jobs/{upload_id}")
    assert prog_res.status_code == 200
    prog_data = prog_res.json()
    assert "status" in prog_data

    # Synchronous processing check on another test run for instant results verification
    db = SessionLocal()
    try:
        sync_summary = BulkInventoryUploadService.start_upload_job(
            file_bytes=csv_content,
            file_name="sync_test.csv",
            column_mapping={"application": "Application", "vendor": "Vendor", "version": "Version", "hostname": "Hostname"},
            run_async=False,
            db_session=db,
        )
        sync_upload_id = sync_summary["upload_id"]

        # 5. Results Endpoint
        res_endpoint = client.get(f"/api/inventory/upload/jobs/{sync_upload_id}/results")
        assert res_endpoint.status_code == 200
        results_list = res_endpoint.json()
        assert len(results_list) == 3

        # 6. CSV Export Endpoint
        exp_csv = client.get(f"/api/inventory/upload/jobs/{sync_upload_id}/export/csv")
        assert exp_csv.status_code == 200
        assert "text/csv" in exp_csv.headers["content-type"]

        # 7. Excel Export Endpoint
        exp_xlsx = client.get(f"/api/inventory/upload/jobs/{sync_upload_id}/export/excel")
        assert exp_xlsx.status_code == 200
        assert len(exp_xlsx.content) > 500

        # 8. Delete Endpoint
        del_res = client.delete(f"/api/inventory/upload/jobs/{sync_upload_id}")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "DELETED"

    finally:
        db.close()
