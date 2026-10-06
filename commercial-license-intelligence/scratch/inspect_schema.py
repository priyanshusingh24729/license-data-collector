import sqlite3

conn = sqlite3.connect('data/license_intelligence.db')
c = conn.cursor()
for tbl in ['applications', 'detected_applications']:
    cols = [col[1] for col in c.execute(f"PRAGMA table_info({tbl})").fetchall()]
    print(tbl, cols)
