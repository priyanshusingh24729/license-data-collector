"""FastAPI endpoints for Automatic Official Source Discovery."""

import logging
import time
from typing import List, Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.config.settings import get_settings
from backend.database.connection import get_db
from backend.models.source import LicenseSource
from backend.models.discovery import DiscoveryRun
from backend.models.enums import (
    SourceType,
    AuthorityLevel,
    SourceStatus,
    DiscoveryStatus,
    DiscoveryRunStatus,
)
from backend.schemas.source import LicenseSourceResponse
from backend.schemas.discovery import (
    DiscoveryTargetRequest,
    DiscoveryExecutionResponse,
    DiscoveryRunResponse,
    SearchStatusResponse,
    SearchQueryRequest,
    SearchQueryResponse,
    SearchResultItem,
)
from backend.sources.discovery.search_provider import SearxngSearchProvider, get_search_provider
from backend.sources.discovery.discovery_engine import SourceDiscoveryEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discovery", tags=["Source Discovery"])


@router.post("/sources", response_model=DiscoveryExecutionResponse, status_code=status.HTTP_200_OK)
def trigger_source_discovery(
    target: DiscoveryTargetRequest,
    db: Session = Depends(get_db)
):
    """
    Executes automated discovery for a commercial software target.
    Discovers, validates official domains, ranks, and registers candidate official sources.
    """
    engine = SourceDiscoveryEngine()
    result = engine.run_discovery(db, target)
    return result


