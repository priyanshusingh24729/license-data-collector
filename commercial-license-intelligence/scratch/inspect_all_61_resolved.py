import sys
import os
sys.path.insert(0, os.path.abspath("."))

from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine

# IDs of the 61 previously UNKNOWN records
unknown_ids = [
    37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56,
    57, 58, 59, 60, 62, 63, 64, 65, 67, 76, 78, 80, 85, 94, 96, 102, 111, 115, 117,
    118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 141, 143, 144,
    146, 148, 153, 154, 159, 179
]

db = SessionLocal()
apps = db.query(DetectedApplication).filter(DetectedApplication.id.in_(unknown_ids)).order_by(DetectedApplication.id).all()

print(f"{'ID':<4} | {'Raw Name':<35} | {'Canonical Name':<35} | {'Vendor':<20} | {'Classification':<20} | {'Ev Status':<10} | {'Rel Score':<8}")
print("-" * 145)

classes = {}
ev_statuses = {}

for a in apps:
    res = HybridLicenseEngine.resolve_hybrid_record(
        app_id=a.id,
        name=a.raw_name,
        publisher=a.raw_publisher,
        version=a.detected_version,
        install_location=a.install_location,
    )
    c = res["classification"]
    ev = res["evidence_status"]
    classes[c] = classes.get(c, 0) + 1
    ev_statuses[ev] = ev_statuses.get(ev, 0) + 1
    print(f"{a.id:<4} | {a.raw_name[:35]:<35} | {res['application'][:35]:<35} | {res['vendor'][:20]:<20} | {c:<20} | {ev:<10} | {res['reliability_score']:.1f}%")

print("\n--- Distribution of the 61 Previously Unknown Records ---")
for c, cnt in sorted(classes.items()):
    print(f"  {c}: {cnt}")

print("\n--- Evidence Status Distribution ---")
for ev, cnt in sorted(ev_statuses.items()):
    print(f"  {ev}: {cnt}")

db.close()
