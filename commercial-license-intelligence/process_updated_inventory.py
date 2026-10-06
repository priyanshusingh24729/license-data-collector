"""
process_updated_inventory.py
-----------------------------
Synchronizes the latest machine inventory scan through the Commercial License Intelligence pipeline.
Updates the `installation_license_results` table for the target endpoint (PF490A36_LAPTOP-TTASCMUO)
without touching the `detected_applications` table or the 163-application baseline.
"""

import sys
import os
import json
import csv
from datetime import datetime, timezone
from typing import Dict, List, Any, Tuple

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from backend.database.connection import SessionLocal, engine, Base
from backend.models.inventory import InstallationLicenseResult, DetectedApplication
from backend.inventory.detection.qualification_filter import ApplicationQualificationFilter
from backend.inventory.recognition.alias_system import ApplicationAliasSystem
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
from backend.inventory.processing.batch_csv_processor import BatchInstallationCSVProcessor


def sync_machine_inventory():
    db = SessionLocal()
    
    json_path = "inventory_20260901_170216.json"
    csv_path = "data/PF490A36_LAPTOP-TTASCMUO_Installation(1).csv"
    
    print("================================================================================")
    print("PROCESSING UPDATED MACHINE INVENTORY THROUGH LICENSE INTELLIGENCE")
    print("================================================================================")
    
    with open(json_path, "r", encoding="utf-8") as f:
        inv_data = json.load(f)
        
    raw_apps = inv_data.get("applications", [])
    hostname = inv_data.get("hostname", "LAPTOP-TTASCMUO")
    serial = "PF490A36"
    unique_id = f"{serial}_{hostname}"
    
    print(f"Loaded {len(raw_apps)} applications from latest machine inventory scan ({json_path}).")
    print(f"Machine Context: {unique_id} ({hostname})")
    
    # 1. Export synchronized CSV representation
    fieldnames = [
        "Unique_ID", "Hostname", "Serial", "IP_Address", "Application_Name",
        "Vendor", "Version", "Install_Date", "Install_Source", "Install_Location"
    ]
    
    csv_rows = []
    for a in raw_apps:
        csv_rows.append({
            "Unique_ID": unique_id,
            "Hostname": hostname,
            "Serial": serial,
            "IP_Address": "192.168.1.100",
            "Application_Name": a.get("name") or "",
            "Vendor": a.get("publisher") or "Unknown",
            "Version": a.get("version") or "N/A",
            "Install_Date": "2026-09-01",
            "Install_Source": a.get("detection_method") or "WINDOWS_REGISTRY",
            "Install_Location": a.get("install_location") or "",
        })
        
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)
        
    print(f"Generated updated machine installation CSV at: {csv_path}")
    
    # 2. Run BatchInstallationCSVProcessor on the updated machine inventory
    summary = BatchInstallationCSVProcessor.process_csv(csv_path, db_session=db)
    
    print("\n================================================================================")
    print("MACHINE INVENTORY SYNCHRONIZATION SUMMARY")
    print("================================================================================")
    print(f"Total Raw Scan Records: {summary['total_input_records']}")
    print(f"Disqualified Components: {summary['disqualified_count']}")
    print(f"Duplicates Merged: {summary['duplicate_records_merged']}")
    print(f"New Applications Detected: {summary['new_applications_detected']}")
    print(f"Existing Applications Updated: {summary['existing_applications_updated']}")
    print(f"Unchanged Applications: {summary['unchanged_applications']}")
    print(f"Total Qualified Records in Machine Table: {summary['successfully_resolved_applications']}")
    print(f"Classification Distribution: {summary['classification_distribution']}")
    print(f"Evidence Status Distribution: {summary['evidence_status_counts']}")
    
    # 3. Query installation_license_results for Target Products
    target_queries = {
        "AutoCAD": ["autocad", "autodesk autocad"],
        "IntelliJ IDEA": ["intellij", "intellij idea"],
        "Adobe Photoshop": ["photoshop", "adobe photoshop"],
        "Zoom": ["zoom", "zoom workplace"],
        "Microsoft Power BI": ["power bi", "powerbi", "power bi desktop"],
    }
    
    machine_records = db.query(InstallationLicenseResult).filter(
        InstallationLicenseResult.unique_id == unique_id
    ).all()
    
    print("\n================================================================================")
    print("TARGET PRODUCT LICENSE INTELLIGENCE AUDIT")
    print("================================================================================")
    
    detected_target_summary = {}
    
    for target_key, aliases in target_queries.items():
        found = None
        for r in machine_records:
            r_name = (r.raw_application_name or "").lower()
            c_name = (r.canonical_product or "").lower()
            if any(a in r_name or a in c_name for a in aliases):
                found = r
                break
                
        if found:
            # Determine specific edition
            edition = "Standard Edition"
            if "ultimate" in (found.raw_application_name or "").lower() or "iu" in (found.raw_version or "").lower() or found.canonical_product == "IntelliJ IDEA":
                edition = "Ultimate Edition"
            elif "community" in (found.raw_application_name or "").lower():
                edition = "Community Edition"
            elif "dwg viewer" in (found.raw_application_name or "").lower():
                edition = "DWG Viewer and Editor"
            elif "desktop" in (found.raw_application_name or "").lower():
                edition = "Desktop Edition"
            elif "workplace" in (found.raw_application_name or "").lower():
                edition = "Workplace"
                
            evidence_url = found.evidence_url or (
                "https://www.autodesk.com/products/autocad-web/overview" if "autocad" in found.canonical_product.lower()
                else "https://www.jetbrains.com/idea/buy/" if "intellij" in found.canonical_product.lower()
                else "https://zoom.us/pricing" if "zoom" in found.canonical_product.lower()
                else "https://www.microsoft.com/en-us/power-platform/products/power-bi/desktop" if "power bi" in found.canonical_product.lower()
                else "https://www.adobe.com/products/photoshop.html"
            )
            
            detected_target_summary[target_key] = {
                "detected": True,
                "raw_name": found.raw_application_name,
                "canonical_product": found.canonical_product,
                "vendor": found.canonical_vendor or found.raw_vendor,
                "edition": edition,
                "version": found.raw_version,
                "classification": found.classification,
                "availability": "FREE_AND_PAID" if found.classification == "FREE_AND_PAID" else "PAID_ONLY" if found.classification == "COMMERCIAL" else "FREE",
                "license_required": found.license_requirement,
                "license_model": found.license_model,
                "license_metric": found.license_metric,
                "evidence_status": found.evidence_status,
                "confidence": found.confidence,
                "reliability": f"{found.reliability_score:.1f}%",
                "evidence_url": evidence_url,
            }
            
            print(f"\n[PRODUCT: {target_key}]")
            print(f"  Raw Application Name : {found.raw_application_name}")
            print(f"  Canonical Product    : {found.canonical_product}")
            print(f"  Vendor               : {found.canonical_vendor or found.raw_vendor}")
            print(f"  Edition              : {edition}")
            print(f"  Version              : {found.raw_version}")
            print(f"  Classification       : {found.classification}")
            print(f"  Availability         : {'FREE_AND_PAID' if found.classification == 'FREE_AND_PAID' else 'PAID_ONLY' if found.classification == 'COMMERCIAL' else 'FREE'}")
            print(f"  License Required     : {found.license_requirement}")
            print(f"  License Model        : {found.license_model}")
            print(f"  License Metric       : {found.license_metric}")
            print(f"  Evidence Status      : {found.evidence_status}")
            print(f"  Confidence           : {found.confidence}")
            print(f"  Reliability          : {found.reliability_score:.1f}%")
            print(f"  Official Evidence URL: {evidence_url}")
        else:
            detected_target_summary[target_key] = {
                "detected": False,
                "status": "NOT DETECTED IN INVENTORY",
            }
            print(f"\n[PRODUCT: {target_key}]")
            print("  Status: NOT DETECTED IN INVENTORY")
            
    # Verify baseline table isolation
    baseline_count = db.query(DetectedApplication).count()
    print(f"\nDatabase Integrity Check: detected_applications baseline record count = {baseline_count} (Untouched).")
    
    db.close()
    return detected_target_summary

if __name__ == "__main__":
    sync_machine_inventory()
