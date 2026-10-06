import sys
import os
import re
sys.path.insert(0, os.path.abspath("."))

from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine

db = SessionLocal()

# 1. DetectedApplication table (163 records)
apps = db.query(DetectedApplication).order_by(DetectedApplication.id).all()

detected_classes = {}
detected_ev_status = {}
detected_conf = {}
unknown_apps = []

for a in apps:
    intel = HybridLicenseEngine.resolve_hybrid_record(
        app_id=a.id,
        name=a.raw_name,
        publisher=a.raw_publisher,
        version=a.detected_version,
        install_location=a.install_location,
    )
    c = intel["classification"]
    ev = intel["evidence_status"]
    conf = intel["confidence"]

    detected_classes[c] = detected_classes.get(c, 0) + 1
    detected_ev_status[ev] = detected_ev_status.get(ev, 0) + 1
    detected_conf[conf] = detected_conf.get(conf, 0) + 1

    if c == "UNKNOWN":
        unknown_apps.append((a.id, a.raw_name, a.normalized_name, a.raw_publisher))

# 2. InstallationLicenseResult table (Machine records)
mach = db.query(InstallationLicenseResult).order_by(InstallationLicenseResult.id).all()

mach_classes = {}
mach_ev_status = {}
mach_conf = {}
mach_unknowns = []

for m in mach:
    c = m.classification
    ev = m.evidence_status
    conf = m.confidence

    mach_classes[c] = mach_classes.get(c, 0) + 1
    mach_ev_status[ev] = mach_ev_status.get(ev, 0) + 1
    mach_conf[conf] = mach_conf.get(conf, 0) + 1

    if c == "UNKNOWN":
        mach_unknowns.append((m.id, m.raw_application_name, m.canonical_product, m.canonical_vendor))

print("================================================================================")
print(f"MAIN APPLICATION INVENTORY AUDIT (Total: {len(apps)})")
print("================================================================================")
print("Classification Breakdown:")
for c, cnt in sorted(detected_classes.items()):
    print(f"  {c}: {cnt}")

print("\nEvidence Status Breakdown:")
for ev, cnt in sorted(detected_ev_status.items()):
    print(f"  {ev}: {cnt}")

print("\nConfidence Breakdown:")
for conf, cnt in sorted(detected_conf.items()):
    print(f"  {conf}: {cnt}")

print(f"\nTotal UNKNOWN in Main Inventory: {len(unknown_apps)}")

print("\n================================================================================")
print(f"MACHINE INSTALLATION INVENTORY AUDIT (Total: {len(mach)})")
print("================================================================================")
print("Classification Breakdown:")
for c, cnt in sorted(mach_classes.items()):
    print(f"  {c}: {cnt}")

print("\nEvidence Status Breakdown:")
for ev, cnt in sorted(mach_ev_status.items()):
    print(f"  {ev}: {cnt}")

print("\nConfidence Breakdown:")
for conf, cnt in sorted(mach_conf.items()):
    print(f"  {conf}: {cnt}")

print(f"\nTotal UNKNOWN in Machine Installations: {len(mach_unknowns)}")
print("================================================================================")

db.close()
