"""
Data schemas and validation contracts for the Evidence Validation & Quality Engine.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from backend.models.enums import FactStatus, ExtractionConfidence, FactType


class ValidationChecks(BaseModel):
    """Granular verification results for individual validation criteria."""
    evidence_exists: bool = False
    evidence_text_matched: bool = False
    product_match: bool = False
    edition_match: bool = False
    version_match: bool = False
    source_authority: bool = False
    temporal_match: bool = True
    direct_evidence: bool = True


class FactValidationResult(BaseModel):
    """Detailed validation evaluation for a single LicenseFact."""
    fact_id: int
    status: FactStatus
    quality: ExtractionConfidence
    quality_score: float = Field(..., ge=0.0, le=1.0)
    checks: ValidationChecks
    reasons: List[str] = Field(default_factory=list)
    validator_version: str = "1.0.0"
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


class FactValidationDetailResponse(BaseModel):
    """API response schema for fact validation audit details."""
    fact_id: int
    vendor_name: str
    product_name: str
    edition: Optional[str] = None
    version: Optional[str] = None
    fact_type: FactType
    normalized_value: str
    status: FactStatus
    quality: ExtractionConfidence
    quality_score: float
    checks: ValidationChecks
    reasons: List[str]
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    document_id: Optional[int] = None
    page_number: Optional[int] = None
    evidence_text: str
    validator_version: str
    validated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationValidationSummaryResponse(BaseModel):
    """Summary metrics and quality audit for an application target."""
    vendor: str
    product: str
    edition: Optional[str] = None
    version: Optional[str] = None
    total_facts: int
    validated: int
    review_required: int
    conflicts: int
    rejected: int
    superseded: int
    unknown: int
    overall_quality: ExtractionConfidence
    facts_summary: List[Dict[str, Any]] = Field(default_factory=list)
    review_queue: List[Dict[str, Any]] = Field(default_factory=list)
