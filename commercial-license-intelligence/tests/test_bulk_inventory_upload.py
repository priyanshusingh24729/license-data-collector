"""
Automated unit and integration test suite for Bulk Software Inventory Upload & License Intelligence.
"""

import io
import json
import pytest
import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.models.inventory_upload import InventoryUpload, InventoryUploadRow, UploadLicenseResult
from backend.inventory.upload.upload_parser import UploadFileParser
from backend.inventory.upload.bulk_upload_processor import BulkUploadProcessor
from backend.inventory.upload.upload_job_manager import UploadJobManager


@pytest.fixture
def client():
    return TestClient(app)


class TestUploadParser:
    """Unit tests for column auto-mapping and file parsing."""

    def test_auto_detect_columns_variations(self):
        headers_1 = ["Software Name", "Publisher", "Product Version", "Computer Name"]
        mapping_1 = UploadFileParser.auto_detect_columns(headers_1)
        assert mapping_1["application"] == "Software Name"
        assert mapping_1["vendor"] == "Publisher"
        assert mapping_1["version"] == "Product Version"
        assert mapping_1["hostname"] == "Computer Name"

        headers_2 = ["Display Name", "Manufacturer", "Display Version", "Device ID"]
        mapping_2 = UploadFileParser.auto_detect_columns(headers_2)
        assert mapping_2["application"] == "Display Name"
        assert mapping_2["vendor"] == "Manufacturer"
        assert mapping_2["version"] == "Display Version"
        assert mapping_2["hostname"] == "Device ID"

    def test_preview_upload_csv(self):
        csv_content = (
            "Application Name,Vendor,Version,Hostname\n"
            "Google Chrome,Google LLC,120.0.6099.130,LAPTOP-01\n"
            "Visual Studio Code,Microsoft Corporation,1.85.1,LAPTOP-01\n"
            "Python 3.11,Python Software Foundation,3.11.7,LAPTOP-02\n"
        ).encode("utf-8")

        preview = UploadFileParser.preview_upload(csv_content, "inventory_sample.csv")
        assert preview["file_type"] == "CSV"
        assert preview["total_rows"] == 3
        assert preview["confidence"] == "HIGH"
        assert len(preview["preview_rows"]) == 3
        assert preview["column_mapping"]["application"] == "Application Name"
        assert preview["column_mapping"]["vendor"] == "Vendor"

    def test_preview_upload_excel(self):
        df = pd.DataFrame([
            {"Software": "Zoom Workplace", "Publisher": "Zoom Video Communications", "Release": "5.17.0", "Machine": "HOST-A"},
            {"Software": "Slack", "Publisher": "Slack Technologies", "Release": "4.36.138", "Machine": "HOST-B"},
        ])
        excel_io = io.BytesIO()
        with pd.ExcelWriter(excel_io, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)

        excel_bytes = excel_io.getvalue()
        preview = UploadFileParser.preview_upload(excel_bytes, "test_inventory.xlsx")
        assert preview["file_type"] == "XLSX"
        assert preview["total_rows"] == 2
        assert preview["column_mapping"]["application"] == "Software"
        assert preview["column_mapping"]["vendor"] == "Publisher"
        assert preview["column_mapping"]["version"] == "Release"
        assert preview["column_mapping"]["hostname"] == "Machine"


