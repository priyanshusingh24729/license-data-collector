"""
Scalable Bulk Inventory Processor with Canonical Product Intelligence Caching.
Separates Application Intelligence from Machine Installation Records.
Supports 89 to 19,000+ raw rows efficiently with batch database operations.
"""

import re
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Callable
import pandas as pd
from sqlalchemy import text

from backend.database.connection import SessionLocal
from backend.models.inventory_upload import (
    InventoryUpload,
    InventoryUploadRow,
    UploadLicenseResult,
)
from backend.inventory.detection.detection_normalizer import DetectionNormalizer
from backend.inventory.detection.qualification_filter import ApplicationQualificationFilter
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
from backend.inventory.recognition.resolved_product_service import ResolvedProductService
from backend.inventory.recognition.lifecycle_service import LifecycleService
from backend.validation.searxng_evidence_validator import SearxngEvidenceValidator
from backend.validation.reliability_score import UNRESOLVED_RELIABILITY_SCORE
from backend.validation.license_validation_layer import LicenseValidationLayer
from backend.validation.consensus_engine import ConsensusVerificationEngine
from backend.config.settings import get_settings
from backend.sources.winget.winget_manifest_service import WinGetManifestService

logger = logging.getLogger(__name__)

EDITION_BUCKETS = {
    "express": "EXPRESS",
    "community": "COMMUNITY",
    "enterprise": "ENTERPRISE",
    "professional": "PRO",
    "standard": "STANDARD",
    "developer": "DEVELOPER",
    "datacenter": "DATACENTER",
    "workgroup": "WORKGROUP",
    "business": "BUSINESS",
}


def extract_version_bucket(app_name: str, version: Optional[str] = None) -> str:
    """
    Detects if software edition differences affect licensing (e.g. SQL Server Express vs Enterprise).
    Point releases (e.g. 124.0.1 vs 124.0.2) map to the same bucket ('ANY') to avoid duplicate web searches.
    """
    text_to_check = f"{app_name or ''} {version or ''}".lower()
    for kw, bucket in EDITION_BUCKETS.items():
        if re.search(rf"\b{kw}\b", text_to_check):
            return bucket
    return "ANY"


