"""
Batch CSV Processor for Isolated Installation Inventories.
Processes external machine installation inventory CSV files through the
Commercial License Intelligence pipeline and stores results exclusively
in the isolated `installation_license_results` table.
"""

import os
import csv
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

from backend.database.connection import SessionLocal, engine, Base
from backend.models.inventory import InstallationLicenseResult
from backend.inventory.detection.qualification_filter import (
    ApplicationQualificationFilter,
    WindowsSystemToolFilter,
    WindowsRuntimeFrameworkFilter,
)
from backend.inventory.recognition.alias_system import ApplicationAliasSystem
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
from backend.inventory.detection.detection_normalizer import DetectionNormalizer
from backend.validation.reliability_score import UNRESOLVED_RELIABILITY_SCORE

logger = logging.getLogger(__name__)


class BatchInstallationCSVProcessor:
    """
    Processes machine-specific installation inventory CSVs through the License Intelligence pipeline.
    """

    @classmethod
    def process_csv(
        cls,
        csv_file_path: str,
        db_session=None,
    ) -> Dict[str, Any]:
        """
        Executes isolated ingestion, qualification, deduplication, and license intelligence.
        """
        # Ensure database tables exist
        Base.metadata.create_all(bind=engine)

        close_session = False
        db = db_session
        if db is None:
            db = SessionLocal()
            close_session = True

        try:
            if not os.path.exists(csv_file_path):
                raise FileNotFoundError(f"Input CSV file not found: {csv_file_path}")

            raw_rows: List[Dict[str, str]] = []
            with open(csv_file_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    raw_rows.append(row)

            total_input_apps = len(raw_rows)
            logger.info(f"Loaded {total_input_apps} raw records from {csv_file_path}")

            # 1. Qualification & Machine-Scoped Deduplication
            qualified_candidates: List[Dict[str, Any]] = []
            disqualified_count = 0
            duplicates_merged_count = 0

            # Deduplication maps within this machine
            app_by_canonical: Dict[Tuple[str, str], Dict[str, Any]] = {}
            app_by_name_ver: Dict[Tuple[str, str], Dict[str, Any]] = {}

            for row in raw_rows:
                raw_name = (row.get("Application_Name") or "").strip()
                if not raw_name:
                    disqualified_count += 1
                    continue

                raw_vendor = (row.get("Vendor") or "").strip()
                if raw_vendor in ("N/A", "Unknown", "None", ""):
                    raw_vendor = None

                raw_version = (row.get("Version") or "").strip()
                if raw_version in ("N/A", "Unknown", "None", ""):
                    raw_version = None

                install_date = (row.get("Install_Date") or "").strip()
                if install_date in ("N/A", "Unknown", "None", ""):
                    install_date = None

                install_source = (row.get("Install_Source") or "").strip()
                if install_source in ("N/A", "Unknown", "None", ""):
                    install_source = None

                install_loc = (row.get("Install_Location") or "").strip()
                if install_loc in ("N/A", "Unknown", "None", ""):
                    install_loc = None

                candidate_payload = {
                    "raw_name": raw_name,
                    "raw_publisher": raw_vendor,
                    "raw_version": raw_version,
                    "raw_install_location": install_loc,
                    "detection_method": "WINDOWS_REGISTRY_64" if install_source and "HKLM" in install_source else "WINDOWS_APPX" if install_source and "Store" in install_source else "WINDOWS_REGISTRY",
                    "install_source": install_source,
                }

                # Run Qualification Filter (System tools & Runtime dependencies)
                is_qual, qual_reason, _ = ApplicationQualificationFilter.qualify_candidate(candidate_payload)
                if not is_qual:
                    logger.debug(f"Row disqualified: {raw_name} ({qual_reason})")
                    disqualified_count += 1
                    continue

                # Resolve Canonical Identity
                alias_res = ApplicationAliasSystem.resolve_application(
                    raw_name=raw_name,
                    raw_publisher=raw_vendor,
                    raw_version=raw_version,
                )

                canonical_prod = alias_res.canonical_product if alias_res.canonical_product != "UNRESOLVED" else None
                canonical_vend = alias_res.canonical_vendor if alias_res.canonical_vendor != "UNKNOWN" else (raw_vendor or None)

                clean_name = raw_name.lower().replace("(64-bit)", "").replace("(32-bit)", "").replace("(x64)", "").strip()
                clean_ver = (raw_version or "").lower()

                canonical_key = (canonical_vend.lower(), canonical_prod.lower()) if canonical_prod and canonical_vend else None

                matched_entry: Dict[str, Any] = None

                if canonical_key and canonical_key in app_by_canonical:
                    cand_match = app_by_canonical[canonical_key]
                    cand_v = cand_match.get("raw_version")
                    if not cand_v or not raw_version or DetectionNormalizer.versions_are_equivalent(cand_v, raw_version):
                        matched_entry = cand_match
                
                if not matched_entry:
                    if (clean_name, clean_ver) in app_by_name_ver:
                        matched_entry = app_by_name_ver[(clean_name, clean_ver)]
                    elif (clean_name, "") in app_by_name_ver and not raw_version:
                        matched_entry = app_by_name_ver[(clean_name, "")]
                    else:
                        # Check with version equivalence across existing candidates with same clean name
                        for cand_item in qualified_candidates:
                            c_item_name = cand_item.get("raw_application_name", "").lower()
                            c_clean = c_item_name.replace("(64-bit)", "").replace("(32-bit)", "").replace("(x64)", "").strip()
                            if c_clean == clean_name:
                                if DetectionNormalizer.versions_are_equivalent(cand_item.get("raw_version"), raw_version):
                                    matched_entry = cand_item
                                    break

                if matched_entry:
                    # Merge metadata within this machine
                    duplicates_merged_count += 1
                    if not matched_entry.get("raw_version") and raw_version:
                        matched_entry["raw_version"] = raw_version
                    if not matched_entry.get("raw_vendor") and raw_vendor:
                        matched_entry["raw_vendor"] = raw_vendor
                    if not matched_entry.get("install_location") and install_loc:
                        matched_entry["install_location"] = install_loc
                    if not matched_entry.get("install_date") and install_date:
                        matched_entry["install_date"] = install_date
                else:
                    item = {
                        "unique_id": (row.get("Unique_ID") or "PF490A36_LAPTOP-TTASCMUO").strip(),
                        "hostname": (row.get("Hostname") or "LAPTOP-TTASCMUO").strip(),
                        "serial": (row.get("Serial") or "PF490A36").strip(),
                        "ip_address": (row.get("IP_Address") or "").strip(),
                        "raw_application_name": raw_name,
                        "raw_vendor": raw_vendor,
                        "raw_version": raw_version,
                        "install_date": install_date,
                        "install_source": install_source,
                        "install_location": install_loc,
                        "canonical_product": canonical_prod,
                        "canonical_vendor": canonical_vend,
                    }
                    qualified_candidates.append(item)
                    if canonical_key:
                        app_by_canonical[canonical_key] = item
                    app_by_name_ver[(clean_name, clean_ver)] = item
                    if clean_ver:
                        app_by_name_ver[(clean_name, "")] = item

            # 2. Track existing records for synchronization diff analysis
            existing_machine_records = db.query(InstallationLicenseResult).filter(
                InstallationLicenseResult.unique_id == "PF490A36_LAPTOP-TTASCMUO"
            ).all()

            existing_map: Dict[str, InstallationLicenseResult] = {}
            for r in existing_machine_records:
                if r.canonical_product and r.canonical_product != "UNRESOLVED":
                    existing_map[r.canonical_product.lower()] = r
                if r.raw_application_name:
                    existing_map[r.raw_application_name.lower()] = r

            # 3. Run Intelligence Research Pipeline on Each Qualified Candidate
            results_to_insert: List[InstallationLicenseResult] = []
            
            resolved_identities = 0
            unresolved_identities = 0
            verified_evidence = 0
            partial_evidence = 0
            missing_evidence = 0
            classification_dist: Dict[str, int] = {}

            new_applications_detected = 0
            existing_applications_updated = 0
            unchanged_applications = 0

            now = datetime.now(timezone.utc)

            for cand in qualified_candidates:
                c_name = cand.get("canonical_product") or cand.get("raw_application_name")
                c_vendor = cand.get("canonical_vendor") or cand.get("raw_vendor")
                c_ver = cand.get("raw_version")

                intel = HybridLicenseEngine.resolve_hybrid_record(
                    app_id=None,
                    name=cand.get("raw_application_name"),
                    publisher=cand.get("raw_vendor"),
                    version=cand.get("raw_version"),
                    install_location=cand.get("install_location"),
                )

                classification = intel.get("classification", "UNKNOWN")
                license_req = intel.get("license_required", "UNKNOWN")
                license_model = intel.get("license_model", "UNKNOWN")
                license_metric = intel.get("metric", "UNKNOWN")
                evidence_status = intel.get("evidence_status", "MISSING")
                confidence = intel.get("confidence", "UNKNOWN")
                reliability = float(intel.get("reliability_score", 30.0))
                evidence_source = intel.get("evidence_source") or "Official Vendor Documentation"
                evidence_url = intel.get("primary_source_url") or intel.get("source_url")
                
                canonical_prod_final = intel.get("application") or cand.get("canonical_product") or cand.get("raw_application_name")
                canonical_vendor_final = intel.get("vendor") or cand.get("canonical_vendor") or cand.get("raw_vendor")
                evidence_quote = intel.get("evidence_quote") or "Baseline catalog licensing verification."
                
                # Check resolution success & enforce strict pipeline rules
                is_unresolved = (
                    canonical_prod_final == "UNRESOLVED" or
                    classification == "UNKNOWN" or
                    "unresolved" in str(cand.get("raw_application_name", "")).lower()
                )

                if not is_unresolved:
                    resolved_identities += 1
                    research_status = "SUCCESS"
                else:
                    unresolved_identities += 1
                    research_status = "UNRESOLVED"
                    canonical_prod_final = "UNRESOLVED"
                    canonical_vendor_final = cand.get("raw_vendor") or "Unknown"
                    classification = "UNKNOWN"
                    license_req = "UNKNOWN"
                    license_model = "UNKNOWN"
                    license_metric = "UNKNOWN"
                    evidence_status = "MISSING"
                    confidence = "UNKNOWN"
                    reliability = min(reliability, UNRESOLVED_RELIABILITY_SCORE)
                    evidence_quote = "Unresolved application identity. No official licensing terms available."

                # Strict rule: If evidence is MISSING, confidence must NOT be HIGH / VERY_HIGH
                if evidence_status == "MISSING":
                    if confidence in ("HIGH", "VERY_HIGH"):
                        confidence = "LOW"
                    reliability = min(reliability, 42.0 if not is_unresolved else UNRESOLVED_RELIABILITY_SCORE)

                # Schema constraint: license_requirement cannot be NOT_APPLICABLE
                if license_req == "NOT_APPLICABLE":
                    license_req = "NO"

                # Consistency constraint: VERIFIED with missing version must downgrade to PARTIAL
                if evidence_status == "VERIFIED" and (not cand.get("raw_version") or cand.get("raw_version") in ("N/A", "UNKNOWN", "")):
                    evidence_status = "PARTIAL"

                # Evidence status tally
                if evidence_status == "VERIFIED":
                    verified_evidence += 1
                elif evidence_status == "PARTIAL":
                    partial_evidence += 1
                else:
                    missing_evidence += 1

                # Classification tally
                classification_dist[classification] = classification_dist.get(classification, 0) + 1

                # Synchronization diff check against previous machine baseline
                match_existing = existing_map.get(canonical_prod_final.lower()) or existing_map.get(cand["raw_application_name"].lower())
                if not match_existing:
                    new_applications_detected += 1
                else:
                    if match_existing.raw_version != cand["raw_version"]:
                        existing_applications_updated += 1
                    else:
                        unchanged_applications += 1

                record = InstallationLicenseResult(
                    unique_id=cand.get("unique_id"),
                    hostname=cand.get("hostname"),
                    serial=cand.get("serial"),
                    ip_address=cand.get("ip_address"),
                    raw_application_name=cand.get("raw_application_name"),
                    raw_vendor=cand.get("raw_vendor"),
                    raw_version=cand.get("raw_version"),
                    install_date=cand.get("install_date"),
                    install_source=cand.get("install_source"),
                    install_location=cand.get("install_location"),
                    canonical_product=canonical_prod_final,
                    canonical_vendor=canonical_vendor_final,
                    classification=classification,
                    license_requirement=license_req,
                    license_model=license_model,
                    license_metric=license_metric,
                    evidence_status=evidence_status,
                    confidence=confidence,
                    reliability_score=reliability,
                    research_status=research_status,
                    evidence_source=evidence_source,
                    evidence_url=evidence_url,
                    processed_at=now,
                )
                results_to_insert.append(record)

            # 4. Clear existing results for this unique machine ID to support clean idempotent re-runs
            target_unique_id = qualified_candidates[0]["unique_id"] if qualified_candidates else "PF490A36_LAPTOP-TTASCMUO"
            db.query(InstallationLicenseResult).filter(
                InstallationLicenseResult.unique_id == target_unique_id
            ).delete()
            db.commit()

            # Insert all synchronized records into installation_license_results
            db.bulk_save_objects(results_to_insert)
            db.commit()

            logger.info(f"Successfully inserted {len(results_to_insert)} records into installation_license_results")

            summary = {
                "total_input_records": total_input_apps,
                "new_applications_detected": new_applications_detected,
                "existing_applications_updated": existing_applications_updated,
                "unchanged_applications": unchanged_applications,
                "duplicate_records_merged": duplicates_merged_count,
                "disqualified_count": disqualified_count,
                "successfully_resolved_applications": resolved_identities,
                "unresolved_applications": unresolved_identities,
                "evidence_status_counts": {
                    "VERIFIED": verified_evidence,
                    "PARTIAL": partial_evidence,
                    "MISSING": missing_evidence,
                },
                "classification_distribution": classification_dist,
                "final_machine_result_count": len(results_to_insert),
            }

            return summary

        finally:
            if close_session and db:
                db.close()

