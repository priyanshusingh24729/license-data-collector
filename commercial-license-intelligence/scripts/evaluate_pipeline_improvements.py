"""
Evaluation Script for Licensing-Data Backend Pipeline Improvements.
Runs the upgraded pipeline on the sample/test dataset and compiles:
1. Number of records enriched by WinGet
2. Number enriched through web discovery
3. Number of PDFs discovered/extracted
4. Number of conflicts detected
5. Accuracy/confidence improvements
6. Any fields that still require manual verification
"""

import os
import sys

# Ensure repository root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import json
import sqlite3
import pandas as pd
from typing import Dict, Any, List
from collections import Counter

from backend.database.connection import SessionLocal
from backend.models.inventory_upload import InventoryUpload, InventoryUploadRow, UploadLicenseResult
from backend.inventory.upload.bulk_upload_processor import BulkUploadProcessor
from backend.sources.winget.winget_manifest_service import WinGetManifestService
from backend.collectors.web.web_collector import WebCollector
from backend.sources.discovery.query_builder import QueryBuilder


def run_evaluation(source_upload_id: str = "upl_20260912_064556_a210f918"):
    print(f"=== Starting Evaluation of Pipeline Improvements on {source_upload_id} ===")
    db = SessionLocal()

    try:
        # Load raw rows from database for the test upload
        rows = db.query(InventoryUploadRow).filter(InventoryUploadRow.upload_id == source_upload_id).all()
        if not rows:
            print(f"Warning: No rows found for {source_upload_id}. Checking any recent upload...")
            recent = db.query(InventoryUpload).order_by(InventoryUpload.id.desc()).first()
            if recent:
                source_upload_id = recent.upload_id
                rows = db.query(InventoryUploadRow).filter(InventoryUploadRow.upload_id == source_upload_id).all()

        print(f"Loaded {len(rows)} raw installation records from upload: {source_upload_id}")

        # Construct DataFrame
        records = []
        for r in rows:
            records.append({
                "Application": r.raw_application,
                "Vendor": r.raw_vendor,
                "Version": r.raw_version,
                "Hostname": r.hostname,
            })
        df = pd.DataFrame(records)

        # Process through BulkUploadProcessor with our new WinGet & Web upgrades
        eval_upload_id = f"eval_{source_upload_id}"
        mapping = {"application": "Application", "vendor": "Vendor", "version": "Version", "hostname": "Hostname"}

        print("\nExecuting BulkUploadProcessor with WinGet Ground Truth & Upgraded Web Discovery...")
        summary = BulkUploadProcessor.process_upload_dataframe(
            upload_id=eval_upload_id,
            file_name="Local_Scan_Sample_Evaluation.json",
            file_type="JSON",
            df=df,
            column_mapping=mapping,
        )
        print(f"Bulk processing complete. Duration: {summary.get('duration_seconds')}s")

        # Query the newly produced UploadLicenseResult records
        results = db.query(UploadLicenseResult).filter(UploadLicenseResult.upload_id == eval_upload_id).all()
        print(f"Retrieved {len(results)} evaluated license result records.")

        # Metric 1: WinGet Enriched Records
        winget_records = [r for r in results if r.evidence_source == "WINGET" or (r.override_reason and "winget" in r.override_reason.lower())]
        # Also check how many products in SQLite winget cache
        conn = sqlite3.connect("data/license_intelligence.db")
        cur = conn.cursor()
        cached_wg = cur.execute("SELECT package_id, package_name, publisher, license, installer_url, installer_sha256 FROM winget_manifests_cache").fetchall()

        # Check records that have installer_url / sha256 or were enriched by winget
        winget_apps = set()
        for r in results:
            if r.evidence_source == "WINGET":
                winget_apps.add(r.canonical_product or r.raw_application)

        # Metric 2: Web Discovery Enriched Records
        web_records = [r for r in results if r.evidence_source in ("SEARXNG", "YACY", "WEB", "SITEMAP", "LLMS_TXT") or (r.evidence_url and "http" in r.evidence_url and r.evidence_source != "WINGET")]

        # Metric 3: PDFs discovered/extracted
        # Test PDF harvester on real vendor licensing pages (e.g. Docker, MongoDB, Tableau)
        pdf_urls_found = []
        collector = WebCollector()
        sample_vendors = [
            ("Docker", "https://docs.docker.com/subscription/details/"),
            ("MongoDB", "https://www.mongodb.com/licensing/server-side-public-license"),
        ]
        for v_name, v_url in sample_vendors:
            try:
                res = collector.collect(v_url, vendor=v_name)
                if res.harvested_pdfs:
                    pdf_urls_found.extend(res.harvested_pdfs)
            except Exception as e:
                pass

        # Metric 4: Conflicts detected
        # WinGet conflicts logged during processing (e.g. catalog ground truth vs WinGet manifest generic labels)
        conflicts_count = summary.get("winget_conflicts_count", 0)

        # Metric 5: Accuracy / Confidence Improvements
        conf_counts = Counter(r.confidence for r in results)
        rel_scores = [r.reliability_score for r in results if r.reliability_score is not None]
        avg_reliability = sum(rel_scores) / len(rel_scores) if rel_scores else 0.0

        # Metric 6: Fields requiring manual verification
        manual_review = [
            r for r in results 
            if r.classification in ("UNKNOWN", "", None) 
            or r.evidence_status == "MISSING"
            or r.confidence in ("LOW", "UNKNOWN")
        ]

        report = {
            "source_upload_id": source_upload_id,
            "eval_upload_id": eval_upload_id,
            "total_records": len(results),
            "unique_applications": summary.get("unique_applications"),
            "1_winget_enriched_records": len(winget_records) or summary.get("winget_enriched_count", 0),
            "1_winget_cached_manifests_count": len(cached_wg),
            "1_winget_sample_manifests": [{"package_id": m[0], "name": m[1], "license": m[3], "has_sha256": bool(m[5])} for m in cached_wg[:5]],
            "2_web_discovery_enriched_records": len(web_records),
            "3_pdfs_discovered_count": len(pdf_urls_found),
            "3_sample_harvested_pdfs": pdf_urls_found[:5],
            "4_conflicts_detected": conflicts_count,
            "5_confidence_distribution": dict(conf_counts),
            "5_average_reliability_score": round(avg_reliability, 2),
            "6_manual_verification_required_count": len(manual_review),
            "6_manual_verification_sample": [
                {"app": r.raw_application, "vendor": r.raw_vendor, "reason": "Missing verified evidence / Unknown classification"}
                for r in manual_review[:5]
            ]
        }

        print("\n" + "="*60)
        print("PIPELINE IMPROVEMENTS EVALUATION REPORT")
        print("="*60)
        print(f"1. Records Enriched by WinGet: {report['1_winget_enriched_records']} (Cached manifests: {report['1_winget_cached_manifests_count']})")
        print(f"2. Records Enriched through Web Discovery: {report['2_web_discovery_enriched_records']}")
        print(f"3. PDFs Discovered/Harvested: {report['3_pdfs_discovered_count']}")
        print(f"4. Conflicts Detected & Preserved: {report['4_conflicts_detected']}")
        print(f"5. Accuracy & Confidence: {report['5_confidence_distribution']} (Avg Reliability: {report['5_average_reliability_score']}%)")
        print(f"6. Records Requiring Manual Verification: {report['6_manual_verification_required_count']}")
        print("="*60)

        out_path = "data/pipeline_improvements_evaluation.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nDetailed report written to: {out_path}")

        return report

    finally:
        db.close()


if __name__ == "__main__":
    run_evaluation()
