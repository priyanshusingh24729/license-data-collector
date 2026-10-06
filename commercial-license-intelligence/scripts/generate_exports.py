import os
import sys
from datetime import datetime, timezone
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.inventory.processing.bulk_upload_service import BulkInventoryUploadService
from backend.inventory.export.standardized_inventory_exporter import (
    StandardizedInventoryExporter,
    STANDARDIZED_COLUMNS,
    FINAL_OUTPUT_COLUMNS,
)

upload_id = "upl_20260912_054946_0152f886"
records = BulkInventoryUploadService.get_upload_results(upload_id=upload_id)
print(f"Retrieved {len(records)} records for upload {upload_id}")

df_std = StandardizedInventoryExporter.transform_inventory(
    records=records,
    scan_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    device_context={"operating_system": "Windows", "device_name": "Local PC"},
)

df_final = StandardizedInventoryExporter.transform_to_final_schema(records)

print(f"df_std shape: {df_std.shape}, columns ({len(df_std.columns)}): {list(df_std.columns)}")
print(f"df_final shape: {df_final.shape}, columns ({len(df_final.columns)}): {list(df_final.columns)}")

assert len(df_std.columns) == 17, f"Expected 17 columns in df_std, got {len(df_std.columns)}"
assert len(df_final.columns) == 10, f"Expected 10 columns in df_final, got {len(df_final.columns)}"

exports_dir = os.path.abspath("exports")
os.makedirs(exports_dir, exist_ok=True)

csv_bytes = StandardizedInventoryExporter.to_csv_bytes(df_std)
excel_bytes = StandardizedInventoryExporter.to_excel_bytes(df_std)
final_csv_bytes = StandardizedInventoryExporter.to_final_csv_bytes(df_final)
final_excel_bytes = StandardizedInventoryExporter.to_final_excel_bytes(df_final)

with open(os.path.join(exports_dir, "Application_Inventory_latest.csv"), "wb") as f:
    f.write(csv_bytes)
with open(os.path.join(exports_dir, "Application_Inventory_latest.xlsx"), "wb") as f:
    f.write(excel_bytes)
with open(os.path.join(exports_dir, "Application_Inventory_final.csv"), "wb") as f:
    f.write(final_csv_bytes)
with open(os.path.join(exports_dir, "Application_Inventory_final.xlsx"), "wb") as f:
    f.write(final_excel_bytes)

print("Export files successfully written.")

# Inspect the target applications in df_final
target_names = ["Python", "MongoDB", "MySQL", "Steam", "Office Home and Student", "Google Chrome", "Java"]
print("\n=== Sample records in df_final ===")
for idx, row in df_final.iterrows():
    app_name = str(row["Application Name"])
    if any(t.lower() in app_name.lower() for t in target_names):
        print(f"{row['Application Name']} | {row['Version']} | {row['Classification']} | {row['License Required']} | {row['License Model']} | {row['Metric']}")
