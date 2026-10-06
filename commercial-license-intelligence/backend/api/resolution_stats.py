"""
FastAPI router for Resolution Cache & Intelligence Pipeline Telemetry.
Provides comprehensive visibility into persistent cache hit rates, search engine utilization (SearXNG vs YaCy),
tier distributions, staleness monitoring, and background revalidation.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.connection import get_db
from backend.inventory.recognition.resolved_product_service import ResolvedProductService
from backend.models.resolved_product_cache import ENGINE_VERSION
from backend.models.inventory_upload import UploadLicenseResult

logger = logging.getLogger("resolution-stats-api")

router = APIRouter(prefix="/api/inventory", tags=["Inventory Resolution Telemetry"])


@router.get("/resolution-stats")
def get_resolution_statistics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns live operational statistics:
    - Cache hit rate %, cumulative lookups, and cumulative hits.
    - Stale cache entries and drift reviews pending.
    - Search engine metrics (SearXNG vs YaCy successes, failures, and cross-validation agreements).
    - Tier distribution breakdown & Tier 4 rate %.
    """
    cache_stats = ResolvedProductService.get_stats(db=db)
    
    # Check search engine metrics and circuit breakers
    search_metrics = {
        "total_queries": 0,
        "engine_success_counts": {},
        "engine_failure_counts": {},
        "cross_validated_agreements": 0,
    }
    circuit_breakers = {}
    try:
        from backend.sources.discovery.search_provider import get_search_provider, _GLOBAL_CHAIN_PROVIDER
        if _GLOBAL_CHAIN_PROVIDER is None:
            get_search_provider()
            from backend.sources.discovery.search_provider import _GLOBAL_CHAIN_PROVIDER as global_chain
        else:
            global_chain = _GLOBAL_CHAIN_PROVIDER

        if global_chain and hasattr(global_chain, "chain"):
            chain = global_chain.chain
            search_metrics.update(chain.metrics)
            circuit_breakers = chain.get_circuit_breaker_states()
        else:
            from backend.search_engines.chain import SearchEngineChain
            circuit_breakers = SearchEngineChain.get_persisted_states()
    except Exception as ex:
        logger.warning(f"Error fetching search telemetry: {ex}")
        try:
            from backend.search_engines.chain import SearchEngineChain
            circuit_breakers = SearchEngineChain.get_persisted_states()
        except Exception:
            pass

    # Tier breakdown across all uploaded software installations
    tier_stats = {}
    tier4_rate_pct = 0.0
    try:
        total_results = db.query(UploadLicenseResult).count()
        if total_results > 0:
            tier1 = db.query(UploadLicenseResult).filter(
                UploadLicenseResult.classification.in_(["COMMERCIAL", "FREE_AND_PAID"]),
                UploadLicenseResult.license_required.in_(["YES", "CONTEXT_DEPENDENT"])
            ).count()

            tier2 = db.query(UploadLicenseResult).filter(
                UploadLicenseResult.classification.in_(["OPEN_SOURCE", "FREEWARE"]),
                UploadLicenseResult.license_required.in_(["NO", "NOT_APPLICABLE", "FREE"])
            ).count()

            tier3 = db.query(UploadLicenseResult).filter(
                UploadLicenseResult.classification.in_([
                    "OS_BUNDLED", "OEM_OR_BUNDLED", "OEM", "LINUX_SYSTEM_PACKAGE",
                    "MACOS_SYSTEM_COMPONENT", "WEB_SHORTCUT_OR_PWA", "WEB_SHORTCUT/PWA",
                    "COMMERCIAL_COMPONENT", "RUNTIME_FRAMEWORK", "SHARED_COMPONENT"
                ])
            ).count()

            tier4 = db.query(UploadLicenseResult).filter(
                (UploadLicenseResult.classification == "UNKNOWN") |
                (UploadLicenseResult.evidence_status == "MISSING")
            ).count()

            tier4_rate_pct = round((tier4 / total_results) * 100.0, 2)

            tier_stats = {
                "total_installations_analyzed": total_results,
                "tier1_commercial_count": tier1,
                "tier2_open_source_count": tier2,
                "tier3_infrastructure_count": tier3,
                "tier4_needs_review_count": tier4,
                "tier4_rate_pct": tier4_rate_pct,
            }
    except Exception as ex:
        logger.warning(f"Error compiling tier statistics: {ex}")

    return {
        "status": "healthy",
        "engine_version": ENGINE_VERSION,
        "cache": cache_stats,
        "search_chain_telemetry": {
            **search_metrics,
            "circuit_breaker_states": circuit_breakers,
        },
        "tier_distribution": tier_stats,
    }


@router.post("/revalidate-stale")
def trigger_stale_revalidation_sweep(
    max_entries: int = Query(default=20, ge=1, le=100),
    max_age_days: int = Query(default=90, ge=1),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Triggers a batch revalidation sweep across stale cached software products.
    Confirmed unchanged products update validation counts; detected license drift is routed to Tier 4 review.
    """
    result = ResolvedProductService.revalidate_all_stale_entries(
        max_entries=max_entries,
        max_age_days=max_age_days,
        db=db,
    )
    return {
        "message": f"Stale revalidation sweep completed for {result.get('processed_count', 0)} entries.",
        "results": result,
    }
