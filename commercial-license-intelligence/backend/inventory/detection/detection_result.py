"""
Pydantic schemas and contracts for Endpoint Inventory Ingestion and Identity Resolution.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from backend.models.enums import (
    DeviceStatus,
    DetectedAppStatus,
    DetectionMethod,
    MatchType,
    ResolutionQueueStatus,
    ExtractionConfidence,
)


class DeviceIngestPayload(BaseModel):
    """Hardware endpoint identity metadata."""
    device_key: str = Field(..., description="Unique persistent identifier for the endpoint (e.g. UUID, serial)")
    hostname: Optional[str] = Field(None, description="Network hostname (e.g. LAPTOP-001)")
    operating_system: Optional[str] = Field(None, description="Operating system name (e.g. Windows, macOS, Linux)")
    os_version: Optional[str] = Field(None, description="OS release version (e.g. 11, 14.5)")
    architecture: Optional[str] = Field(None, description="CPU architecture (e.g. x64, arm64)")
    agent_version: Optional[str] = Field(None, description="Version of inventory collector agent")


class ApplicationIngestItem(BaseModel):
    """Raw software installation item reported by an endpoint."""
    name: str = Field(..., description="Raw application name as reported by OS/Registry")
    publisher: Optional[str] = Field(None, description="Raw publisher name")
    version: Optional[str] = Field(None, description="Raw installed version string")
    install_location: Optional[str] = Field(None, description="File system path of installation")
    install_source: Optional[str] = Field(None, description="Package origin (e.g. MSI, Homebrew, Apt)")
    architecture: Optional[str] = Field(None, description="Application architecture (e.g. 64-bit, 32-bit)")
    detection_method: DetectionMethod = Field(DetectionMethod.WINDOWS_REGISTRY, description="Detection source")


class InventoryIngestRequest(BaseModel):
    """Payload to ingest endpoint inventory from an agent or automated import."""
    device: DeviceIngestPayload
    applications: List[ApplicationIngestItem] = Field(..., min_length=1)


class IngestedApplicationSummary(BaseModel):
    """Summary of an ingested application and its resolution status."""
    raw_name: str
    normalized_name: str
    normalized_publisher: Optional[str] = None
    detected_version: Optional[str] = None
    resolution_type: MatchType
    resolution_confidence: ExtractionConfidence
    resolved_application_id: Optional[int] = None
    resolved_display_name: Optional[str] = None
    queue_id: Optional[int] = None


class InventoryIngestResponse(BaseModel):
    """Response detailing ingestion metrics and resolution outcomes."""
    device_id: int
    device_key: str
    total_reported: int
    resolved_count: int
    unresolved_count: int
    applications: List[IngestedApplicationSummary] = Field(default_factory=list)


class ResolutionCandidateDetail(BaseModel):
    """Candidate catalog application for an unresolved detection."""
    candidate_id: int
    vendor_name: str
    product_name: str
    edition: Optional[str] = None
    version: Optional[str] = None
    operating_system: Optional[str] = None
    match_score: float
    confidence: ExtractionConfidence
    reason: Optional[str] = None


class ResolutionQueueItemResponse(BaseModel):
    """Human review queue item for ambiguous or low-confidence matches."""
    queue_id: int
    detected_application_id: int
    device_key: str
    hostname: Optional[str] = None
    raw_name: str
    raw_publisher: Optional[str] = None
    raw_version: Optional[str] = None
    normalized_name: str
    operating_system: Optional[str] = None
    match_type: MatchType
    match_score: float
    confidence: ExtractionConfidence
    status: ResolutionQueueStatus
    created_at: datetime
    candidates: List[ResolutionCandidateDetail] = Field(default_factory=list)


class ManualResolveRequest(BaseModel):
    """Payload to manually accept, reject, or map an unresolved detection to a catalog application."""
    accepted_application_id: Optional[int] = Field(None, description="Catalog application ID to bind to")
    action: ResolutionQueueStatus = Field(ResolutionQueueStatus.ACCEPTED, description="ACCEPTED or REJECTED")


class InventoryCatalogAppSummary(BaseModel):
    """Catalog application with installation metrics and licensing intelligence status."""
    id: int
    vendor_name: str
    product_name: str
    edition: Optional[str] = None
    version: Optional[str] = None
    operating_system: Optional[str] = None
    installed_count: int = 0
    license_profile_id: Optional[int] = None
    license_classification: str = "UNKNOWN"
    license_model: str = "UNKNOWN"
    license_metric: str = "UNKNOWN"
    overall_confidence: ExtractionConfidence = ExtractionConfidence.UNKNOWN
    profile_status: str = "NOT_RESEARCHED"


class DeviceDetailResponse(BaseModel):
    """Detailed view of an endpoint device and its installed software."""
    id: int
    device_key: str
    hostname: Optional[str] = None
    operating_system: Optional[str] = None
    os_version: Optional[str] = None
    architecture: Optional[str] = None
    status: DeviceStatus
    last_seen_at: datetime
    installed_applications: List[Dict[str, Any]] = Field(default_factory=list)


class InstallationLicenseResultResponse(BaseModel):
    """Processed license intelligence record for machine-specific installation inventory."""
    id: int
    unique_id: str
    hostname: Optional[str] = None
    serial: Optional[str] = None
    ip_address: Optional[str] = None
    raw_application_name: str
    raw_vendor: Optional[str] = None
    raw_version: Optional[str] = None
    install_date: Optional[str] = None
    install_source: Optional[str] = None
    install_location: Optional[str] = None
    canonical_product: Optional[str] = None
    canonical_vendor: Optional[str] = None
    classification: Optional[str] = None
    license_requirement: Optional[str] = None
    license_model: Optional[str] = None
    license_metric: Optional[str] = None
    evidence_status: Optional[str] = None
    confidence: Optional[str] = None
    reliability_score: Optional[float] = None
    evidence_source: Optional[str] = None
    evidence_url: Optional[str] = None
    research_status: Optional[str] = None
    processed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MachineInventorySummaryResponse(BaseModel):
    """Summary of a machine with processed installation license results."""
    unique_id: str
    hostname: Optional[str] = None
    serial: Optional[str] = None
    ip_address: Optional[str] = None
    total_records: int
    processed_at: Optional[datetime] = None

