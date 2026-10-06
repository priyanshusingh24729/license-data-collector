from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
from backend.inventory.recognition.microsoft_identity_resolver import MicrosoftProductIdentityResolver
from backend.inventory.recognition.alias_system import ApplicationAliasSystem

db = SessionLocal()
detected_apps = db.query(DetectedApplication).order_by(DetectedApplication.id.asc()).all()

print(f"Total detected apps: {len(detected_apps)}")
unknown_records = []
all_results = []

for da in detected_apps:
    h = HybridLicenseEngine.resolve_hybrid_record(da.id, da.normalized_name, da.normalized_publisher, da.detected_version)
    c = h["classification"]
    all_results.append((da, h))
    if c == "UNKNOWN":
        unknown_records.append((da, h))

print(f"Total UNKNOWN in baseline: {len(unknown_records)}")

print("\n--- UNKNOWN RECORDS BREAKDOWN ---")
for da, h in unknown_records:
    is_ms = MicrosoftProductIdentityResolver.is_microsoft_or_windows_related(da.raw_name, da.raw_publisher, da.raw_name)
    alias = ApplicationAliasSystem.resolve_application(da.raw_name, da.raw_publisher, da.detected_version)
    print(f"ID {da.id:03d}:")
    print(f"  Raw Name: '{da.raw_name}' | Raw Pub: '{da.raw_publisher}'")
    print(f"  Norm Name: '{da.normalized_name}' | Norm Pub: '{da.normalized_publisher}'")
    print(f"  Is MS/Windows: {is_ms}")
    print(f"  Alias Canonical: '{alias.canonical_product}' | Conf: {alias.confidence_score}")
    print(f"  Hybrid Result: App='{h.get('application')}', Vendor='{h.get('vendor')}', EvStatus='{h.get('evidence_status')}', Quote='{h.get('evidence_quote')}'")
    print("-" * 50)

db.close()
