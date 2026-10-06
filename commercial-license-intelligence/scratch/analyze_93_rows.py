import sqlite3
import pandas as pd

conn = sqlite3.connect('data/license_intelligence.db')
cursor = conn.cursor()

cursor.execute("SELECT upload_id FROM inventory_uploads WHERE file_name LIKE '%PF490A36%' ORDER BY created_at DESC LIMIT 1")
res = cursor.fetchone()
upload_id = res[0] if res else None

query = f"""
    SELECT row_index, raw_application, canonical_product, version, classification, 
           license_required, license_model, metric, conflict_status, consensus_status, override_reason
    FROM upload_license_results 
    WHERE upload_id = '{upload_id}'
    ORDER BY row_index ASC
"""
df = pd.read_sql_query(query, conn)

with open('scratch/93_rows_report.txt', 'w', encoding='utf-8') as f:
    f.write(f"Upload ID: {upload_id}\n")
    f.write(f"Total rows: {len(df)}\n\n")
    f.write(f"{'Idx':3s} | {'Raw Application':32s} | {'Canonical Product':30s} | {'Classification':16s} | {'Req':4s} | {'Metric':22s} | {'License Model':35s} | {'Conflict Status':20s} | {'Override Reason'}\n")
    f.write("-" * 180 + "\n")
    for idx, r in df.iterrows():
        app = str(r['raw_application'])[:32] if pd.notna(r['raw_application']) else ''
        canon = str(r['canonical_product'])[:30] if pd.notna(r['canonical_product']) else ''
        cls_ = str(r['classification'])[:16] if pd.notna(r['classification']) else ''
        req = str(r['license_required'])[:4] if pd.notna(r['license_required']) else ''
        met = str(r['metric'])[:22] if pd.notna(r['metric']) else ''
        mod = str(r['license_model'])[:35] if pd.notna(r['license_model']) else ''
        conf = str(r['conflict_status'])[:20] if pd.notna(r['conflict_status']) else ''
        reason = str(r['override_reason']) if pd.notna(r['override_reason']) else ''
        f.write(f"{r['row_index']:3d} | {app:32s} | {canon:30s} | {cls_:16s} | {req:4s} | {met:22s} | {mod:35s} | {conf:20s} | {reason}\n")

print("Wrote scratch/93_rows_report.txt")
