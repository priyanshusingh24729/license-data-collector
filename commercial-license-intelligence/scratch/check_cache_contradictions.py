import sqlite3

conn = sqlite3.connect('data/license_intelligence.db')
cursor = conn.cursor()

# 1. Non-commercial marked YES
cursor.execute("""
    SELECT id, normalized_name, canonical_product, classification, license_required, license_model, metric 
    FROM resolved_products_cache 
    WHERE classification IN ('FREEWARE', 'OPEN_SOURCE', 'OS_BUNDLED', 'OEM_OR_BUNDLED', 'FREE') 
      AND license_required = 'YES'
""")
bad_yes = cursor.fetchall()
print(f"Found {len(bad_yes)} non-commercial cache rows marked license_required = 'YES':")
for r in bad_yes[:15]:
    print(r)

# 2. Commercial marked NO
cursor.execute("""
    SELECT id, normalized_name, canonical_product, classification, license_required, license_model, metric 
    FROM resolved_products_cache 
    WHERE classification = 'COMMERCIAL'
      AND license_required = 'NO'
""")
bad_no = cursor.fetchall()
print(f"\nFound {len(bad_no)} commercial cache rows marked license_required = 'NO':")
for r in bad_no[:15]:
    print(r)
