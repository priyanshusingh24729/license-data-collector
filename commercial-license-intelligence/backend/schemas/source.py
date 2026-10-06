"""Pydantic schemas for the License Source Registry."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from backend.models.enums import (
    SourceType,
    AuthorityLevel,
    ScopeType,
    CollectionMethod,
    SourceStatus,
    AccessType,
)


class LicenseSourceBase(BaseModel):
    """Base schema for a license source."""
    vendor_name: str = Field(..., min_length=1, max_length=255, description="Vendor name (e.g. Adobe, Microsoft)")
    product_name: Optional[str] = Field(None, max_length=255, description="Specific product name if applicable")
    scope_type: ScopeType = Field(default=ScopeType.VENDOR, description="Scope of source applicability")
    scope_identifier: str = Field(..., min_length=1, max_length=255, description="Specific scope identifier matching scope_type")
    source_name: str = Field(..., min_length=1, max_length=255, description="Human-readable title of the source")
    source_type: SourceType = Field(default=SourceType.OFFICIAL_TERMS, description="Source classification")
    authority_level: AuthorityLevel = Field(default=AuthorityLevel.OFFICIAL_VENDOR, description="Authority ranking")
    official_domain: Optional[str] = Field(None, max_length=255, description="Expected official domain (e.g. adobe.com)")
    base_domain: Optional[str] = Field(None, max_length=255, description="Base domain extracted from URL")
    source_url: str = Field(..., description="Full URL of the licensing source")
    description: Optional[str] = Field(None, description="Descriptive context or notes about the source")
    is_active: bool = Field(default=True, description="Whether source is active for collection")
    is_public: bool = Field(default=True, description="Whether source is publicly accessible")
    status: SourceStatus = Field(default=SourceStatus.ACTIVE, description="Operational status of source")
    access_type: AccessType = Field(default=AccessType.PUBLIC, description="Access requirement tier")
    collection_method: CollectionMethod = Field(default=CollectionMethod.WEB, description="Intended collection approach")
    priority: int = Field(default=1, ge=1, le=100, description="Priority ranking (1 is highest)")


class LicenseSourceCreate(LicenseSourceBase):
    """Schema for registering a new license source."""
    pass


class LicenseSourceUpdate(BaseModel):
    """Schema for partially updating a license source."""
    vendor_name: Optional[str] = Field(None, min_length=1, max_length=255)
    product_name: Optional[str] = Field(None, max_length=255)
    scope_type: Optional[ScopeType] = None
    scope_identifier: Optional[str] = Field(None, min_length=1, max_length=255)
    source_name: Optional[str] = Field(None, min_length=1, max_length=255)
    source_type: Optional[SourceType] = None
    authority_level: Optional[AuthorityLevel] = None
    official_domain: Optional[str] = None
    base_domain: Optional[str] = None
    source_url: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None
    status: Optional[SourceStatus] = None
    access_type: Optional[AccessType] = None
    collection_method: Optional[CollectionMethod] = None
    priority: Optional[int] = Field(None, ge=1, le=100)


class LicenseSourceResponse(LicenseSourceBase):
    """Schema for returning license source details."""
    id: int
    normalized_url: str
    last_checked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SourceResolutionQuery(BaseModel):
    """Query parameters for source resolution."""
    vendor: str = Field(..., description="Target software vendor")
    product: Optional[str] = Field(None, description="Target product name")
    edition: Optional[str] = Field(None, description="Target product edition (e.g. Standard, Pro, Enterprise)")
    version: Optional[str] = Field(None, description="Target product version or release year (e.g. 2025, v12)")
    active_only: bool = Field(default=True, description="Whether to include only active sources")


class SourceResolutionResponse(BaseModel):
    """Response containing prioritized applicable sources."""
    vendor: str
    product: Optional[str] = None
    edition: Optional[str] = None
    version: Optional[str] = None
    total_sources: int
    sources: List[LicenseSourceResponse]
