import os
import sys
import json
import sqlite3
import pandas as pd
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath("."))

from backend.database.connection import SessionLocal
from backend.models.inventory_upload import InventoryUpload, InventoryUploadRow, UploadLicenseResult
from backend.inventory.upload.bulk_upload_processor import BulkUploadProcessor
from backend.inventory.export.standardized_inventory_exporter import StandardizedInventoryExporter

TARGET_UPLOAD_ID = sys.argv[1] if len(sys.argv) > 1 else "upl_20260925_060821_4fa0996a"

def reprocess_and_audit():
    print("=" * 80)
    print(f"REPROCESSING UPLOAD: {TARGET_UPLOAD_ID}")
    print("=" * 80)

    db = SessionLocal()
    try:
        raw_rows = db.query(InventoryUploadRow).filter(
            InventoryUploadRow.upload_id == TARGET_UPLOAD_ID
        ).order_by(InventoryUploadRow.row_index).all()

        print(f"Found {len(raw_rows)} raw rows in database.")
        if not raw_rows:
            print("No rows found!")
            return

        # Reconstruct DataFrame from raw_data
        df_records = []
        for r in raw_rows:
            row_dict = r.raw_data if isinstance(r.raw_data, dict) else json.loads(r.raw_data)
            df_records.append(row_dict)

        df = pd.DataFrame(df_records)
        print(f"Constructed DataFrame with shape {df.shape}, columns: {list(df.columns)}")

        # Delete existing license results and upload rows for this upload_id so processor can recreate them cleanly
        deleted_res = db.query(UploadLicenseResult).filter(UploadLicenseResult.upload_id == TARGET_UPLOAD_ID).delete()
        deleted_rows = db.query(InventoryUploadRow).filter(InventoryUploadRow.upload_id == TARGET_UPLOAD_ID).delete()
        db.commit()
        print(f"Cleaned previous results: {deleted_res} results, {deleted_rows} raw rows.")

        # Re-run processor
        col_mapping = {
            "application": "Application_Name" if "Application_Name" in df.columns else "Name",
            "vendor": "Vendor" if "Vendor" in df.columns else None,
            "version": "Version" if "Version" in df.columns else None,
            "hostname": "Hostname" if "Hostname" in df.columns else None,
            "install_location": "Install_Location" if "Install_Location" in df.columns else None,
            "install_source": "Install_Source" if "Install_Source" in df.columns else None,
        }

        # Prevent external network calls during audit evaluation
        os.environ["ENABLE_WINGET_CLI_SEARCH"] = "false"
        os.environ["ENABLE_SEARXNG_FALLBACK"] = "false"

        summary = BulkUploadProcessor.process_upload_dataframe(
            upload_id=TARGET_UPLOAD_ID,
            file_name="PF490A36_LAPTOP-TTASCMUO_Installation.csv",
            file_type="CSV",
            df=df,
            column_mapping=col_mapping,
        )
        print("Processing Summary:", summary)

        # Retrieve new results
        new_results = db.query(UploadLicenseResult).filter(
            UploadLicenseResult.upload_id == TARGET_UPLOAD_ID
        ).order_by(UploadLicenseResult.row_index).all()

        print(f"\nGenerated {len(new_results)} new results.")

        # Export to Standardized CSV
        dict_records = []
        for r in new_results:
            dict_records.append({
                "App_ID": r.row_index,
                "raw_application": r.raw_application,
                "Application Name": r.canonical_product,
                "Normalized_Application": r.canonical_product,
                "Vendor": r.canonical_vendor,
                "Version": r.version,
                "Operating_System": "Windows",
                "Classification": r.classification,
                "License Required": r.license_required,
                "License Model": r.license_model,
                "Metric": r.metric,
                "IsEndOfLife": r.is_end_of_life,
                "IsEndOfSupport": r.is_end_of_support,
                "Evidence URL": r.evidence_url,
                "is_already_resolved": True,
                "conflict_status": r.conflict_status,
            })

        df_std = StandardizedInventoryExporter.transform_inventory(
            records=dict_records,
            scan_timestamp="2026-09-15 04:58:41",
            device_context={"operating_system": "Windows", "device_name": "LAPTOP-TTASCMUO"},
        )

        csv_bytes = StandardizedInventoryExporter.to_csv_bytes(df_std)
        out_csv = "data/standardized_inventory_93.csv"
        with open(out_csv, "wb") as f:
            f.write(csv_bytes)
        print(f"Saved standardized export to {out_csv} ({len(df_std)} rows)")

        # Save to exports/Application_Inventory_latest.csv as well
        os.makedirs("exports", exist_ok=True)
        with open("exports/Application_Inventory_latest.csv", "wb") as f:
            f.write(csv_bytes)

        # Audit Check:
        print("\n" + "=" * 80)
        print("AUDIT OF TARGET ROWS IN EXPORTED CSV:")
        print("=" * 80)
        
        # Check target applications:
        target_check_ids = [2, 3, 4, 5, 11, 13, 20, 23, 25, 34, 35, 43, 46, 49, 51, 53, 57, 59, 63, 65, 73, 84, 87, 88, 89, 91, 93, 94]
        for idx, row in df_std.iterrows():
            app_id = int(row["App_ID"]) if str(row["App_ID"]).isdigit() else idx + 1
            if app_id in target_check_ids:
                print(f"Row {app_id:2d}: {row['Name']:<32} | Req: {row['License Required']:<3} | EOL: {str(row['IsEndOfLife']):<4} | EOS: {str(row['IsEndOfSupport']):<4} | Metric: {str(row['Metric']):<16} | Model: {row['License Model']}")

        # Audit for any contradictory rows
        contradictions = []
        for idx, row in df_std.iterrows():
            c = str(row["Classification"]).upper()
            req = str(row["License Required"]).upper()
            nlr = str(row["NoLicenseRequired"])
            name = row["Name"]
            app_id = row["App_ID"]

            # Contradiction A: Commercial/Freemium marked as NO
            if c in ("COMMERCIAL", "FREE_AND_PAID", "TRIAL", "PAID") and req != "YES":
                contradictions.append(f"Row {app_id}: {name} ({c}) has License Required = {req}")
            
            # Contradiction B: Freeware/OSS/OS Bundled/Commercial Component marked as YES
            if c in ("FREEWARE", "OPEN_SOURCE", "OS_BUNDLED", "OEM_OR_BUNDLED", "FREE", "COMMERCIAL_COMPONENT") and req != "NO":
                contradictions.append(f"Row {app_id}: {name} ({c}) has License Required = {req}")

            # Contradiction C: NoLicenseRequired mismatch with License Required
            if req == "YES" and nlr != "0":
                contradictions.append(f"Row {app_id}: {name} License Required = YES but NoLicenseRequired = {nlr}")
            if req == "NO" and nlr != "1":
                contradictions.append(f"Row {app_id}: {name} License Required = NO but NoLicenseRequired = {nlr}")

        print("\n" + "=" * 80)
        print(f"TOTAL CONTRADICTIONS REMAINING: {len(contradictions)}")
        print("=" * 80)
        for err in contradictions:
            print("  [FAIL]", err)
        if not contradictions:
            print("  [PASS] 100% PERFECT DATA HARMONY ACHIEVED ACROSS ALL 93 ROWS!")

    finally:
        db.close()

if __name__ == "__main__":
    reprocess_and_audit()
