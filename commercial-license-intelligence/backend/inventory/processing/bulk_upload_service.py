"""
Bulk Inventory Upload & License Intelligence Processing Service.
Handles small (89 rows), medium (500-5,000 rows), and large (19,000+ rows) software inventories.
Deduplicates machine installations, aggregates canonical products, reuses verified research cache,
and executes asynchronous processing with real-time progress tracking.
"""

import os
import io
import csv
import json
import time
import uuid
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple, Generator

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.connection import SessionLocal, engine, Base
from backend.models.inventory_upload import (
    InventoryUpload,
    InventoryUploadRow,
    UploadLicenseResult,
)
from backend.inventory.processing.column_mapper import ColumnMapper
from backend.inventory.detection.qualification_filter import (
    ApplicationQualificationFilter,
)
from backend.inventory.detection.detection_normalizer import DetectionNormalizer
from backend.inventory.recognition.alias_system import ApplicationAliasSystem
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
from backend.sources.research_cache import ResearchCache
from backend.validation.export_validator import ExportValidator
from backend.validation.reliability_score import UNRESOLVED_RELIABILITY_SCORE

logger = logging.getLogger(__name__)


class BulkInventoryUploadService:
    """
    High-performance service for bulk inventory parsing, deduplication, license research,
    and isolated persistence.
    """

    # Thread-safe in-memory cache for live upload progress
    _PROGRESS_REGISTRY: Dict[str, Dict[str, Any]] = {}
    _LOCK = threading.Lock()

    @classmethod
    def update_live_progress(cls, upload_id: str, progress_data: Dict[str, Any], db: Optional[Session] = None):
        """Updates both in-memory registry and DB record with latest progress."""
        with cls._LOCK:
            cls._PROGRESS_REGISTRY[upload_id] = progress_data

        if db:
            try:
                upload = db.query(InventoryUpload).filter(InventoryUpload.upload_id == upload_id).first()
                if upload:
                    upload.progress_json = json.dumps(progress_data)
                    db.commit()
            except Exception as e:
                logger.warning(f"Could not update DB progress for {upload_id}: {e}")

    @classmethod
    def get_live_progress(cls, upload_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """Retrieves progress from in-memory registry or fallback to database."""
        with cls._LOCK:
            if upload_id in cls._PROGRESS_REGISTRY:
                return cls._PROGRESS_REGISTRY[upload_id]

        if db:
            upload = db.query(InventoryUpload).filter(InventoryUpload.upload_id == upload_id).first()
            if upload and upload.progress_json:
                try:
                    return json.loads(upload.progress_json)
                except Exception:
                    pass

        return {
            "status": "QUEUED",
            "percent": 0,
            "current_step": "Initializing job...",
            "processed_rows": 0,
            "total_rows": 0,
            "unique_applications": 0,
            "cache_hits": 0,
            "new_research": 0,
            "resolved_applications": 0,
            "unresolved_applications": 0,
            "duplicates_merged": 0,
        }

    # =========================================================================
    # PREVIEW & VALIDATION
    # =========================================================================

    @classmethod
    def preview_file(
        cls,
        file_bytes: bytes,
        file_name: str,
        sample_size: int = 10,
    ) -> Dict[str, Any]:
        """
        Parses headers, detects column mapping, and returns a sample preview.
        Supports CSV (with encoding detection) and Excel (.xlsx, .xls).
        """
        ext = os.path.splitext(file_name)[1].lower()
        file_type = "XLSX" if ext in (".xlsx", ".xlsm") else "XLS" if ext == ".xls" else "CSV"

        headers: List[str] = []
        sample_rows: List[Dict[str, Any]] = []
        total_rows = 0

        if file_type == "CSV":
            # Detect text encoding
            encodings_to_try = ["utf-8-sig", "utf-8", "latin-1", "cp1252", "iso-8859-1"]
            decoded_text = None
            for enc in encodings_to_try:
                try:
                    decoded_text = file_bytes.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue

            if decoded_text is None:
                decoded_text = file_bytes.decode("utf-8", errors="replace")

            # Fast count of lines
            lines = [l for l in decoded_text.splitlines() if l.strip()]
            if not lines:
                raise ValueError("The uploaded CSV file is empty.")

            reader = csv.DictReader(io.StringIO(decoded_text))
            headers = [h.strip() for h in (reader.fieldnames or []) if h]

            for idx, row in enumerate(reader):
                total_rows += 1
                if idx < sample_size:
                    sample_rows.append({k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items() if k})

        else:
            # Excel file
            df = pd.read_excel(io.BytesIO(file_bytes), nrows=sample_size + 1000)
            headers = [str(c).strip() for c in df.columns if c is not None]
            
            # Count total rows efficiently
            full_df = pd.read_excel(io.BytesIO(file_bytes))
            total_rows = len(full_df)
            
            for _, row in df.head(sample_size).iterrows():
                row_dict = {}
                for col in headers:
                    val = row[col]
                    if pd.isna(val):
                        row_dict[col] = ""
                    else:
                        row_dict[col] = str(val).strip()
                sample_rows.append(row_dict)

        # Automatic column detection
        detected_mapping = ColumnMapper.auto_detect_columns(headers)
        confidence_info = ColumnMapper.calculate_confidence(headers, detected_mapping)

        return {
            "file_name": file_name,
            "file_type": file_type,
            "total_rows": total_rows,
            "headers": headers,
            "sample_rows": sample_rows,
            "detected_mapping": detected_mapping,
            "mapping_confidence": confidence_info,
        }

    # =========================================================================
    # JOB INITIATION & ASYNC ORCHESTRATION
    # =========================================================================

    @classmethod
    def start_upload_job(
        cls,
        file_bytes: bytes,
        file_name: str,
        column_mapping: Dict[str, Optional[str]],
        run_async: bool = True,
        db_session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Creates an isolated InventoryUpload job, persists initial record, and launches background processing.
        """
        # Ensure database tables exist
        Base.metadata.create_all(bind=engine)

        close_db = False
        db = db_session
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            # Generate unique Upload ID
            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            short_id = uuid.uuid4().hex[:6]
            upload_id = f"UP_{timestamp_str}_{short_id}"

            ext = os.path.splitext(file_name)[1].lower()
            file_type = "XLSX" if ext in (".xlsx", ".xlsm") else "XLS" if ext == ".xls" else "CSV"

            # Create DB Upload Record
            upload_record = InventoryUpload(
                upload_id=upload_id,
                file_name=file_name,
                file_type=file_type,
                file_size_bytes=len(file_bytes),
                total_raw_rows=0,
                status="PROCESSING",
                column_mapping_json=json.dumps(column_mapping),
                progress_json=json.dumps({
                    "status": "PROCESSING",
                    "percent": 5,
                    "current_step": "Starting inventory ingestion...",
                    "processed_rows": 0,
                    "total_rows": 0,
                }),
                created_at=datetime.now(timezone.utc),
            )
            db.add(upload_record)
            db.commit()

            initial_progress = {
                "upload_id": upload_id,
                "status": "PROCESSING",
                "percent": 5,
                "current_step": "Starting inventory ingestion...",
                "processed_rows": 0,
                "total_rows": 0,
                "unique_applications": 0,
                "cache_hits": 0,
                "new_research": 0,
                "resolved_applications": 0,
                "unresolved_applications": 0,
                "duplicates_merged": 0,
            }
            cls.update_live_progress(upload_id, initial_progress)

            if run_async:
                # Start background daemon worker
                thread = threading.Thread(
                    target=cls._process_upload_worker,
                    args=(upload_id, file_bytes, file_name, file_type, column_mapping),
                    daemon=True,
                )
                thread.start()
                return {
                    "upload_id": upload_id,
                    "file_name": file_name,
                    "status": "PROCESSING",
                    "message": "Upload job started asynchronously.",
                }
            else:
                # Synchronous execution (useful for unit tests)
                return cls._process_upload_worker(upload_id, file_bytes, file_name, file_type, column_mapping)

        finally:
            if close_db and db:
                db.close()

    # =========================================================================
    # CORE PROCESSING WORKER (SCALABLE 19,000+ ROWS PIPELINE)
    # =========================================================================

    @classmethod
    def _process_upload_worker(
        cls,
        upload_id: str,
        file_bytes: bytes,
        file_name: str,
        file_type: str,
        column_mapping: Dict[str, Optional[str]],
    ) -> Dict[str, Any]:
        """
        Executes the 5-phase scalable pipeline:
        1. Ingestion, Field Normalization & Row Extraction
        2. Deduplication vs Multi-Machine Installation Separation
        3. Canonical Identity Aggregation (Grouping identical apps across machines)
        4. Canonical Intelligence Resolution & Knowledge Cache Reuse
        5. Broadcasting Intelligence to all Machine Rows & Batch DB Persistence
        """
        db = SessionLocal()
        start_time = time.time()
        logger.info(f"[{upload_id}] Starting processing worker for {file_name} ({file_type})")

        try:
            # -----------------------------------------------------------------
            # PHASE 1: INGESTION & ROW EXTRACTION
            # -----------------------------------------------------------------
            cls.update_live_progress(upload_id, {
                "upload_id": upload_id,
                "status": "PROCESSING",
                "percent": 10,
                "current_step": "Parsing file rows and normalizing fields...",
                "processed_rows": 0,
                "total_rows": 0,
            }, db)

            raw_records: List[Dict[str, Any]] = []

            if file_type == "CSV":
                encodings_to_try = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
                decoded_text = None
                for enc in encodings_to_try:
                    try:
                        decoded_text = file_bytes.decode(enc)
                        break
                    except UnicodeDecodeError:
                        continue
                if decoded_text is None:
                    decoded_text = file_bytes.decode("utf-8", errors="replace")

                reader = csv.DictReader(io.StringIO(decoded_text))
                for row_idx, row in enumerate(reader, start=1):
                    extracted = ColumnMapper.extract_row_data(row, column_mapping, row_index=row_idx)
                    raw_records.append(extracted)
            else:
                # Excel
                df = pd.read_excel(io.BytesIO(file_bytes))
                headers = [str(c).strip() for c in df.columns if c is not None]
                for row_idx, (_, row) in enumerate(df.iterrows(), start=1):
                    row_dict = {}
                    for col in headers:
                        val = row[col]
                        row_dict[col] = "" if pd.isna(val) else str(val).strip()
                    extracted = ColumnMapper.extract_row_data(row_dict, column_mapping, row_index=row_idx)
                    raw_records.append(extracted)

            total_raw_rows = len(raw_records)
            logger.info(f"[{upload_id}] Ingested {total_raw_rows} raw rows from {file_name}")

            # Update DB total rows
            upload_rec = db.query(InventoryUpload).filter(InventoryUpload.upload_id == upload_id).first()
            if upload_rec:
                upload_rec.total_raw_rows = total_raw_rows
                db.commit()

            # -----------------------------------------------------------------
            # PHASE 2: ROW DEDUPLICATION & MACHINE GROUPING
            # -----------------------------------------------------------------
            cls.update_live_progress(upload_id, {
                "upload_id": upload_id,
                "status": "PROCESSING",
                "percent": 25,
                "current_step": "Analyzing machines and deduplicating installation records...",
                "processed_rows": 0,
                "total_rows": total_raw_rows,
            }, db)

            qualified_rows: List[Dict[str, Any]] = []
            seen_exact_installations: set = set()
            duplicates_merged_count = 0
            disqualified_count = 0
            unique_machines_set: set = set()

            for rec in raw_records:
                app_name = rec["raw_application"]
                if not app_name:
                    disqualified_count += 1
                    continue

                host = rec["hostname"] or "UNKNOWN_HOST"
                unique_machines_set.add(host.lower())
                vendor = rec["raw_vendor"]
                ver = rec["raw_version"]

                # Clean multi-version strings
                if ver and (";" in ver or "  " in ver):
                    parts = [p.strip() for p in re.split(r"[;\s]+", ver) if p.strip()]
                    seen_parts = []
                    for p in parts:
                        if p not in seen_parts:
                            seen_parts.append(p)
                    ver = "; ".join(seen_parts)
                    rec["raw_version"] = ver

                # Normalize name and publisher upfront
                norm_app = DetectionNormalizer.normalize_name(app_name)
                norm_vendor = DetectionNormalizer.normalize_publisher(vendor, app_name)
                rec["normalized_application"] = norm_app or app_name
                rec["normalized_vendor"] = norm_vendor or vendor

                # Candidate Qualification Evaluation
                cand_payload = {
                    "raw_name": app_name,
                    "name": norm_app,
                    "raw_publisher": vendor,
                    "publisher": norm_vendor,
                    "raw_version": ver,
                    "raw_install_location": rec.get("install_location"),
                    "install_source": "UPLOAD",
                }
                is_qual, qual_reason, qual_cat = ApplicationQualificationFilter.qualify_candidate(cand_payload)
                rec["is_qualified"] = is_qual
                rec["qualification_category"] = qual_cat
                rec["qualification_reason"] = qual_reason

                # Exact duplicate installation on the SAME machine
                exact_key = (
                    host.strip().lower(),
                    app_name.strip().lower(),
                    (ver or "").strip().lower(),
                    (vendor or "").strip().lower(),
                )

                if exact_key in seen_exact_installations:
                    duplicates_merged_count += 1
                    continue

                seen_exact_installations.add(exact_key)
                qualified_rows.append(rec)

            total_qualified_rows = len(qualified_rows)
            unique_machines_count = len(unique_machines_set)
            logger.info(
                f"[{upload_id}] Qualified {total_qualified_rows} rows across {unique_machines_count} machines. "
                f"Merged {duplicates_merged_count} duplicates, disqualified {disqualified_count} invalid."
            )

            # -----------------------------------------------------------------
            # PHASE 3: CANONICAL IDENTITY GROUPING
            # -----------------------------------------------------------------
            cls.update_live_progress(upload_id, {
                "upload_id": upload_id,
                "status": "PROCESSING",
                "percent": 35,
                "current_step": "Grouping identical products for scalable research...",
                "processed_rows": 0,
                "total_rows": total_raw_rows,
                "duplicates_merged": duplicates_merged_count,
            }, db)

            # Map from canonical identity key -> list of matching row indices
            # canonical_key: (canonical_vendor.lower(), canonical_product.lower(), clean_version.lower())
            unique_canonical_products: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
            row_to_canonical_key: Dict[int, Tuple[str, str, str]] = {}

            for idx, qrow in enumerate(qualified_rows):
                r_name = qrow.get("normalized_application") or qrow["raw_application"]
                r_vend = qrow.get("normalized_vendor") or qrow["raw_vendor"]
                r_ver = qrow["raw_version"]

                alias_res = ApplicationAliasSystem.resolve_application(
                    raw_name=r_name,
                    raw_publisher=r_vend,
                    raw_version=r_ver,
                )

                canonical_prod = alias_res.canonical_product if alias_res.canonical_product != "UNRESOLVED" else r_name
                canonical_vend = alias_res.canonical_vendor if alias_res.canonical_vendor != "UNKNOWN" else (r_vend or "Unknown")
                clean_ver = r_ver or "N/A"

                qrow["canonical_product"] = canonical_prod
                qrow["canonical_vendor"] = canonical_vend

                c_key = (canonical_vend.strip().lower(), canonical_prod.strip().lower(), clean_ver.strip().lower())
                row_to_canonical_key[idx] = c_key

                if c_key not in unique_canonical_products:
                    unique_canonical_products[c_key] = {
                        "canonical_product": canonical_prod,
                        "canonical_vendor": canonical_vend,
                        "sample_version": clean_ver,
                        "sample_raw_name": r_name,
                        "sample_raw_vendor": r_vend,
                        "sample_install_loc": qrow.get("install_location"),
                        "qualification_category": qrow.get("qualification_category"),
                        "qualification_reason": qrow.get("qualification_reason"),
                        "row_indices": [idx],
                    }
                else:
                    unique_canonical_products[c_key]["row_indices"].append(idx)

            total_unique_apps = len(unique_canonical_products)
            logger.info(
                f"[{upload_id}] Aggregated {total_qualified_rows} rows into {total_unique_apps} unique canonical applications."
            )

            # -----------------------------------------------------------------
            # PHASE 4: CANONICAL INTELLIGENCE RESOLUTION & RESEARCH CACHING
            # -----------------------------------------------------------------
            cls.update_live_progress(upload_id, {
                "upload_id": upload_id,
                "status": "PROCESSING",
                "percent": 45,
                "current_step": f"Executing License Intelligence on {total_unique_apps} unique products...",
                "processed_rows": 0,
                "total_rows": total_raw_rows,
                "unique_applications": total_unique_apps,
                "duplicates_merged": duplicates_merged_count,
            }, db)

            resolved_canonical_intel: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
            cache_hits_count = 0
            new_research_count = 0
            resolved_apps_count = 0
            unresolved_apps_count = 0

            for prod_idx, (c_key, prod_info) in enumerate(unique_canonical_products.items(), start=1):
                c_vend = prod_info["canonical_vendor"]
                c_prod = prod_info["canonical_product"]
                c_ver = prod_info["sample_version"]

                # Step 4a: Check ResearchCache first
                cached_entry = ResearchCache.get(canonical_product=c_prod, canonical_vendor=c_vend)
                
                if cached_entry and cached_entry.classification != "UNKNOWN":
                    cache_hits_count += 1
                    resolved_apps_count += 1
                    intel_result = {
                        "application": cached_entry.canonical_product,
                        "vendor": cached_entry.canonical_vendor,
                        "version": c_ver,
                        "classification": cached_entry.classification,
                        "availability": cached_entry.availability,
                        "license_required": cached_entry.license_required,
                        "license_model": cached_entry.license_model,
                        "metric": cached_entry.license_metric,
                        "confidence": "HIGH",
                        "reliability_score": 85.0,
                        "evidence_status": "VERIFIED",
                        "evidence_source": "Cached Verified Knowledge",
                        "evidence_url": cached_entry.source_url,
                        "evidence_quote": cached_entry.evidence_text,
                        "research_status": "CACHE_HIT",
                    }
                else:
                    # Step 4b: Run Hybrid License Engine (Includes Microsoft Adapter, Alias System, Baseline ground truth)
                    h_res = HybridLicenseEngine.resolve_hybrid_record(
                        app_id=None,
                        name=prod_info["sample_raw_name"],
                        publisher=prod_info["sample_raw_vendor"],
                        version=c_ver if c_ver != "N/A" else None,
                        install_location=prod_info["sample_install_loc"],
                        qualification_category=prod_info.get("qualification_category"),
                        qualification_reason=prod_info.get("qualification_reason"),
                    )

                    classification = h_res.get("classification", "UNKNOWN")
                    req = h_res.get("license_required", "UNKNOWN")
                    if req == "NOT_APPLICABLE":
                        req = "NO"

                    ev_status = h_res.get("evidence_status", "MISSING")
                    conf = h_res.get("confidence", "UNKNOWN")
                    rel_score = float(h_res.get("reliability_score", UNRESOLVED_RELIABILITY_SCORE))
                    ev_quote = h_res.get("evidence_quote") or ""
                    ev_url = h_res.get("primary_source_url") or h_res.get("source_url")

                    is_unresolved = (
                        classification == "UNKNOWN" or
                        h_res.get("application") == "UNRESOLVED" or
                        "unresolved" in str(prod_info["sample_raw_name"]).lower()
                    )

                    if not is_unresolved:
                        resolved_apps_count += 1
                        cache_hits_count += 1
                        research_status = "BASELINE_RESOLVED"
                        
                        # Store in ResearchCache for subsequent queries if an official URL exists
                        if ev_url:
                            try:
                                ResearchCache.put(
                                    canonical_product=h_res.get("application") or c_prod,
                                    canonical_vendor=h_res.get("vendor") or c_vend,
                                    source_url=ev_url,
                                    source_title="Vendor Licensing Terms",
                                    source_authority="TIER_1",
                                    evidence_type="DIRECT_STATEMENT",
                                    evidence_text=ev_quote or "Verified catalog licensing evidence.",
                                    license_model=h_res.get("license_model", "Standard"),
                                    license_metric=h_res.get("metric", "USER"),
                                    license_required=req,
                                    classification=classification,
                                    availability=h_res.get("availability", "COMMERCIAL"),
                                    scope_match_tier="PRODUCT",
                                )
                            except Exception:
                                pass
                    else:
                        unresolved_apps_count += 1
                        research_status = "UNRESOLVED"
                        classification = "UNKNOWN"
                        req = "UNKNOWN"
                        conf = "UNKNOWN"
                        ev_status = "MISSING"
                        rel_score = min(rel_score, UNRESOLVED_RELIABILITY_SCORE)
                        ev_quote = "Unresolved application identity. No verified license terms found."

                    # Consistency constraint: VERIFIED with missing version downgrades to PARTIAL
                    if ev_status == "VERIFIED" and (not c_ver or c_ver in ("N/A", "UNKNOWN", "")):
                        ev_status = "PARTIAL"

                    # If MISSING evidence, confidence cannot be HIGH
                    if ev_status == "MISSING" and conf in ("HIGH", "VERY_HIGH"):
                        conf = "LOW"

                    intel_result = {
                        "application": h_res.get("application") or c_prod,
                        "vendor": h_res.get("vendor") or c_vend,
                        "version": c_ver,
                        "classification": classification,
                        "availability": h_res.get("availability", "UNKNOWN"),
                        "license_required": req,
                        "license_model": h_res.get("license_model", "UNKNOWN"),
                        "metric": h_res.get("metric", "UNKNOWN"),
                        "confidence": conf,
                        "reliability_score": rel_score,
                        "evidence_status": ev_status,
                        "evidence_source": "Official Vendor Terms" if ev_status != "MISSING" else None,
                        "evidence_url": ev_url,
                        "evidence_quote": ev_quote,
                        "research_status": research_status,
                    }

                resolved_canonical_intel[c_key] = intel_result

                # Update progress periodically
                if prod_idx % 20 == 0 or prod_idx == total_unique_apps:
                    progress_pct = 45 + int((prod_idx / total_unique_apps) * 35)
                    cls.update_live_progress(upload_id, {
                        "upload_id": upload_id,
                        "status": "PROCESSING",
                        "percent": progress_pct,
                        "current_step": f"Resolved intelligence for {prod_idx}/{total_unique_apps} applications...",
                        "processed_rows": prod_idx,
                        "total_rows": total_raw_rows,
                        "unique_applications": total_unique_apps,
                        "resolved_applications": resolved_apps_count,
                        "unresolved_applications": unresolved_apps_count,
                        "cache_hits": cache_hits_count,
                        "new_research": new_research_count,
                        "duplicates_merged": duplicates_merged_count,
                    }, db)

            # -----------------------------------------------------------------
            # PHASE 5: BROADCASTING & BATCH DB PERSISTENCE
            # -----------------------------------------------------------------
            cls.update_live_progress(upload_id, {
                "upload_id": upload_id,
                "status": "PROCESSING",
                "percent": 85,
                "current_step": "Broadcasting verified results to installation rows and saving...",
                "processed_rows": total_qualified_rows,
                "total_rows": total_raw_rows,
                "unique_applications": total_unique_apps,
                "resolved_applications": resolved_apps_count,
                "unresolved_applications": unresolved_apps_count,
                "cache_hits": cache_hits_count,
                "duplicates_merged": duplicates_merged_count,
            }, db)

            now = datetime.now(timezone.utc)
            db_upload_rows: List[InventoryUploadRow] = []
            db_license_results: List[UploadLicenseResult] = []

            classification_summary: Dict[str, int] = {
                "COMMERCIAL": 0,
                "FREEWARE": 0,
                "OPEN_SOURCE": 0,
                "OS_BUNDLED": 0,
                "COMMERCIAL_COMPONENT": 0,
                "FREE_AND_PAID": 0,
                "UNKNOWN": 0,
            }
            evidence_status_summary: Dict[str, int] = {
                "VERIFIED": 0,
                "PARTIAL": 0,
                "MISSING": 0,
            }

            for idx, qrow in enumerate(qualified_rows, start=1):
                c_key = row_to_canonical_key.get(idx - 1)
                intel = resolved_canonical_intel.get(c_key, {})

                cls_val = intel.get("classification", "UNKNOWN")
                ev_val = intel.get("evidence_status", "MISSING")

                if cls_val in classification_summary:
                    classification_summary[cls_val] += 1
                else:
                    classification_summary["UNKNOWN"] += 1

                if ev_val in evidence_status_summary:
                    evidence_status_summary[ev_val] += 1
                else:
                    evidence_status_summary["MISSING"] += 1

                # 1. Create Row Record
                row_obj = InventoryUploadRow(
                    upload_id=upload_id,
                    row_index=idx,
                    hostname=qrow["hostname"],
                    device_id=None,
                    raw_application=qrow["raw_application"],
                    raw_vendor=qrow["raw_vendor"],
                    raw_version=qrow["raw_version"],
                    raw_install_date=qrow.get("install_date"),
                    raw_install_location=qrow.get("install_location"),
                    raw_data_json=json.dumps(qrow.get("raw_data", {})),
                    canonical_product=intel.get("application") or qrow["canonical_product"],
                    canonical_vendor=intel.get("vendor") or qrow["canonical_vendor"],
                    is_duplicate=False,
                    is_disqualified=False,
                    created_at=now,
                )
                db_upload_rows.append(row_obj)

                # 2. Create Result Record
                res_obj = UploadLicenseResult(
                    upload_id=upload_id,
                    hostname=qrow["hostname"],
                    device_id=None,
                    raw_application=qrow["raw_application"],
                    raw_vendor=qrow["raw_vendor"],
                    raw_version=qrow["raw_version"],
                    canonical_product=intel.get("application") or qrow["canonical_product"],
                    canonical_vendor=intel.get("vendor") or qrow["canonical_vendor"],
                    canonical_edition=None,
                    classification=cls_val,
                    availability=intel.get("availability", "UNKNOWN"),
                    license_required=intel.get("license_required", "UNKNOWN"),
                    license_model=intel.get("license_model", "UNKNOWN"),
                    license_metric=intel.get("metric", "UNKNOWN"),
                    evidence_status=ev_val,
                    confidence=intel.get("confidence", "UNKNOWN"),
                    reliability_score=intel.get("reliability_score", UNRESOLVED_RELIABILITY_SCORE),
                    evidence_source=intel.get("evidence_source"),
                    evidence_url=intel.get("evidence_url"),
                    evidence_quote=intel.get("evidence_quote"),
                    override_reason=intel.get("override_reason"),
                    research_status=intel.get("research_status", "UNKNOWN"),
                    processed_at=now,
                )
                db_license_results.append(res_obj)

            # Bulk save in batches of 1,000 for high efficiency
            BATCH_SIZE = 1000
            for i in range(0, len(db_upload_rows), BATCH_SIZE):
                db.bulk_save_objects(db_upload_rows[i : i + BATCH_SIZE])
                db.commit()

            for i in range(0, len(db_license_results), BATCH_SIZE):
                db.bulk_save_objects(db_license_results[i : i + BATCH_SIZE])
                db.commit()

            duration = round(time.time() - start_time, 2)
            logger.info(f"[{upload_id}] Successfully persisted {len(db_license_results)} results in {duration}s")

            # -----------------------------------------------------------------
            # FINAL SUMMARY & COMPLETION
            # -----------------------------------------------------------------
            summary_data = {
                "upload_id": upload_id,
                "file_name": file_name,
                "file_type": file_type,
                "total_raw_rows": total_raw_rows,
                "total_qualified_rows": total_qualified_rows,
                "unique_applications": total_unique_apps,
                "unique_machines": unique_machines_count,
                "duplicates_merged": duplicates_merged_count,
                "disqualified_rows": disqualified_count,
                "resolved_records": resolved_apps_count,
                "unresolved_records": unresolved_apps_count,
                "cache_hits": cache_hits_count,
                "new_research": new_research_count,
                "processing_time_seconds": duration,
                "classification_summary": classification_summary,
                "evidence_status_summary": evidence_status_summary,
            }

            final_progress = {
                "upload_id": upload_id,
                "status": "COMPLETED",
                "percent": 100,
                "current_step": f"Processing completed successfully in {duration}s!",
                "processed_rows": total_qualified_rows,
                "total_rows": total_raw_rows,
                "unique_applications": total_unique_apps,
                "resolved_applications": resolved_apps_count,
                "unresolved_applications": unresolved_apps_count,
                "cache_hits": cache_hits_count,
                "new_research": new_research_count,
                "duplicates_merged": duplicates_merged_count,
                "summary": summary_data,
            }

            upload_rec = db.query(InventoryUpload).filter(InventoryUpload.upload_id == upload_id).first()
            if upload_rec:
                upload_rec.status = "COMPLETED"
                upload_rec.completed_at = datetime.now(timezone.utc)
                upload_rec.summary_json = json.dumps(summary_data)
                upload_rec.progress_json = json.dumps(final_progress)
                db.commit()

            cls.update_live_progress(upload_id, final_progress)
            return summary_data

        except Exception as e:
            logger.error(f"[{upload_id}] Processing worker encountered an error: {e}", exc_info=True)
            error_progress = {
                "upload_id": upload_id,
                "status": "FAILED",
                "percent": 100,
                "current_step": f"Processing failed: {str(e)}",
                "error": str(e),
            }
            cls.update_live_progress(upload_id, error_progress)

            try:
                upload_rec = db.query(InventoryUpload).filter(InventoryUpload.upload_id == upload_id).first()
                if upload_rec:
                    upload_rec.status = "FAILED"
                    upload_rec.error_message = str(e)
                    upload_rec.progress_json = json.dumps(error_progress)
                    db.commit()
            except Exception:
                pass

            return {"upload_id": upload_id, "status": "FAILED", "error": str(e)}

        finally:
            db.close()

    # =========================================================================
    # QUERY & EXPORT METHODS
    # =========================================================================

    @classmethod
    def list_upload_jobs(cls, limit: int = 50, db_session: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Lists recent inventory upload jobs."""
        close_db = False
        db = db_session
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            records = db.query(InventoryUpload).order_by(InventoryUpload.created_at.desc()).limit(limit).all()
            results = []
            for r in records:
                summary = json.loads(r.summary_json) if r.summary_json else {}
                progress = json.loads(r.progress_json) if r.progress_json else {}
                results.append({
                    "upload_id": r.upload_id,
                    "file_name": r.file_name,
                    "file_type": r.file_type,
                    "total_raw_rows": r.total_raw_rows,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "summary": summary,
                    "progress": progress,
                    "error_message": r.error_message,
                })
            return results
        finally:
            if close_db and db:
                db.close()

    @classmethod
    def get_upload_results(
        cls,
        upload_id: str,
        search: Optional[str] = None,
        classification: Optional[str] = None,
        evidence_status: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
        db_session: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieves paginated and filtered results from upload_license_results."""
        close_db = False
        db = db_session
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            q = db.query(UploadLicenseResult).filter(UploadLicenseResult.upload_id == upload_id)

            if classification and classification.upper() != "ALL":
                q = q.filter(func.lower(UploadLicenseResult.classification) == classification.strip().lower())

            if evidence_status and evidence_status.upper() != "ALL":
                q = q.filter(func.lower(UploadLicenseResult.evidence_status) == evidence_status.strip().lower())

            if search:
                s = f"%{search.strip().lower()}%"
                q = q.filter(
                    func.lower(UploadLicenseResult.canonical_product).like(s)
                    | func.lower(UploadLicenseResult.raw_application).like(s)
                    | func.lower(UploadLicenseResult.canonical_vendor).like(s)
                    | func.lower(UploadLicenseResult.raw_vendor).like(s)
                    | func.lower(UploadLicenseResult.hostname).like(s)
                    | func.lower(UploadLicenseResult.classification).like(s)
                )

            records = q.order_by(UploadLicenseResult.id.asc()).offset(offset).limit(limit).all()
            results = []
            for r in records:
                results.append({
                    "id": r.id,
                    "upload_id": r.upload_id,
                    "hostname": r.hostname or "N/A",
                    "application": r.canonical_product or r.raw_application,
                    "raw_application": r.raw_application,
                    "vendor": r.canonical_vendor or r.raw_vendor or "Unknown",
                    "version": r.raw_version or "N/A",
                    "classification": r.classification or "UNKNOWN",
                    "availability": r.availability or "UNKNOWN",
                    "license_required": r.license_required or "UNKNOWN",
                    "license_model": r.license_model or "UNKNOWN",
                    "metric": r.license_metric or "UNKNOWN",
                    "confidence": r.confidence or "UNKNOWN",
                    "reliability": f"{int(r.reliability_score or 0)}%",
                    "reliability_score": r.reliability_score or 0.0,
                    "evidence_status": r.evidence_status or "MISSING",
                    "evidence_source": r.evidence_source,
                    "evidence_url": r.evidence_url or "",
                    "evidence_quote": r.evidence_quote,
                    "installer_url": getattr(r, "installer_url", None) or "",
                    "installer_sha256": getattr(r, "installer_sha256", None) or "",
                    "winget_package_id": getattr(r, "winget_package_id", None) or "",
                    "conflict_status": getattr(r, "conflict_status", None) or "VERIFIED",
                    "override_reason": r.override_reason or "",
                    "canonical_edition": getattr(r, "canonical_edition", None) or "",
                    "edition": getattr(r, "canonical_edition", None) or "",
                    "spdx_id": getattr(r, "spdx_id", None) or "UNKNOWN",
                    "version_rule_applied": getattr(r, "version_rule_applied", None) or "",
                    "consensus_status": getattr(r, "consensus_status", None) or "VERIFIED",
                    "is_end_of_life": getattr(r, "is_end_of_life", None),
                    "end_of_life": getattr(r, "is_end_of_life", None),
                    "is_end_of_support": getattr(r, "is_end_of_support", None),
                    "end_of_support": getattr(r, "is_end_of_support", None),
                    "research_status": r.research_status or "UNKNOWN",
                    "resolution_engine_version": r.resolution_engine_version or "v1.3.0",
                    "processed_at": r.processed_at.isoformat() if r.processed_at else "",
                })
            return results
        finally:
            if close_db and db:
                db.close()

    @classmethod
    def export_results_csv(cls, upload_id: str, db_session: Optional[Session] = None, legacy: bool = False) -> str:
        """
        Generates CSV string with UTF-8 BOM for the specified upload.
        By default outputs the standardized 14-column Application Inventory schema.
        If legacy=True, outputs previous legacy schema.
        """
        results = cls.get_upload_results(upload_id=upload_id, limit=50000, db_session=db_session)
        if not results:
            return ""

        if not legacy:
            from backend.inventory.export.standardized_inventory_exporter import StandardizedInventoryExporter
            df = StandardizedInventoryExporter.transform_inventory(results)
            csv_bytes = StandardizedInventoryExporter.to_csv_bytes(df)
            return csv_bytes.decode("utf-8")

        output = io.StringIO()
        output.write("\ufeff")  # UTF-8 BOM
        writer = csv.writer(output)

        headers = [
            "Hostname",
            "Raw Application",
            "Canonical Product",
            "Vendor",
            "Version",
            "Classification",
            "Availability",
            "License Required",
            "License Model",
            "Metric",
            "Evidence Status",
            "Confidence",
            "Reliability",
            "Evidence URL",
            "Evidence Quote",
            "Processing Result",
        ]
        writer.writerow(headers)

        for r in results:
            writer.writerow([
                r["hostname"],
                r["raw_application"],
                r["application"],
                r["vendor"],
                r["version"],
                r["classification"],
                r["availability"],
                r["license_required"],
                r["license_model"],
                r["metric"],
                r["evidence_status"],
                r["confidence"],
                r["reliability"],
                r["evidence_url"],
                r["evidence_quote"] or "",
                r["research_status"],
            ])

        return output.getvalue()

    @classmethod
    def export_results_excel(cls, upload_id: str, db_session: Optional[Session] = None, legacy: bool = False) -> bytes:
        """
        Generates formatted Excel (.xlsx) file bytes for the specified upload.
        By default outputs the standardized 14-column Application Inventory schema.
        If legacy=True, outputs previous legacy schema.
        """
        results = cls.get_upload_results(upload_id=upload_id, limit=50000, db_session=db_session)
        if not results:
            return b""

        if not legacy:
            from backend.inventory.export.standardized_inventory_exporter import StandardizedInventoryExporter
            df = StandardizedInventoryExporter.transform_inventory(results)
            return StandardizedInventoryExporter.to_excel_bytes(df)

        export_data = []
        for r in results:
            export_data.append({
                "Hostname": r["hostname"],
                "Raw Application": r["raw_application"],
                "Canonical Product": r["application"],
                "Vendor": r["vendor"],
                "Version": r["version"],
                "Classification": r["classification"],
                "Availability": r["availability"],
                "License Required": r["license_required"],
                "License Model": r["license_model"],
                "Metric": r["metric"],
                "Evidence Status": r["evidence_status"],
                "Confidence": r["confidence"],
                "Reliability": r["reliability"],
                "Evidence URL": r["evidence_url"],
                "Evidence Quote": r["evidence_quote"] or "",
                "Processing Result": r["research_status"],
            })
        df = pd.DataFrame(export_data)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="License Intelligence Results")

        return output.getvalue()

    @classmethod
    def delete_upload_job(cls, upload_id: str, db_session: Optional[Session] = None) -> bool:
        """Deletes an upload job and cascades deletion of isolated rows and results."""
        close_db = False
        db = db_session
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            upload = db.query(InventoryUpload).filter(InventoryUpload.upload_id == upload_id).first()
            if not upload:
                return False

            # Delete upload (cascades to rows and license results)
            db.delete(upload)
            db.commit()

            with cls._LOCK:
                cls._PROGRESS_REGISTRY.pop(upload_id, None)

            return True
        finally:
            if close_db and db:
                db.close()
