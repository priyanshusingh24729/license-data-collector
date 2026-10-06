import re
from typing import Dict, Any, List, Tuple
from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine, BASELINE_INVENTORY_162
from backend.inventory.recognition.alias_system import ApplicationAliasSystem

db = SessionLocal()

print("Auditing both Baseline (163 records) and Machine Results (86 records)...")

detected_apps = db.query(DetectedApplication).order_by(DetectedApplication.id.asc()).all()
mach_apps = db.query(InstallationLicenseResult).order_by(InstallationLicenseResult.id.asc()).all()

print(f"Total Detected Applications: {len(detected_apps)}")
print(f"Total Machine Installation Results: {len(mach_apps)}")

# Identify all Freeware and Free_and_Paid records
freeware_records = []
free_and_paid_records = []
other_records = []

for da in detected_apps:
    h = HybridLicenseEngine.resolve_hybrid_record(da.id, da.normalized_name, da.normalized_publisher, da.detected_version)
    c = h["classification"]
    item = {
        "source": "BASELINE",
        "id": da.id,
        "raw_name": da.raw_name,
        "canonical_name": h["application"],
        "vendor": h["vendor"],
        "version": h["version"],
        "classification": c,
        "availability": h["availability"],
        "license_required": h["license_required"],
        "license_model": h["license_model"],
        "metric": h["metric"],
        "confidence": h["confidence"],
        "reliability": h["reliability_score"],
        "evidence_status": h["evidence_status"],
        "evidence_quote": h.get("evidence_quote"),
    }
    if c == "FREEWARE":
        freeware_records.append(item)
    elif c == "FREE_AND_PAID":
        free_and_paid_records.append(item)
    else:
        other_records.append(item)

print(f"\nBaseline FREEWARE: {len(freeware_records)}")
print(f"Baseline FREE_AND_PAID: {len(free_and_paid_records)}")
print(f"Baseline Other: {len(other_records)}")

db.close()
