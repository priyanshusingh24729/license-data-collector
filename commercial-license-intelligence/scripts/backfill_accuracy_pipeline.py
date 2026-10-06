import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.validation.license_validation_layer import LicenseValidationLayer
from backend.inventory.recognition.catalog import RecognitionCatalog
from backend.inventory.export.standardized_inventory_exporter import (
    StandardizedInventoryExporter,
    STANDARDIZED_COLUMNS,
    FINAL_OUTPUT_COLUMNS,
)
from backend.inventory.processing.bulk_upload_service import BulkInventoryUploadService

db_path = os.path.abspath("data/license_intelligence.db")
con = sqlite3.connect(db_path)
cur = con.cursor()

tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print(f"Connected to {db_path}, tables: {tables}")

# 1. Backfill resolved_products_cache
if "resolved_products_cache" in tables:
    cache_rows = cur.execute("SELECT id, normalized_name, canonical_product, license_model, classification, license_metric, license_required FROM resolved_products_cache").fetchall()
    print(f"Total resolved_products_cache rows: {len(cache_rows)}")
    cache_updated = 0
    for r in cache_rows:
        row_id, prod, canon, old_model, cls_val, metric, lic_req = r
        app_name = canon or prod or ""
        rule = RecognitionCatalog.find_rule_by_name(app_name)
        new_model = None
        new_req = lic_req
        new_canon = canon
        
        # Check MySQL Community Server
        if "mysql" in app_name.lower():
            rule = RecognitionCatalog.find_rule_by_name("MySQL Server 8.0")
            new_canon = "MySQL Community Server"
            new_model = "GPL-2.0 — Free/Open Source"
            new_req = "NO"
            cls_val = "OPEN_SOURCE"
            metric = "No License Required"
        elif "python" in app_name.lower():
            new_model = "PSF License — Free/Open Source"
            new_req = "NO"
            cls_val = "OPEN_SOURCE"
            metric = "No License Required"
        elif "mongodb" in app_name.lower():
            new_model = "SSPL-1.0 — Free to Use"
            new_req = "NO"
            cls_val = "OPEN_SOURCE"
            metric = "No License Required"
        elif "steam" in app_name.lower():
            new_canon = "Steam"
            new_model = "Freeware"
            new_req = "NO"
            cls_val = "FREEWARE"
            metric = "No License Required"
        elif any(t in app_name.lower() for t in ("home & student", "home and student", "ltsc", "2019", "2021", "2024")):
            new_model = "Commercial — Perpetual"
            new_req = "YES"
            cls_val = "COMMERCIAL"
        elif rule:
            new_model = RecognitionCatalog.derive_combined_license_model(rule)
            new_canon = rule.canonical_name
            if "NO" in rule.license_required.value:
                new_req = "NO"
            elif "YES" in rule.license_required.value:
                new_req = "YES"
        else:
            new_model = LicenseValidationLayer.build_combined_license_model(
                raw_model=old_model,
                metric=metric,
                classification=cls_val,
                app_name=app_name,
            )
            
        if new_model and (new_model != old_model or new_canon != canon or new_req != lic_req):
            cur.execute("""
                UPDATE resolved_products_cache 
                SET license_model = ?, canonical_product = ?, classification = ?, license_metric = ?, metric = ?, license_required = ?
                WHERE id = ?
            """, (new_model, new_canon, cls_val, metric, metric, new_req, row_id))
            cache_updated += 1
            
    print(f"Updated {cache_updated} cache rows in resolved_products_cache.")
    con.commit()

