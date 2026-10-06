from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine, BASELINE_INVENTORY_162
from backend.inventory.recognition.microsoft_identity_resolver import MicrosoftProductIdentityResolver
from backend.inventory.recognition.alias_system import ApplicationAliasSystem

db = SessionLocal()
detected_apps = db.query(DetectedApplication).order_by(DetectedApplication.id.asc()).all()

print(f"Total DetectedApplication records in DB: {len(detected_apps)}")

# Check each of the 163 records
for da in detected_apps:
    h = HybridLicenseEngine.resolve_hybrid_record(da.id, da.normalized_name, da.normalized_publisher, da.detected_version)
    b_match = next((b for b in BASELINE_INVENTORY_162 if b["id"] == da.id), None)
    alias = ApplicationAliasSystem.resolve_application(da.raw_name, da.raw_publisher, da.detected_version)
    is_ms = MicrosoftProductIdentityResolver.is_microsoft_or_windows_related(da.normalized_name, da.normalized_publisher, da.raw_name)
    ms_res = MicrosoftProductIdentityResolver.resolve_identity(da.raw_name, da.raw_publisher, da.detected_version, da.raw_name) if is_ms else None
    
    print(f"ID: {da.id:03d} | Raw: '{da.raw_name}' | Class: {h['classification']} | InBaseline: {b_match is not None} | is_ms: {is_ms} | MS_Can: {ms_res.canonical_name if ms_res else 'N/A'} | Alias: {alias.canonical_product} (conf={alias.confidence_score})")

db.close()
