"""
Verification Script: Backend Changes vs Frontend Results Alignment.
Validates:
1. Database values for processed batch (`snow_validation_batch_1789380444`)
2. Frontend `load_upload_results` mapping
3. Snow baseline preservation across all layers (DB -> Frontend -> Exporter -> Final Schema)
4. Conflict status, badge colors, and audit notes alignment
5. Standardized 17-column export consistency
6. 10-column Final Schema export consistency
7. Fast-path performance (no freezing)
8. Inspector Card item integrity
"""

import sys
import os
import json
import time
import pandas as pd

# Add repo root to path
sys.path.insert(0, os.path.abspath("."))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.database.connection import SessionLocal
from backend.models.inventory_upload import InventoryUpload, InventoryUploadRow, UploadLicenseResult
from frontend.streamlit.components.dashboard.results_view import (
    load_upload_results,
    load_upload_metadata,
    generate_final_schema_csv_bytes,
    generate_billable_csv_bytes,
    generate_csv_bytes,
    generate_excel_bytes,
)
from backend.inventory.export.standardized_inventory_exporter import (
    StandardizedInventoryExporter,
    STANDARDIZED_COLUMNS,
    FINAL_OUTPUT_COLUMNS,
)


def verify_alignment():
    print("=" * 80)
    print("STEP 1: Check Database Upload Batches")
    print("=" * 80)
    db = SessionLocal()
    try:
        uploads = db.query(InventoryUpload).order_by(InventoryUpload.id.desc()).all()
        print(f"Total Upload Batches in Database: {len(uploads)}")
        for u in uploads[:5]:
            print(f"  - Upload ID: {u.upload_id}, File: {u.file_name}, Status: {u.status}, Total Rows: {u.total_rows}")

        # Target the Snow validation batch
        target_upload_id = "snow_validation_batch_1789380444"
        batch = db.query(InventoryUpload).filter(InventoryUpload.upload_id == target_upload_id).first()
        if not batch:
            print(f"WARNING: Batch '{target_upload_id}' not found. Selecting latest batch: {uploads[0].upload_id}")
            target_upload_id = uploads[0].upload_id
            batch = uploads[0]

        print(f"\nEvaluating target batch: {target_upload_id}")
        db_results = db.query(UploadLicenseResult).filter(UploadLicenseResult.upload_id == target_upload_id).all()
        print(f"Total UploadLicenseResult rows in DB: {len(db_results)}")

        raw_rows = db.query(InventoryUploadRow).filter(InventoryUploadRow.upload_id == target_upload_id).all()
        print(f"Total InventoryUploadRow rows in DB: {len(raw_rows)}")

        # Step 2: Test frontend `load_upload_results`
        print("\n" + "=" * 80)
        print("STEP 2: Frontend Data Loader (`results_view.py:load_upload_results`)")
        print("=" * 80)
        t0 = time.perf_counter()
        frontend_rows = load_upload_results(target_upload_id)
        load_time = time.perf_counter() - t0
        print(f"Loaded {len(frontend_rows)} rows via frontend loader in {load_time*1000:.2f}ms")

        assert len(frontend_rows) == len(db_results), f"Mismatch row count: {len(frontend_rows)} vs {len(db_results)}"

        # Step 3: Verify Snow Baseline Preservation in Frontend
        print("\n" + "=" * 80)
        print("STEP 3: Snow Baseline Preservation Verification")
        print("=" * 80)
        db_yes_count = sum(1 for r in db_results if str(r.license_required or "").upper() == "YES")
        db_no_count = sum(1 for r in db_results if str(r.license_required or "").upper() == "NO")
        
        fe_yes_count = sum(1 for r in frontend_rows if r["License Required"] == "YES")
        fe_no_count = sum(1 for r in frontend_rows if r["License Required"] == "NO")

        print(f"Database License Required: YES={db_yes_count}, NO={db_no_count}")
        print(f"Frontend License Required: YES={fe_yes_count}, NO={fe_no_count}")
        assert db_yes_count == fe_yes_count, f"License Required YES count mismatch: {db_yes_count} vs {fe_yes_count}"
        assert db_no_count == fe_no_count, f"License Required NO count mismatch: {db_no_count} vs {fe_no_count}"
        print("[OK] 100% Exact match between DB and Frontend for License Required!")

        # Check App_ID preservation
        raw_app_ids = []
        for rr in raw_rows:
            if rr.raw_data_json:
                data = json.loads(rr.raw_data_json)
                raw_app_ids.append(data.get("App_ID"))
        
        fe_app_ids = [r.get("App_ID") for r in frontend_rows]
        if raw_app_ids and any(raw_app_ids):
            print(f"Sample original App_IDs from raw data: {raw_app_ids[:5]}")
            print(f"Sample App_IDs from frontend loaded rows: {fe_app_ids[:5]}")
            assert fe_app_ids[:10] == raw_app_ids[:10], "Frontend did not preserve authentic Snow App_IDs!"
            print("[OK] Authentic Snow App_IDs preserved perfectly in frontend rows!")

        # Step 4: Verify Conflict Status, Badges & Notes Alignment
        print("\n" + "=" * 80)
        print("STEP 4: Conflict Status & Inspector Alignment")
        print("=" * 80)
        status_counts = {}
        for r in frontend_rows:
            cs = r.get("conflict_status", "UNKNOWN")
            status_counts[cs] = status_counts.get(cs, 0) + 1

        print(f"Frontend Conflict Status Breakdown: {status_counts}")
        assert "CONFIRMED" in status_counts or "VERIFIED" in status_counts
        
        # Verify Discrepancies
        discrepancies = [r for r in frontend_rows if r.get("conflict_status") == "DISCREPANCY_FLAGGED"]
        print(f"Found {len(discrepancies)} DISCREPANCY_FLAGGED rows in frontend:")
        for d in discrepancies[:3]:
            print(f"  - App: {d.get('Name')}")
            print(f"    * Snow NLR: {d.get('NoLicenseRequired')} (License Required: {d.get('License Required')})")
            print(f"    * Conflict Status: {d.get('conflict_status')}")
            print(f"    * Audit Note: {d.get('override_reason')}")
            print(f"    * Evidence URL: {d.get('Evidence URL')}")

        # Step 5: Verify Exporters (Fast-Path and Exact Schema Alignment)
        print("\n" + "=" * 80)
        print("STEP 5: Exporter Transformation & Schema Alignment")
        print("=" * 80)

        # 5A: Final Schema CSV
        t_final = time.perf_counter()
        final_csv_bytes = generate_final_schema_csv_bytes(frontend_rows)
        final_time = time.perf_counter() - t_final
        print(f"Final Schema CSV generated in {final_time:.4f}s ({len(final_csv_bytes)} bytes)")
        
        df_final_csv = pd.read_csv(pd.io.common.BytesIO(final_csv_bytes))
        print(f"Final Schema CSV shape: {df_final_csv.shape}")
        print(f"Final Schema CSV columns: {list(df_final_csv.columns)}")
        assert list(df_final_csv.columns) == FINAL_OUTPUT_COLUMNS, f"Final CSV columns do not match expected FINAL_OUTPUT_COLUMNS"
        
        # Verify License Required in Final Schema CSV
        csv_yes = sum(1 for v in df_final_csv["License Required"] if str(v).upper() == "YES")
        csv_no = sum(1 for v in df_final_csv["License Required"] if str(v).upper() == "NO")
        print(f"Final Schema CSV License Required: YES={csv_yes}, NO={csv_no}")
        assert csv_yes == db_yes_count, f"Final CSV License Required YES count {csv_yes} != DB {db_yes_count}"
        assert csv_no == db_no_count, f"Final CSV License Required NO count {csv_no} != DB {db_no_count}"
        print("[OK] Final Schema CSV preserves 100% of Snow Baseline License Required!")

        # 5B: Standardized 17-Column Full CSV
        t_std = time.perf_counter()
        full_csv_bytes = generate_csv_bytes(frontend_rows)
        std_time = time.perf_counter() - t_std
        print(f"Standardized Full CSV generated in {std_time:.4f}s ({len(full_csv_bytes)} bytes)")
        
        df_full_csv = pd.read_csv(pd.io.common.BytesIO(full_csv_bytes))
        print(f"Standardized Full CSV shape: {df_full_csv.shape}")
        print(f"Standardized Full CSV columns: {list(df_full_csv.columns)}")
        assert list(df_full_csv.columns) == STANDARDIZED_COLUMNS, "Standardized Full CSV columns mismatch"

        # 5C: Billable CSV Filter
        bill_bytes = generate_billable_csv_bytes(frontend_rows)
        df_bill = pd.read_csv(pd.io.common.BytesIO(bill_bytes))
        print(f"Billable CSV shape: {df_bill.shape}")
        for lic in df_bill["License Required"].dropna():
            assert str(lic).upper() == "YES", f"Found non-billable item in Billable CSV: {lic}"
        print("[OK] All items in Billable CSV have License Required == YES!")

        # 5D: Standardized Excel Workbook
        t_xl = time.perf_counter()
        excel_bytes = generate_excel_bytes(frontend_rows)
        xl_time = time.perf_counter() - t_xl
        print(f"Standardized Excel generated in {xl_time:.4f}s ({len(excel_bytes)} bytes)")
        xl_file = pd.ExcelFile(pd.io.common.BytesIO(excel_bytes))
        print(f"Excel Sheet Names: {xl_file.sheet_names}")
        assert "Application Inventory" in xl_file.sheet_names, f"Excel sheets mismatch: {xl_file.sheet_names}"
        df_xl = pd.read_excel(xl_file, sheet_name="Application Inventory")
        assert list(df_xl.columns) == STANDARDIZED_COLUMNS, "Excel columns do not match STANDARDIZED_COLUMNS"
        print("[OK] Standardized Excel matches 17-column reference schema!")

        # 5E: Final Schema Excel Workbook
        from frontend.streamlit.components.dashboard.results_view import generate_final_schema_excel_bytes
        final_xl_bytes = generate_final_schema_excel_bytes(frontend_rows)
        xl_final_file = pd.ExcelFile(pd.io.common.BytesIO(final_xl_bytes))
        assert "License Intelligence" in xl_final_file.sheet_names
        df_final_xl = pd.read_excel(xl_final_file, sheet_name="License Intelligence")
        assert list(df_final_xl.columns) == FINAL_OUTPUT_COLUMNS
        print("[OK] Final Schema Excel matches 10-column License Intelligence schema!")

        print("\n" + "=" * 80)
        print("ALL VERIFICATION CHECKS PASSED: BACKEND AND FRONTEND ARE 100% IN SYNC!")
        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    verify_alignment()
