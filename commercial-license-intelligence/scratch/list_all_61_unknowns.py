from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine

db = SessionLocal()
detected_apps = db.query(DetectedApplication).order_by(DetectedApplication.id.asc()).all()

unknown_list = []
for da in detected_apps:
    h = HybridLicenseEngine.resolve_hybrid_record(da.id, da.normalized_name, da.normalized_publisher, da.detected_version)
    if h["classification"] == "UNKNOWN":
        unknown_list.append((da, h))

print(f"Total UNKNOWN baseline records: {len(unknown_list)}\n")
for i, (da, h) in enumerate(unknown_list, 1):
    print(f"[{i:02d}] ID: {da.id:03d} | Raw: '{da.raw_name}' | Pub: '{da.raw_publisher}' | NormName: '{da.normalized_name}' | NormPub: '{da.normalized_publisher}' | Ver: '{da.detected_version}'")
    print(f"     App: '{h['application']}' | Vendor: '{h['vendor']}' | EvStatus: {h['evidence_status']} | Conf: {h['confidence']} | Rel: {h['reliability_score']}%")
    print(f"     Quote: {h['evidence_quote'][:100] if h['evidence_quote'] else 'None'}")
    print()

db.close()
