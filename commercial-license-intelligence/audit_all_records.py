from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine

db = SessionLocal()
detected_apps = db.query(DetectedApplication).order_by(DetectedApplication.id.asc()).all()

print("=== 163 BASELINE APPLICATIONS AUDIT LIST ===")
for da in detected_apps:
    h = HybridLicenseEngine.resolve_hybrid_record(da.id, da.normalized_name, da.normalized_publisher, da.detected_version)
    print(f"ID {da.id:03d}: Raw: '{da.raw_name}' | Canonical: '{h['application']}' | Vendor: '{h['vendor']}' | Class: {h['classification']} | Req: {h['license_required']} | Model: {h['license_model']} | Metric: {h['metric']} | Ev: {h['evidence_status']} | Conf: {h['confidence']} | Rel: {h['reliability_score']}%")

print("\n=== 86 MACHINE INSTALLATION RESULTS AUDIT LIST ===")
mach_apps = db.query(InstallationLicenseResult).order_by(InstallationLicenseResult.id.asc()).all()
for ma in mach_apps:
    print(f"Mach ID {ma.id:03d}: Raw: '{ma.raw_application_name}' | Canonical: '{ma.canonical_product}' | Vendor: '{ma.canonical_vendor}' | Class: {ma.classification} | Req: {ma.license_requirement} | Model: {ma.license_model} | Metric: {ma.license_metric} | Ev: {ma.evidence_status} | Conf: {ma.confidence} | Rel: {ma.reliability_score}%")

db.close()
