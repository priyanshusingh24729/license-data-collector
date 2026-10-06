"""
generate_sanitized_export.py
----------------------------
Generates audit-ready, executive-grade software license intelligence reports:
1. data/sanitized_commercial_license_inventory.csv (Full Clean Multi-Tier Inventory)
2. data/commercial_software_billable_report.csv (Tier 1: Commercial & Billable Applications Only)
3. data/sanitized_inventory_summary.json (Executive KPI Metrics & Distributions)
"""

import sys
import os
import csv
import json
from collections import defaultdict
from typing import Dict, List, Any

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.database import SessionLocal
from backend.models.inventory import InstallationLicenseResult, DetectedApplication
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine


def get_tier(classification: str, license_required: str = None) -> str:
    """Assigns software into clear executive tiers."""
    c = (classification or "").upper()
    req = (license_required or "").upper()

    # If license is explicitly not required (free runtime, driver, OS utility, component), exclude from Tier 1 Billable
    if req in ("NO", "NOT_APPLICABLE", "FREE"):
        if c in ("OPEN_SOURCE", "FREEWARE"):
            return "Tier 2: Freeware & Developer Open Source"
        return "Tier 3: OS & System Infrastructure"

    if c in ("COMMERCIAL", "FREE_AND_PAID") and req in ("YES", "CONTEXT_DEPENDENT"):
        return "Tier 1: Commercial & Billable"
    elif c in ("COMMERCIAL", "FREE_AND_PAID") and not req:
        return "Tier 1: Commercial & Billable"
    elif c in ("OPEN_SOURCE", "FREEWARE"):
        return "Tier 2: Freeware & Developer Open Source"
    elif c in ("OS_BUNDLED", "OEM_OR_BUNDLED", "OEM", "LINUX_SYSTEM_PACKAGE", "MACOS_SYSTEM_COMPONENT", "WEB_SHORTCUT_OR_PWA", "WEB_SHORTCUT/PWA", "COMMERCIAL_COMPONENT", "RUNTIME_FRAMEWORK", "SHARED_COMPONENT"):
        return "Tier 3: OS & System Infrastructure"
    else:
        return "Tier 4: Unclassified / Review Required"


