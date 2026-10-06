from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
from backend.inventory.recognition.microsoft_identity_resolver import MicrosoftProductIdentityResolver
from backend.inventory.recognition.alias_system import ApplicationAliasSystem

db = SessionLocal()
detected_apps = db.query(DetectedApplication).order_by(DetectedApplication.id.asc()).all()

unknown_items = []
for da in detected_apps:
    h = HybridLicenseEngine.resolve_hybrid_record(da.id, da.normalized_name, da.normalized_publisher, da.detected_version)
    if h["classification"] == "UNKNOWN":
        alias = ApplicationAliasSystem.resolve_application(da.raw_name, da.raw_publisher, da.detected_version)
        is_ms = MicrosoftProductIdentityResolver.is_microsoft_or_windows_related(da.normalized_name, da.normalized_publisher, da.raw_name)
        ms_res = MicrosoftProductIdentityResolver.resolve_identity(da.raw_name, da.raw_publisher, da.detected_version, da.raw_name) if is_ms else None
        unknown_items.append({
            "id": da.id,
            "raw_name": da.raw_name,
            "raw_publisher": da.raw_publisher,
            "norm_name": da.normalized_name,
            "norm_publisher": da.normalized_publisher,
            "version": da.detected_version,
            "install_location": da.install_location,
            "is_ms": is_ms,
            "ms_canonical": ms_res.canonical_name if ms_res else None,
            "ms_vendor": ms_res.canonical_vendor if ms_res else None,
            "ms_type": ms_res.product_type.value if ms_res else None,
            "ms_conf": ms_res.identity_confidence if ms_res else None,
            "alias_canonical": alias.canonical_product,
            "alias_vendor": alias.canonical_vendor,
            "alias_conf": alias.confidence_score,
            "ev_status": h["evidence_status"],
            "quote": h["evidence_quote"]
        })

print(f"=== TOTAL UNKNOWNS: {len(unknown_items)} ===")
for idx, u in enumerate(unknown_items, 1):
    print(f"{idx:02d}. ID={u['id']:03d} | raw_name='{u['raw_name']}' | raw_pub='{u['raw_publisher']}' | install_loc='{u['install_location']}'")
    print(f"    norm_name='{u['norm_name']}' | is_ms={u['is_ms']} | ms_canonical='{u['ms_canonical']}' | ms_type={u['ms_type']}")
    print(f"    alias_canonical='{u['alias_canonical']}' (conf={u['alias_conf']})")
    print(f"    ev_status={u['ev_status']} | quote={u['quote'][:80] if u['quote'] else ''}")
    print()

db.close()
