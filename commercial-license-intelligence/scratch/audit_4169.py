import sqlite3
import re

conn = sqlite3.connect('data/license_intelligence.db')
c = conn.cursor()

c.execute("""
    SELECT 
        id, raw_application, raw_vendor, raw_version, 
        canonical_product, canonical_vendor, version,
        classification, license_required, license_model, 
        confidence, evidence_status, evidence_url, hostname
    FROM upload_license_results 
    WHERE upload_id = 'upl_20260904_091122_79c9da10'
""")
rows = c.fetchall()

# Quality Checks across all 4169 rows:
# 1. PWA & raw GUIDs
pwa_guid_noise = 0
# 2. Linux OS shared libraries (lib*, gir*, python3-*, fonts-*)
linux_sys_pkg = 0
# 3. macOS daemons
macos_daemons = 0
# 4. False positives (Google Docs YES, VirtualBox YES)
false_positives = 0
# 5. Vendor hallucinations (Gkbd Capplet -> Apple, etc.)
vendor_mismatches = 0
# 6. VERIFIED but empty URL
empty_url_verified = 0
# 7. Corrupted version strings with excessive spacing/tabs
corrupted_versions = 0

for r in rows:
    raw_app = r[1] or ""
    canon_app = r[4] or ""
    canon_vend = r[5] or ""
    ver = r[6] or ""
    cls = r[7] or ""
    req = r[8] or ""
    ev_stat = r[11] or ""
    ev_url = r[12] or ""

    if raw_app.startswith("cr.sb.") or raw_app.startswith("1_https___") or "sharepoint.com" in raw_app.lower() or raw_app.endswith("_cw5n1h2txyewy"):
        pwa_guid_noise += 1

    lower_app = raw_app.lower()
    if lower_app.startswith(("lib", "gir1.2-", "python3-", "fonts-", "linux-image-", "linux-headers-")):
        linux_sys_pkg += 1

    if canon_app in ("Google Docs", "Google Sheets", "Google Slides", "Gmail") and req == "YES":
        false_positives += 1
    elif canon_app == "Oracle VirtualBox" and req == "YES":
        false_positives += 1

    if canon_app == "Gkbd Capplet" and canon_vend == "Apple Inc.":
        vendor_mismatches += 1
    elif canon_app == "Photos" and canon_vend == "Apple Inc." and "2026." in ver:
        vendor_mismatches += 1
    elif canon_app == "ParentalControls" and "Microsoft" in canon_vend:
        vendor_mismatches += 1

    if ev_stat == "VERIFIED" and (not ev_url or ev_url.strip() == ""):
        empty_url_verified += 1

    if "   " in ver or "\t" in ver:
        corrupted_versions += 1

print(f"Total Rows: {len(rows)}")
print(f"PWA / GUID / URL Noise: {pwa_guid_noise}")
print(f"Linux Shared Libraries & Package Noise: {linux_sys_pkg}")
print(f"License False Positives (Google Docs/VirtualBox): {false_positives}")
print(f"Cross-OS Vendor Hallucinations: {vendor_mismatches}")
print(f"VERIFIED with Empty URL: {empty_url_verified}")
print(f"Corrupted Version Formatting: {corrupted_versions}")
