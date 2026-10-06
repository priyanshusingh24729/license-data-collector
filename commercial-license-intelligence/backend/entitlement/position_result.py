"""
Pydantic schemas and contracts for License Entitlements, Consumption, and Position Calculations.
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from backend.models.enums import (
    EntitlementType,
    EntitlementStatus,
    EntitlementSourceType,
    LicensePositionStatus,
    LicenseMetricValue,
)


class EntitlementCreateRequest(BaseModel):
    """Payload to create an official license entitlement record."""
    application_id: Optional[int] = Field(None, description="Catalog application ID (if known)")
    vendor_name: str = Field(..., description="Software publisher/vendor (e.g. Adobe)")
    product_name: str = Field(..., description="Software product (e.g. Acrobat)")
    edition: Optional[str] = Field(None, description="Software edition (e.g. Pro)")
    version: Optional[str] = Field(None, description="Version or release (e.g. 2025)")
    entitlement_type: EntitlementType = Field(EntitlementType.PURCHASED, description="PURCHASED, SUBSCRIBED, etc.")
    quantity: float = Field(..., ge=0, description="Licensed quantity (non-negative)")
    metric: str = Field(..., description="License metric: NAMED_USER, DEVICE, INSTALLATION, CORE, etc.")
    license_start_date: Optional[datetime] = Field(None, description="Validity start date")
    license_end_date: Optional[datetime] = Field(None, description="Validity expiration date")
    agreement_id: Optional[str] = Field(None, description="Agreement identifier")
    contract_reference: Optional[str] = Field(None, description="Contract or purchase order reference")
    source_type: EntitlementSourceType = Field(EntitlementSourceType.MANUAL_ENTRY, description="Origin of record")
    source_reference: Optional[str] = Field(None, description="Source citation")


class EntitlementResponse(BaseModel):
    """Response model representing a registered license entitlement."""
    id: int
    application_id: int
    vendor_name: str
    product_name: str
    edition: Optional[str] = None
    version: Optional[str] = None
    entitlement_type: EntitlementType
    quantity: float
    metric: str
    license_start_date: Optional[datetime] = None
    license_end_date: Optional[datetime] = None
    agreement_id: Optional[str] = None
    contract_reference: Optional[str] = None
    source_type: EntitlementSourceType
    source_reference: Optional[str] = None
    status: EntitlementStatus
    created_at: datetime


class ConsumptionCreateRequest(BaseModel):
    """Payload to record measured license consumption."""
    application_id: int
    consumption_metric: str = Field(..., description="NAMED_USER, DEVICE, INSTALLATION, etc.")
    consumption_quantity: float = Field(1.0, gt=0, description="Quantity consumed")
    user_reference: Optional[str] = Field(None, description="Pseudonymous user identifier (e.g. USER-001)")
    device_reference: Optional[str] = Field(None, description="Device identifier or hostname")
    device_id: Optional[int] = None
    detected_application_id: Optional[int] = None
    source_type: str = "MANUAL_ASSIGNMENT"
    source_reference: Optional[str] = None


class ConsumptionResponse(BaseModel):
    """Response model for a recorded consumption event."""
    id: int
    application_id: int
    consumption_metric: str
    consumption_quantity: float
    user_reference: Optional[str] = None
    device_reference: Optional[str] = None
    device_id: Optional[int] = None
    status: str
    created_at: datetime


class LicensePositionResponse(BaseModel):
    """Calculated license position for an application."""
    application_id: int
    vendor_name: str
    product_name: str
    edition: Optional[str] = None
    version: Optional[str] = None
    operating_system: Optional[str] = None

    # Licensing Intelligence Context
    profile_license_model: str = "UNKNOWN"
    profile_license_metric: str = "UNKNOWN"

    # Reconciliation Metrics
    metric: Optional[str] = None
    entitled_quantity: Optional[float] = None
    consumed_quantity: Optional[float] = None
    installed_devices_count: int = 0
    available_quantity: Optional[float] = None
    overdeployment_quantity: Optional[float] = None

    # Status
    position_status: LicensePositionStatus
    status_reason: Optional[str] = None
    calculated_at: datetime
    calculation_version: str = "1.0.0"


class LicensePositionHistoryResponse(BaseModel):
    """Historical snapshot record of position calculation."""
    id: int
    application_id: int
    metric: Optional[str] = None
    entitled_quantity: Optional[float] = None
    consumed_quantity: Optional[float] = None
    available_quantity: Optional[float] = None
    overdeployment_quantity: Optional[float] = None
    position_status: LicensePositionStatus
    status_reason: Optional[str] = None
    calculated_at: datetime
    calculation_version: str
