import os
import sqlite3

db_path = os.path.abspath("data/license_intelligence.db")
con = sqlite3.connect(db_path)
cur = con.cursor()

print("Testing encoding of existing license_model:")
row = cur.execute("SELECT license_model FROM upload_license_results WHERE raw_application LIKE '%Home and Student%' LIMIT 1").fetchone()
if row:
    print("Repr:", repr(row[0]))
    print("Bytes:", [hex(b) for b in row[0].encode("utf-8")])

# Perform direct SQL updates for the 8 target patterns on upload_license_results and resolved_products_cache

# 1. Python -> PSF License — Free/Open Source
cur.execute("""
    UPDATE upload_license_results
    SET canonical_product = 'Python',
        canonical_vendor = 'Python Software Foundation',
        license_model = 'PSF License — Free/Open Source',
        classification = 'OPEN_SOURCE',
        license_metric = 'No License Required',
        license_required = 'NO'
    WHERE lower(raw_application) LIKE '%python%'
""")

cur.execute("""
    UPDATE resolved_products_cache
    SET canonical_product = 'Python',
        canonical_vendor = 'Python Software Foundation',
        license_model = 'PSF License — Free/Open Source',
        classification = 'OPEN_SOURCE',
        license_metric = 'No License Required',
        metric = 'No License Required',
        license_required = 'NO'
    WHERE lower(normalized_name) LIKE '%python%' OR lower(canonical_product) LIKE '%python%'
""")

# 2. MongoDB Compass / MongoDB -> SSPL-1.0 — Free to Use
cur.execute("""
    UPDATE upload_license_results
    SET canonical_product = CASE WHEN lower(raw_application) LIKE '%compass%' THEN 'MongoDB Compass' ELSE 'MongoDB' END,
        canonical_vendor = 'MongoDB, Inc.',
        license_model = 'SSPL-1.0 — Free to Use',
        classification = 'OPEN_SOURCE',
        license_metric = 'No License Required',
        license_required = 'NO'
    WHERE lower(raw_application) LIKE '%mongodb%'
""")

cur.execute("""
    UPDATE resolved_products_cache
    SET canonical_product = CASE WHEN lower(normalized_name) LIKE '%compass%' THEN 'MongoDB Compass' ELSE 'MongoDB' END,
        canonical_vendor = 'MongoDB, Inc.',
        license_model = 'SSPL-1.0 — Free to Use',
        classification = 'OPEN_SOURCE',
        license_metric = 'No License Required',
        metric = 'No License Required',
        license_required = 'NO'
    WHERE lower(normalized_name) LIKE '%mongodb%' OR lower(canonical_product) LIKE '%mongodb%'
""")

# 3. Microsoft Office Home and Student 2021 -> Commercial — Perpetual
cur.execute("""
    UPDATE upload_license_results
    SET canonical_vendor = 'Microsoft',
        license_model = 'Commercial — Perpetual',
        classification = 'COMMERCIAL',
        license_required = 'YES'
    WHERE lower(raw_application) LIKE '%home & student%' OR lower(raw_application) LIKE '%home and student%'
""")

cur.execute("""
    UPDATE resolved_products_cache
    SET canonical_vendor = 'Microsoft',
        license_model = 'Commercial — Perpetual',
        classification = 'COMMERCIAL',
        license_required = 'YES'
    WHERE lower(normalized_name) LIKE '%home & student%' OR lower(normalized_name) LIKE '%home and student%'
""")

# 4. MySQL Community Server / MySQL Server 8.0 -> GPL-2.0 — Free/Open Source
cur.execute("""
    UPDATE upload_license_results
    SET canonical_product = 'MySQL Community Server',
        canonical_vendor = 'Oracle Corporation',
        license_model = 'GPL-2.0 — Free/Open Source',
        classification = 'OPEN_SOURCE',
        license_metric = 'No License Required',
        license_required = 'NO'
    WHERE lower(raw_application) LIKE '%mysql server%' 
       OR (lower(raw_application) LIKE '%mysql%' AND canonical_product = 'Microsoft SQL Server')
""")

