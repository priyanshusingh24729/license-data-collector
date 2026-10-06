"""
End-to-End Pipeline Verification Script:
Input -> Processing -> Database -> API Response -> Frontend Display

Validates that the entire licensing intelligence pipeline executes end-to-end and produces reliable results:
- WinGet manifest integration and matching
- Source-priority enrichment and conflict handling
- Sitemap/robots discovery, llms.txt, PDF harvesting
- Evidence extraction & lifecycle EOL/EOS
- License validation & confidence scoring
- SQLite persistence (UploadLicenseResult with 6 new columns)
- FastAPI / BulkInventoryUploadService API response
- Frontend results_view data loading, 10-column Final Schema, and 17-column Standardized Inventory
"""

import os
import sys
import json
import sqlite3
import pandas as pd
from datetime import datetime, timezone

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from backend.database.connection import SessionLocal
from backend.models.inventory_upload import InventoryUpload, InventoryUploadRow, UploadLicenseResult
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


def run_e2e_verification():
    print("=" * 70)
    print("RUNNING END-TO-END LICENSING INTELLIGENCE PIPELINE VERIFICATION")
    print("=" * 70)

    db = SessionLocal()
    test_upload_id = f"e2e_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        # 1. INPUT: Load sample inventory rows
        print("\n[STEP 1: INPUT]")
        # Find existing upload rows from previous scan
        recent_upload = db.query(InventoryUpload).filter(InventoryUpload.total_rows > 50).order_by(InventoryUpload.id.desc()).first()
        benchmark_records = [
            {"Application": "Microsoft Visual Studio 2022 Community", "Vendor": "Microsoft Corporation", "Version": "17.9.0", "Hostname": "DEV-BENCH"},
            {"Application": "Microsoft Visual Studio 2022 Enterprise", "Vendor": "Microsoft Corporation", "Version": "17.9.0", "Hostname": "DEV-BENCH"},
            {"Application": "Microsoft Visual Studio 2022", "Vendor": "Microsoft Corporation", "Version": "17.9.0", "Hostname": "DEV-BENCH"},
            {"Application": "Docker Desktop", "Vendor": "Docker Inc.", "Version": "4.28.0", "Hostname": "DEV-BENCH"},
            {"Application": "HashiCorp Terraform", "Vendor": "HashiCorp", "Version": "1.6.0", "Hostname": "DEV-BENCH"},
            {"Application": "Redis", "Vendor": "Redis Ltd.", "Version": "7.4.0", "Hostname": "DEV-BENCH"},
            {"Application": "7-Zip", "Vendor": "Igor Pavlov", "Version": "23.01", "Hostname": "DEV-BENCH"},
            {"Application": "Git", "Vendor": "The Git Development Community", "Version": "2.44.0", "Hostname": "DEV-BENCH"},
            {"Application": "Tableau Desktop", "Vendor": "Tableau Software", "Version": "2023.3", "Hostname": "DEV-BENCH"},
        ]

        if recent_upload:
            source_id = recent_upload.upload_id
            raw_rows = db.query(InventoryUploadRow).filter(InventoryUploadRow.upload_id == source_id).limit(25).all()
            print(f"Loaded {len(raw_rows)} inventory rows from source upload: {source_id} ({recent_upload.file_name})")
            input_records = [
                {
                    "Application": r.raw_application,
                    "Vendor": r.raw_vendor,
                    "Version": r.raw_version,
                    "Hostname": r.hostname or "DESKTOP-TEST",
                }
                for r in raw_rows
            ]
            # Add benchmark items to ensure 6 requirements are always validated
            input_records.extend(benchmark_records)
        else:
            print("No source upload found with >50 rows, creating standard sample inventory...")
            input_records = benchmark_records

        df_input = pd.DataFrame(input_records)
        print(f"Input DataFrame created with {len(df_input)} records.")

        # 2. PROCESSING: Ingestion -> Normalization -> Recognition -> WinGet -> Web -> Lifecycle -> Validation
        print("\n[STEP 2: PROCESSING PIPELINE]")
        mapping = {"application": "Application", "vendor": "Vendor", "version": "Version", "hostname": "Hostname"}
        summary = BulkUploadProcessor.process_upload_dataframe(
            upload_id=test_upload_id,
            file_name="E2E_Test_Sample_Inventory.csv",
            file_type="CSV",
            df=df_input,
            column_mapping=mapping,
        )
        print(f"Pipeline executed successfully!")
        print(f"  - Status: {summary.get('status')}")
        print(f"  - Total Rows: {summary.get('total_rows')}")
        print(f"  - Resolved: {summary.get('resolved_count')}")
        print(f"  - WinGet Enriched: {summary.get('winget_enriched_count')}")
        print(f"  - Duration: {summary.get('duration_seconds')}s")

        assert summary.get("status") == "COMPLETED", "Pipeline execution status is not COMPLETED"

        # 3. DATABASE: Verify SQLite Persistence and new columns
        print("\n[STEP 3: DATABASE VERIFICATION]")
        db_results = db.query(UploadLicenseResult).filter(UploadLicenseResult.upload_id == test_upload_id).all()
        print(f"Queried database for upload_id={test_upload_id}: {len(db_results)} rows found.")
        assert len(db_results) == len(df_input), f"Expected {len(df_input)} results in DB, got {len(db_results)}"

        winget_matched_in_db = 0
        installer_urls_in_db = 0
        sha256_in_db = 0
        eol_eos_in_db = 0
        spdx_ids_in_db = 0
        consensus_statuses_in_db = 0

        for r in db_results:
            if getattr(r, "winget_package_id", None):
                winget_matched_in_db += 1
            if getattr(r, "installer_url", None):
                installer_urls_in_db += 1
            if getattr(r, "installer_sha256", None):
                sha256_in_db += 1
            if getattr(r, "is_end_of_life", None) is not None or getattr(r, "is_end_of_support", None) is not None:
                eol_eos_in_db += 1
            if getattr(r, "spdx_id", None):
                spdx_ids_in_db += 1
            if getattr(r, "consensus_status", None):
                consensus_statuses_in_db += 1

        print(f"Database Column Verification:")
        print(f"  - WinGet Package IDs: {winget_matched_in_db} / {len(db_results)}")
        print(f"  - Installer URLs: {installer_urls_in_db} / {len(db_results)}")
        print(f"  - Installer SHA-256 Hashes: {sha256_in_db} / {len(db_results)}")
        print(f"  - Lifecycle EOL/EOS Evaluated: {eol_eos_in_db} / {len(db_results)}")
        print(f"  - SPDX IDs: {spdx_ids_in_db} / {len(db_results)}")
        print(f"  - Consensus Statuses: {consensus_statuses_in_db} / {len(db_results)}")
        assert winget_matched_in_db > 0, "No WinGet package IDs persisted to DB"
        assert sha256_in_db > 0, "No installer SHA-256 hashes persisted to DB"
        assert consensus_statuses_in_db > 0, "No consensus_status persisted to DB"

        # 4. API RESPONSE: Verify FastAPI BulkInventoryUploadService.get_upload_results
        print("\n[STEP 4: API RESPONSE VERIFICATION]")
        api_results = BulkInventoryUploadService.get_upload_results(upload_id=test_upload_id, limit=5000, db_session=db)
        print(f"API get_upload_results returned {len(api_results)} records.")
        assert len(api_results) == len(df_input), f"API returned {len(api_results)}, expected {len(df_input)}"

        sample_api_rec = next((x for x in api_results if x.get("winget_package_id")), api_results[0])
        print(f"Sample API Record for '{sample_api_rec.get('application')}':")
        required_api_keys = [
            "application", "vendor", "version", "classification", "license_required",
            "license_model", "metric", "confidence", "reliability", "evidence_status",
            "evidence_source", "evidence_url", "installer_url", "installer_sha256",
            "winget_package_id", "conflict_status", "override_reason", "is_end_of_life",
            "is_end_of_support", "resolution_engine_version",
            "canonical_edition", "spdx_id", "version_rule_applied", "consensus_status"
        ]
        missing_keys = [k for k in required_api_keys if k not in sample_api_rec]
        assert not missing_keys, f"API response is missing required keys: {missing_keys}"

        print(f"  - Package ID: {sample_api_rec.get('winget_package_id')}")
        print(f"  - Installer URL: {sample_api_rec.get('installer_url')}")
        print(f"  - SHA-256: {sample_api_rec.get('installer_sha256')}")
        print(f"  - Canonical Edition: {sample_api_rec.get('canonical_edition')}")
        print(f"  - SPDX ID: {sample_api_rec.get('spdx_id')}")
        print(f"  - Version Rule: {sample_api_rec.get('version_rule_applied')}")
        print(f"  - Consensus Status: {sample_api_rec.get('consensus_status')}")
        print(f"  - Conflict Status: {sample_api_rec.get('conflict_status')}")
        print(f"  - License Required: {sample_api_rec.get('license_required')}")
        print(f"  - License Model: {sample_api_rec.get('license_model')}")
        print(f"  - Metric: {sample_api_rec.get('metric')}")
        print(f"  - Classification: {sample_api_rec.get('classification')}")
        print(f"  - Evidence Source: {sample_api_rec.get('evidence_source')}")
        print(f"  - Reliability: {sample_api_rec.get('reliability')}")

        # 5. FRONTEND DISPLAY: Verify results_view loading & Table Exporters
        print("\n[STEP 5: FRONTEND DISPLAY & EXPORTERS VERIFICATION]")
        frontend_rows = load_upload_results(test_upload_id)
        print(f"frontend load_upload_results loaded {len(frontend_rows)} rows.")
        assert len(frontend_rows) == len(df_input), f"Frontend loaded {len(frontend_rows)}, expected {len(df_input)}"

        # Verify all new fields in frontend rows
        sample_front_rec = next((x for x in frontend_rows if x.get("winget_package_id")), frontend_rows[0])
        assert "winget_package_id" in sample_front_rec, "winget_package_id missing in frontend rows"
        assert "installer_url" in sample_front_rec, "installer_url missing in frontend rows"
        assert "installer_sha256" in sample_front_rec, "installer_sha256 missing in frontend rows"
        assert "conflict_status" in sample_front_rec, "conflict_status missing in frontend rows"
        assert "evidence_source" in sample_front_rec, "evidence_source missing in frontend rows"
        assert "evidence_quote" in sample_front_rec, "evidence_quote missing in frontend rows"
        assert "canonical_edition" in sample_front_rec, "canonical_edition missing in frontend rows"
        assert "spdx_id" in sample_front_rec, "spdx_id missing in frontend rows"
        assert "version_rule_applied" in sample_front_rec, "version_rule_applied missing in frontend rows"
        assert "consensus_status" in sample_front_rec, "consensus_status missing in frontend rows"

        # Verify 10-Column Final Schema transformation
        df_final = StandardizedInventoryExporter.transform_to_final_schema(frontend_rows)
        assert list(df_final.columns) == FINAL_OUTPUT_COLUMNS, f"Final schema columns mismatch: {list(df_final.columns)}"
        print(f"Final Schema (10 columns) validated: {len(df_final)} rows.")

        # Verify 17-Column Standardized Inventory transformation
        df_std = StandardizedInventoryExporter.transform_inventory(frontend_rows)
        assert list(df_std.columns) == STANDARDIZED_COLUMNS, f"Standardized schema columns mismatch: {list(df_std.columns)}"
        print(f"Standardized Inventory (17 columns) validated: {len(df_std)} rows.")

        # 6. CORE 6 LICENSING REQUIREMENTS BENCHMARK VERIFICATION
        print("\n[STEP 6: 6 LICENSING REQUIREMENTS VERIFICATION ON BENCHMARK ROWS]")
        
        # 1. Edition Disambiguation
        vs_comm = next(r for r in frontend_rows if "Community" in r.get("raw_application", "") or "Community" in r.get("application", ""))
        vs_ent = next(r for r in frontend_rows if "Enterprise" in r.get("raw_application", "") or "Enterprise" in r.get("application", ""))
        vs_amb = next(r for r in frontend_rows if r.get("raw_application") == "Microsoft Visual Studio 2022")

        print(f"  [Req 1: Edition Disambiguation]")
        print(f"    - Community Edition: {vs_comm.get('canonical_edition')} | Metric: {vs_comm.get('metric')} | Required: {vs_comm.get('license_required')}")
        print(f"    - Enterprise Edition: {vs_ent.get('canonical_edition')} | Metric: {vs_ent.get('metric')} | Required: {vs_ent.get('license_required')}")
        print(f"    - Bare Studio (Ambiguous): {vs_amb.get('canonical_edition')} | Status: {vs_amb.get('consensus_status')} | Metric: {vs_amb.get('metric')}")
        assert vs_comm.get("canonical_edition") == "Community", f"Expected Community, got {vs_comm.get('canonical_edition')}"
        assert vs_comm.get("license_required") is False, "Visual Studio Community should not require commercial license"
        assert vs_ent.get("canonical_edition") == "Enterprise", f"Expected Enterprise, got {vs_ent.get('canonical_edition')}"
        assert vs_ent.get("license_required") is True, "Visual Studio Enterprise requires license"
        assert vs_amb.get("canonical_edition") == "EDITION_AMBIGUOUS", f"Expected EDITION_AMBIGUOUS, got {vs_amb.get('canonical_edition')}"
        assert vs_amb.get("metric") in ["UNKNOWN", ""], f"Expected UNKNOWN metric for ambiguous edition, got {vs_amb.get('metric')}"

        # 2. Version Inflection Engine
        docker_row = next(r for r in frontend_rows if "Docker Desktop" in r.get("Application", "") or "Docker Desktop" in r.get("raw_application", ""))
        terraform_row = next(r for r in frontend_rows if "Terraform" in r.get("Application", "") or "Terraform" in r.get("raw_application", ""))
        redis_row = next(r for r in frontend_rows if r.get("raw_application") == "Redis" or r.get("Application") == "Redis")

        print(f"  [Req 2: Version-Inflection Engine]")
        print(f"    - Docker Desktop 4.28.0: Rule='{docker_row.get('version_rule_applied')}' | Metric={docker_row.get('metric')} | Req={docker_row.get('license_required')}")
        print(f"    - Terraform 1.6.0: Rule='{terraform_row.get('version_rule_applied')}' | SPDX={terraform_row.get('spdx_id')}")
        print(f"    - Redis 7.4.0: Rule='{redis_row.get('version_rule_applied')}' | SPDX={redis_row.get('spdx_id')}")
        assert "4.0" in str(docker_row.get("version_rule_applied")), "Docker Desktop version rule not applied"
        assert docker_row.get("license_required") is True, "Docker Desktop 4.x should require license for commercial/enterprise"
        assert "1.5.6" in str(terraform_row.get("version_rule_applied")), "Terraform version rule not applied"
        assert "7.4" in str(redis_row.get("version_rule_applied")), "Redis version rule not applied"

        # 3. Authoritative Vendor Legal Sources
        print(f"  [Req 3: Authoritative Vendor Legal Sources]")
        print(f"    - Docker Legal Source: {docker_row.get('evidence_source')} | URL: {docker_row.get('evidence_url')}")
        assert "docker.com" in str(docker_row.get("evidence_url")), f"Authoritative Docker legal URL missing: {docker_row.get('evidence_url')}"

        # 4. SPDX License Taxonomy
        zip_row = next(r for r in frontend_rows if "7-Zip" in r.get("raw_application", "") or "7-Zip" in r.get("Application", ""))
        git_row = next(r for r in frontend_rows if r.get("raw_application") == "Git" or r.get("Application") == "Git")
        print(f"  [Req 4: SPDX License Taxonomy]")
        print(f"    - 7-Zip SPDX ID: {zip_row.get('spdx_id')}")
        print(f"    - Git SPDX ID: {git_row.get('spdx_id')}")
        print(f"    - Terraform SPDX ID: {terraform_row.get('spdx_id')}")
        print(f"    - Redis SPDX ID: {redis_row.get('spdx_id')}")
        assert zip_row.get("spdx_id") in ["LGPL-2.1-or-later", "LGPL-3.0-only", "LGPL-2.1-only", "LGPL-3.0-or-later"], f"Unexpected 7-Zip SPDX: {zip_row.get('spdx_id')}"
        assert git_row.get("spdx_id") in ["GPL-2.0-only", "GPL-3.0-only", "GPL-2.0-or-later", "GPL-3.0-or-later"], f"Unexpected Git SPDX: {git_row.get('spdx_id')}"
        assert terraform_row.get("spdx_id") == "BSL-1.1", f"Expected BSL-1.1, got {terraform_row.get('spdx_id')}"
        assert redis_row.get("spdx_id") in ["RSAL-2.0", "SSPL-1.0"], f"Unexpected Redis SPDX: {redis_row.get('spdx_id')}"

        # 5. Exact Licensing Metrics
        print(f"  [Req 5: Exact Licensing Metrics]")
        tableau_row = next(r for r in frontend_rows if "Tableau Desktop" in r.get("application", ""))
        print(f"    - Tableau Desktop Metric: {tableau_row.get('metric')}")
        print(f"    - Docker Desktop Metric: {docker_row.get('metric')}")
        print(f"    - 7-Zip Metric: {zip_row.get('metric')}")
        assert tableau_row.get("metric") in ["Named User", "User"], f"Tableau metric expected Named User, got {tableau_row.get('metric')}"
        assert docker_row.get("metric") == "Named User", f"Docker Desktop metric expected Named User, got {docker_row.get('metric')}"
        assert zip_row.get("metric") == "No License Required", f"7-Zip metric expected No License Required, got {zip_row.get('metric')}"

        # 6. Multi-Source Consensus Verification
        print(f"  [Req 6: Multi-Source Consensus Verification]")
        print(f"    - Docker Consensus Status: {docker_row.get('consensus_status')}")
        print(f"    - Visual Studio Ambiguous Status: {vs_amb.get('consensus_status')}")
        print(f"    - 7-Zip Consensus Status: {zip_row.get('consensus_status')}")
        assert docker_row.get("consensus_status") in ["HIGH_CONSENSUS", "VERIFIED"], f"Expected consensus, got {docker_row.get('consensus_status')}"
        assert vs_amb.get("consensus_status") == "EDITION_AMBIGUOUS", f"Expected EDITION_AMBIGUOUS, got {vs_amb.get('consensus_status')}"

        # Verify exports
        final_csv = generate_final_schema_csv_bytes(frontend_rows)
        excel_bytes = generate_excel_bytes(frontend_rows)
        assert len(final_csv) > 100, "Final Schema CSV generation failed or empty"
        assert len(excel_bytes) > 1000, "Standardized Excel generation failed or empty"
        print(f"Generated Final Schema CSV ({len(final_csv)} bytes) and Excel ({len(excel_bytes)} bytes) successfully.")

        print("\n" + "=" * 70)
        print("ALL END-TO-END VERIFICATION CHECKS PASSED PERFECTLY!")
        print("Input -> Processing -> Database -> API Response -> Frontend Display")
        print("=" * 70)
        return True

    finally:
        db.close()


if __name__ == "__main__":
    success = run_e2e_verification()
    sys.exit(0 if success else 1)
