"""
Cross-Upload Persistent Product Intelligence Cache Service with Background Revalidation & Drift Detection.
Coordinates querying, upserting, staleness detection, and background revalidation
for the `resolved_products_cache` database table.
"""

import json
import uuid
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple, List

from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database.connection import SessionLocal
from backend.models.resolved_product_cache import ResolvedProductCache, ENGINE_VERSION
from backend.models.tier4_feedback import PendingCatalogRule, CatalogAuditLog
from backend.inventory.detection.detection_normalizer import DetectionNormalizer

logger = logging.getLogger(__name__)

DEFAULT_CACHE_TTL_DAYS = 90
CONTEXT_DEPENDENT_TTL_DAYS = 30


class ResolvedProductService:
    """
    Thread-safe service managing persistent cross-upload product resolution caching.
    Features:
    - In-memory write-through cache for microsecond lookups in large batches.
    - Non-blocking staleness handling: returns cached data immediately while queuing background revalidation.
    - Anti-drift protection: if revalidation finds license terms have changed, it routes to Tier 4 human review
      instead of silently overwriting high-stakes commercial decisions.
    - Full telemetry on lookups, hits, hit rates, and engine breakdown.
    """
    _mem_cache: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    _lock = threading.Lock()
    _reval_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="StalenessRevalWorker")
    
    # Telemetry counters
    _cumulative_lookups: int = 0
    _cumulative_hits: int = 0

    @classmethod
    def _make_key(cls, name: str, vendor: Optional[str] = None, version_bucket: Optional[str] = None) -> Tuple[str, str, str]:
        n_low = (name or "").strip().lower()
        # Preserve setup bootstrapper / component identity so it does not collapse into parent engine
        if any(w in n_low for w in (" setup", " installer", " bootstrapper", " setup support files")) and not any(p in n_low for p in ("visual studio code", "git", "python", "node.js", "docker", "brave", "chrome", "firefox", "zoom", "chatgpt")):
            n_clean = n_low
        else:
            n_clean = DetectionNormalizer.normalize_name(name or "").strip().lower()
        v_clean = DetectionNormalizer.normalize_publisher(vendor or "", raw_name=name).strip().lower() if vendor else ""
        b_clean = (version_bucket or "ANY").strip().upper()
        return (n_clean, v_clean, b_clean)

    @classmethod
    def get_cached_resolution(
        cls,
        name: str,
        publisher: Optional[str] = None,
        version_bucket: Optional[str] = "ANY",
        max_age_days: int = DEFAULT_CACHE_TTL_DAYS,
        db: Optional[Session] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves cached resolution if previously resolved.
        If the entry is stale (> TTL), it returns the cached data immediately (non-blocking)
        and asynchronously queues a background revalidation job.
        """
        if not name:
            return None

        with cls._lock:
            cls._cumulative_lookups += 1

        mem_key = cls._make_key(name, publisher, version_bucket)

        # 1. Fast in-memory check
        with cls._lock:
            if mem_key in cls._mem_cache:
                cached_res = dict(cls._mem_cache[mem_key])
                cls._cumulative_hits += 1
                return cached_res

        # 2. Database lookup
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            norm_name, norm_vend, v_bucket = mem_key

            # Try exact match with version_bucket first, then fallback to ANY
            rec = db.query(ResolvedProductCache).filter(
                ResolvedProductCache.normalized_name == norm_name,
                ResolvedProductCache.normalized_vendor == (norm_vend or None),
                ResolvedProductCache.version_bucket == v_bucket,
            ).first()

            if not rec and v_bucket != "ANY":
                rec = db.query(ResolvedProductCache).filter(
                    ResolvedProductCache.normalized_name == norm_name,
                    ResolvedProductCache.normalized_vendor == (norm_vend or None),
                    ResolvedProductCache.version_bucket == "ANY",
                ).first()

            # Fallback matching with normalized_name alone if vendor is empty
            if not rec and not norm_vend:
                rec = db.query(ResolvedProductCache).filter(
                    ResolvedProductCache.normalized_name == norm_name,
                ).first()

            if not rec:
                return None

            # Defensive guard: reject poisoned or contradictory cached resolutions
            canon_p = (rec.canonical_product or "").strip()
            class_p = (rec.classification or "").strip().upper()
            lic_req_p = (rec.license_required or "").strip().upper()
            ev_quote_low = (rec.evidence_quote or "").lower()

            # Case A: Poisoned generic company names or non-commercial marked as YES
            if canon_p in ("Microsoft", "Google", "Unknown", "Oracle", "Adobe") or (
                class_p in ("FREEWARE", "OPEN_SOURCE", "OS_BUNDLED", "OEM_OR_BUNDLED") and lic_req_p == "YES"
            ):
                logger.warning(
                    f"Rejecting poisoned cache entry id={rec.id} for '{name}': "
                    f"canonical='{canon_p}', class='{class_p}', lic_req='{lic_req_p}'"
                )
                return None

            # Case B: Contradictory freeware entry when evidence explicitly proves commercial requirement
            if class_p in ("FREEWARE", "FREE") and lic_req_p == "NO":
                if any(phrase in ev_quote_low for phrase in (
                    "commercial work or school accounts require",
                    "requires an eligible microsoft 365",
                    "commercial use requires",
                    "commercial license required",
                    "requires a paid commercial",
                    "paid commercial subscription",
                )):
                    logger.warning(
                        f"Auto-repairing contradictory cache entry id={rec.id} for '{name}': "
                        f"cached as {class_p}/NO but evidence states commercial requirement. Upgrading cache to FREE_AND_PAID / YES."
                    )
                    rec.classification = "FREE_AND_PAID"
                    rec.availability = "FREE_AND_PAID"
                    rec.license_required = "YES"
                    rec.metric = "Users"
                    rec.license_metric = "Users"
                    if not rec.license_model or "Freeware" in rec.license_model:
                        rec.license_model = "Freemium / Named User Subscription"
                    try:
                        db.commit()
                    except Exception as e_c:
                        logger.debug(f"Cache auto-repair commit notice: {e_c}")

            # Case C: Setup utility or installer candidate matching a parent commercial engine record
            name_low = (name or "").lower()
            if any(w in name_low for w in (" setup", " installer", " bootstrapper", " setup support files")) and not any(p in name_low for p in ("visual studio code", "git", "python", "node.js", "docker", "brave", "chrome", "firefox", "zoom", "chatgpt")):
                if rec.classification in ("COMMERCIAL", "FREE_AND_PAID") and not any(w in (rec.canonical_product or "").lower() for w in ("setup", "installer", "bootstrapper")):
                    logger.warning(
                        f"Rejecting commercial engine cache hit id={rec.id} for setup utility '{name}'"
                    )
                    return None

            # Case D: Authoritative catalog rule specifies CONTEXT_DEPENDENT
            try:
                from backend.inventory.recognition.catalog import RecognitionCatalog
                from backend.inventory.recognition.models import FinalLicenseStatus
                cat_rule = RecognitionCatalog.find_rule_by_name(canon_p, rec.canonical_vendor) or RecognitionCatalog.find_rule_by_name(name, publisher)
                if cat_rule and (getattr(cat_rule, "license_requirement", None) == "CONTEXT_DEPENDENT" or getattr(cat_rule, "license_required", None) == FinalLicenseStatus.LICENSE_REQUIRED_CONTEXT_DEPENDENT):
                    if rec.license_required != "CONTEXT_DEPENDENT":
                        rec.license_required = "CONTEXT_DEPENDENT"
                        try:
                            db.commit()
                        except Exception:
                            pass
            except Exception as e_cat:
                logger.debug(f"Catalog check notice: {e_cat}")

            with cls._lock:
                cls._cumulative_hits += 1

            now = datetime.now(timezone.utc)
            last_val = rec.last_validated_at
            if last_val and last_val.tzinfo is None:
                last_val = last_val.replace(tzinfo=timezone.utc)

            # Shorter TTL for products in flux / CONTEXT_DEPENDENT
            effective_ttl = CONTEXT_DEPENDENT_TTL_DAYS if rec.license_required == "CONTEXT_DEPENDENT" else max_age_days

            is_stale = False
            if last_val and (now - last_val).days > effective_ttl:
                is_stale = True

            res_dict = rec.to_dict()
            res_dict["is_cached"] = True
            res_dict["is_stale"] = is_stale

            with cls._lock:
                cls._mem_cache[mem_key] = res_dict

            # If stale: trigger background revalidation without blocking caller
            if is_stale:
                cls.schedule_background_revalidation(rec.id)

            return res_dict

        except Exception as e:
            logger.warning(f"Error checking resolved products cache for '{name}': {e}")
            return None
        finally:
            if close_db:
                db.close()

    @classmethod
    def schedule_background_revalidation(cls, rec_id: int):
        """Asynchronously dispatches a stale product revalidation worker."""
        try:
            cls._reval_executor.submit(cls.revalidate_product_entry, rec_id)
        except Exception as ex:
            logger.warning(f"Failed to submit background revalidation for record {rec_id}: {ex}")

    @classmethod
    def revalidate_product_entry(cls, rec_id: int, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Revalidates a single cached product against live search/evidence sources.
        Guarantees:
        - If unchanged: updates last_validated_at and increments validation_count.
        - If changed (Drift Detected): NEVER silently overwrites! Creates a PendingCatalogRule
          for Tier 4 human confirmation and logs a CatalogAuditLog event.
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            rec = db.query(ResolvedProductCache).filter(ResolvedProductCache.id == rec_id).first()
            if not rec:
                return {"status": "not_found", "rec_id": rec_id}

            logger.info(f"[StalenessRevalidator] Starting background revalidation for '{rec.canonical_product}'...")

            from backend.validation.searxng_evidence_validator import SearxngEvidenceValidator
            fresh_ev = SearxngEvidenceValidator.validate_application(
                app_name=rec.canonical_product,
                vendor=rec.canonical_vendor,
                version=None,
            )

            now = datetime.now(timezone.utc)

            # If external search returned no decisive evidence, don't degrade high-confidence data
            if not fresh_ev or fresh_ev.classification in ("UNKNOWN", None) or fresh_ev.evidence_status == "MISSING":
                rec.last_validated_at = now
                db.commit()
                return {
                    "status": "unmodified_no_new_evidence",
                    "product": rec.canonical_product,
                    "classification": rec.classification
                }

            is_drift = (
                fresh_ev.classification != rec.classification or
                (fresh_ev.license_required and fresh_ev.license_required != rec.license_required)
            )

            if not is_drift:
                # Confirmed unchanged!
                rec.last_validated_at = now
                rec.validation_count = (rec.validation_count or 1) + 1
                if fresh_ev.evidence_url:
                    rec.evidence_url = fresh_ev.evidence_url
                if fresh_ev.evidence_quote:
                    rec.evidence_quote = fresh_ev.evidence_quote
                db.commit()

                # Refresh in-memory entry
                mem_key = cls._make_key(rec.normalized_name, rec.normalized_vendor, rec.version_bucket)
                with cls._lock:
                    if mem_key in cls._mem_cache:
                        cls._mem_cache[mem_key].update(rec.to_dict())

                logger.info(f"[StalenessRevalidator] Confirmed unchanged: '{rec.canonical_product}' is still {rec.classification}.")
                return {
                    "status": "confirmed_unchanged",
                    "product": rec.canonical_product,
                    "classification": rec.classification,
                    "validation_count": rec.validation_count,
                }
            else:
                # DRIFT DETECTED: terms may have changed! DO NOT silently overwrite!
                rule_id = f"drift_{uuid.uuid4().hex[:8]}"
                diff_summary = f"Cached: {rec.classification} ({rec.license_required}) -> Revalidation Detected: {fresh_ev.classification} ({fresh_ev.license_required})"

                # Stage to Tier 4 Human Review
                pending_rule = PendingCatalogRule(
                    rule_id=rule_id,
                    signature_id=f"staleness:{rec.normalized_name}:{rec.normalized_vendor}",
                    matched_pattern=rec.canonical_product,
                    canonical_name=rec.canonical_product,
                    vendor=rec.canonical_vendor,
                    license_type=fresh_ev.classification,
                    license_required=fresh_ev.license_required or "YES",
                    metric=fresh_ev.license_model or rec.metric or "NOT_APPLICABLE",
                    tier=1 if fresh_ev.classification in ("COMMERCIAL", "FREE_AND_PAID") else 2,
                    evidence_url=fresh_ev.evidence_url,
                    evidence_quote=fresh_ev.evidence_quote,
                    resolved_by="staleness_revalidator",
                    confidence="staleness_drift_detected",
                    scope="exact_match",
                    status="pending_review",
                    occurrence_count=rec.validation_count or 1,
                    diff_preview=diff_summary,
                )
                db.add(pending_rule)

                # Write Audit Trail
                audit_log = CatalogAuditLog(
                    action="staleness_drift_flagged",
                    rule_id=rule_id,
                    rule_json=json.dumps({
                        "product": rec.canonical_product,
                        "vendor": rec.canonical_vendor,
                        "old_classification": rec.classification,
                        "new_classification": fresh_ev.classification,
                        "old_required": rec.license_required,
                        "new_required": fresh_ev.license_required,
                    }),
                    performed_by="staleness_revalidator",
                    details=f"Staleness revalidation detected license drift for '{rec.canonical_product}'. {diff_summary}. Routed to Tier 4 for human review.",
                )
                db.add(audit_log)

                # Flag cache entry with review notice
                rec.override_reason = f"Staleness drift flagged: was {rec.classification}, revalidation suggested {fresh_ev.classification} (Pending Tier 4 Review)"
                rec.last_validated_at = now
                db.commit()

                logger.warning(f"[StalenessRevalidator] DRIFT DETECTED for '{rec.canonical_product}': {diff_summary}. Routed to Tier 4 review.")
                return {
                    "status": "drift_flagged_to_tier4",
                    "product": rec.canonical_product,
                    "rule_id": rule_id,
                    "diff": diff_summary,
                }

        except Exception as e:
            logger.exception(f"Error during revalidation of record {rec_id}: {e}")
            return {"status": "error", "rec_id": rec_id, "error": str(e)}
        finally:
            if close_db:
                db.close()

    @classmethod
    def revalidate_all_stale_entries(cls, max_entries: int = 20, max_age_days: int = DEFAULT_CACHE_TTL_DAYS, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Executes a scheduled or triggerable batch sweep of stale cache entries.
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            now = datetime.now(timezone.utc)
            cutoff_date = now - timedelta(days=max_age_days)

            stale_records = db.query(ResolvedProductCache).filter(
                ResolvedProductCache.last_validated_at < cutoff_date
            ).limit(max_entries).all()

            results = []
            for r in stale_records:
                res = cls.revalidate_product_entry(r.id, db=db)
                results.append(res)

            return {
                "total_stale_found": len(stale_records),
                "processed_count": len(results),
                "details": results,
            }
        finally:
            if close_db:
                db.close()

    @classmethod
    def upsert_resolution(
        cls,
        record: Dict[str, Any],
        evidence_source: str,
        raw_name: Optional[str] = None,
        raw_vendor: Optional[str] = None,
        version_bucket: Optional[str] = "ANY",
        engine_version: str = ENGINE_VERSION,
        db: Optional[Session] = None,
    ) -> None:
        """
        Saves or updates a resolved product record into the global persistent cache.
        """
        app_name = raw_name or record.get("application") or ""
        vend_name = raw_vendor or record.get("vendor") or ""
        classification = record.get("classification")

        if not app_name or classification in ("UNKNOWN", None, ""):
            return

        mem_key = cls._make_key(app_name, vend_name, version_bucket)
        norm_name, norm_vend, v_bucket = mem_key

        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            rec = db.query(ResolvedProductCache).filter(
                ResolvedProductCache.normalized_name == norm_name,
                ResolvedProductCache.normalized_vendor == (norm_vend or None),
                ResolvedProductCache.version_bucket == v_bucket,
            ).first()

            now = datetime.now(timezone.utc)
            canonical_app = record.get("application") or app_name
            canonical_vend = record.get("vendor") or vend_name or "Unknown"

            if rec:
                rec.canonical_product = canonical_app
                rec.canonical_vendor = canonical_vend
                rec.classification = classification
                rec.availability = record.get("availability")
                rec.license_required = record.get("license_required", "NO")
                rec.license_model = record.get("license_model")
                rec.license_metric = record.get("metric") or record.get("license_metric")
                rec.metric = record.get("metric") or record.get("license_metric")
                rec.parent_product = record.get("parent_product")
                rec.confidence = record.get("confidence")
                rec.reliability_score = record.get("reliability_score", 0.0)
                rec.reliability_str = record.get("reliability_str")
                rec.evidence_source = evidence_source
                rec.evidence_status = record.get("evidence_status", "VERIFIED")
                rec.evidence_url = record.get("source_url") or record.get("primary_source_url") or record.get("evidence_url")
                rec.evidence_quote = record.get("evidence_quote")
                rec.override_reason = record.get("override_reason")
                rec.resolution_engine_version = engine_version
                rec.last_validated_at = now
                rec.validation_count = (rec.validation_count or 1) + 1
            else:
                rec = ResolvedProductCache(
                    normalized_name=norm_name,
                    normalized_vendor=norm_vend or None,
                    version_bucket=v_bucket,
                    canonical_product=canonical_app,
                    canonical_vendor=canonical_vend,
                    classification=classification,
                    availability=record.get("availability"),
                    license_required=record.get("license_required", "NO"),
                    license_model=record.get("license_model"),
                    license_metric=record.get("metric") or record.get("license_metric"),
                    metric=record.get("metric") or record.get("license_metric"),
                    parent_product=record.get("parent_product"),
                    confidence=record.get("confidence"),
                    reliability_score=record.get("reliability_score", 0.0),
                    reliability_str=record.get("reliability_str"),
                    evidence_source=evidence_source,
                    evidence_status=record.get("evidence_status", "VERIFIED"),
                    evidence_url=record.get("source_url") or record.get("primary_source_url") or record.get("evidence_url"),
                    evidence_quote=record.get("evidence_quote"),
                    override_reason=record.get("override_reason"),
                    resolution_engine_version=engine_version,
                    first_resolved_at=now,
                    last_validated_at=now,
                    validation_count=1,
                )
                db.add(rec)

            db.commit()

            # Update memory cache
            saved_dict = rec.to_dict()
            with cls._lock:
                cls._mem_cache[mem_key] = saved_dict

        except Exception as e:
            db.rollback()
            logger.warning(f"Failed to upsert resolved product cache for '{app_name}': {e}")
        finally:
            if close_db:
                db.close()

    @classmethod
    def get_stats(cls, db: Optional[Session] = None) -> Dict[str, Any]:
        """Returns rich health statistics on the persistent resolved product cache."""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            total_cached = db.query(ResolvedProductCache).count()
            by_source = {}
            source_counts = db.query(
                ResolvedProductCache.evidence_source,
                func.count(ResolvedProductCache.id)
            ).group_by(ResolvedProductCache.evidence_source).all()

            for src, cnt in source_counts:
                by_source[src or "UNKNOWN"] = cnt

            by_class = {}
            class_counts = db.query(
                ResolvedProductCache.classification,
                func.count(ResolvedProductCache.id)
            ).group_by(ResolvedProductCache.classification).all()

            for cls_name, cnt in class_counts:
                by_class[cls_name or "UNKNOWN"] = cnt

            # Count stale entries
            now = datetime.now(timezone.utc)
            cutoff_date = now - timedelta(days=DEFAULT_CACHE_TTL_DAYS)
            stale_count = db.query(ResolvedProductCache).filter(
                ResolvedProductCache.last_validated_at < cutoff_date
            ).count()

            # Count pending drift reviews
            drift_count = db.query(PendingCatalogRule).filter(
                PendingCatalogRule.status == "pending_review",
                PendingCatalogRule.resolved_by == "staleness_revalidator"
            ).count()

            with cls._lock:
                lookups = cls._cumulative_lookups
                hits = cls._cumulative_hits

            hit_rate_pct = round((hits / lookups) * 100.0, 2) if lookups > 0 else 0.0

            return {
                "total_cached_products": total_cached,
                "cumulative_lookups": lookups,
                "cumulative_hits": hits,
                "hit_rate_pct": hit_rate_pct,
                "stale_entries_count": stale_count,
                "drift_flagged_count": drift_count,
                "sources_breakdown": by_source,
                "classifications_breakdown": by_class,
                "memory_cache_size": len(cls._mem_cache),
            }
        except Exception as e:
            logger.warning(f"Error fetching cache stats: {e}")
            return {"total_cached_products": 0, "error": str(e)}
        finally:
            if close_db:
                db.close()
