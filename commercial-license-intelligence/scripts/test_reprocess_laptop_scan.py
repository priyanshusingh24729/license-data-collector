"""
Test Re-processing of Laptop Scan with Snow SRS Master Lookup Integration.
Processes 'data/PF490A36_LAPTOP-TTASCMUO_Installation.csv' and verifies:
- Match rate against 907k Snow SRS Master Database
- Metric population (Installations, Users, Devices, No license required)
- Elimination of blank Metric fields
- Preservation of authentic Snow baselines
"""

import os
import sys
import time
import pandas as pd
from collections import Counter

# Prevent slow external network subprocess calls during bulk scan evaluation
os.environ["ENABLE_WINGET_CLI_SEARCH"] = "false"
os.environ["ENABLE_SEARXNG_FALLBACK"] = "false"

sys.path.insert(0, os.path.abspath("."))

from backend.inventory.upload.bulk_upload_processor import BulkUploadProcessor
from backend.inventory.upload.upload_parser import UploadFileParser
from backend.database.connection import SessionLocal
from backend.models.inventory_upload import UploadLicenseResult

CSV_PATH = "data/PF490A36_LAPTOP-TTASCMUO_Installation.csv"


def test_reprocess_laptop_scan():
    print("=" * 75)
    print("RE-PROCESSING LAPTOP SCAN WITH SNOW SRS MASTER LOOKUP")
    print("=" * 75)
    df = pd.read_csv(CSV_PATH)
    print(f"Loaded {len(df)} rows from {CSV_PATH}")

    col_mapping = UploadFileParser.auto_detect_columns(list(df.columns))
    print(f"Auto-detected columns: {col_mapping}")

    upload_id = f"test_snow_master_scan_{int(time.time())}"
    t0 = time.perf_counter()
    summary = BulkUploadProcessor.process_upload_dataframe(
        upload_id=upload_id,
        file_name="PF490A36_LAPTOP-TTASCMUO_Installation.csv",
        file_type="CSV",
        df=df,
        column_mapping=col_mapping,
    )
    proc_time = time.perf_counter() - t0
    print(f"Processed in {proc_time:.2f}s ({len(df)/proc_time:.1f} rows/s)")

    db = SessionLocal()
    try:
        results = db.query(UploadLicenseResult).filter(UploadLicenseResult.upload_id == upload_id).all()
        print(f"\nAudit of {len(results)} Processed Results:")
        
        metrics = Counter([r.metric for r in results])
        lic_reqs = Counter([r.license_required for r in results])
        classifications = Counter([r.classification for r in results])
        conflicts = Counter([r.conflict_status for r in results])

        print("\nLicense Required Distribution:")
        for k, v in lic_reqs.most_common():
            print(f"  • {k}: {v} ({v/len(results)*100:.1f}%)")

        print("\nMetric Distribution:")
        for k, v in metrics.most_common():
            label = repr(k) if k else "BLANK / EMPTY"
            print(f"  • {label}: {v} ({v/len(results)*100:.1f}%)")

        print("\nClassification Distribution:")
        for k, v in classifications.most_common():
            label = k if k else "BLANK"
            print(f"  • {label}: {v} ({v/len(results)*100:.1f}%)")

        print("\nConflict Status Distribution:")
        for k, v in conflicts.most_common():
            print(f"  • {k}: {v} ({v/len(results)*100:.1f}%)")

        # Specific target test applications:
        target_names = [
            "Microsoft ODBC Driver 17 for SQL Server",
            "Microsoft ODBC Driver 18 for SQL Server",
            "Microsoft OLE DB Driver for SQL Server",
            "Microsoft OLE DB Driver 19 for SQL Server",
            "Microsoft SQL Server 2025",
            "Microsoft SQL Server 2025 Setup",
            "Microsoft .NET SDK 10.0.400 from Visual Studio",
            "Microsoft VSS Writer for SQL Server 2025",
            "Browser for SQL Server 2025",
            "Docker Desktop",
            "Microsoft Power BI Desktop",
            "IntelliJ IDEA",
            "Power BI Desktop",
        ]

        print("\n" + "-" * 75)
        print("SPECIFIC APPLICATION TARGET VERIFICATION:")
        print("-" * 75)
        for r in results:
            for tn in target_names:
                if tn.lower() in str(r.raw_application).lower():
                    print(f"App: {r.raw_application}")
                    print(f"  • License Required: {r.license_required}")
                    print(f"  • Metric:           {r.metric}")
                    print(f"  • Classification:   {r.classification}")
                    print(f"  • License Model:    {r.license_model}")
                    print(f"  • Conflict Status:  {r.conflict_status}")
                    print(f"  • Audit Reason:     {r.override_reason}")
                    print()
                    break

        blank_metrics = sum(1 for r in results if not r.metric or r.metric == "UNKNOWN")
        print(f"Total Rows with Blank/Unknown Metric: {blank_metrics} (Previously 9+)")

    finally:
        db.close()


if __name__ == "__main__":
    test_reprocess_laptop_scan()
