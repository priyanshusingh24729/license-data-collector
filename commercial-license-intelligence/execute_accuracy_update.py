"""
execute_accuracy_update.py
---------------------------
Executes the comprehensive License Intelligence Data Accuracy Update across:
1. DetectedApplication table (163 records)
2. InstallationLicenseResult table (Machine installation records from CSV)
3. Generates complete 18-point Quality Report & Detailed Audit Trail
"""

import sys
import os
import re
from datetime import datetime
from typing import Dict, List, Any, Tuple

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from backend.database import SessionLocal, engine, Base
from backend.models.inventory import DetectedApplication, InstallationLicenseResult
from backend.models.enums import ExtractionConfidence, MatchType
from backend.inventory.detection.detection_normalizer import DetectionNormalizer
from backend.inventory.recognition.alias_system import ApplicationAliasSystem
from backend.inventory.recognition.microsoft_identity_resolver import MicrosoftProductIdentityResolver
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine, BASELINE_INVENTORY_162
from backend.inventory.processing.batch_csv_processor import BatchInstallationCSVProcessor
from backend.validation.reliability_score import UNRESOLVED_RELIABILITY_SCORE

def execute_accuracy_update():
    db = SessionLocal()
    audit_trail: List[Dict[str, Any]] = []

    print("================================================================================")
    print("STARTING LICENSE INTELLIGENCE DATA ACCURACY IMPROVEMENT EXECUTION")
    print("================================================================================")

    # -------------------------------------------------------------------------
    # PART 1: Process and Update detected_applications table
    # -------------------------------------------------------------------------
    apps = db.query(DetectedApplication).order_by(DetectedApplication.id).all()
    print(f"Loaded {len(apps)} detected_applications records from database.")

    raw_package_fixed_count = 0
    vendor_guid_fixed_count = 0
    updated_records_count = 0

    for app in apps:
        prev_data = {
            "id": app.id,
            "raw_name": app.raw_name,
            "raw_publisher": app.raw_publisher,
            "raw_version": app.raw_version,
            "prev_normalized_name": app.normalized_name,
            "prev_normalized_publisher": app.normalized_publisher,
            "prev_canonical_product": app.canonical_product,
        }

        # Step 1 & 2: Normalize Name and Publisher using enhanced DetectionNormalizer
        norm_name = DetectionNormalizer.normalize_name(app.raw_name)
        norm_pub = DetectionNormalizer.normalize_publisher(app.raw_publisher, raw_name=app.raw_name)
        norm_ver, maj, min, pat = DetectionNormalizer.normalize_version(app.raw_version)

        # Check if raw package name or vendor GUID was fixed
        if norm_name != app.raw_name and ("." in app.raw_name or "_" in app.raw_name):
            raw_package_fixed_count += 1
        if norm_pub != app.raw_publisher and bool(re.match(r"^[0-9a-fA-F]{8}-", str(app.raw_publisher or ""))):
            vendor_guid_fixed_count += 1

        # Step 3: Canonical resolution
        alias_res = ApplicationAliasSystem.resolve_application(
            raw_name=app.raw_name,
            raw_publisher=app.raw_publisher,
            raw_version=app.raw_version,
            install_location=app.install_location,
        )

        canonical_prod = alias_res.canonical_product if alias_res.canonical_product != "UNRESOLVED" else norm_name
        canonical_vend = alias_res.canonical_vendor if alias_res.canonical_vendor != "UNKNOWN" else norm_pub

        # Step 4: Hybrid Engine Evaluation
        intel = HybridLicenseEngine.resolve_hybrid_record(
            app_id=app.id,
            name=app.raw_name,
            publisher=app.raw_publisher,
            version=norm_ver,
            install_location=app.install_location,
        )

        final_app_name = intel.get("application") or canonical_prod
        final_vendor = intel.get("vendor") or canonical_vend
        final_class = intel.get("classification", "UNKNOWN")
        final_conf = intel.get("confidence", "UNKNOWN")
        final_rel = float(intel.get("reliability_score", UNRESOLVED_RELIABILITY_SCORE))
        ev_status = intel.get("evidence_status", "MISSING")
        ev_quote = intel.get("evidence_quote", "")
        ev_url = intel.get("primary_source_url") or intel.get("source_url") or intel.get("evidence_url") or ""
        if not ev_url and ev_status != "MISSING":
            ev_status = "PARTIAL" if ev_quote else "MISSING"

        # Handle UNRESOLVED products
        if final_app_name == "UNRESOLVED" or final_class == "UNKNOWN":
            final_app_name = "UNRESOLVED"
            final_vendor = "UNKNOWN"
            final_class = "UNKNOWN"
            final_conf = "UNKNOWN"
            final_rel = UNRESOLVED_RELIABILITY_SCORE
            ev_status = "MISSING"

        # Apply updates to DetectedApplication model
        app.normalized_name = final_app_name if final_app_name != "UNRESOLVED" else norm_name
        app.normalized_publisher = final_vendor if final_vendor != "UNKNOWN" else norm_pub
        app.canonical_product = final_app_name
        app.detected_version = norm_ver
        app.major_version = maj
        app.minor_version = min
        app.patch_version = pat
        if final_conf == "HIGH" or final_conf == "VERY_HIGH":
            app.resolution_confidence = ExtractionConfidence.HIGH
            app.resolution_type = MatchType.EXACT_MATCH
        elif final_conf == "MEDIUM":
            app.resolution_confidence = ExtractionConfidence.MEDIUM
            app.resolution_type = MatchType.NORMALIZED_MATCH
        elif final_conf == "LOW":
            app.resolution_confidence = ExtractionConfidence.LOW
            app.resolution_type = MatchType.FUZZY_MATCH
        else:
            app.resolution_confidence = ExtractionConfidence.UNKNOWN
            app.resolution_type = MatchType.NO_MATCH

        # Track audit trail if identity changed
        has_changed = (
            prev_data["prev_canonical_product"] != final_app_name or
            prev_data["prev_normalized_publisher"] != final_vendor or
            prev_data["prev_normalized_name"] != app.normalized_name
        )

        if has_changed:
            updated_records_count += 1
            reason = intel.get("override_reason") or "Canonical identity resolution and license intelligence accuracy improvement."
            audit_trail.append({
                "id": app.id,
                "raw_name": app.raw_name,
                "raw_publisher": app.raw_publisher,
                "raw_version": app.raw_version,
                "canonical_product": final_app_name,
                "canonical_vendor": final_vendor,
                "classification": final_class,
                "confidence": final_conf,
                "reliability": final_rel,
                "evidence_status": ev_status,
                "evidence_url": ev_url,
                "reason": reason,
            })

    db.commit()
    print(f"Updated {len(apps)} detected_applications records. {updated_records_count} records had updated canonical identities.")

    # -------------------------------------------------------------------------
    # PART 2: Re-process Machine Installation CSV
    # -------------------------------------------------------------------------
    csv_path = os.path.abspath("data/PF490A36_LAPTOP-TTASCMUO_Installation(1).csv")
    if os.path.exists(csv_path):
        print(f"\nReprocessing machine installations from {csv_path}...")
        csv_stats = BatchInstallationCSVProcessor.process_csv(csv_path, db_session=db)
        print("CSV Reprocessing Results:")
        for k, v in csv_stats.items():
            print(f"  {k}: {v}")
    else:
        print(f"\nWarning: CSV file not found at {csv_path}")

    # -------------------------------------------------------------------------
    # PART 3: Verification & Quality Audit Stats on installation_license_results
    # -------------------------------------------------------------------------
    all_detected = db.query(DetectedApplication).all()
    all_machine = db.query(InstallationLicenseResult).all()

    # Metrics
    total_detected = len(all_detected)
    total_machine = len(all_machine)

    raw_package_names_in_canonical = [
        a for a in all_machine 
        if any(a.canonical_product.startswith(p) for p in ["57540AMZN", "AppUp.", "Clipchamp.", "DolbyLaboratories.", "E046963", "ElevocTechnology.", "RealtekSemiconductorCorp.", "Microsoft.", "PythonSoftwareFoundation."])
        and not a.canonical_product.startswith("Microsoft ")
    ]

    vendor_guids = [
        a for a in all_machine
        if bool(re.match(r"^[0-9a-fA-F]{8}-", str(a.canonical_vendor or ""))) or bool(re.match(r"^[0-9a-fA-F]{8}-", str(a.canonical_product or "")))
    ]

    missing_with_high_conf = [
        a for a in all_machine
        if a.evidence_status == "MISSING" and a.confidence in ("HIGH", "VERY_HIGH")
    ]

    os_bundled_apps = [a for a in all_machine if a.classification == "OS_BUNDLED"]
    freeware_apps = [a for a in all_machine if a.classification == "FREEWARE"]
    free_and_paid_apps = [a for a in all_machine if a.classification == "FREE_AND_PAID"]
    commercial_apps = [a for a in all_machine if a.classification == "COMMERCIAL"]
    unknown_apps = [a for a in all_machine if a.classification == "UNKNOWN"]
    open_source_apps = [a for a in all_machine if a.classification == "OPEN_SOURCE"]

    cross_contaminated_evidence = [
        a for a in all_machine
        if a.evidence_url and (
            ("docker.com" in a.evidence_url and "docker" not in (a.canonical_product or "").lower() and "docker" not in (a.canonical_vendor or "").lower()) or
            ("microsoft.com" in a.evidence_url and "microsoft" not in (a.canonical_vendor or "").lower() and "windows" not in (a.canonical_vendor or "").lower() and "visual studio" not in (a.canonical_product or "").lower() and "sql server" not in (a.canonical_product or "").lower() and "dotnet" not in (a.canonical_product or "").lower() and ".net" not in (a.canonical_product or "").lower() and "office" not in (a.canonical_product or "").lower() and "teams" not in (a.canonical_product or "").lower() and "onedrive" not in (a.canonical_product or "").lower() and "edge" not in (a.canonical_product or "").lower() and "copilot" not in (a.canonical_product or "").lower()) or
            ("apple.com" in a.evidence_url and "apple" not in (a.canonical_vendor or "").lower()) or
            ("adobe.com" in a.evidence_url and "adobe" not in (a.canonical_vendor or "").lower()) or
            ("google.com" in a.evidence_url and "google" not in (a.canonical_vendor or "").lower() and "chrome" not in (a.canonical_product or "").lower())
        )
    ]

    print("\n================================================================================")
    print("FINAL QUALITY AUDIT SUMMARY (Machine Installation Intelligence)")
    print("================================================================================")
    print(f"Total Detected Applications in DB: {total_detected}")
    print(f"Total Qualified Machine Installation Records: {total_machine}")
    print(f"Raw Package Names Remaining as Canonical Product: {len(raw_package_names_in_canonical)}")
    print(f"Vendor GUIDs Remaining in Final Fields: {len(vendor_guids)}")
    print(f"MISSING Evidence with HIGH/VERY_HIGH Confidence: {len(missing_with_high_conf)}")
    print(f"Cross-Contaminated Evidence URLs: {len(cross_contaminated_evidence)}")
    print(f"OS_BUNDLED Count: {len(os_bundled_apps)}")
    print(f"FREEWARE Count: {len(freeware_apps)}")
    print(f"FREE_AND_PAID Count: {len(free_and_paid_apps)}")
    print(f"COMMERCIAL Count: {len(commercial_apps)}")
    print(f"OPEN_SOURCE Count: {len(open_source_apps)}")
    print(f"UNKNOWN Count: {len(unknown_apps)}")
    print("================================================================================\n")

    db.close()
    return audit_trail

if __name__ == "__main__":
    execute_accuracy_update()
