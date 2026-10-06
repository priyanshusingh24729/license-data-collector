import sys
import os
sys.path.insert(0, os.path.abspath("."))
from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine

db = SessionLocal()

print("=== DUPLICATE ANALYSIS ON DETECTED APPLICATIONS (163) ===")
apps = db.query(DetectedApplication).order_by(DetectedApplication.id.asc()).all()

# Group by normalized_name
by_norm = {}
for a in apps:
    h = HybridLicenseEngine.resolve_hybrid_record(a.id, a.normalized_name, a.normalized_publisher, a.detected_version)
    canon = (h['vendor'], h['application'])
    by_norm.setdefault(canon, []).append((a, h))

print(f"Total Unique Canonical Products in 163 baseline: {len(by_norm)}")
for canon, list_apps in sorted(by_norm.items(), key=lambda x: len(x[1]), reverse=True):
    if len(list_apps) > 1:
        print(f"\n• Canonical: {canon[1]} (Vendor: {canon[0]}) -> {len(list_apps)} records:")
        for a, h in list_apps:
            print(f"    ID {a.id:03d}: raw_name='{a.raw_name}' | norm_name='{a.normalized_name}' | raw_ver='{a.raw_version}' | norm_pub='{a.normalized_publisher}' | class={h['classification']}")

print("\n=== DUPLICATE ANALYSIS ON INSTALLATION LICENSE RESULTS (86) ===")
machs = db.query(InstallationLicenseResult).order_by(InstallationLicenseResult.id.asc()).all()
by_mach_canon = {}
for m in machs:
    canon = (m.canonical_vendor, m.canonical_product)
    by_mach_canon.setdefault(canon, []).append(m)

print(f"Total Unique Canonical Products in 86 machine results: {len(by_mach_canon)}")
for canon, list_m in sorted(by_mach_canon.items(), key=lambda x: len(x[1]), reverse=True):
    if len(list_m) > 1:
        print(f"\n• Canonical: {canon[1]} (Vendor: {canon[0]}) -> {len(list_m)} records:")
        for m in list_m:
            print(f"    Mach ID {m.id:03d}: raw_name='{m.raw_application_name}' | ver='{m.raw_version}' | class={m.classification}")

db.close()
