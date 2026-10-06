import sqlite3

conn = sqlite3.connect('data/license_intelligence.db')
c = conn.cursor()
query = """
SELECT upload_id, file_name, total_raw_rows, total_rows, created_at 
FROM inventory_uploads 
WHERE file_name LIKE '%srs%' OR file_name LIKE '%metric%' OR file_name LIKE '%app%'
ORDER BY created_at DESC
"""
rows = c.execute(query).fetchall()
print(f"Found {len(rows)} matching uploads:")
for r in rows:
    print(r)
