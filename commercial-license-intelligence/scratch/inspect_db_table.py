import sys
import os
sys.path.insert(0, os.path.abspath("."))

from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine

db = SessionLocal()
apps = db.query(DetectedApplication).order_by(DetectedApplication.id).all()
print(f"Total DetectedApplication records: {len(apps)}")
for a in apps:
    # Streamlit calls it with name=da.normalized_name, publisher=da.normalized_publisher
    res = HybridLicenseEngine.resolve_hybrid_record(
        app_id=a.id,
        name=a.normalized_name,
        publisher=a.normalized_publisher,
        version=a.detected_version,
    )
    print(f"ID {a.id:03d} | raw={a.raw_name!r:35} | norm={a.normalized_name!r:40} | class={res['classification']:12} | conf={res['confidence']:6} | rel={res['reliability_score']:.1f}% | ev={res['evidence_status']}")

db.close()
