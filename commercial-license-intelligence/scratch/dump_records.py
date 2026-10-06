import sys
import os
sys.path.insert(0, os.path.abspath("."))
from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine

db = SessionLocal()
apps = db.query(DetectedApplication).order_by(DetectedApplication.id.asc()).all()
print(f"Total detected apps: {len(apps)}")

with open("scratch/all_163_detected.txt", "w", encoding="utf-8") as f:
    for a in apps:
        h = HybridLicenseEngine.resolve_hybrid_record(a.id, a.normalized_name, a.normalized_publisher, a.detected_version)
        line = f"ID {a.id:03d} | raw_name={a.raw_name!r} | norm_name={a.normalized_name!r} | raw_pub={a.raw_publisher!r} | norm_pub={a.normalized_publisher!r} | canon_prod={h['application']!r} | canon_vend={h['vendor']!r} | class={h['classification']} | req={h['license_required']} | model={h['license_model']} | ev={h['evidence_status']} | conf={h['confidence']} | rel={h['reliability_score']}%\n"
        f.write(line)

machs = db.query(InstallationLicenseResult).order_by(InstallationLicenseResult.id.asc()).all()
print(f"Total machine apps: {len(machs)}")

with open("scratch/all_86_machine.txt", "w", encoding="utf-8") as f:
    for m in machs:
        line = f"ID {m.id:03d} | raw_name={m.raw_application_name!r} | raw_vend={m.raw_vendor!r} | canon_prod={m.canonical_product!r} | canon_vend={m.canonical_vendor!r} | ver={m.raw_version!r} | class={m.classification} | req={m.license_requirement} | model={m.license_model} | ev={m.evidence_status} | conf={m.confidence} | rel={m.reliability_score}% | url={m.evidence_url!r}\n"
        f.write(line)

print("Wrote scratch files successfully.")
db.close()
