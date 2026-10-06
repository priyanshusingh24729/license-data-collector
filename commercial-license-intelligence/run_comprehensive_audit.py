import json
from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine

db = SessionLocal()

print("================================================================================")
print("             ACCURACY IMPROVEMENT AUDIT & VERIFICATION REPORT                    ")
print("================================================================================")

detected_apps = db.query(DetectedApplication).order_by(DetectedApplication.id.asc()).all()
mach_apps = db.query(InstallationLicenseResult).order_by(InstallationLicenseResult.id.asc()).all()

print(f"\n1. Total Baseline Telemetry Records in 'detected_applications': {len(detected_apps)}")
print(f"2. Total Machine Records in 'installation_license_results': {len(mach_apps)}")

# Baseline Audit
baseline_class_counts = {}
baseline_ev_counts = {}
baseline_unresolved = 0
baseline_freeware_count = 0
baseline_free_paid_count = 0

for da in detected_apps:
    h = HybridLicenseEngine.resolve_hybrid_record(da.id, da.normalized_name, da.normalized_publisher, da.detected_version)
    c = h["classification"]
    ev = h["evidence_status"]
    baseline_class_counts[c] = baseline_class_counts.get(c, 0) + 1
    baseline_ev_counts[ev] = baseline_ev_counts.get(ev, 0) + 1
    if c == "FREEWARE":
        baseline_freeware_count += 1
    elif c == "FREE_AND_PAID":
        baseline_free_paid_count += 1
    if h["application"] == "UNRESOLVED" or c == "UNKNOWN":
        baseline_unresolved += 1

print("\n--- BASELINE DATASET (163 Records) CLASSIFICATION DISTRIBUTION ---")
for k, v in sorted(baseline_class_counts.items()):
    print(f"  • {k}: {v}")

print("\n--- BASELINE EVIDENCE STATUS BREAKDOWN ---")
for k, v in sorted(baseline_ev_counts.items()):
    print(f"  • {k}: {v}")

# Machine Results Audit
mach_class_counts = {}
mach_ev_counts = {}
mach_unresolved = 0
mach_freeware_count = 0
mach_free_paid_count = 0

for ma in mach_apps:
    c = ma.classification
    ev = ma.evidence_status
    mach_class_counts[c] = mach_class_counts.get(c, 0) + 1
    mach_ev_counts[ev] = mach_ev_counts.get(ev, 0) + 1
    if c == "FREEWARE":
        mach_freeware_count += 1
    elif c == "FREE_AND_PAID":
        mach_free_paid_count += 1
    if ma.canonical_product == "UNRESOLVED" or c == "UNKNOWN":
        mach_unresolved += 1

print("\n--- MACHINE DATASET (86 Records) CLASSIFICATION DISTRIBUTION ---")
for k, v in sorted(mach_class_counts.items()):
    print(f"  • {k}: {v}")

print("\n--- MACHINE EVIDENCE STATUS BREAKDOWN ---")
for k, v in sorted(mach_ev_counts.items()):
    print(f"  • {k}: {v}")

print("\n--- ANTIGRAVITY SPECIFIC AUDIT VERIFICATION ---")
antigravity_records = [ma for ma in mach_apps if "antigravity" in ma.raw_application_name.lower() or "antigravity" in str(ma.canonical_product).lower()]
for ar in antigravity_records:
    print(f"  • ID {ar.id}: Raw='{ar.raw_application_name}' | Canonical='{ar.canonical_product}' | Class='{ar.classification}' | Req='{ar.license_requirement}' | Model='{ar.license_model}' | Ev='{ar.evidence_status}' | Conf='{ar.confidence}' | Rel={ar.reliability_score}% | URL='{ar.evidence_url}'")

db.close()
