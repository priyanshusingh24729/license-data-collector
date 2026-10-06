"""
Data schemas and contracts for the PDF & Official Document Collector.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from backend.models.enums import DocumentCollectionStatus, DocumentClassification


class PageContent(BaseModel):
    """Extracted text and metrics for a specific document page."""
    page_number: int = Field(..., ge=1, description="1-indexed page number")
    text: str = Field(..., description="Extracted textual content on this page")
    character_count: int = 0
    word_count: int = 0


class DocumentMetadata(BaseModel):
    """Extracted low-level metadata from PDF header/trailers."""
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    page_count: int = 0
    file_size_bytes: int = 0
    content_type: str = "application/pdf"
    sha256_hash: str
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None


class DocumentCollectionResult(BaseModel):
    """Structured result returned by PDF & Document collectors."""
    source_id: Optional[int] = None
    vendor_name: str
    requested_url: str
    final_url: str
    status: DocumentCollectionStatus
    classification: DocumentClassification = DocumentClassification.UNKNOWN
    text_extractable: bool = True
    ocr_required: bool = False
    metadata: Optional[DocumentMetadata] = None
    pages: List[PageContent] = Field(default_factory=list)
    clean_text: Optional[str] = None
    raw_file_path: Optional[str] = None
    error_message: Optional[str] = None
    is_cached_or_unchanged: bool = False

    model_config = ConfigDict(from_attributes=True)


class DocumentCollectionRequest(BaseModel):
    """Payload to trigger document collection for a registered source."""
    source_id: int = Field(..., description="Registered LicenseSource ID to collect")
    force_refresh: bool = Field(False, description="Force re-download even if already collected")


class DocumentSummaryResponse(BaseModel):
    """Summary schema for listing collected official documents."""
    id: int
    source_id: Optional[int] = None
    vendor_name: str
    requested_url: str
    final_url: str
    status: str
    document_classification: DocumentClassification
    title: Optional[str] = None
    page_count: Optional[int] = None
    file_size: Optional[int] = None
    content_hash: Optional[str] = None
    text_extractable: bool = True
    ocr_required: bool = False
    retrieved_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentPageResponse(BaseModel):
    """Response schema for a single extracted page."""
    page_number: int
    text: str
    character_count: int

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentSummaryResponse):
    """Detailed response schema with full clean text and page listings."""
    document_author: Optional[str] = None
    document_subject: Optional[str] = None
    clean_text: Optional[str] = None
    raw_storage_path: Optional[str] = None
    pages: List[DocumentPageResponse] = Field(default_factory=list)
