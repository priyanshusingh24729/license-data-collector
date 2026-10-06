from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine, BASELINE_INVENTORY_162
from backend.inventory.recognition.microsoft_identity_resolver import MicrosoftProductIdentityResolver
from backend.research.windows_product_adapter import WindowsProductResearchAdapter
from backend.validation.microsoft_evidence_validator import MicrosoftEvidenceValidator
import json

db = SessionLocal()
detected_apps = db.query(DetectedApplication).order_by(DetectedApplication.id.asc()).all()

unknowns = []
for da in detected_apps:
    h = HybridLicenseEngine.resolve_hybrid_record(da.id, da.normalized_name, da.normalized_publisher, da.detected_version)
    if h["classification"] == "UNKNOWN":
        is_ms = MicrosoftProductIdentityResolver.is_microsoft_or_windows_related(da.normalized_name, da.normalized_publisher, da.raw_name)
        ms_id = MicrosoftProductIdentityResolver.resolve_identity(da.raw_name, da.raw_publisher, da.detected_version, da.raw_name)
        research = WindowsProductResearchAdapter.research_product(ms_id, "UNKNOWN", "UNKNOWN") if is_ms else None
        
        # also check if da.id is in BASELINE_INVENTORY_162
        b_entry = next((b for b in BASELINE_INVENTORY_162 if b["id"] == da.id), None)
        
        unknowns.append({
            "id": da.id,
            "raw_name": da.raw_name,
            "raw_pub": da.raw_publisher,
            "norm_name": da.normalized_name,
            "norm_pub": da.normalized_publisher,
            "version": da.detected_version,
            "install_loc": da.install_location,
            "baseline_entry": b_entry,
            "is_ms": is_ms,
            "ms_canonical": ms_id.canonical_name if is_ms else None,
            "ms_vendor": ms_id.canonical_vendor if is_ms else None,
            "ms_type": ms_id.product_type.value if is_ms else None,
            "ms_conf": ms_id.identity_confidence if is_ms else None,
            "research_ev_status": research.evidence_status if research else None,
            "research_class": research.classification if research else None,
            "research_tier": research.evidence_tier_name if research else None,
            "research_quote": research.evidence_quote if research else None,
        })

with open("scratch/all_61_unknowns.json", "w", encoding="utf-8") as f:
    json.dump(unknowns, f, indent=2)

print(f"Dumped {len(unknowns)} UNKNOWN records to scratch/all_61_unknowns.json")
db.close()
