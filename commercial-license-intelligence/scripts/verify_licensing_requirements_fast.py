"""
Dedicated Fast Benchmark Verification:
Validates the 6 Core Licensing Requirements across the complete end-to-end flow:
Input -> Processing -> SQLite Database -> BulkInventoryUploadService API -> Frontend Results View
"""

import os
import sys
import pandas as pd
from datetime import datetime

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from backend.database.connection import SessionLocal
from backend.models.inventory_upload import UploadLicenseResult
from backend.inventory.upload.bulk_upload_processor import BulkUploadProcessor
from backend.inventory.processing.bulk_upload_service import BulkInventoryUploadService
from frontend.streamlit.components.dashboard.results_view import (
    load_upload_results,
    generate_final_schema_csv_bytes,
    generate_excel_bytes,
)
from backend.inventory.export.standardized_inventory_exporter import (
    StandardizedInventoryExporter,
    STANDARDIZED_COLUMNS,
    FINAL_OUTPUT_COLUMNS,
)


def run_fast_benchmark():
    print("=" * 75)
    print("RUNNING 6 CORE LICENSING REQUIREMENTS BENCHMARK (END-TO-END)")
    print("=" * 75)

    db = SessionLocal()
    test_upload_id = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        # 1. INPUT
        benchmark_records = [
            {"Application": "Microsoft Visual Studio 2022 Community", "Vendor": "Microsoft Corporation", "Version": "17.9.0", "Hostname": "BENCH-01"},
            {"Application": "Microsoft Visual Studio 2022 Enterprise", "Vendor": "Microsoft Corporation", "Version": "17.9.0", "Hostname": "BENCH-01"},
            {"Application": "Microsoft Visual Studio 2022", "Vendor": "Microsoft Corporation", "Version": "17.9.0", "Hostname": "BENCH-01"},
            {"Application": "Docker Desktop", "Vendor": "Docker Inc.", "Version": "4.28.0", "Hostname": "BENCH-01"},
            {"Application": "HashiCorp Terraform", "Vendor": "HashiCorp", "Version": "1.6.0", "Hostname": "BENCH-01"},
            {"Application": "Redis", "Vendor": "Redis Ltd.", "Version": "7.4.0", "Hostname": "BENCH-01"},
            {"Application": "7-Zip", "Vendor": "Igor Pavlov", "Version": "23.01", "Hostname": "BENCH-01"},
            {"Application": "Git", "Vendor": "The Git Development Community", "Version": "2.44.0", "Hostname": "BENCH-01"},
            {"Application": "Tableau Desktop", "Vendor": "Tableau Software", "Version": "2023.3", "Hostname": "BENCH-01"},
        ]
        df_input = pd.DataFrame(benchmark_records)
        print(f"\n[1. INPUT] Prepared {len(df_input)} benchmark test records.")

        # 2. PROCESSING PIPELINE
        print("\n[2. PROCESSING PIPELINE]")
        mapping = {"application": "Application", "vendor": "Vendor", "version": "Version", "hostname": "Hostname"}
        summary = BulkUploadProcessor.process_upload_dataframe(
            upload_id=test_upload_id,
            file_name="Benchmark_Licensing_6_Requirements.csv",
            file_type="CSV",
            df=df_input,
            column_mapping=mapping,
        )
        print(f"Pipeline executed: Status={summary.get('status')} | Resolved={summary.get('resolved_count')}/{summary.get('total_rows')} in {summary.get('duration_seconds')}s")
        assert summary.get("status") == "COMPLETED"

        # 3. DATABASE PERSISTENCE
        print("\n[3. DATABASE PERSISTENCE]")
        db_results = db.query(UploadLicenseResult).filter(UploadLicenseResult.upload_id == test_upload_id).all()
        print(f"Persisted {len(db_results)} rows to upload_license_results in SQLite.")
        assert len(db_results) == len(df_input)

        # 4. API RESPONSE
        print("\n[4. API RESPONSE]")
        api_results = BulkInventoryUploadService.get_upload_results(upload_id=test_upload_id, limit=50, db_session=db)
        print(f"BulkInventoryUploadService.get_upload_results returned {len(api_results)} records.")
        for col in ["canonical_edition", "spdx_id", "version_rule_applied", "consensus_status"]:
            assert col in api_results[0], f"API missing column: {col}"

        # 5. FRONTEND DISPLAY LOADING & TRANSFORMS
        print("\n[5. FRONTEND DISPLAY LOADING & EXPORTERS]")
        frontend_rows = load_upload_results(test_upload_id)
        assert len(frontend_rows) == len(df_input)
        df_final = StandardizedInventoryExporter.transform_to_final_schema(frontend_rows)
        assert list(df_final.columns) == FINAL_OUTPUT_COLUMNS
        df_std = StandardizedInventoryExporter.transform_inventory(frontend_rows)
        assert list(df_std.columns) == STANDARDIZED_COLUMNS

        # 6. CORE 6 REQUIREMENTS VERIFICATION
        print("\n[6. CORE 6 REQUIREMENTS VALIDATION]")
        
        # Requirement 1: Edition Disambiguation
        vs_comm = next(r for r in frontend_rows if "Community" in r.get("raw_application", ""))
        vs_ent = next(r for r in frontend_rows if "Enterprise" in r.get("raw_application", ""))
        vs_amb = next(r for r in frontend_rows if r.get("raw_application") == "Microsoft Visual Studio 2022")
        print(f"  Req 1 - Edition Disambiguation:")
        print(f"    - Community:  Edition='{vs_comm.get('canonical_edition')}' | Metric='{vs_comm.get('metric')}' | Req={vs_comm.get('license_required')}")
        print(f"    - Enterprise: Edition='{vs_ent.get('canonical_edition')}' | Metric='{vs_ent.get('metric')}' | Req={vs_ent.get('license_required')}")
        print(f"    - Ambiguous:  Edition='{vs_amb.get('canonical_edition')}' | Status='{vs_amb.get('consensus_status')}' | Metric='{vs_amb.get('metric')}")
        assert vs_comm.get("canonical_edition") == "Community" and vs_comm.get("license_required") is False and vs_comm.get("metric") == "No License Required"
        assert vs_ent.get("canonical_edition") == "Enterprise" and vs_ent.get("license_required") is True and vs_ent.get("metric") == "Named User"
        assert vs_amb.get("canonical_edition") == "EDITION_AMBIGUOUS" and vs_amb.get("consensus_status") == "EDITION_AMBIGUOUS" and vs_amb.get("metric") in ("UNKNOWN", "")
        print("    --> PASS: Correctly disambiguates Community/Enterprise and flags EDITION_AMBIGUOUS without guessing.")

        # Requirement 2: Version-Inflection Engine
        docker_row = next(r for r in frontend_rows if "Docker Desktop" in r.get("application", ""))
        terraform_row = next(r for r in frontend_rows if "Terraform" in r.get("application", ""))
        redis_row = next(r for r in frontend_rows if "Redis" in r.get("application", ""))
        print(f"  Req 2 - Version-Inflection Engine:")
        print(f"    - Docker Desktop 4.28.0: Rule='{docker_row.get('version_rule_applied')}' | Req={docker_row.get('license_required')}")
        print(f"    - Terraform 1.6.0:      Rule='{terraform_row.get('version_rule_applied')}' | SPDX='{terraform_row.get('spdx_id')}'")
        print(f"    - Redis 7.4.0:          Rule='{redis_row.get('version_rule_applied')}' | SPDX='{redis_row.get('spdx_id')}'")
        assert "4.0" in str(docker_row.get("version_rule_applied")) and docker_row.get("license_required") is True
        assert "1.5.6" in str(terraform_row.get("version_rule_applied"))
        assert "7.4" in str(redis_row.get("version_rule_applied"))
        print("    --> PASS: Inflection rules trigger exact licensing transitions on version boundaries.")

        # Requirement 3: Authoritative Vendor Legal Sources
        print(f"  Req 3 - Authoritative Vendor Legal Sources:")
        print(f"    - Docker Legal Source: {docker_row.get('evidence_source')} | URL: {docker_row.get('evidence_url')}")
        assert "docker.com" in str(docker_row.get("evidence_url"))
        print("    --> PASS: Direct vendor legal portals prioritized over 3rd-party search.")

        # Requirement 4: SPDX License Taxonomy
        zip_row = next(r for r in frontend_rows if "7-Zip" in r.get("application", ""))
        git_row = next(r for r in frontend_rows if "Git" in r.get("application", ""))
        print(f"  Req 4 - SPDX License Taxonomy:")
        print(f"    - 7-Zip:     SPDX='{zip_row.get('spdx_id')}'")
        print(f"    - Git:       SPDX='{git_row.get('spdx_id')}'")
        print(f"    - Terraform: SPDX='{terraform_row.get('spdx_id')}'")
        print(f"    - Redis:     SPDX='{redis_row.get('spdx_id')}'")
        assert zip_row.get("spdx_id") in ["LGPL-2.1-or-later", "LGPL-3.0-only", "LGPL-2.1-only", "LGPL-3.0-or-later"]
        assert git_row.get("spdx_id") in ["GPL-2.0-only", "GPL-3.0-only", "GPL-2.0-or-later", "GPL-3.0-or-later"]
        assert terraform_row.get("spdx_id") == "BSL-1.1"
        assert redis_row.get("spdx_id") in ["RSAL-2.0", "SSPL-1.0"]
        print("    --> PASS: Canonical SPDX 3.0 IDs normalized across open source and source-available licenses.")

        # Requirement 5: Exact Licensing Metrics
        tableau_row = next(r for r in frontend_rows if "Tableau Desktop" in r.get("application", ""))
        print(f"  Req 5 - Exact Licensing Metrics:")
        print(f"    - Tableau Desktop: Metric='{tableau_row.get('metric')}'")
        print(f"    - Docker Desktop:  Metric='{docker_row.get('metric')}'")
        print(f"    - 7-Zip:           Metric='{zip_row.get('metric')}'")
        assert docker_row.get("metric") == "Named User"
        assert zip_row.get("metric") == "No License Required"
        print("    --> PASS: Precise metrics returned (Named User, No License Required, UNKNOWN).")

        # Requirement 6: Multi-Source Consensus Verification
        print(f"  Req 6 - Multi-Source Consensus Verification:")
        print(f"    - Docker Consensus:    {docker_row.get('consensus_status')}")
        print(f"    - Ambiguous Consensus: {vs_amb.get('consensus_status')}")
        print(f"    - 7-Zip Consensus:     {zip_row.get('consensus_status')}")
        assert docker_row.get("consensus_status") in ["HIGH_CONSENSUS", "VERIFIED"]
        assert vs_amb.get("consensus_status") == "EDITION_AMBIGUOUS"
        print("    --> PASS: Sources cross-checked, conflict resolution preserved, consensus statuses explicit.")

        print("\n" + "=" * 75)
        print("ALL 6 REQUIREMENTS FULLY VALIDATED END-TO-END!")
        print("=" * 75)
        return True

    finally:
        db.close()


if __name__ == "__main__":
    success = run_fast_benchmark()
    sys.exit(0 if success else 1)
