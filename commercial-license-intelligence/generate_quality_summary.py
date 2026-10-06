from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine

db = SessionLocal()
detected_apps = db.query(DetectedApplication).order_by(DetectedApplication.id.asc()).all()
mach_apps = db.query(InstallationLicenseResult).order_by(InstallationLicenseResult.id.asc()).all()

print("================================================================================")
print("                          FINAL QUALITY AUDIT SUMMARY                           ")
print("================================================================================")

print(f"\n1. Total Records Audited (Baseline + Machine): {len(detected_apps) + len(mach_apps)} (163 Baseline, 86 Machine)")
print(f"2. Baseline Records Audited: {len(detected_apps)}")
print(f"3. Machine Records Audited: {len(mach_apps)}")

# Calculate baseline metrics
baseline_classes = {}
baseline_evs = {}
for da in detected_apps:
    h = HybridLicenseEngine.resolve_hybrid_record(da.id, da.normalized_name, da.normalized_publisher, da.detected_version)
    c = h["classification"]
    ev = h["evidence_status"]
    baseline_classes[c] = baseline_classes.get(c, 0) + 1
    baseline_evs[ev] = baseline_evs.get(ev, 0) + 1

# Calculate machine metrics
mach_classes = {}
mach_evs = {}
for ma in mach_apps:
    c = ma.classification
    ev = ma.evidence_status
    mach_classes[c] = mach_classes.get(c, 0) + 1
    mach_evs[ev] = mach_evs.get(ev, 0) + 1

print("\n--- CLASSIFICATION DISTRIBUTION (BASELINE - 163 Records) ---")
for k, v in sorted(baseline_classes.items()):
    print(f"  • {k}: {v}")

print("\n--- EVIDENCE STATUS (BASELINE - 163 Records) ---")
for k, v in sorted(baseline_evs.items()):
    print(f"  • {k}: {v}")

print("\n--- CLASSIFICATION DISTRIBUTION (MACHINE - 86 Records) ---")
for k, v in sorted(mach_classes.items()):
    print(f"  • {k}: {v}")

print("\n--- EVIDENCE STATUS (MACHINE - 86 Records) ---")
for k, v in sorted(mach_evs.items()):
    print(f"  • {k}: {v}")

db.close()
