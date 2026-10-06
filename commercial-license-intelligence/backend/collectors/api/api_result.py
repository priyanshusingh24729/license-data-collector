"""
Data schemas and contracts for the Optional Vendor API Collector.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field
from backend.models.enums import ApiCollectionStatus, AccessType, AuthenticationType


class ApiFetchResult(BaseModel):
    """Low-level HTTP fetch payload returned by ApiClient."""
    status: ApiCollectionStatus
    status_code: Optional[int] = None
    content_type: str = "application/json"
    response_bytes: bytes = b""
    response_text: str = ""
    parsed_json: Optional[Any] = None
    response_hash: str = ""
    response_size_bytes: int = 0
    error_message: Optional[str] = None


class ApiCollectionResult(BaseModel):
    """Structured result returned by ApiCollector after processing."""
    source_id: Optional[int] = None
    vendor_name: str
    request_url: str
    http_method: str = "GET"
    status: ApiCollectionStatus
    http_status: Optional[int] = None
    content_type: Optional[str] = None
    response_size: Optional[int] = None
    response_hash: Optional[str] = None
    raw_response_text: Optional[str] = None
    parsed_json: Optional[Any] = None
    is_cached_or_unchanged: bool = False
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ApiCollectionRequest(BaseModel):
    """Payload to trigger API collection for a registered source."""
    source_id: int = Field(..., description="Registered LicenseSource ID with collection_method=API")
    force_refresh: bool = Field(False, description="Force request even if cached response exists")


class ApiSourceStatusResponse(BaseModel):
    """Status metadata for an API source without exposing any secrets."""
    source_id: int
    vendor_name: str
    source_name: str
    api_url: str
    access_type: AccessType
    authentication_type: AuthenticationType
    credentials_configured: bool = Field(..., description="True if required credentials are present in env")
    last_collection_status: Optional[str] = None
    last_collection_time: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ApiDocumentSummaryResponse(BaseModel):
    """Summary schema for listing collected API evidence."""
    id: int
    source_id: Optional[int] = None
    vendor_name: str
    request_url: str
    http_method: str
    response_status: Optional[int] = None
    content_type: Optional[str] = None
    response_size: Optional[int] = None
    response_hash: Optional[str] = None
    collection_status: ApiCollectionStatus
    retrieved_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApiDocumentDetailResponse(ApiDocumentSummaryResponse):
    """Detailed response schema with raw payload and parsed JSON structure."""
    response_body: Optional[str] = None
    parsed_json: Optional[Any] = None
    error_message: Optional[str] = None
