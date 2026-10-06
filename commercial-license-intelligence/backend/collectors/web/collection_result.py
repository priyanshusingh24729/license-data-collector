"""
Data models and response contracts for the Web Content Collector.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from backend.models.enums import CollectionStatus


class DocumentSection(BaseModel):
    """Structured section within a collected document."""
    heading_level: str = Field("H2", description="Heading level e.g. H1, H2, H3")
    heading_text: str = Field(..., description="Text of the section heading")
    paragraphs: List[str] = Field(default_factory=list, description="Paragraph texts under this heading")
    lists: List[List[str]] = Field(default_factory=list, description="Bullet or numbered list items")
    raw_text: str = Field("", description="Consolidated textual content of the section")


class TableData(BaseModel):
    """Structured tabular data extracted from HTML tables."""
    caption: Optional[str] = None
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    markdown_repr: str = Field("", description="Markdown-formatted table string")


class HttpResponseMetadata(BaseModel):
    """HTTP response network metadata."""
    status_code: int
    content_type: str
    content_length: int = 0
    final_url: str
    redirect_chain: List[str] = Field(default_factory=list)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WebCollectionResult(BaseModel):
    """Comprehensive result object returned by WebCollector."""
    requested_url: str
    final_url: str
    vendor: str
    status: CollectionStatus
    http_metadata: Optional[HttpResponseMetadata] = None
    title: Optional[str] = None
    clean_text: Optional[str] = None
    markdown_content: Optional[str] = None
    is_rendered_spa: bool = False
    structured_sections: List[DocumentSection] = Field(default_factory=list)
    tables: List[TableData] = Field(default_factory=list)
    content_hash: Optional[str] = None
    raw_storage_path: Optional[str] = None
    word_count: int = 0
    character_count: int = 0
    error_message: Optional[str] = None
    is_cached_or_unchanged: bool = False
    discovered_sitemap_urls: List[str] = Field(default_factory=list)
    llms_txt_url: Optional[str] = None
    harvested_pdfs: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class WebCollectionRequest(BaseModel):
    """Request payload to trigger web content collection."""
    url: Optional[str] = Field(None, description="Direct URL to collect")
    source_id: Optional[int] = Field(None, description="Registered LicenseSource ID to collect")
    vendor: Optional[str] = Field(None, description="Vendor name for domain validation")
    expected_domain: Optional[str] = Field(None, description="Expected official domain")
    force_refresh: bool = Field(False, description="Force collection even if previously collected")


class CollectedDocumentSummaryResponse(BaseModel):
    """Summary schema for listing collected document evidence records."""
    id: int
    source_id: Optional[int] = None
    vendor_name: str
    requested_url: str
    final_url: str
    status: CollectionStatus
    http_status: Optional[int] = None
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    content_hash: Optional[str] = None
    title: Optional[str] = None
    retrieved_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CollectedDocumentDetailResponse(CollectedDocumentSummaryResponse):
    """Detailed schema including full clean text, sections, and tables."""
    clean_text: Optional[str] = None
    structured_sections: Optional[List[Dict[str, Any]]] = None
    tables_data: Optional[List[Dict[str, Any]]] = None
    redirect_chain: Optional[List[str]] = None
    raw_storage_path: Optional[str] = None
