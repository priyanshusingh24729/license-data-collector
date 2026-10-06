import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.inventory.export.standardized_inventory_exporter import (
    StandardizedInventoryExporter,
    STANDARDIZED_COLUMNS,
    FINAL_OUTPUT_COLUMNS,
)
from backend.inventory.processing.bulk_upload_service import BulkInventoryUploadService

db_path = os.path.abspath("data/license_intelligence.db")
con = sqlite3.connect(db_path)
cur = con.cursor()

# Find latest upload_id from inventory_uploads or upload_license_results
cur.execute("SELECT upload_id FROM inventory_uploads ORDER BY created_at DESC LIMIT 1")
row = cur.fetchone()
upload_id = row[0] if row else None
print(f"Latest upload_id in DB: {upload_id}")

if upload_id:
    results = BulkInventoryUploadService.get_upload_results(upload_id=upload_id)
else:
    # Fallback to reading distinct apps from upload_license_results
    rows = cur.execute("SELECT DISTINCT canonical_product, raw_application, canonical_vendor, raw_vendor, version, raw_version, classification, license_required, license_model, license_metric, evidence_url FROM upload_license_results LIMIT 200").fetchall()
    results = []
    for r in rows:
        results.append({
            "application": r[0] or r[1],
            "raw_application": r[1],
            "vendor": r[2] or r[3],
            "raw_vendor": r[3],
            "version": r[4] or r[5] or "",
            "raw_version": r[5] or "",
            "classification": r[6],
            "license_required": r[7],
            "license_model": r[8],
            "metric": r[9],
            "evidence_url": r[10] or "",
        })

con.close()

if not results:
    # Fallback to reading the existing CSV if DB was empty
    existing_csv = os.path.abspath("exports/Application_Inventory_latest.csv")
    if os.path.exists(existing_csv):
        df_old = pd.read_csv(existing_csv)
        results = df_old.to_dict(orient="records")

print(f"Transforming {len(results)} inventory records...")
df_std = StandardizedInventoryExporter.transform_inventory(
    records=results,
    scan_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    device_context={"operating_system": "Windows", "device_name": "Local PC"},
)

print(f"Standardized DataFrame columns ({len(df_std.columns)}): {list(df_std.columns)}")
assert len(df_std.columns) == 17, f"Expected 17 columns, got {len(df_std.columns)}"
assert "License Type" not in df_std.columns, "License Type must not be in standardized columns"
assert "LicenseType" not in df_std.columns, "LicenseType must not be in standardized columns"

# Generate 10-column final schema
df_final = StandardizedInventoryExporter.transform_to_final_schema(results)
print(f"Final DataFrame columns ({len(df_final.columns)}): {list(df_final.columns)}")
assert len(df_final.columns) == 10, f"Expected 10 columns, got {len(df_final.columns)}"
assert list(df_final.columns) == FINAL_OUTPUT_COLUMNS
assert "License Type" not in df_final.columns

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
exports_dir = os.path.join(root_dir, "exports")
os.makedirs(exports_dir, exist_ok=True)

latest_csv = os.path.join(exports_dir, "Application_Inventory_latest.csv")
latest_excel = os.path.join(exports_dir, "Application_Inventory_latest.xlsx")

csv_bytes = StandardizedInventoryExporter.to_csv_bytes(df_std)
excel_bytes = StandardizedInventoryExporter.to_excel_bytes(df_std)

with open(latest_csv, "wb") as f_c:
    f_c.write(csv_bytes)
with open(latest_excel, "wb") as f_x:
    f_x.write(excel_bytes)

print(f"Successfully regenerated {latest_csv} and {latest_excel}")
print(df_std[["Name", "License Required", "License Model", "Metric"]].head(10))
