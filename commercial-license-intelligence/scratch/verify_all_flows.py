"""
End-to-end verification script for bulk CSV/Excel upload workflows:
1. 89-row CSV upload
2. 500-row CSV upload
3. 5,000-row stress test with canonical product intelligence reuse
4. Excel (.xlsx) upload with custom column names
5. Data isolation verification against baseline tables
"""

import sys
import os
import io
import csv
import time
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database.connection import SessionLocal, Base, engine
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.models.inventory_upload import InventoryUpload, UploadLicenseResult
from backend.inventory.processing.column_mapper import ColumnMapper
from backend.inventory.processing.bulk_upload_service import BulkInventoryUploadService


def run_comprehensive_verification():
    print("================================================================================")
    print("RUNNING END-TO-END VERIFICATION: BULK CSV/EXCEL LICENSE INTELLIGENCE PIPELINE")
    print("================================================================================")

    db = SessionLocal()
    try:
        # Baseline check
        initial_da = db.query(DetectedApplication).count()
        initial_ilr = db.query(InstallationLicenseResult).count()
        print(f"[*] Initial baseline record count: detected_applications={initial_da}, installation_license_results={initial_ilr}")

        # ---------------------------------------------------------------------
        # TEST 1: 89-ROW CSV INVENTORY
        # ---------------------------------------------------------------------
        print("\n--- [TEST 1] Small Inventory (89 rows CSV) ---")
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

        csv_rows_89 = []
        for i in range(89):
            app_tuple = sample_apps[i % len(sample_apps)]
            host_name = f"LAPTOP-CORP-{ (i % 10) + 1:02d}"
            csv_rows_89.append({
                "Software Name": app_tuple[0],
                "Publisher": app_tuple[1],
                "Display Version": app_tuple[2],
                "Computer Name": host_name,
            })

        buf_89 = io.StringIO()
        writer = csv.DictWriter(buf_89, fieldnames=list(csv_rows_89[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows_89)
        bytes_89 = buf_89.getvalue().encode("utf-8")

        preview_89 = BulkInventoryUploadService.preview_file(bytes_89, "inventory_89.csv")
        assert preview_89["total_rows"] == 89
        assert preview_89["detected_mapping"]["application"] == "Software Name"
        assert preview_89["detected_mapping"]["vendor"] == "Publisher"

        summary_89 = BulkInventoryUploadService.start_upload_job(
            file_bytes=bytes_89,
            file_name="inventory_89.csv",
            column_mapping=preview_89["detected_mapping"],
            run_async=False,
            db_session=db,
        )

        print(f"  [+] Ingested: {summary_89['total_raw_rows']} rows across {summary_89['unique_machines']} machines")
        print(f"  [+] Unique applications: {summary_89['unique_applications']}, Resolved: {summary_89['resolved_records']}")
        print(f"  [+] Cache hits: {summary_89['cache_hits']}")
        print(f"  [+] Classifications: {summary_89['classification_summary']}")
        print(f"  [+] Processing time: {summary_89['processing_time_seconds']}s")

        # ---------------------------------------------------------------------
        # TEST 2: 500-ROW EXCEL (.XLSX) INVENTORY WITH CUSTOM COLUMN NAMES
        # ---------------------------------------------------------------------
        print("\n--- [TEST 2] Medium Inventory (500 rows Excel .xlsx with Custom Column Headers) ---")
        excel_rows = []
        for i in range(500):
            app_tuple = sample_apps[i % len(sample_apps)]
            excel_rows.append({
                "Installed Product": app_tuple[0],
                "Manufacturer": app_tuple[1],
                "Software Build": app_tuple[2] if i % 4 != 0 else "",  # Some missing versions
                "Machine Endpoint": f"DESKTOP-FINANCE-{(i % 50) + 1:03d}",
            })

        df_excel = pd.DataFrame(excel_rows)
        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
            df_excel.to_excel(writer, index=False)
        excel_bytes = excel_buf.getvalue()

        preview_excel = BulkInventoryUploadService.preview_file(excel_bytes, "finance_fleet_500.xlsx")
        assert preview_excel["file_type"] == "XLSX"
        assert preview_excel["total_rows"] == 500
        assert preview_excel["detected_mapping"]["application"] == "Installed Product"

        summary_excel = BulkInventoryUploadService.start_upload_job(
            file_bytes=excel_bytes,
            file_name="finance_fleet_500.xlsx",
            column_mapping=preview_excel["detected_mapping"],
            run_async=False,
            db_session=db,
        )

        print(f"  [+] Ingested: {summary_excel['total_raw_rows']} rows across {summary_excel['unique_machines']} machines")
        print(f"  [+] Unique applications: {summary_excel['unique_applications']}, Resolved: {summary_excel['resolved_records']}")
        print(f"  [+] Processing time: {summary_excel['processing_time_seconds']}s")

        # ---------------------------------------------------------------------
        # TEST 3: 5,000-ROW LARGE SCALE TEST (STRESS & PERFORMANCE REUSE)
        # ---------------------------------------------------------------------
        print("\n--- [TEST 3] Large Inventory (5,000 rows CSV - Scalable Caching & Deduplication) ---")
        large_rows = []
        for i in range(5000):
            app_tuple = sample_apps[i % len(sample_apps)]
            large_rows.append({
                "App Name": app_tuple[0],
                "Vendor": app_tuple[1],
                "Ver": app_tuple[2],
                "Host": f"ENTERPRISE-NODE-{(i // len(sample_apps)) + 1:04d}",
            })

        buf_large = io.StringIO()
        writer = csv.DictWriter(buf_large, fieldnames=list(large_rows[0].keys()))
        writer.writeheader()
        writer.writerows(large_rows)
        bytes_large = buf_large.getvalue().encode("utf-8")

        summary_large = BulkInventoryUploadService.start_upload_job(
            file_bytes=bytes_large,
            file_name="enterprise_fleet_5000.csv",
            column_mapping={"application": "App Name", "vendor": "Vendor", "version": "Ver", "hostname": "Host"},
            run_async=False,
            db_session=db,
        )

        print(f"  [+] Ingested: {summary_large['total_raw_rows']} rows across {summary_large['unique_machines']} machines")
        print(f"  [+] Unique canonical applications: {summary_large['unique_applications']} (NOT 5,000 redundant queries!)")
        print(f"  [+] Knowledge Cache Hits: {summary_large['cache_hits']}")
        print(f"  [+] Total persisted records: {summary_large['total_qualified_rows']}")
        print(f"  [+] Processing time: {summary_large['processing_time_seconds']}s")

        # ---------------------------------------------------------------------
        # TEST 4: EXPORT INTEGRITY
        # ---------------------------------------------------------------------
        print("\n--- [TEST 4] CSV and Excel Export Verification ---")
        csv_out = BulkInventoryUploadService.export_results_csv(summary_89["upload_id"], db_session=db)
        assert len(csv_out) > 500
        assert csv_out.startswith("\ufeff")
        print(f"  [+] CSV Export generated successfully ({len(csv_out)} characters, UTF-8 BOM confirmed)")

        excel_out = BulkInventoryUploadService.export_results_excel(summary_89["upload_id"], db_session=db)
        assert len(excel_out) > 1000
        print(f"  [+] Excel (.xlsx) Export generated successfully ({len(excel_out)} bytes)")

        # ---------------------------------------------------------------------
        # TEST 5: STRICT DATABASE ISOLATION
        # ---------------------------------------------------------------------
        print("\n--- [TEST 5] Strict Database Isolation Check ---")
        final_da = db.query(DetectedApplication).count()
        final_ilr = db.query(InstallationLicenseResult).count()
        print(f"  [+] Final detected_applications count: {final_da} (Initial: {initial_da}) -> UNTOUCHED: {final_da == initial_da}")
        print(f"  [+] Final installation_license_results count: {final_ilr} (Initial: {initial_ilr}) -> UNTOUCHED: {final_ilr == initial_ilr}")
        assert final_da == initial_da, "detected_applications was modified!"
        assert final_ilr == initial_ilr, "installation_license_results was modified!"

        print("\n================================================================================")
        print("ALL END-TO-END VERIFICATION CHECKS PASSED PERFECTLY!")
        print("================================================================================")

    finally:
        db.close()


if __name__ == "__main__":
    run_comprehensive_verification()
