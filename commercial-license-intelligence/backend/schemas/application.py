"""
Pydantic contracts and data schemas for Application Catalog, CSV Import, and Batch Research.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from backend.models.enums import (
    ApplicationStatus,
    ApplicationResearchStatus,
    BatchStatus,
    BatchItemStatus,
)


class ApplicationCreateRequest(BaseModel):
    """Payload to register a new application in the catalog."""
    vendor: str = Field(..., description="Software publisher (e.g. Adobe)")
    product: str = Field(..., description="Software product (e.g. Acrobat)")
    edition: Optional[str] = Field(None, description="Edition (e.g. Pro, Standard)")
    version: Optional[str] = Field(None, description="Version (e.g. 2025, 11.0)")
    operating_system: Optional[str] = Field(None, description="Target OS (e.g. Windows, macOS, Linux)")
    architecture: Optional[str] = Field(None, description="Architecture (e.g. x64, arm64)")
    display_name: Optional[str] = Field(None, description="Human readable display name")
    publisher: Optional[str] = Field(None, description="Publisher name if different from vendor")
    product_identifier: Optional[str] = Field(None, description="Vendor SKU or internal identifier")


class ApplicationResponse(BaseModel):
    """Cataloged software application response entity."""
    id: int
    vendor_name: str
    product_name: str
    display_name: Optional[str] = None
    edition: Optional[str] = None
    version: Optional[str] = None
    operating_system: Optional[str] = None
    architecture: Optional[str] = None
    publisher: Optional[str] = None
    product_identifier: Optional[str] = None
    application_key: str
    status: ApplicationStatus
    research_status: ApplicationResearchStatus
    current_profile_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CsvImportPreviewResponse(BaseModel):
    """Preview metrics and validation breakdown for CSV application imports."""
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    preview_records: List[Dict[str, Any]] = Field(default_factory=list)
    invalid_records: List[Dict[str, Any]] = Field(default_factory=list)


class CsvImportExecuteRequest(BaseModel):
    """Payload to execute an imported list of validated application records."""
    records: List[Dict[str, Any]]


class BatchResearchRequest(BaseModel):
    """Payload to launch a controlled batch research job."""
    application_ids: List[int] = Field(..., description="List of catalog application IDs to research")
    name: Optional[str] = Field(None, description="Optional batch job name")
    force_refresh: bool = Field(False, description="Whether to bypass cached license profiles")


class BatchItemDetail(BaseModel):
    """Individual item progress in a batch."""
    id: int
    application_id: int
    vendor_name: str
    product_name: str
    status: BatchItemStatus
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BatchResearchResponse(BaseModel):
    """Execution status and progress metrics for a batch research job."""
    batch_id: int
    name: str
    total: int
    queued: int
    running: int
    completed: int
    partial: int
    failed: int
    status: BatchStatus
    progress_percentage: float
    started_at: datetime
    completed_at: Optional[datetime] = None
    items: List[BatchItemDetail] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
