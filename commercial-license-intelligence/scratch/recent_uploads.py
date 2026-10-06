import sqlite3

conn = sqlite3.connect('data/license_intelligence.db')
c = conn.cursor()
rows = c.execute("SELECT upload_id, file_name, total_raw_rows, total_rows FROM inventory_uploads ORDER BY id DESC LIMIT 50").fetchall()
for r in rows:
    print(r)
