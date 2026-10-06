"""Pydantic schemas for Automatic Source Discovery."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from backend.models.enums import (
    SourceType,
    AuthorityLevel,
    ScopeType,
    CollectionMethod,
    AccessType,
    DiscoveryStatus,
    DiscoveryRunStatus,
    DomainValidationStatus,
    RelevanceTier,
)


class DiscoveryTargetRequest(BaseModel):
    """Input payload to trigger official license source discovery."""
    vendor: str = Field(..., min_length=1, max_length=255, description="Software vendor or publisher (e.g. Adobe)")
    product: Optional[str] = Field(None, max_length=255, description="Product name (e.g. Acrobat)")
    edition: Optional[str] = Field(None, max_length=255, description="Product edition (e.g. Pro)")
    version: Optional[str] = Field(None, max_length=255, description="Product version or release (e.g. 2025)")
    os: Optional[str] = Field(None, max_length=50, description="Operating system environment (e.g. Windows)")
    max_queries: int = Field(default=10, ge=1, le=25, description="Maximum search queries to generate and execute")
    store_discovered: bool = Field(default=True, description="Whether to persist accepted candidates into license_sources")


class DiscoveredSourceCandidate(BaseModel):
    """Structured result representing an automatically discovered source candidate."""
    source_url: str
    normalized_url: str
    source_title: str
    source_type: SourceType
    authority_level: AuthorityLevel
    official_domain: Optional[str] = None
    base_domain: Optional[str] = None
    domain_status: DomainValidationStatus
    relevance_score: int = Field(..., ge=0, le=100)
    relevance_tier: RelevanceTier
    ranking_reasons: List[str] = []
    discovery_method: str = "SEARCH"
    matched_vendor: bool = False
    matched_product: bool = False
    matched_edition: bool = False
    matched_version: bool = False
    scope_type: ScopeType = ScopeType.VENDOR
    scope_identifier: str = ""
    collection_method: CollectionMethod = CollectionMethod.WEB
    access_type: AccessType = AccessType.PUBLIC
    discovery_timestamp: datetime
    is_existing: bool = False
    existing_source_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class DiscoveryExecutionResponse(BaseModel):
    """Response payload detailing the execution results of source discovery."""
    run_id: Optional[int] = None
    status: DiscoveryRunStatus
    vendor: str
    product: Optional[str] = None
    edition: Optional[str] = None
    version: Optional[str] = None
    os: Optional[str] = None
    queries_executed: int = 0
    sources_found: int = 0
    sources_accepted: int = 0
    sources_rejected: int = 0
    candidates: List[DiscoveredSourceCandidate] = []
    message: Optional[str] = None


class DiscoveryRunResponse(BaseModel):
    """Schema representing a persistent discovery run record."""
    id: int
    vendor_name: str
    product_name: Optional[str] = None
    edition: Optional[str] = None
    version: Optional[str] = None
    os: Optional[str] = None
    status: DiscoveryRunStatus
    queries_executed: int
    sources_found: int
    sources_accepted: int
    sources_rejected: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    details: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SearchStatusResponse(BaseModel):
    """Schema representing live status and diagnostics of the search provider."""
    provider: str
    base_url: str
    is_online: bool
    latency_ms: Optional[float] = None
    categories: Optional[str] = None
    engines: Optional[str] = None
    fallback_available: bool = True
    status_message: str
    trafilatura_active: bool = True
    headless_browser_active: bool = True


class SearchResultItem(BaseModel):
    """Schema for individual search item returned in test queries."""
    url: str
    title: str
    snippet: Optional[str] = None
    engine: str = "unknown"
    rank: int = 1
    scraped_markdown: Optional[str] = None
    scraped_tables: List[str] = Field(default_factory=list)
    is_spa_rendered: bool = False


class SearchQueryRequest(BaseModel):
    """Input payload to execute a test query via SearXNG."""
    query: str = Field(..., min_length=1, max_length=500, description="Search query string")
    num_results: int = Field(default=5, ge=1, le=20, description="Number of results to retrieve")
    categories: Optional[str] = Field(None, description="Comma-separated category filters (e.g. 'general,it')")
    engines: Optional[str] = Field(None, description="Comma-separated engine filters (e.g. 'google,bing,duckduckgo')")
    ingest_content: bool = Field(default=False, description="Ingest top results via Trafilatura & Headless Browser")


class SearchQueryResponse(BaseModel):
    """Response payload containing search query execution results."""
    query: str
    total_results: int
    latency_ms: float
    provider_used: str
    ingestion_layer_used: bool = False
    results: List[SearchResultItem] = []
    primary_markdown_evidence: Optional[str] = None
    primary_tables: List[str] = Field(default_factory=list)
