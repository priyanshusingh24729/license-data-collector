from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
from backend.inventory.recognition.microsoft_identity_resolver import MicrosoftProductIdentityResolver
from backend.research.windows_product_adapter import WindowsProductResearchAdapter
from backend.validation.microsoft_evidence_validator import MicrosoftEvidenceValidator

db = SessionLocal()
detected_apps = db.query(DetectedApplication).order_by(DetectedApplication.id.asc()).all()

unknowns = []
for da in detected_apps:
    h = HybridLicenseEngine.resolve_hybrid_record(da.id, da.normalized_name, da.normalized_publisher, da.detected_version)
    if h["classification"] == "UNKNOWN":
        is_ms = MicrosoftProductIdentityResolver.is_microsoft_or_windows_related(da.normalized_name, da.normalized_publisher, da.raw_name)
        ms_id = MicrosoftProductIdentityResolver.resolve_identity(da.raw_name, da.raw_publisher, da.detected_version, da.raw_name)
        research = WindowsProductResearchAdapter.research_product(ms_id, "UNKNOWN", "UNKNOWN") if is_ms else None
        unknowns.append({
            "id": da.id,
            "raw_name": da.raw_name,
            "raw_pub": da.raw_publisher,
            "norm_name": da.normalized_name,
            "norm_pub": da.normalized_publisher,
            "version": da.detected_version,
            "is_ms": is_ms,
            "ms_canonical": ms_id.canonical_name if is_ms else None,
            "ms_vendor": ms_id.canonical_vendor if is_ms else None,
            "ms_type": ms_id.product_type.value if is_ms else None,
            "ms_conf": ms_id.identity_confidence if is_ms else None,
            "research_ev_status": research.evidence_status if research else None,
            "research_class": research.classification if research else None,
            "research_quote": research.evidence_quote if research else None,
            "research_tier": research.evidence_tier_name if research else None,
            "h_app": h["application"],
            "h_vendor": h["vendor"],
            "h_ev": h["evidence_status"],
            "h_conf": h["confidence"],
            "h_rel": h["reliability_score"],
        })

print(f"Total unknowns: {len(unknowns)}")
for u in unknowns:
    print(f"ID {u['id']:03d} | Raw: {u['raw_name']} | Pub: {u['raw_pub']}")
    print(f"   Norm: {u['norm_name']} | NormPub: {u['norm_pub']}")
    print(f"   MS: is_ms={u['is_ms']}, canonical={u['ms_canonical']}, vendor={u['ms_vendor']}, type={u['ms_type']}, conf={u['ms_conf']}")
    print(f"   Research: ev_status={u['research_ev_status']}, class={u['research_class']}, tier={u['research_tier']}")
    print(f"   Quote: {u['research_quote']}")
    print("-" * 60)

db.close()