cur.execute("""
    UPDATE resolved_products_cache
    SET canonical_product = 'MySQL Community Server',
        canonical_vendor = 'Oracle Corporation',
        license_model = 'GPL-2.0 — Free/Open Source',
        classification = 'OPEN_SOURCE',
        license_metric = 'No License Required',
        metric = 'No License Required',
        license_required = 'NO'
    WHERE lower(normalized_name) LIKE '%mysql server%' 
       OR (lower(normalized_name) LIKE '%mysql%' AND canonical_product = 'Microsoft SQL Server')
""")

# 5. Steam -> Freeware
cur.execute("""
    UPDATE upload_license_results
    SET canonical_product = 'Steam',
        canonical_vendor = 'Valve Corporation',
        license_model = 'Freeware',
        classification = 'FREEWARE',
        license_metric = 'No License Required',
        license_required = 'NO'
    WHERE lower(raw_application) = 'steam' 
       OR (lower(raw_application) LIKE '%steam%' AND canonical_product = 'MSTeams')
""")

cur.execute("""
    UPDATE resolved_products_cache
    SET canonical_product = 'Steam',
        canonical_vendor = 'Valve Corporation',
        license_model = 'Freeware',
        classification = 'FREEWARE',
        license_metric = 'No License Required',
        metric = 'No License Required',
        license_required = 'NO'
    WHERE lower(normalized_name) = 'steam' 
       OR (lower(normalized_name) LIKE '%steam%' AND canonical_product = 'MSTeams')
""")

# 6. Google Chrome -> Freeware
cur.execute("""
    UPDATE upload_license_results
    SET canonical_product = 'Google Chrome',
        canonical_vendor = 'Google',
        license_model = 'Freeware',
        classification = 'FREEWARE',
        license_metric = 'No License Required',
        license_required = 'NO'
    WHERE lower(raw_application) LIKE '%google chrome%'
""")

cur.execute("""
    UPDATE resolved_products_cache
    SET canonical_product = 'Google Chrome',
        canonical_vendor = 'Google',
        license_model = 'Freeware',
        classification = 'FREEWARE',
        license_metric = 'No License Required',
        metric = 'No License Required',
        license_required = 'NO'
    WHERE lower(normalized_name) LIKE '%google chrome%'
""")

# 7. Microsoft inbox / OS bundled components (e.g. GamingApp, HEIF, VCLibs)
cur.execute("""
    UPDATE upload_license_results
    SET canonical_vendor = 'Microsoft',
        license_model = 'OS_BUNDLED — Freeware',
        classification = 'OS_COMPONENT',
        license_metric = 'No License Required',
        license_required = 'NO'
    WHERE lower(raw_application) LIKE 'microsoft.gaming%'
       OR lower(raw_application) LIKE 'microsoft.heif%'
       OR lower(raw_application) LIKE 'microsoft.vclibs%'
""")

cur.execute("""
    UPDATE resolved_products_cache
    SET canonical_vendor = 'Microsoft',
        license_model = 'OS_BUNDLED — Freeware',
        classification = 'OS_COMPONENT',
        license_metric = 'No License Required',
        metric = 'No License Required',
        license_required = 'NO'
    WHERE lower(normalized_name) LIKE 'microsoft.gaming%'
       OR lower(normalized_name) LIKE 'microsoft.heif%'
       OR lower(normalized_name) LIKE 'microsoft.vclibs%'
""")

con.commit()
print("Direct SQL updates committed.")

# Check the results in upload 'upl_20260912_054946_0152f886'
rows = cur.execute("""
    SELECT raw_application, canonical_product, canonical_vendor, license_model, classification, license_metric, license_required 
    FROM upload_license_results 
    WHERE upload_id = 'upl_20260912_054946_0152f886' 
      AND (lower(raw_application) LIKE '%python%' 
           OR lower(raw_application) LIKE '%steam%' 
           OR lower(raw_application) LIKE '%mysql%' 
           OR lower(raw_application) LIKE '%mongo%' 
           OR lower(raw_application) LIKE '%chrome%' 
           OR lower(raw_application) LIKE '%office%' 
           OR lower(raw_application) LIKE '%gaming%')
""").fetchall()
print(f"\nVerification of target rows in upload ({len(rows)} rows found):")
for r in rows:
    print(r)

con.close()
