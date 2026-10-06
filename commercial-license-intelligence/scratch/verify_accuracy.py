import sqlite3
import pandas as pd

conn = sqlite3.connect('data/license_intelligence.db')

queries = [
    ("Apple Driver", "SELECT canonical_product, canonical_vendor, classification, license_required, evidence_url FROM upload_license_results WHERE raw_application LIKE '%USBAAPL%' LIMIT 1"),
    ("Silicon Labs Driver", "SELECT canonical_product, canonical_vendor, classification, license_required, evidence_url FROM upload_license_results WHERE raw_application LIKE '%silabenm%' LIMIT 1"),
    ("Realtek Driver", "SELECT canonical_product, canonical_vendor, classification, license_required, evidence_url FROM upload_license_results WHERE raw_application LIKE '%Realtek USB Ethernet%' LIMIT 1"),
    ("Fortemedia", "SELECT canonical_product, canonical_vendor, classification, license_required, evidence_url FROM upload_license_results WHERE raw_application LIKE '%Fortemedia%' LIMIT 1"),
    ("Windows KB Update", "SELECT canonical_product, canonical_vendor, classification, license_required, evidence_url FROM upload_license_results WHERE raw_application LIKE '%KB5001716%' LIMIT 1"),
    ("Corel Shell Extension", "SELECT canonical_product, canonical_vendor, classification, license_required, evidence_url FROM upload_license_results WHERE raw_application LIKE '%Corel Graphics - Windows Shell%' LIMIT 1"),
    ("CrowdStrike Sensor", "SELECT canonical_product, canonical_vendor, classification, license_required, evidence_url FROM upload_license_results WHERE raw_application LIKE '%CrowdStrike Windows Sensor%' LIMIT 1"),
    ("HP Hardware Diagnostics", "SELECT canonical_product, canonical_vendor, classification, license_required, evidence_url FROM upload_license_results WHERE raw_application LIKE '%HP PC Hardware Diagnostics%' LIMIT 1"),
    ("Windows Scan App", "SELECT canonical_product, canonical_vendor, classification, license_required, evidence_url FROM upload_license_results WHERE raw_application LIKE '%WindowsScan%' LIMIT 1"),
    ("Visual Studio Sub-MSI", "SELECT canonical_product, canonical_vendor, classification, license_required, evidence_url FROM upload_license_results WHERE raw_application LIKE '%vs_CoreEditorFonts%' LIMIT 1"),
]

print(f"{'ITEM':25s} | {'PRODUCT':35s} | {'VENDOR':25s} | {'CLASS':15s} | {'REQ':5s}")
print("-" * 115)
for label, sql in queries:
    cursor = conn.cursor()
    cursor.execute(sql)
    row = cursor.fetchone()
    if row:
        prod, vend, cls, req, url = row
        print(f"{label:25s} | {str(prod)[:35]:35s} | {str(vend)[:25]:25s} | {str(cls):15s} | {str(req):5s}")
    else:
        print(f"{label:25s} | NOT FOUND IN HISTORICAL UPLOADS")

conn.close()
