import sqlite3
import csv
from collections import Counter

conn = sqlite3.connect('data/license_intelligence.db')
c = conn.cursor()

c.execute("""
    SELECT 
        raw_application, raw_vendor, raw_version, 
        canonical_product, canonical_vendor, version,
        classification, license_required, license_model, 
        confidence, evidence_status, evidence_url, hostname
    FROM upload_license_results 
    WHERE upload_id = 'upl_20260904_091122_79c9da10'
""")
rows = c.fetchall()
print(f"Total rows retrieved: {len(rows)}")

cls_counter = Counter(r[6] for r in rows)
req_counter = Counter(r[7] for r in rows)
ev_counter = Counter(r[10] for r in rows)
conf_counter = Counter(r[9] for r in rows)

print("Classification distribution:")
for k, v in cls_counter.most_common():
    print(f"  {k}: {v}")

print("\nLicense Required distribution:")
for k, v in req_counter.most_common():
    print(f"  {k}: {v}")

print("\nEvidence Status distribution:")
for k, v in ev_counter.most_common():
    print(f"  {k}: {v}")