class BulkUploadProcessor:
    """
    High-performance, isolated bulk software inventory processor.
    """

    @classmethod
    def process_upload_dataframe(
        cls,
        upload_id: str,
        file_name: str,
        file_type: str,
        df: pd.DataFrame,
        column_mapping: Dict[str, Optional[str]],
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Executes end-to-end bulk upload processing:
        1. Ingests raw rows into inventory_upload_rows
        2. Groups unique application tuples
        3. Resolves each unique application once via HybridLicenseEngine
        4. Applies verified intelligence to all matching machine installations
        5. Bulk saves into upload_license_results
        """
        start_time = time.time()
        db = SessionLocal()

        try:
            # 1. Clean & Prepare DataFrame
            df = df.fillna("")
            df.columns = [str(c).strip() for c in df.columns]
            total_rows = len(df)

            app_col = column_mapping.get("application") or (df.columns[0] if len(df.columns) > 0 else "Application")
            vendor_col = column_mapping.get("vendor")
            ver_col = column_mapping.get("version")
            host_col = column_mapping.get("hostname")
            loc_col = column_mapping.get("install_location")
            src_col = column_mapping.get("install_source")

            # Always clear previous rows and results for this upload_id to prevent duplicates on re-run
            db.query(InventoryUploadRow).filter(InventoryUploadRow.upload_id == upload_id).delete()
            db.query(UploadLicenseResult).filter(UploadLicenseResult.upload_id == upload_id).delete()
            db.commit()

            upload_rec = db.query(InventoryUpload).filter(InventoryUpload.upload_id == upload_id).first()
            if not upload_rec:
                upload_rec = InventoryUpload(
                    upload_id=upload_id,
                    file_name=file_name,
                    file_type=file_type,
                    total_rows=total_rows,
                    status="PROCESSING",
                    column_mapping=column_mapping,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(upload_rec)
                db.commit()
                db.refresh(upload_rec)
            else:
                upload_rec.status = "PROCESSING"
                upload_rec.total_rows = total_rows
                upload_rec.column_mapping = column_mapping
                db.commit()

            logger.info(f"[{upload_id}] Starting processing of {total_rows} rows from '{file_name}'")

            # 3. Ingest Raw Rows & Build Installation List
            raw_installations: List[Dict[str, Any]] = []
            upload_row_objects: List[InventoryUploadRow] = []
            unique_hostnames = set()

            for idx, row in df.iterrows():
                raw_app = str(row.get(app_col, "")).strip()
                if not raw_app:
                    raw_app = "Unknown Application"

                raw_vendor = str(row.get(vendor_col, "")).strip() if vendor_col and vendor_col in row else None
                if raw_vendor in ("N/A", "Unknown", "None", "", "nan", "null"):
                    raw_vendor = None

                raw_ver = str(row.get(ver_col, "")).strip() if ver_col and ver_col in row else None
                if raw_ver in ("N/A", "Unknown", "None", "", "nan", "null"):
                    raw_ver = None

                host = str(row.get(host_col, "")).strip() if host_col and host_col in row else None
                if host in ("N/A", "Unknown", "None", "", "nan", "null"):
                    host = None
                if host:
                    unique_hostnames.add(host)

                loc = str(row.get(loc_col, "")).strip() if loc_col and loc_col in row else None
                if loc in ("N/A", "Unknown", "None", "", "nan", "null"):
                    loc = None

                src = str(row.get(src_col, "")).strip() if src_col and src_col in row else None

                item_dict = {
                    "row_index": idx + 1,
                    "hostname": host,
                    "raw_application": raw_app,
                    "raw_vendor": raw_vendor,
                    "raw_version": raw_ver,
                    "install_location": loc,
                    "install_source": src,
                    "raw_data": row.to_dict(),
                }
                raw_installations.append(item_dict)

                upload_row_objects.append(
                    InventoryUploadRow(
                        upload_id=upload_id,
                        row_index=idx + 1,
                        hostname=host,
                        raw_application=raw_app,
                        raw_vendor=raw_vendor,
                        raw_version=raw_ver,
                        raw_data=row.to_dict(),
                    )
                )

            # Bulk save raw rows in chunks
            CHUNK_SIZE = 1000
            for i in range(0, len(upload_row_objects), CHUNK_SIZE):
                db.bulk_save_objects(upload_row_objects[i : i + CHUNK_SIZE])
            db.commit()

            # 4. Group Unique Applications (Decoupled Product Caching Key)
            # Resolves at the (normalized_name, normalized_vendor, version_bucket, qual_cat) level
            # Point releases share the same resolution while setup components are isolated from standalone engines
            unique_product_groups: Dict[Tuple[str, Optional[str], str, str], List[int]] = {}

            for inst in raw_installations:
                norm_app = DetectionNormalizer.normalize_name(
                    inst["raw_application"],
                    install_location=inst["install_location"]
                )
                norm_pub = DetectionNormalizer.normalize_publisher(
                    inst["raw_vendor"],
                    raw_name=inst["raw_application"]
                )
                v_bucket = extract_version_bucket(inst["raw_application"], inst["raw_version"])
                
                cand = {
                    "raw_name": inst["raw_application"],
                    "raw_publisher": inst["raw_vendor"],
                    "install_location": inst["install_location"],
                    "install_source": inst.get("install_source"),
                    "raw_version": inst["raw_version"],
                }
                _, _, qual_cat = ApplicationQualificationFilter.qualify_candidate(cand)

                group_key = (
                    norm_app.lower(),
                    norm_pub.lower() if norm_pub else None,
                    v_bucket,
                    qual_cat,
                )

                if group_key not in unique_product_groups:
                    unique_product_groups[group_key] = []
                unique_product_groups[group_key].append(inst["row_index"])

            unique_app_count = len(unique_product_groups)
            upload_rec.unique_applications = unique_app_count
            upload_rec.unique_machines = len(unique_hostnames)
            db.commit()

            logger.info(f"[{upload_id}] Collapsed {total_rows} records into {unique_app_count} distinct product groups.")

            # 5. Resolve Product Intelligence Once Per Unique Product
            intelligence_cache: Dict[Tuple[str, Optional[str], str, str], Dict[str, Any]] = {}
            validator = SearxngEvidenceValidator()
            resolved_count = 0
            unresolved_count = 0
            cache_hits = 0
            new_researched = 0
            winget_enriched_count = 0
            winget_conflicts_count = 0
            web_discovery_count = 0

            group_idx = 0
            for group_key, row_indices in unique_product_groups.items():
                group_idx += 1
                sample_inst = raw_installations[row_indices[0] - 1]
                v_bucket = group_key[2]

                # Step 5A: Check Global Cross-Upload Persistent Cache (resolved_products_cache)
                cached_rec = ResolvedProductService.get_cached_resolution(
                    name=sample_inst["raw_application"],
                    publisher=sample_inst["raw_vendor"],
                    version_bucket=v_bucket,
                    db=db,
                )

                qual_cat = group_key[3]
                # Defensive check: A shared component / setup bootstrapper must not be resolved
                # by a cached parent commercial database engine or standalone application record
                if qual_cat == "SHARED_COMPONENT" and cached_rec:
                    if cached_rec.get("classification") != "COMMERCIAL_COMPONENT":
                        cached_rec = None
                elif qual_cat == "STANDALONE_APPLICATION" and cached_rec:
                    if cached_rec.get("classification") == "COMMERCIAL_COMPONENT":
                        cached_rec = None

                if cached_rec:
                    h_rec = dict(cached_rec)
                    h_rec["version"] = sample_inst["raw_version"] or h_rec.get("version") or "N/A"
                    cache_hits += 1

                    # Enrich cached record with WinGet installer & license metadata if not yet augmented
                    if getattr(get_settings(), "ENABLE_WINGET_INTEGRATION", True) and not h_rec.get("installer_sha256"):
                        try:
                            winget_service = WinGetManifestService()
                            winget_manifest = winget_service.resolve_application(
                                app_name=sample_inst["raw_application"],
                                publisher=sample_inst["raw_vendor"],
                                version=sample_inst["raw_version"]
                            )
                            if winget_manifest:
                                has_catalog = bool(h_rec.get("override_type") in (
                                    "EVIDENCE_CONFIRMED", "CATALOG_RECOGNITION", "METRIC_CORRECTION", "MICROSOFT_ADAPTER_VERIFIED"
                                ))
                                h_rec, winget_logs = winget_service.apply_winget_enrichment(
                                    record=h_rec,
                                    manifest=winget_manifest,
                                    has_catalog_ground_truth=has_catalog
                                )
                                winget_enriched_count += len(row_indices)
                                for wlog in winget_logs:
                                    logger.info(f"[{upload_id}] {wlog}")
                                    if "[Conflict]" in wlog:
                                        winget_conflicts_count += 1
                        except Exception as wg_err:
                            logger.debug(f"[{upload_id}] WinGet cached enrichment notice: {wg_err}")
                else:
                    # Step 5B: Resolve via hardened HybridLicenseEngine
                    h_rec = HybridLicenseEngine.resolve_hybrid_record(
                        app_id=None,
                        name=sample_inst["raw_application"],
                        publisher=sample_inst["raw_vendor"],
                        version=sample_inst["raw_version"],
                        raw_package_name=sample_inst["raw_application"],
                        install_location=sample_inst["install_location"],
                        install_source=sample_inst.get("install_source"),
                        version_bucket=v_bucket,
                    )

                    # Step 5B.1: WinGet Manifest Integration (High-Confidence Ground Truth & Provenance)
                    if getattr(get_settings(), "ENABLE_WINGET_INTEGRATION", True):
                        try:
                            winget_service = WinGetManifestService()
                            winget_manifest = winget_service.resolve_application(
                                app_name=sample_inst["raw_application"],
                                publisher=sample_inst["raw_vendor"],
                                version=sample_inst["raw_version"]
                            )
                            if winget_manifest:
                                has_catalog = bool(h_rec.get("override_type") in (
                                    "EVIDENCE_CONFIRMED", "CATALOG_RECOGNITION", "METRIC_CORRECTION", "MICROSOFT_ADAPTER_VERIFIED"
                                ))
                                h_rec, winget_logs = winget_service.apply_winget_enrichment(
                                    record=h_rec,
                                    manifest=winget_manifest,
                                    has_catalog_ground_truth=has_catalog
                                )
                                winget_enriched_count += len(row_indices)
                                for wlog in winget_logs:
                                    logger.info(f"[{upload_id}] {wlog}")
                                    if "[Conflict]" in wlog:
                                        winget_conflicts_count += 1
                        except Exception as wg_err:
                            logger.warning(f"[{upload_id}] WinGet resolution notice for {sample_inst['raw_application']}: {wg_err}")

                    # Step 5C: Validate & enrich via SearXNG/YaCy ONLY for genuine standalone apps lacking evidence
                    qual_cat = h_rec.get("qualification_category")
                    is_infra_or_system = qual_cat in (
                        "OS_SYSTEM_COMPONENT", "RUNTIME_FRAMEWORK", "SHARED_COMPONENT",
                        "INSTALLER_INFRASTRUCTURE", "LINUX_SYSTEM_PACKAGE",
                        "MACOS_SYSTEM_COMPONENT", "WEB_SHORTCUT/PWA", "WEB_SHORTCUT_OR_PWA"
                    ) or h_rec.get("classification") in ("OS_BUNDLED", "OEM_OR_BUNDLED", "LINUX_SYSTEM_PACKAGE", "MACOS_SYSTEM_COMPONENT", "WEB_SHORTCUT/PWA", "WEB_SHORTCUT_OR_PWA", "COMMERCIAL_COMPONENT")

                    # Fast bypass: Skip external internet search for internal utilities, OEM drivers, or empty vendor noise
                    raw_app_str = (sample_inst.get("raw_application") or "").strip()
                    raw_vend_str = (sample_inst.get("raw_vendor") or "").strip()
                    eff_vend = h_rec.get("vendor") or raw_vend_str
                    has_no_vendor = not eff_vend or eff_vend.upper() in ("UNKNOWN", "NONE", "N/A", "")

                    INTERNAL_HINTS = (
                        "driver", "oem", "branding", "chameleon", "patch", "hotfix", "kb",
                        "service pack", "update for", "redistributable", "support assistant",
                        "container", "vantage", "chipset", "firmware", "touchpad", "synaptics"
                    )
                    is_internal_util = (has_no_vendor and any(h in raw_app_str.lower() for h in INTERNAL_HINTS)) or len(raw_app_str) <= 3

                    if not is_infra_or_system and not is_internal_util and (not h_rec.get("source_url") or h_rec.get("classification") == "UNKNOWN"):
                        validator.validate_and_enrich(
                            app_name=h_rec.get("application") or sample_inst["raw_application"],
                            vendor=h_rec.get("vendor") or sample_inst["raw_vendor"],
                            version=sample_inst["raw_version"],
                            record=h_rec,
                        )
                        if h_rec.get("evidence_url"):
                            new_researched += 1
                            web_discovery_count += len(row_indices)

                    # Clean up generic root URLs that do not provide deep verified proof
                    ev_url = h_rec.get("source_url") or h_rec.get("primary_source_url") or h_rec.get("evidence_url") or ""
                    if ev_url.rstrip("/") in ("https://www.microsoft.com", "https://support.microsoft.com", "https://packages.ubuntu.com"):
                        if h_rec.get("classification") in ("OEM_OR_BUNDLED", "OS_BUNDLED", "FREEWARE", "COMMERCIAL_COMPONENT"):
                            h_rec["evidence_url"] = ""
                            h_rec["source_url"] = ""
                            h_rec["primary_source_url"] = ""

                    # Step 5D: Persist verified resolution into Global Cache (never search again!)
                    if h_rec.get("classification") != "UNKNOWN":
                        ev_src = h_rec.get("evidence_source") or ("WINGET" if h_rec.get("source_type") == "WINGET" else ("SEARXNG" if new_researched > 0 else (h_rec.get("override_type") or "HYBRID_ENGINE")))
                        ResolvedProductService.upsert_resolution(
                            record=h_rec,
                            evidence_source=ev_src,
                            raw_name=sample_inst["raw_application"],
                            raw_vendor=sample_inst["raw_vendor"],
                            version_bucket=v_bucket,
                            db=db,
                        )

                is_resolved = bool(h_rec.get("classification") != "UNKNOWN" and h_rec.get("evidence_status") != "MISSING")
                
                # Check if it was resolved from baseline, catalog, or deterministic identity engines (if not already counted from cache)
                if not h_rec.get("is_cached"):
                    if h_rec.get("override_type") in ("EVIDENCE_CONFIRMED", "MICROSOFT_ADAPTER_VERIFIED", "IDENTITY_CORRECTION", "CATALOG_RECOGNITION", "DRIVER_EXCLUSION", "OS_UPDATE_EXCLUSION", "LINUX_SYSTEM_PACKAGE", "APPLE_IDENTITY_RESOLVER"):
                        cache_hits += 1
                    elif is_resolved and new_researched == 0:
                        cache_hits += 1

                if is_resolved:
                    resolved_count += len(row_indices)
                else:
                    unresolved_count += len(row_indices)

                intelligence_cache[group_key] = h_rec

                # Update progress periodically
                if group_idx % 5 == 0 or group_idx == unique_app_count:
                    processed_so_far = sum(len(unique_product_groups[k]) for k in list(unique_product_groups.keys())[:group_idx])
                    upload_rec.processed_rows = processed_so_far
                    upload_rec.resolved_count = resolved_count
                    upload_rec.unresolved_count = unresolved_count
                    upload_rec.cache_hits = cache_hits
                    upload_rec.new_researched = new_researched
                    db.commit()

                    if progress_callback:
                        progress_callback({
                            "upload_id": upload_id,
                            "status": "PROCESSING",
                            "total_rows": total_rows,
                            "processed_rows": processed_so_far,
                            "unique_applications": unique_app_count,
                            "resolved_count": resolved_count,
                            "unresolved_count": unresolved_count,
                            "cache_hits": cache_hits,
                            "new_researched": new_researched,
                            "progress_percent": int((processed_so_far / total_rows) * 100) if total_rows > 0 else 100,
                        })

            # 6. Build Final License Results for All Installations
            results_to_insert: List[UploadLicenseResult] = []

            for inst in raw_installations:
                norm_app = DetectionNormalizer.normalize_name(
                    inst["raw_application"],
                    install_location=inst["install_location"]
                )
                norm_pub = DetectionNormalizer.normalize_publisher(
                    inst["raw_vendor"],
                    raw_name=inst["raw_application"]
                )
                v_bucket = extract_version_bucket(inst["raw_application"], inst["raw_version"])
                
                cand = {
                    "raw_name": inst["raw_application"],
                    "raw_publisher": inst["raw_vendor"],
                    "install_location": inst["install_location"],
                    "install_source": inst.get("install_source"),
                    "raw_version": inst["raw_version"],
                }
                _, _, qual_cat = ApplicationQualificationFilter.qualify_candidate(cand)

                group_key = (
                    norm_app.lower(),
                    norm_pub.lower() if norm_pub else None,
                    v_bucket,
                    qual_cat,
                )

                h_rec = intelligence_cache.get(group_key)
                if not h_rec:
                    # Fallback
                    h_rec = {
                        "application": norm_app,
                        "vendor": norm_pub or "UNKNOWN",
                        "version": inst["raw_version"] or "N/A",
                        "classification": None,
                        "availability": None,
                        "license_required": "YES",
                        "license_model": None,
                        "metric": None,
                        "confidence": "UNKNOWN",
                        "reliability_score": UNRESOLVED_RELIABILITY_SCORE,
                        "reliability_str": f"{UNRESOLVED_RELIABILITY_SCORE:.0f}%",
                        "evidence_status": "MISSING",
                        "evidence_quote": None,
                        "source_url": None,
                    }

                # Evaluate version-aware lifecycle (IsEndOfLife, IsEndOfSupport)
                life_override = LifecycleService.evaluate_lifecycle(
                    app_name=h_rec.get("application") or inst["raw_application"],
                    version=inst["raw_version"] or h_rec.get("version"),
                    publisher=h_rec.get("vendor") or inst["raw_vendor"],
                )

                # ---------------------------------------------------------
                # Snow Authoritative Baseline Extraction
                # ---------------------------------------------------------
                raw_row = inst.get("raw_data") or {}
                snow_no_lic_raw = raw_row.get("NoLicenseRequired")
                if snow_no_lic_raw is None:
                    snow_no_lic_raw = raw_row.get("no_license_required")
                snow_metric_raw = raw_row.get("Metric")
                if snow_metric_raw is None:
                    snow_metric_raw = raw_row.get("metric")
                snow_eol_raw = raw_row.get("IsEndOfLife")
                if snow_eol_raw is None:
                    snow_eol_raw = raw_row.get("is_end_of_life")
                snow_eos_raw = raw_row.get("IsEndOfSupport")
                if snow_eos_raw is None:
                    snow_eos_raw = raw_row.get("is_end_of_support")

                snow_baseline_active = (
                    snow_no_lic_raw is not None 
                    and str(snow_no_lic_raw).strip() in ("0", "1")
                )

                # If raw upload lacks Snow baseline headers (e.g. laptop scan or generic inventory),
                # perform metadata lookup against the 907k Snow SRS master database for App_ID and Normalized_Application
                snow_master_match = None
                if not snow_baseline_active:
                    from backend.inventory.recognition.snow_srs_service import SnowSRSMasterService
                    snow_master_match = SnowSRSMasterService.lookup(
                        raw_name=inst["raw_application"],
                        vendor=inst["raw_vendor"],
                        version=inst["raw_version"],
                        os_name=raw_row.get("Operating_System") or raw_row.get("OS") or "Windows",
                        ostype=raw_row.get("OSType"),
                    )
                    if snow_master_match:
                        # Enrich raw_row with authentic Snow metadata for UI and export preservation
                        # Note: External master database lookup does NOT constitute an authoritative customer baseline override.
                        raw_row["App_ID"] = snow_master_match.app_id
                        raw_row["Normalized_Application"] = snow_master_match.normalized_application
                        if raw_row.get("IsEndOfLife") is None and snow_master_match.is_end_of_life is not None:
                            raw_row["IsEndOfLife"] = snow_master_match.is_end_of_life
                        if raw_row.get("IsEndOfSupport") is None and snow_master_match.is_end_of_support is not None:
                            raw_row["IsEndOfSupport"] = snow_master_match.is_end_of_support
                        if snow_eol_raw is None and snow_master_match.is_end_of_life is not None:
                            snow_eol_raw = snow_master_match.is_end_of_life
                        if snow_eos_raw is None and snow_master_match.is_end_of_support is not None:
                            snow_eos_raw = snow_master_match.is_end_of_support
                        if (snow_metric_raw is None or str(snow_metric_raw).strip() in ("", "None", "UNKNOWN", "nan")) and snow_master_match.metric:
                            snow_metric_raw = snow_master_match.metric
                            raw_row["Metric"] = snow_master_match.metric

                snow_baseline_dict = None
                if snow_baseline_active:
                    snow_baseline_dict = {
                        "NoLicenseRequired": str(snow_no_lic_raw).strip(),
                        "Metric": str(snow_metric_raw).strip() if snow_metric_raw is not None else None,
                        "IsEndOfLife": snow_eol_raw,
                        "IsEndOfSupport": snow_eos_raw,
                    }

                # Multi-source consensus synthesis (Edition Disambiguation, Version Inflection, Legal Portal, WinGet, Catalog)
                consensus_res = ConsensusVerificationEngine.verify_and_synthesize(
                    raw_name=inst["raw_application"],
                    raw_vendor=inst["raw_vendor"],
                    raw_version=inst["raw_version"],
                    catalog_record=h_rec,
                    winget_manifest=None,
                    install_location=inst["install_location"],
                    snow_baseline=snow_baseline_dict,
                )

                # Validate and sanitize all intelligence fields
                v_cand = {
                    "Application Name": consensus_res.canonical_product or h_rec.get("application") or inst["raw_application"],
                    "Version": inst["raw_version"] or h_rec.get("version"),
                    "OS": "Windows",
                    "Classification": consensus_res.classification,
                    "License Required": consensus_res.license_required,
                    "License Model": consensus_res.license_model,
                    "Metric": consensus_res.metric,
                    "Evidence URL": consensus_res.evidence_url or h_rec.get("source_url") or h_rec.get("primary_source_url") or h_rec.get("evidence_url"),
                }
                validated = LicenseValidationLayer.validate_and_sanitize(
                    v_cand,
                    lifecycle_override=life_override,
                )

                # ---------------------------------------------------------
                # License Intelligence Decision & Customer-Grade SAM Logic
                # ---------------------------------------------------------
                intel_lic_req = validated["License Required"]
                intel_metric = validated["Metric"]
                intel_classification = validated["Classification"] or ""

                final_lic_req = intel_lic_req
                final_metric = intel_metric if intel_metric and intel_metric != "UNKNOWN" else None

                # Lifecycle Arbitration:
                # Priority 1: Baseline SRS dump metadata (customer baseline or 907k Snow SRS Master match)
                if snow_eol_raw is not None and str(snow_eol_raw).strip() in ("0", "1"):
                    final_eol = int(str(snow_eol_raw).strip())
                else:
                    final_eol = life_override[0]

                if snow_eos_raw is not None and str(snow_eos_raw).strip() in ("0", "1"):
                    final_eos = int(str(snow_eos_raw).strip())
                else:
                    final_eos = life_override[1]

                final_conflict_status = consensus_res.conflict_status or h_rec.get("conflict_status") or "VERIFIED"
                final_consensus_status = consensus_res.consensus_status or "VERIFIED"
                final_override_reason = consensus_res.resolution_notes or h_rec.get("override_reason")

                # Client-Side / SAM Business Logic Rules:
                # 1. Non-commercial applications (FREEWARE, OPEN_SOURCE, OS_BUNDLED, OEM_OR_BUNDLED, FREE, COMMERCIAL_COMPONENT)
                #    NEVER require a license from a SAM POV.
                if intel_classification in ("OS_BUNDLED", "FREEWARE", "OPEN_SOURCE", "OEM_OR_BUNDLED", "FREE", "COMMERCIAL_COMPONENT"):
                    final_lic_req = "NO"
                    final_metric = "No license required"
                # 2. Commercial / Freemium applications (COMMERCIAL, FREE_AND_PAID, TRIAL, PAID, or final_lic_req == YES)
                #    DO require a commercial license / subscription for enterprise organizational use.
                elif final_lic_req == "YES" or intel_classification in ("COMMERCIAL", "FREE_AND_PAID", "TRIAL", "PAID"):
                    final_lic_req = "YES"
                    # Priority 1: If baseline SRS master database has an authentic commercial metric (e.g. Installations, Devices, Processor Cores)
                    s_metric_clean = str(snow_metric_raw).strip() if snow_metric_raw is not None else ""
                    if s_metric_clean and s_metric_clean.lower() not in ("no license required", "unknown", "null", "none", "nan", ""):
                        final_metric = s_metric_clean
                    elif not final_metric or final_metric in ("UNKNOWN", "No license required", "No License Required"):
                        final_metric = consensus_res.metric if consensus_res.metric and consensus_res.metric not in ("UNKNOWN", "No License Required") else "Users"

                if snow_baseline_active:
                    snow_lic_req = "YES" if str(snow_no_lic_raw).strip() == "0" else "NO"
                    has_discrepancy = (
                        consensus_res.conflict_status == "DISCREPANCY_FLAGGED"
                        or (
                            consensus_res.license_required in ("YES", "NO")
                            and consensus_res.consensus_status not in ("INSUFFICIENT_EVIDENCE", "UNKNOWN")
                            and consensus_res.classification not in ("UNKNOWN", "", None)
                            and consensus_res.license_required != snow_lic_req
                        )
                    )

                    if has_discrepancy:
                        final_conflict_status = "DISCREPANCY_FLAGGED"
                        final_consensus_status = "REVIEW_RECOMMENDED"
                        snow_label = "No License Required (1)" if snow_lic_req == "NO" else "License Required (0)"
                        intel_label = consensus_res.license_required if consensus_res.license_required in ("YES", "NO") else intel_lic_req

                        if intel_classification in ("OS_BUNDLED", "FREEWARE", "OPEN_SOURCE", "OEM_OR_BUNDLED", "FREE", "COMMERCIAL_COMPONENT"):
                            final_lic_req = "NO"
                            final_metric = "No license required"
                            final_override_reason = (
                                f"AUDIT DISCREPANCY: Snow baseline indicates {snow_label}, "
                                f"but official vendor evidence confirms {intel_classification} (Free / No License Required). "
                                f"Corrected to NO for customer audit; flagged for review."
                            )
                        elif intel_classification == "COMMERCIAL" and snow_lic_req == "NO":
                            # Customer explicitly provided baseline indicating NO for commercial app (e.g. Docker Desktop baseline test)
                            final_lic_req = snow_lic_req
                            final_override_reason = (
                                f"AUDIT DISCREPANCY: Snow baseline indicates {snow_label}, "
                                f"but official vendor evidence indicates {intel_label}. "
                                f"Snow baseline preserved; flagged for auditor review."
                            )
                        else:
                            final_lic_req = "YES"
                            final_override_reason = (
                                f"AUDIT DISCREPANCY: Snow baseline indicates {snow_label} (client binary), "
                                f"but enterprise commercial use requires an active subscription / commercial license ({final_metric}). "
                                f"Customer POV enforced as YES; flagged for review."
                            )
                    elif consensus_res.conflict_status == "CONFIRMED" and consensus_res.consensus_status in ("HIGH_CONSENSUS", "VERIFIED", "SINGLE_SOURCE_VERIFIED"):
                        final_conflict_status = "CONFIRMED"
                        final_consensus_status = "VERIFIED"
                        final_override_reason = (
                            f"Confirmed by independent evidence: Snow baseline ({snow_lic_req}) "
                            f"agrees with official vendor intelligence."
                        )
                    else:
                        final_conflict_status = "CONFIRMED"
                        final_consensus_status = consensus_res.consensus_status if consensus_res.consensus_status != "REVIEW_RECOMMENDED" else "VERIFIED"
                        final_override_reason = "Snow baseline preserved."

                    # Metric Arbitration:
                    s_metric = str(snow_metric_raw).strip() if snow_metric_raw is not None else ""
                    # Protect Users metric: If verified intelligence or user-scoped installation detected Users,
                    # do not let legacy Terminal Server 'Devices' metric overwrite it
                    if intel_metric in ("Users", "Named User") and s_metric.lower() == "devices":
                        final_metric = "Users"
                    elif s_metric and s_metric.upper() not in ("NULL", "NONE", "") and not (intel_classification in ("OS_BUNDLED", "FREEWARE", "OPEN_SOURCE", "OEM_OR_BUNDLED", "FREE", "COMMERCIAL_COMPONENT") and s_metric.lower() in ("installations", "devices")):
                        final_metric = s_metric
                    elif final_lic_req == "NO":
                        final_metric = "No license required"
                    else:
                        if (
                            intel_metric and intel_metric not in ("UNKNOWN", "", "No License Required")
                            and consensus_res.consensus_status in ("HIGH_CONSENSUS", "VERIFIED", "SINGLE_SOURCE_VERIFIED")
                            and consensus_res.classification not in ("UNKNOWN", "", None)
                        ):
                            final_metric = intel_metric
                            if final_conflict_status != "DISCREPANCY_FLAGGED":
                                final_conflict_status = "ENRICHED"
                            final_override_reason = (
                                f"Enriched: Snow Metric was NULL. Populated verified metric '{final_metric}' "
                                f"from {consensus_res.evidence_source or 'intelligence'}."
                            )

                    # Lifecycle Arbitration:
                    if snow_eol_raw is not None and str(snow_eol_raw).strip() in ("0", "1"):
                        final_eol = int(str(snow_eol_raw).strip())
                    if snow_eos_raw is not None and str(snow_eos_raw).strip() in ("0", "1"):
                        final_eos = int(str(snow_eos_raw).strip())

                # Synchronize raw_row metadata for UI and export consistency
                if final_lic_req == "YES":
                    raw_row["NoLicenseRequired"] = 0
                elif final_lic_req == "NO":
                    raw_row["NoLicenseRequired"] = 1
                raw_row["Metric"] = final_metric
                raw_row["IsEndOfLife"] = final_eol
                raw_row["IsEndOfSupport"] = final_eos

                # Harmonize classification and license model with authoritative Snow baseline
                final_classification = validated["Classification"] or ""
                if not final_classification or final_classification == "UNKNOWN":
                    if snow_baseline_active:
                        if final_lic_req == "NO":
                            final_classification = "OPEN_SOURCE" if consensus_res.spdx_id and consensus_res.spdx_id != "UNKNOWN" else "FREEWARE"
                        else:
                            final_classification = "COMMERCIAL"
                    else:
                        if consensus_res.classification and consensus_res.classification != "UNKNOWN":
                            final_classification = consensus_res.classification
                        elif final_lic_req == "NO":
                            final_classification = "FREEWARE"
                        elif final_lic_req == "YES":
                            final_classification = "COMMERCIAL"

                final_license_model = validated["License Model"] or ""
                if not final_license_model or final_license_model.upper() in ("UNKNOWN", "NONE", ""):
                    if final_lic_req == "NO":
                        if final_classification in ("FREEWARE", "OS_BUNDLED", "OEM_OR_BUNDLED"):
                            final_license_model = "Freeware" if final_classification == "FREEWARE" else "No License Required"
                        elif final_classification == "OPEN_SOURCE":
                            final_license_model = "Free / Open Source"
                        else:
                            final_license_model = "No License Required"
                    else:
                        if final_metric == "Installations":
                            final_license_model = "Commercial — Per Installation"
                        elif final_metric == "Devices":
                            final_license_model = "Commercial — Per Device"
                        elif final_metric == "Processor Cores":
                            final_license_model = "Commercial — Per Core"
                        elif final_metric and str(final_metric).strip() not in ("UNKNOWN", "None", "", "Users"):
                            final_license_model = f"Commercial — Per {final_metric}"
                        else:
                            final_license_model = "Commercial — Subscription"
                elif final_lic_req == "YES" and final_license_model in ("Commercial — Subscription", "Commercial — Per Seat Subscription", "Unknown", ""):
                    if final_metric == "Installations":
                        final_license_model = "Commercial — Per Installation"
                    elif final_metric == "Devices":
                        final_license_model = "Commercial — Per Device"
                    elif final_metric == "Processor Cores":
                        final_license_model = "Commercial — Per Core"

                proc_result = "SUCCESS" if final_classification and final_classification != "UNKNOWN" else "UNRESOLVED"

                final_ev_src = consensus_res.evidence_source or h_rec.get("evidence_source", "GLOBAL_CACHE" if h_rec.get("is_cached") else "PIPELINE")
                # Official source priority: Never treat SEARXNG/search-engine as the evidence source itself
                if final_ev_src and str(final_ev_src).upper() in ("SEARXNG", "DEVSEARCH", "SEARCH_ENGINE", "SEARCH"):
                    ev_url_val = validated.get("Evidence URL") or consensus_res.evidence_url or h_rec.get("source_url")
                    if ev_url_val:
                        try:
                            from urllib.parse import urlparse
                            netloc = urlparse(ev_url_val).netloc.lower().split(":")[0]
                            if netloc.startswith("www."):
                                netloc = netloc[4:]
                            v_name = consensus_res.canonical_vendor or h_rec.get("vendor") or ""
                            if v_name and v_name.lower() in netloc:
                                final_ev_src = f"Official {v_name} Documentation"
                            else:
                                final_ev_src = f"Official Documentation ({netloc})"
                        except Exception:
                            final_ev_src = "Official Vendor Documentation"
                    else:
                        final_ev_src = "Official Vendor Documentation"

                final_quote = consensus_res.evidence_quote or h_rec.get("evidence_quote")
                if h_rec.get("installer_sha256"):
                    sha_tag = f"[WinGet Verified] SHA256: {h_rec.get('installer_sha256')} | Installer: {h_rec.get('installer_url')}"
                    final_quote = f"{final_quote} | {sha_tag}" if final_quote else sha_tag
                    if "WINGET" not in str(final_ev_src):
                        final_ev_src = f"{final_ev_src}+WINGET"

                # Enrich dual-use rights for customer-facing evidence (Outlook, OneDrive, Teams, Power BI, etc.)
                DUAL_USE_TERMS = {
                    "outlook for windows": "Personal use: Free | Commercial / Work & School use: Requires eligible Microsoft 365 license",
                    "microsoft onedrive": "Personal use: Free (5 GB) | Commercial / Work use: Requires eligible Microsoft 365 license or commercial OneDrive plan",
                    "microsoft onenote": "Personal use: Free | Commercial / Work use: Requires eligible Microsoft 365 license",
                    "microsoft teams": "Personal use: Free personal messaging | Commercial / Work use: Requires eligible Microsoft 365 or Teams commercial license",
                    "microsoft whiteboard": "Personal use: Free personal Microsoft account | Commercial / Work use: Requires eligible Microsoft 365 commercial subscription",
                    "todos": "Personal use: Free personal Microsoft account | Commercial / Work use: Requires eligible Microsoft 365 license",
                    "microsoft to do": "Personal use: Free personal Microsoft account | Commercial / Work use: Requires eligible Microsoft 365 license",
                    "power bi desktop": "Personal use: Free local authoring | Commercial / Work use: Requires eligible Microsoft 365 or Power BI Pro license",
                    "chatgpt": "Personal use: Free tier | Commercial use: Requires ChatGPT Team or Enterprise subscription",
                    "spotify music": "Personal use: Free ad-supported | Commercial use: Requires commercial license (personal subscription excludes public broadcast)",
                    "copilot": "Personal use: Free in-browser/Windows | Commercial / Work use: Requires Microsoft 365 Copilot commercial add-on license",
                    "microsoft 365 copilot": "Personal use: Free in-browser/Windows | Commercial / Work use: Requires Microsoft 365 Copilot commercial add-on license",
                    "clipchamp": "Personal use: Free basic editing | Commercial / Work use: Requires Microsoft 365 commercial subscription or Clipchamp Premium",
                }

                raw_clean_key = DetectionNormalizer.normalize_name(inst["raw_application"]).lower()
                canon_clean_key = (validated.get("Application Name") or "").lower()
                matched_dual_term = DUAL_USE_TERMS.get(raw_clean_key) or DUAL_USE_TERMS.get(canon_clean_key)
                if not matched_dual_term:
                    for k, v in DUAL_USE_TERMS.items():
                        if k in raw_clean_key or k in canon_clean_key:
                            matched_dual_term = v
                            break

                if matched_dual_term:
                    if final_quote:
                        if "Personal use:" not in final_quote:
                            final_quote = f"{final_quote} | [Usage Rights] {matched_dual_term}"
                    else:
                        final_quote = f"[Usage Rights] {matched_dual_term}"

                res_obj = UploadLicenseResult(
                    upload_id=upload_id,
                    row_index=inst["row_index"],
                    hostname=inst["hostname"],
                    raw_application=inst["raw_application"],
                    raw_vendor=inst["raw_vendor"],
                    raw_version=inst["raw_version"],
                    canonical_product=validated["Application Name"],
                    canonical_vendor=consensus_res.canonical_vendor or h_rec.get("vendor") or DetectionNormalizer.normalize_publisher(inst["raw_vendor"], raw_name=inst["raw_application"]),
                    canonical_edition=consensus_res.canonical_edition,
                    version=inst["raw_version"] or h_rec.get("version") or "N/A",
                    classification=final_classification,
                    availability=h_rec.get("availability") or "",
                    license_required=final_lic_req,
                    license_model=final_license_model,
                    metric=final_metric,
                    license_metric=final_metric,
                    spdx_id=consensus_res.spdx_id,
                    version_rule_applied=consensus_res.version_rule_applied,
                    confidence=consensus_res.confidence or h_rec.get("confidence") or "UNKNOWN",
                    reliability_score=consensus_res.reliability_score if consensus_res.reliability_score is not None else h_rec.get("reliability_score", 0.0),
                    reliability_str=f"{int(consensus_res.reliability_score or 0)}%",
                    evidence_status=h_rec.get("evidence_status") or "MISSING",
                    evidence_source=final_ev_src,
                    evidence_url=validated["Evidence URL"] or "",
                    evidence_quote=final_quote,
                    installer_url=h_rec.get("installer_url"),
                    installer_sha256=h_rec.get("installer_sha256"),
                    winget_package_id=h_rec.get("winget_package_id"),
                    is_end_of_life=final_eol,
                    is_end_of_support=final_eos,
                    conflict_status=final_conflict_status,
                    consensus_status=final_consensus_status,
                    override_reason=final_override_reason,
                    resolution_engine_version="v1.2.0",
                    research_status="COMPLETED",
                    processing_result=proc_result,
                    created_at=datetime.now(timezone.utc),
                )
                results_to_insert.append(res_obj)

            # Bulk save results in chunks
            for i in range(0, len(results_to_insert), CHUNK_SIZE):
                db.bulk_save_objects(results_to_insert[i : i + CHUNK_SIZE])
            db.commit()

            # 7. Finalize Upload Status
            upload_rec.status = "COMPLETED"
            upload_rec.processed_rows = total_rows
            upload_rec.resolved_count = resolved_count
            upload_rec.unresolved_count = unresolved_count
            upload_rec.cache_hits = cache_hits
            upload_rec.new_researched = new_researched
            upload_rec.completed_at = datetime.now(timezone.utc)
            db.commit()

            duration = time.time() - start_time
            logger.info(f"[{upload_id}] Successfully processed {total_rows} records ({resolved_count} resolved, {unresolved_count} unresolved) in {duration:.2f}s.")

            final_summary = {
                "upload_id": upload_id,
                "status": "COMPLETED",
                "total_rows": total_rows,
                "processed_rows": total_rows,
                "unique_applications": unique_app_count,
                "unique_machines": len(unique_hostnames),
                "resolved_count": resolved_count,
                "unresolved_count": unresolved_count,
                "cache_hits": cache_hits,
                "new_researched": new_researched,
                "winget_enriched_count": winget_enriched_count,
                "winget_conflicts_count": winget_conflicts_count,
                "web_discovery_count": web_discovery_count,
                "duration_seconds": round(duration, 2),
            }

            if progress_callback:
                progress_callback(final_summary)

            return final_summary

        except Exception as e:
            logger.exception(f"[{upload_id}] Bulk upload processing failed: {e}")
            if upload_rec:
                upload_rec.status = "FAILED"
                upload_rec.error_message = str(e)
                db.commit()
            if progress_callback:
                progress_callback({
                    "upload_id": upload_id,
                    "status": "FAILED",
                    "error": str(e),
                })
            raise
        finally:
            db.close()
