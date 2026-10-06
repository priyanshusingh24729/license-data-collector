import sqlite3

conn = sqlite3.connect('data/license_intelligence.db')
cursor = conn.cursor()

cursor.execute("SELECT id, normalized_name, normalized_vendor, canonical_product, canonical_vendor, classification, license_required, license_model, metric, last_validated_at FROM resolved_products_cache WHERE normalized_name LIKE '%management%studio%'")
rows = cursor.fetchall()
print(f"Found {len(rows)} SSMS cache rows:")
for r in rows:
    print(r)