@router.get("/sources", response_model=List[LicenseSourceResponse])
def get_discovered_sources(
    vendor: Optional[str] = Query(None, description="Filter by vendor"),
    product: Optional[str] = Query(None, description="Filter by product"),
    status_filter: Optional[SourceStatus] = Query(None, alias="status", description="Filter by source status"),
    discovery_status: Optional[DiscoveryStatus] = Query(None, description="Filter by discovery status"),
    authority: Optional[AuthorityLevel] = Query(None, description="Filter by authority level"),
    source_type: Optional[SourceType] = Query(None, description="Filter by source type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Retrieve automatically discovered and registered sources."""
    query = db.query(LicenseSource)

    if vendor:
        query = query.filter(func.lower(LicenseSource.vendor_name) == vendor.strip().lower())
    if product:
        query = query.filter(func.lower(LicenseSource.product_name) == product.strip().lower())
    if status_filter:
        query = query.filter(LicenseSource.status == status_filter)
    if discovery_status:
        query = query.filter(LicenseSource.discovery_status == discovery_status)
    if authority:
        query = query.filter(LicenseSource.authority_level == authority)
    if source_type:
        query = query.filter(LicenseSource.source_type == source_type)

    return query.order_by(
        LicenseSource.relevance_score.desc().nullslast(),
        LicenseSource.priority.asc(),
        LicenseSource.id.asc()
    ).offset(skip).limit(limit).all()


@router.get("/sources/{source_id}", response_model=LicenseSourceResponse)
def get_discovered_source(source_id: int, db: Session = Depends(get_db)):
    """Retrieve details for a single discovered source."""
    src = db.query(LicenseSource).filter(LicenseSource.id == source_id).first()
    if not src:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source candidate with ID {source_id} not found."
        )
    return src


@router.get("/runs", response_model=List[DiscoveryRunResponse])
def list_discovery_runs(
    vendor: Optional[str] = Query(None),
    status_filter: Optional[DiscoveryRunStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Retrieve historical records of automatic discovery executions."""
    query = db.query(DiscoveryRun)
    if vendor:
        query = query.filter(func.lower(DiscoveryRun.vendor_name) == vendor.strip().lower())
    if status_filter:
        query = query.filter(DiscoveryRun.status == status_filter)

    return query.order_by(DiscoveryRun.id.desc()).offset(skip).limit(limit).all()


@router.get("/runs/{run_id}", response_model=DiscoveryRunResponse)
def get_discovery_run(run_id: int, db: Session = Depends(get_db)):
    """Retrieve status and metrics for a specific discovery run."""
    run_record = db.query(DiscoveryRun).filter(DiscoveryRun.id == run_id).first()
    if not run_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discovery run with ID {run_id} not found."
        )
    return run_record


@router.get("/search/status", response_model=SearchStatusResponse)
def get_search_engine_status():
    """
    Returns live connectivity and health metrics for the active search provider (SearXNG).
    Pings SEARXNG_BASE_URL to determine if the local/remote instance is operational.
    """
    settings = get_settings()
    provider_name = (settings.SEARCH_PROVIDER or "SearXNG").strip()
    base_url = getattr(settings, "SEARXNG_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
    categories = getattr(settings, "SEARXNG_CATEGORIES", "general,it")
    engines = getattr(settings, "SEARXNG_ENGINES", None)
    fallback_available = getattr(settings, "ENABLE_DEV_SEARCH_FALLBACK", True)

    is_online = False
    latency_ms = None
    status_msg = "Unknown"

    start_t = time.time()
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{base_url}/search", params={"q": "ping", "format": "json"})
            latency_ms = round((time.time() - start_t) * 1000, 1)
            if resp.status_code == 200:
                is_online = True
                status_msg = f"SearXNG is online and responding ({latency_ms}ms)."
            else:
                status_msg = f"SearXNG returned HTTP {resp.status_code}. Format JSON may need to be enabled."
    except Exception as e:
        latency_ms = round((time.time() - start_t) * 1000, 1)
        if fallback_available:
            status_msg = f"SearXNG offline ({type(e).__name__}). DevSearchProvider fallback active."
        else:
            status_msg = f"SearXNG offline ({type(e).__name__}). No fallback available."

    return SearchStatusResponse(
        provider=provider_name,
        base_url=base_url,
        is_online=is_online,
        latency_ms=latency_ms,
        categories=categories,
        engines=engines,
        fallback_available=fallback_available,
        status_message=status_msg,
    )


@router.post("/search/query", response_model=SearchQueryResponse)
def execute_search_query(req: SearchQueryRequest):
    """
    Executes an on-demand search query via the resilient 3-Engine Search Chain
    (SearXNG -> YaCy -> DuckDuckGo -> Dev fallback) and routes top results through
    the Modern Web Ingestion layer (Trafilatura & Headless Browser Fallback).
    """
    provider = get_search_provider()
    start_t = time.time()
    results = provider.search(req.query, num_results=req.num_results)

    items: List[SearchResultItem] = []
    primary_md: Optional[str] = None
    primary_tbls: List[str] = []
    ingested = False

    for idx, r in enumerate(results):
        scraped_md = None
        scraped_tbls = []
        is_spa = False

        # Ingest the top 1-2 authoritative results if requested
        if req.ingest_content and idx < 2 and r.url.startswith("http"):
            try:
                from backend.collectors.web.web_collector import WebCollector
                collector = WebCollector()
                collection = collector.collect(r.url)
                if collection.clean_text:
                    scraped_md = collection.markdown_content or collection.clean_text
                    is_spa = collection.is_rendered_spa
                    for tbl in collection.tables:
                        if tbl.markdown_repr:
                            scraped_tbls.append(tbl.markdown_repr)
                    if idx == 0:
                        primary_md = scraped_md[:2000] if scraped_md else None
                        primary_tbls = scraped_tbls
                        ingested = True
            except Exception as e:
                logger.warning(f"Failed to ingest {r.url}: {e}")

        items.append(
            SearchResultItem(
                url=r.url,
                title=r.title,
                snippet=r.snippet,
                engine=r.engine,
                rank=r.rank,
                scraped_markdown=scraped_md[:1000] if scraped_md else None,
                scraped_tables=scraped_tbls,
                is_spa_rendered=is_spa,
            )
        )

    latency_ms = round((time.time() - start_t) * 1000, 1)
    engine_types = set(r.engine for r in results)
    provider_used = f"Search Chain ({', '.join(sorted(engine_types))})" if results else "Search Chain (0 results)"

    return SearchQueryResponse(
        query=req.query,
        total_results=len(items),
        latency_ms=latency_ms,
        provider_used=provider_used,
        ingestion_layer_used=ingested,
        results=items,
        primary_markdown_evidence=primary_md,
        primary_tables=primary_tbls,
    )