class TestBulkUploadProcessor:
    """Integration tests for scalable processing, intelligence caching, and data isolation."""

    def test_small_inventory_89_rows_processing(self):
        # Create an 89-row dataset
        apps_sample = [
            ("Google Chrome", "Google LLC", "120.0.6099.130"),
            ("Microsoft Teams", "Microsoft Corporation", "24004.1309.2689.2246"),
            ("Visual Studio Code", "Microsoft Corporation", "1.85.1"),
            ("Python 3.12.0", "Python Software Foundation", "3.12.0"),
            ("Git", "Software Freedom Conservancy", "2.43.0"),
            ("7-Zip", "Igor Pavlov", "23.01"),
            ("VLC media player", "VideoLAN", "3.0.20"),
            ("Postman", "Postman, Inc.", "10.22.0"),
            ("Adobe Acrobat Reader DC", "Adobe Inc.", "23.008.20470"),
            ("Microsoft.GamingApp", "Microsoft Corporation", "2608.1001.17.0"),
        ]

        rows = []
        for i in range(89):
            app_tpl = apps_sample[i % len(apps_sample)]
            rows.append({
                "Application": app_tpl[0],
                "Vendor": app_tpl[1],
                "Version": app_tpl[2],
                "Hostname": f"DESKTOP-{i % 5:02d}",
            })

        df = pd.DataFrame(rows)
        upload_id = "test_upload_89_rows"

        mapping = {
            "application": "Application",
            "vendor": "Vendor",
            "version": "Version",
            "hostname": "Hostname",
        }

        summary = BulkUploadProcessor.process_upload_dataframe(
            upload_id=upload_id,
            file_name="sample_89.csv",
            file_type="CSV",
            df=df,
            column_mapping=mapping,
        )

        assert summary["status"] == "COMPLETED"
        assert summary["total_rows"] == 89
        assert summary["unique_applications"] == 10
        assert summary["unique_machines"] == 5
        assert summary["resolved_count"] + summary["unresolved_count"] == 89
        assert summary["resolved_count"] >= 53

        # Verify results in database
        db = SessionLocal()
        try:
            results = db.query(UploadLicenseResult).filter(UploadLicenseResult.upload_id == upload_id).all()
            assert len(results) == 89

            # Verify Xbox app resolution
            xbox_res = [r for r in results if r.raw_application == "Microsoft.GamingApp"]
            assert len(xbox_res) > 0
            for xr in xbox_res:
                assert xr.canonical_product == "Xbox app for Windows"
                assert xr.classification in ("FREEWARE", "OS_BUNDLED")
                assert xr.license_required == "NO"
        finally:
            db.close()

    def test_scalable_intelligence_caching_large_dataset(self):
        # 1,000 installations of Chrome and VS Code across 200 machines
        rows = []
        for i in range(1000):
            if i % 2 == 0:
                rows.append({
                    "Software": "Google Chrome",
                    "Publisher": "Google",
                    "Version": "120.0.0.0",
                    "Machine": f"PC-{i % 200:03d}",
                })
            else:
                rows.append({
                    "Software": "Visual Studio Code",
                    "Publisher": "Microsoft",
                    "Version": "1.85.0",
                    "Machine": f"PC-{i % 200:03d}",
                })

        df = pd.DataFrame(rows)
        upload_id = "test_upload_caching_1000"

        mapping = {
            "application": "Software",
            "vendor": "Publisher",
            "version": "Version",
            "hostname": "Machine",
        }

        summary = BulkUploadProcessor.process_upload_dataframe(
            upload_id=upload_id,
            file_name="large_simulated.csv",
            file_type="CSV",
            df=df,
            column_mapping=mapping,
        )

        assert summary["status"] == "COMPLETED"
        assert summary["total_rows"] == 1000
        # Exactly 2 unique application product tuples collapsed!
        assert summary["unique_applications"] == 2
        assert summary["unique_machines"] == 200
        assert summary["resolved_count"] == 1000
        # Cache hits should be present
        assert summary["cache_hits"] >= 2

    def test_missing_vendor_and_version_graceful_handling(self):
        rows = [
            {"App": "Git", "Machine": "HOST-1"},
            {"App": "Python", "Machine": "HOST-2"},
            {"App": "Notepad++", "Machine": "HOST-3"},
        ]
        df = pd.DataFrame(rows)
        upload_id = "test_missing_vendor_version"

        summary = BulkUploadProcessor.process_upload_dataframe(
            upload_id=upload_id,
            file_name="sparse.csv",
            file_type="CSV",
            df=df,
            column_mapping={"application": "App", "hostname": "Machine"},
        )

        assert summary["status"] == "COMPLETED"
        assert summary["total_rows"] == 3
        assert summary["resolved_count"] >= 2

    def test_data_isolation_existing_tables_untouched(self):
        db = SessionLocal()
        try:
            detected_apps_count_before = db.query(DetectedApplication).count()
            installation_results_count_before = db.query(InstallationLicenseResult).count()

            # Run an upload
            df = pd.DataFrame([
                {"Name": "Test App Isolation", "Vendor": "Acme Corp", "Version": "1.0", "Host": "ISO-01"}
            ])
            BulkUploadProcessor.process_upload_dataframe(
                upload_id="test_isolation_check",
                file_name="iso.csv",
                file_type="CSV",
                df=df,
                column_mapping={"application": "Name", "vendor": "Vendor", "version": "Version", "hostname": "Host"},
            )

            detected_apps_count_after = db.query(DetectedApplication).count()
            installation_results_count_after = db.query(InstallationLicenseResult).count()

            # Assert complete isolation
            assert detected_apps_count_after == detected_apps_count_before
            assert installation_results_count_after == installation_results_count_before
        finally:
            db.close()


class TestUploadAPIEndpoints:
    """REST API integration tests."""

    def test_api_preview_and_process_flow(self, client):
        csv_data = "Software Name,Publisher,Version,Hostname\nGoogle Chrome,Google,120.0,PC-01\n"
        files = {"file": ("test_inventory.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}

        # 1. Preview
        res = client.post("/api/inventory/upload/preview", files=files)
        assert res.status_code == 200
        preview = res.json()
        assert preview["total_rows"] == 1

        # 2. Process / Start
        files = {"file": ("test_inventory.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
        res_proc = client.post("/api/inventory/upload/process", files=files)
        assert res_proc.status_code == 200
        proc_data = res_proc.json()
        upload_id = proc_data["upload_id"]
        assert upload_id.lower().startswith("up")

        # 3. Job Status with wait
        import time
        for _ in range(20):
            res_status = client.get(f"/api/inventory/upload/jobs/{upload_id}")
            assert res_status.status_code == 200
            status_data = res_status.json()
            if status_data.get("status") in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.3)

        assert status_data["upload_id"] == upload_id
        assert status_data["status"] == "COMPLETED"

        # 4. Results
        res_results = client.get(f"/api/inventory/upload/jobs/{upload_id}/results")
        assert res_results.status_code == 200
        results_data = res_results.json()
        assert isinstance(results_data, list)
        assert len(results_data) >= 1

        # 5. Export CSV
        res_csv = client.get(f"/api/inventory/upload/jobs/{upload_id}/export/csv")
        assert res_csv.status_code == 200
        assert "text/csv" in res_csv.headers["content-type"]

        # 6. Export Excel
        res_xlsx = client.get(f"/api/inventory/upload/jobs/{upload_id}/export/excel")
        assert res_xlsx.status_code == 200
        assert "spreadsheetml" in res_xlsx.headers["content-type"]
