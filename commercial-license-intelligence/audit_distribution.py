from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine

db = SessionLocal()
detected_apps = db.query(DetectedApplication).order_by(DetectedApplication.id.asc()).all()
mach_apps = db.query(InstallationLicenseResult).order_by(InstallationLicenseResult.id.asc()).all()

print(f"Total baseline records: {len(detected_apps)}")
print(f"Total machine records: {len(mach_apps)}")

# Identify all records and their proposed adjustments
print("\n=== BASELINE CLASSIFICATIONS CURRENT AUDIT ===")
baseline_classes = {}
for da in detected_apps:
    h = HybridLicenseEngine.resolve_hybrid_record(da.id, da.normalized_name, da.normalized_publisher, da.detected_version)
    c = h["classification"]
    baseline_classes[c] = baseline_classes.get(c, 0) + 1

for k, v in sorted(baseline_classes.items()):
    print(f"  {k}: {v}")

print("\n=== MACHINE CLASSIFICATIONS CURRENT AUDIT ===")
mach_classes = {}
for ma in mach_apps:
    c = ma.classification
    mach_classes[c] = mach_classes.get(c, 0) + 1

for k, v in sorted(mach_classes.items()):
    print(f"  {k}: {v}")

db.close()
