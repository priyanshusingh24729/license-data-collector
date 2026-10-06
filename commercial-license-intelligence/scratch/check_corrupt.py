import sqlite3

conn = sqlite3.connect('data/license_intelligence.db')
c = conn.cursor()
c.execute("""
    SELECT raw_application, canonical_product, canonical_vendor, classification, license_required, evidence_url, count(1) 
    FROM upload_license_results 
    WHERE raw_application LIKE '%Windows Driver Package%' OR raw_application LIKE '%Fortemedia%'
    GROUP BY raw_application, canonical_product, canonical_vendor, classification, license_required, evidence_url
""")
for r in c.fetchall():
    print(r)
conn.close()