def export_sanitized_inventory():
    db = SessionLocal()
    try:
        installations = db.query(InstallationLicenseResult).order_by(
            InstallationLicenseResult.canonical_product.asc()
        ).all()

        if not installations:
            print("[WARNING] No installation records found in InstallationLicenseResult.")
            return

        print(f"Loaded {len(installations)} machine installation records from database.")

        # Aggregate versions by (canonical_product, canonical_vendor, hostname)
        grouped: Dict[tuple, Dict[str, Any]] = defaultdict(lambda: {
            "versions": set(),
            "count": 0,
            "classification": "",
            "availability": "",
            "license_required": "",
            "license_model": "",
            "metric": "",
            "confidence": "",
            "evidence_status": "",
            "evidence_url": "",
            "raw_apps": set(),
        })

        for inst in installations:
            key = (
                inst.canonical_product or inst.raw_application_name,
                inst.canonical_vendor or inst.raw_vendor or "UNKNOWN",
                inst.hostname or "LAPTOP-TTASCMUO"
            )
            g = grouped[key]
            g["count"] += 1
            if inst.raw_version and inst.raw_version != "N/A":
                g["versions"].add(inst.raw_version)
            
            g["classification"] = inst.classification or "UNKNOWN"
            g["availability"] = "FREE" if inst.classification in ("OPEN_SOURCE", "FREEWARE") else ("PAID" if inst.classification == "COMMERCIAL" else "CONTEXT_DEPENDENT")
            g["license_required"] = inst.license_requirement or "UNKNOWN"
            g["license_model"] = inst.license_model or "UNKNOWN"
            g["metric"] = inst.license_metric or "NOT_APPLICABLE"
            g["confidence"] = inst.confidence or "UNKNOWN"
            g["evidence_status"] = inst.evidence_status or "MISSING"
            g["evidence_url"] = inst.evidence_url or ""
            if inst.raw_application_name:
                g["raw_apps"].add(inst.raw_application_name)

        # Build clean rows
        full_rows: List[Dict[str, Any]] = []
        billable_rows: List[Dict[str, Any]] = []

        for (prod, vend, host), data in sorted(grouped.items(), key=lambda x: (get_tier(x[1]["classification"], x[1]["license_required"]), x[0][0])):
            tier = get_tier(data["classification"], data["license_required"])
            sorted_vers = sorted(list(data["versions"]))
            if len(sorted_vers) == 0:
                ver_str = "N/A"
            elif len(sorted_vers) <= 2:
                ver_str = "; ".join(sorted_vers)
            else:
                ver_str = f"{sorted_vers[0]}; {sorted_vers[1]} (+{len(sorted_vers) - 2} more)"

            row = {
                "Tier": tier,
                "Canonical Product": prod,
                "Vendor / Publisher": vend,
                "Installed Version(s)": ver_str,
                "Install Count": data["count"],
                "Classification": data["classification"],
                "Availability": data["availability"],
                "License Required": data["license_required"],
                "Licensing Model": data["license_model"],
                "License Metric": data["metric"],
                "Confidence": data["confidence"],
                "Evidence Status": data["evidence_status"],
                "Evidence URL": data["evidence_url"],
                "Device Hostname": host,
            }
            full_rows.append(row)

            if tier == "Tier 1: Commercial & Billable":
                billable_rows.append({
                    "Canonical Product": prod,
                    "Vendor / Publisher": vend,
                    "Installed Version(s)": ver_str,
                    "Install Count": data["count"],
                    "Classification": data["classification"],
                    "License Required": data["license_required"],
                    "Licensing Model": data["license_model"],
                    "License Metric": data["metric"],
                    "Confidence": data["confidence"],
                    "Evidence Status": data["evidence_status"],
                    "Evidence URL": data["evidence_url"],
                    "Device Hostname": host,
                })

        # Save data/sanitized_commercial_license_inventory.csv
        out_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(out_dir, exist_ok=True)

        full_csv_path = os.path.join(out_dir, "sanitized_commercial_license_inventory.csv")
        with open(full_csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(full_rows[0].keys()))
            writer.writeheader()
            writer.writerows(full_rows)

        print(f"[OK] Generated full sanitized inventory: {full_csv_path} ({len(full_rows)} unique products)")

        # Save data/commercial_software_billable_report.csv
        billable_csv_path = os.path.join(out_dir, "commercial_software_billable_report.csv")
        with open(billable_csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(billable_rows[0].keys()))
            writer.writeheader()
            writer.writerows(billable_rows)

        print(f"[OK] Generated executive billable report: {billable_csv_path} ({len(billable_rows)} billable products)")

        # Summary KPIs
        tier_counts = defaultdict(int)
        for r in full_rows:
            tier_counts[r["Tier"]] += 1

        summary_data = {
            "total_unique_products": len(full_rows),
            "total_installations": sum(r["Install Count"] for r in full_rows),
            "tier_distribution": dict(tier_counts),
            "billable_product_count": len(billable_rows),
            "cross_contaminated_urls": sum(1 for r in full_rows if "docker.com" in r["Evidence URL"] and "docker" not in r["Canonical Product"].lower()),
        }

        summary_json_path = os.path.join(out_dir, "sanitized_inventory_summary.json")
        with open(summary_json_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2)

        print(f"[OK] Summary KPIs saved: {summary_json_path}")
        print("\n--- TIER DISTRIBUTION ---")
        for t, cnt in sorted(tier_counts.items()):
            print(f"  * {t}: {cnt} products")

    finally:
        db.close()


if __name__ == "__main__":
    export_sanitized_inventory()