# 2. Backfill upload_license_results
if "upload_license_results" in tables:
    results_rows = cur.execute("""
        SELECT id, raw_application, canonical_product, canonical_vendor, raw_vendor, 
               classification, license_required, license_model, license_metric, evidence_url 
        FROM upload_license_results
    """).fetchall()
    print(f"Total upload_license_results rows: {len(results_rows)}")
    results_updated = 0
    for r in results_rows:
        row_id, raw_app, canon, canon_vend, raw_vend, cls_val, lic_req, old_model, metric, ev_url = r
        app_name = canon or raw_app or ""
        
        # Determine improved canonicals and license model
        new_canon = canon
        new_vend = canon_vend
        new_model = None
        new_req = lic_req
        new_cls = cls_val
        new_metric = metric
        
        # Target bad patterns correction
        app_low = app_name.lower()
        if "mysql" in app_low:
            new_canon = "MySQL Community Server"
            new_vend = "Oracle"
            new_model = "GPL-2.0 — Free/Open Source"
            new_req = "NO"
            new_cls = "OPEN_SOURCE"
            new_metric = "No License Required"
        elif "python" in app_low:
            new_model = "PSF License — Free/Open Source"
            new_req = "NO"
            new_cls = "OPEN_SOURCE"
            new_metric = "No License Required"
        elif "mongodb" in app_low:
            new_model = "SSPL-1.0 — Free to Use"
            new_req = "NO"
            new_cls = "OPEN_SOURCE"
            new_metric = "No License Required"
        elif "steam" in app_low:
            new_canon = "Steam"
            new_vend = "Valve Corporation"
            new_model = "Freeware"
            new_req = "NO"
            new_cls = "FREEWARE"
            new_metric = "No License Required"
        elif any(t in app_low for t in ("home & student", "home and student", "ltsc", "2019", "2021", "2024")):
            new_model = "Commercial — Perpetual"
            new_req = "YES"
            new_cls = "COMMERCIAL"
        else:
            rule = RecognitionCatalog.find_rule_by_name(app_name)
            if rule:
                new_model = RecognitionCatalog.derive_combined_license_model(rule)
                new_canon = rule.canonical_name
                new_vend = rule.canonical_vendor
                if "NO" in rule.license_required.value:
                    new_req = "NO"
                elif "YES" in rule.license_required.value:
                    new_req = "YES"
                new_cls = rule.classification
            else:
                new_model = LicenseValidationLayer.build_combined_license_model(
                    raw_model=old_model,
                    metric=metric,
                    classification=cls_val,
                    app_name=app_name,
                )

        if new_model and (new_model != old_model or new_canon != canon or new_vend != canon_vend or new_req != lic_req):
            cur.execute("""
                UPDATE upload_license_results 
                SET license_model = ?, canonical_product = ?, canonical_vendor = ?, 
                    classification = ?, license_required = ?, license_metric = ?
                WHERE id = ?
            """, (new_model, new_canon, new_vend, new_cls, new_req, new_metric, row_id))
            results_updated += 1

    print(f"Updated {results_updated} upload_license_results rows.")
    con.commit()

# 3. Clean up any remaining license_type columns in tables
for t in tables:
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})").fetchall()]
    if "license_type" in cols:
        try:
            cur.execute(f"ALTER TABLE {t} DROP COLUMN license_type")
            print(f"Successfully dropped license_type from {t}")
            con.commit()
        except Exception:
            cur.execute(f"UPDATE {t} SET license_type = NULL")
            con.commit()

con.close()
print("Backfill complete. Now regenerating exports...")

# 4. Regenerate export files
cur_upload_id = None
con = sqlite3.connect(db_path)
cur = con.cursor()
row = cur.execute("SELECT upload_id FROM inventory_uploads ORDER BY created_at DESC LIMIT 1").fetchone()
if row:
    cur_upload_id = row[0]
con.close()

if cur_upload_id:
    records = BulkInventoryUploadService.get_upload_results(upload_id=cur_upload_id)
else:
    records = []

if not records:
    existing_csv = os.path.abspath("exports/Application_Inventory_latest.csv")
    if os.path.exists(existing_csv):
        df_old = pd.read_csv(existing_csv)
        records = df_old.to_dict(orient="records")

if records:
    print(f"Transforming {len(records)} records for export...")
    df_std = StandardizedInventoryExporter.transform_inventory(
        records=records,
        scan_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        device_context={"operating_system": "Windows", "device_name": "Local PC"},
    )
    df_final = StandardizedInventoryExporter.transform_to_final_schema(records)
    
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

    print("Exports generated successfully:")
    print("  -> Application_Inventory_latest.csv (17 columns)")
    print("  -> Application_Inventory_latest.xlsx (17 columns)")
    print("  -> Application_Inventory_final.csv (10 columns)")
    print("  -> Application_Inventory_final.xlsx (10 columns)")
