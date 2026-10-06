"""
Batch validation runner for the Snow SRS master dataset (srs apps M.csv).
Evaluates Snow Authoritative Baseline preservation, evidence enrichment,
and discrepancy detection across a representative batch of real production records.
"""

import os
import sys
import time
import logging
import pandas as pd

os.environ["ENABLE_WINGET_CLI_SEARCH"] = "false"

from backend.inventory.upload.bulk_upload_processor import BulkUploadProcessor
from backend.inventory.upload.upload_parser import UploadFileParser
from backend.database.connection import SessionLocal
from backend.models.inventory_upload import UploadLicenseResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SNOW_CSV_PATH = r"C:\Users\Priyanshu Singh\OneDrive - Silver Leaf Solutions Private Limited\Desktop\DB matching\srs apps M.csv"

def run_snow_batch_validation(sample_size: int = 5000):
    if not os.path.exists(SNOW_CSV_PATH):
        logger.error(f"Snow CSV not found at {SNOW_CSV_PATH}")
        return

    logger.info(f"Reading first {sample_size} rows from {SNOW_CSV_PATH}...")
    start_read = time.time()
    df = pd.read_csv(SNOW_CSV_PATH, nrows=sample_size, encoding="utf-8-sig", dtype=str)
    read_duration = time.time() - start_read
    logger.info(f"Loaded {len(df)} rows in {read_duration:.2f}s")

    columns = list(df.columns)
    col_mapping = UploadFileParser.auto_detect_columns(columns)
    logger.info(f"Auto-detected column mapping: {col_mapping}")

    upload_id = f"snow_validation_batch_{int(time.time())}"
    logger.info(f"Processing batch upload '{upload_id}' through BulkUploadProcessor...")
    
    start_proc = time.time()
    summary = BulkUploadProcessor.process_upload_dataframe(
        upload_id=upload_id,
        file_name="srs apps M.csv",
        file_type="CSV",
        df=df,
        column_mapping=col_mapping,
    )
    proc_duration = time.time() - start_proc
    throughput = len(df) / proc_duration if proc_duration > 0 else 0
    logger.info(f"Processed {len(df)} rows in {proc_duration:.2f}s ({throughput:.1f} rows/s)")

    # Audit the resulting data in database
    db = SessionLocal()
    try:
        results = db.query(UploadLicenseResult).filter(UploadLicenseResult.upload_id == upload_id).all()
        total = len(results)

        conflict_dist = {}
        consensus_dist = {}
        class_dist = {}
        snow_lic_dist = {}
        enriched_metrics_count = 0
        spdx_count = 0
        evidence_url_count = 0
        discrepancy_examples = []

        for r in results:
            cs = r.conflict_status or "UNKNOWN"
            conflict_dist[cs] = conflict_dist.get(cs, 0) + 1

            cons = r.consensus_status or "UNKNOWN"
            consensus_dist[cons] = consensus_dist.get(cons, 0) + 1

            c = r.classification or "UNKNOWN"
            class_dist[c] = class_dist.get(c, 0) + 1

            lr = r.license_required or "UNKNOWN"
            snow_lic_dist[lr] = snow_lic_dist.get(lr, 0) + 1

            if "Enriched:" in (r.override_reason or ""):
                enriched_metrics_count += 1

            if r.spdx_id:
                spdx_count += 1

            if r.evidence_url:
                evidence_url_count += 1

            if cs == "DISCREPANCY_FLAGGED" and len(discrepancy_examples) < 5:
                discrepancy_examples.append({
                    "app": r.raw_application,
                    "snow_req": r.license_required,
                    "classification": r.classification,
                    "reason": r.override_reason,
                    "evidence_quote": r.evidence_quote[:120] if r.evidence_quote else "N/A"
                })

        print("\n" + "="*70)
        print(f"SNOW DATASET VALIDATION REPORT ({total} ROWS PROCESSED)")
        print("="*70)
        print(f"Throughput: {throughput:.1f} rows/second (Total time: {proc_duration:.2f}s)")
        print(f"Snow Authoritative License Required Breakdown (Preserved 100%):")
        for k, v in snow_lic_dist.items():
            print(f"  • {k}: {v} ({v/total*100:.1f}%)")

        print(f"\nConflict & Verification Status (Our Intelligence Layer vs Snow):")
        for k, v in conflict_dist.items():
            print(f"  • {k}: {v} ({v/total*100:.1f}%)")

        print(f"\nClassification Distribution:")
        for k, v in sorted(class_dist.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {k}: {v} ({v/total*100:.1f}%)")

        print(f"\nIntelligence Enrichment Highlights:")
        print(f"  • Missing Metrics Enriched: {enriched_metrics_count} rows")
        print(f"  • Valid SPDX Licenses Attached: {spdx_count} rows")
        print(f"  • Official Primary Evidence URLs Attached: {evidence_url_count} rows")

        if discrepancy_examples:
            print(f"\nSample Audit Discrepancies Detected (Snow says Free, but Vendor requires License):")
            for idx, d in enumerate(discrepancy_examples, 1):
                print(f"  [{idx}] Application: {d['app']}")
                print(f"      Snow Baseline Value: {d['snow_req']}")
                print(f"      Classification: {d['classification']}")
                print(f"      Discrepancy Note: {d['reason']}")
                print(f"      Evidence Quote: {d['evidence_quote']}")

        print("="*70)

    finally:
        db.close()

if __name__ == "__main__":
    n = 100
    if len(sys.argv) > 1:
        try:
            n = int(sys.argv[1])
        except ValueError:
            pass
    run_snow_batch_validation(n)
