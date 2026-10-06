import sys
import os
sys.path.insert(0, os.path.abspath("."))

from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine

db = SessionLocal()
apps = db.query(DetectedApplication).order_by(DetectedApplication.id).all()

unknowns_remaining = []
resolved_summary = []

for a in apps:
    res = HybridLicenseEngine.resolve_hybrid_record(
        app_id=a.id,
        name=a.raw_name,
        publisher=a.raw_publisher,
        version=a.detected_version,
        install_location=a.install_location,
    )
    if res["classification"] == "UNKNOWN":
        unknowns_remaining.append((a.id, a.raw_name, a.normalized_name, a.raw_publisher, res))
    else:
        resolved_summary.append((a.id, a.raw_name, res["application"], res["vendor"], res["classification"], res["evidence_status"], res["confidence"], res["reliability_score"]))

print(f"Total apps evaluated: {len(apps)}")
print(f"Total remaining UNKNOWN: {len(unknowns_remaining)}")
print(f"Total RESOLVED: {len(resolved_summary)}")

print("\n--- Remaining UNKNOWN Records ---")
for uid, raw, norm, pub, r in unknowns_remaining:
    print(f"ID {uid:03d} | raw='{raw}' | norm='{norm}' | pub='{pub}' | res_app='{r['application']}' | res_class='{r['classification']}' | ev='{r['evidence_status']}'")

print("\n--- Sample of Resolved Records (First 20) ---")
for rid, raw, res_app, res_vend, res_class, ev_st, conf, rel in resolved_summary[:20]:
    print(f"ID {rid:03d} | raw='{raw}' -> '{res_app}' ({res_vend}) | Class: {res_class} | Ev: {ev_st} | Conf: {conf} | Rel: {rel:.1f}%")

db.close()
