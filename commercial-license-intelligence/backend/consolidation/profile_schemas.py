"""
Pydantic contracts and data models for the License Knowledge Consolidation Engine.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from backend.models.enums import ProfileStatus, ExtractionConfidence, FactType


class ApplicationProfileRequest(BaseModel):
    """Payload to request or generate a consolidated application license profile."""
    vendor: str = Field(..., description="Software publisher (e.g. Adobe)")
    product: str = Field(..., description="Software product (e.g. Acrobat)")
    edition: Optional[str] = Field(None, description="Software edition (e.g. Pro, Standard)")
    version: Optional[str] = Field(None, description="Software version (e.g. 2025, 2020)")


class FieldExplanation(BaseModel):
    """Structured field-level explanation linking a consolidated value to supporting fact IDs."""
    value: str
    confidence: ExtractionConfidence
    supporting_fact_ids: List[int] = Field(default_factory=list)
    conflicting_values: Optional[List[str]] = None


class ProfileSummaryBlock(BaseModel):
    """Deterministic summary object for clean serialization."""
    required: str = "UNKNOWN"
    classification: str = "UNKNOWN"
    model: str = "UNKNOWN"
    metric: str = "UNKNOWN"
    duration: str = "UNKNOWN"


class LicenseProfileResponse(BaseModel):
    """Comprehensive application license intelligence profile response."""
    id: int
    vendor: str
    product: str
    edition: Optional[str] = None
    version: Optional[str] = None

    license_classification: str = "UNKNOWN"
    license_required: str = "UNKNOWN"
    license_model: str = "UNKNOWN"
    license_metric: str = "UNKNOWN"
    license_duration: str = "UNKNOWN"

    commercial_use: str = "UNKNOWN"
    educational_use: str = "UNKNOWN"
    trial_available: str = "UNKNOWN"

    overall_confidence: ExtractionConfidence
    profile_status: ProfileStatus

    validated_fact_count: int = 0
    review_fact_count: int = 0
    conflict_fact_count: int = 0
    unknown_fact_count: int = 0

    profile_hash: str
    explanations: Dict[str, FieldExplanation] = Field(default_factory=dict)
    supporting_facts: List[Dict[str, Any]] = Field(default_factory=list)

    license_summary: Optional[ProfileSummaryBlock] = None
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProfileVersionResponse(BaseModel):
    """Historical profile version snapshot."""
    id: int
    profile_id: int
    profile_hash: str
    profile_data: Dict[str, Any]
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)
