import sqlite3
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.validation.license_validation_layer import LicenseValidationLayer
from backend.inventory.recognition.catalog import RecognitionCatalog

db_path = os.path.abspath("data/license_intelligence.db")
if not os.path.exists(db_path):
    print("Database not found at", db_path)
    sys.exit(0)

con = sqlite3.connect(db_path)
cur = con.cursor()

tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables in database:", tables, flush=True)

for t in tables:
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})").fetchall()]
    if "license_type" in cols:
        print(f"  -> {t} has license_type column", flush=True)

# Check upload_license_results
if "upload_license_results" in tables:
    cols = [r[1] for r in cur.execute("PRAGMA table_info(upload_license_results)").fetchall()]
    rows = cur.execute("SELECT id, canonical_product, raw_application, classification, license_required, license_model, license_metric FROM upload_license_results").fetchall()
    print(f"Total upload_license_results rows: {len(rows)}", flush=True)
    
    updated = 0
    for idx, r in enumerate(rows):
        row_id, canon, raw_app, cls_val, lic_req, lic_model, lic_metric = r
        app_name = canon or raw_app or ""
        
        rule = RecognitionCatalog.find_rule_by_name(app_name)
        if rule:
            combined = RecognitionCatalog.derive_combined_license_model(rule)
        else:
            combined = LicenseValidationLayer.build_combined_license_model(
                raw_model=lic_model,
                metric=lic_metric,
                classification=cls_val,
                app_name=app_name,
            )
        
        if combined and combined != lic_model:
            cur.execute("UPDATE upload_license_results SET license_model = ? WHERE id = ?", (combined, row_id))
            updated += 1
        if (idx + 1) % 50 == 0 or (idx + 1) == len(rows):
            print(f"Processed {idx + 1}/{len(rows)} rows...", flush=True)
            
    print(f"Updated {updated} upload_license_results with combined license_model.", flush=True)
    con.commit()

# If SQLite supports DROP COLUMN (SQLite 3.35.0+)
for t in tables:
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})").fetchall()]
    if "license_type" in cols:
        try:
            cur.execute(f"ALTER TABLE {t} DROP COLUMN license_type")
            print(f"Successfully dropped column license_type from {t}")
            con.commit()
        except Exception as e:
            print(f"Could not drop column directly from {t} ({e}), setting NULL")
            cur.execute(f"UPDATE {t} SET license_type = NULL")
            con.commit()

con.close()
print("Migration completed successfully.")
