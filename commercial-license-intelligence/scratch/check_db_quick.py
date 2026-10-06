import sqlite3

conn = sqlite3.connect('data/license_intelligence.db')
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(upload_license_results)")
print("upload_license_results schema:")
for col in cursor.fetchall():
    print(col)

cursor.execute("PRAGMA table_info(inventory_uploads)")
print("\ninventory_uploads schema:")
for col in cursor.fetchall():
    print(col)

cursor.execute("SELECT id, upload_id, raw_application_name, classification, license_required, license_model, no_license_required, metric FROM upload_license_results LIMIT 5")
print("\nupload_license_results sample:")
for r in cursor.fetchall():
    print(r)
