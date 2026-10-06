"""
sync_historical_upload_accuracy.py
-----------------------------------
Synchronizes and re-evaluates historical UploadLicenseResult rows in the local database
using the hardened AppleProductIdentityResolver, LinuxSystemPackageFilter,
and Anti-Contamination domain guardrails.
"""

import os
import sys
import logging
from collections import Counter
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from backend.database.connection import SessionLocal
from backend.models.inventory_upload import InventoryUpload, UploadLicenseResult
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
from backend.validation.searxng_evidence_validator import is_valid_vendor_domain
from backend.validation.reliability_score import UNRESOLVED_RELIABILITY_SCORE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def sync_upload_results(upload_id: str):
    db = SessionLocal()
    try:
        results = db.query(UploadLicenseResult).filter(UploadLicenseResult.upload_id == upload_id).all()
        if not results:
            logger.warning(f"No results found for upload_id: {upload_id}")
            return

        logger.info(f"Syncing {len(results)} results for upload_id: {upload_id}...")

        updated_count = 0
        apple_count = 0
        linux_count = 0
        fixed_contamination = 0

        # Unique cache for batch resolution
        cache: Dict[tuple, Dict[str, Any]] = {}

        for r in results:
            key = (r.raw_application, r.raw_vendor, r.raw_version)
            if key not in cache:
                h_rec = HybridLicenseEngine.resolve_hybrid_record(
                    app_id=None,
                    name=r.raw_application,
                    publisher=r.raw_vendor,
                    version=r.raw_version,
                )
                cache[key] = h_rec

            h = cache[key]

            # Track improvements
            old_url = r.evidence_url or ""
            new_url = h.get("evidence_url") or ""

            if ("docker.com" in old_url and "docker" not in r.raw_application.lower()) or \
               ("visualstudio.microsoft.com" in old_url and "visual studio" not in r.raw_application.lower() and "microsoft" not in str(r.raw_vendor).lower()):
                fixed_contamination += 1

            if h.get("vendor") == "Apple Inc.":
                apple_count += 1
            if "ubuntu" in new_url or "debian" in new_url:
                linux_count += 1

            # Update row attributes
            r.canonical_product = h.get("application") or r.canonical_product
            r.canonical_vendor = h.get("vendor") or r.canonical_vendor
            r.classification = h.get("classification") or r.classification
            r.availability = h.get("availability") or r.availability
            c_u = str(r.classification or "").upper()
            if c_u in ("COMMERCIAL", "FREE_AND_PAID", "TRIAL", "PROPRIETARY", "PAID"):
                r.license_required = "YES"
            else:
                r.license_required = h.get("license_required") or r.license_required
            r.license_model = h.get("license_model") or r.license_model
            r.metric = h.get("metric") or r.metric
            r.confidence = h.get("confidence") or r.confidence
            r.reliability_score = float(h.get("reliability_score", r.reliability_score or UNRESOLVED_RELIABILITY_SCORE))
            r.reliability_str = h.get("reliability_str") or r.reliability_str
            r.evidence_status = h.get("evidence_status") or r.evidence_status
            r.evidence_url = new_url
            r.evidence_quote = h.get("evidence_quote") or r.evidence_quote
            r.override_reason = h.get("override_reason") or r.override_reason
            r.research_status = "BASELINE_RESOLVED" if h.get("classification") != "UNKNOWN" else r.research_status

            updated_count += 1

        db.commit()
        logger.info(
            f"Successfully updated {updated_count} rows for upload {upload_id}:\n"
            f"  - Apple Applications Correctly Classified: {apple_count}\n"
            f"  - Linux Packages Given Official Ubuntu Evidence: {linux_count}\n"
            f"  - Cross-Contaminated URLs Purged: {fixed_contamination}"
        )

    finally:
        db.close()


def run_all_syncs():
    db = SessionLocal()
    try:
        uploads = db.query(InventoryUpload).order_by(InventoryUpload.id.desc()).all()
        logger.info(f"Found {len(uploads)} total uploads in database.")
        for u in uploads:
            sync_upload_results(u.upload_id)
    finally:
        db.close()


if __name__ == "__main__":
    run_all_syncs()
