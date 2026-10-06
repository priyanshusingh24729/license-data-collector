import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database.connection import SessionLocal
from sqlalchemy import text

db = SessionLocal()
tables = [
    'applications',
    'detected_applications',
    'installation_license_results',
    'inventory_uploads',
    'inventory_upload_rows',
    'upload_license_results',
    'license_profiles',
    'license_facts',
    'license_sources',
    'official_domain_registry',
    'application_resolution_queue'
]

for t in tables:
    try:
        c = db.execute(text(f"SELECT count(1) FROM {t}")).scalar()
        print(f"{t}: {c}")
    except Exception as e:
        print(f"{t}: ERROR {e}")

# Check recent uploads in inventory_uploads
print("\n--- Recent Inventory Uploads ---")
uploads = db.execute(text("SELECT id, upload_id, file_name, status, total_rows, unique_applications FROM inventory_uploads ORDER BY id DESC LIMIT 5")).fetchall()
for u in uploads:
    print(u)

# Check upload 118
print("\n--- Upload 118 Stats ---")
u118 = db.execute(text("SELECT classification, count(1) FROM upload_license_results WHERE upload_id = 'upl_20260903_154648_36f467a1' GROUP BY classification")).fetchall()
for row in u118:
    print(row)

print("\n--- Remaining Unknowns in Upload 118 ---")
rem = db.execute(text("SELECT raw_application, raw_vendor, count(1) FROM upload_license_results WHERE upload_id = 'upl_20260903_154648_36f467a1' AND (classification = 'UNKNOWN' OR classification IS NULL) GROUP BY raw_application, raw_vendor")).fetchall()
print(f"Total Unique Unknown Groups: {len(rem)}")
for r in rem:
    print(r)

