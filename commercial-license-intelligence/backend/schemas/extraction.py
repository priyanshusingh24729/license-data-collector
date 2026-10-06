"""
Pydantic schemas and contracts for the License Fact Extraction Engine.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from backend.models.enums import (
    FactType,
    FactStatus,
    EvidenceType,
    ExtractionConfidence,
    ExtractionRunStatus,
    ScopeType,
)


class ExtractedFactCandidate(BaseModel):
    """Candidate licensing fact extracted from text with verifiable evidence."""
    fact_type: FactType
    fact_value: str
    normalized_value: str
    scope_type: ScopeType = ScopeType.PRODUCT
    scope_value: str = "ALL"
    confidence: ExtractionConfidence = ExtractionConfidence.MEDIUM
    confidence_score: float = Field(0.7, ge=0.0, le=1.0)
    status: FactStatus = FactStatus.EXTRACTED
    evidence_text: str
    evidence_type: EvidenceType = EvidenceType.DIRECT_STATEMENT
    page_number: Optional[int] = None
    section_name: Optional[str] = None
    document_id: Optional[int] = None
    source_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ApplicationExtractionRequest(BaseModel):
    """Payload to request license intelligence extraction for an application target."""
    vendor: str = Field(..., description="Software publisher (e.g. Adobe)")
    product: str = Field(..., description="Software product (e.g. Acrobat)")
    edition: Optional[str] = Field(None, description="Software edition (e.g. Pro, Standard)")
    version: Optional[str] = Field(None, description="Software version (e.g. 2025, 11.0)")


class DocumentExtractionRequest(BaseModel):
    """Payload to trigger extraction on a single collected document."""
    document_id: int = Field(..., description="Collected document ID to extract from")
    target_product: Optional[str] = None
    target_edition: Optional[str] = None
    target_version: Optional[str] = None


class FactEvidenceResponse(BaseModel):
    """Evidence snippet details."""
    id: int
    source_id: Optional[int] = None
    document_id: Optional[int] = None
    page_number: Optional[int] = None
    section: Optional[str] = None
    evidence_text: str
    evidence_hash: str
    evidence_type: EvidenceType

    model_config = ConfigDict(from_attributes=True)


class FactSummaryResponse(BaseModel):
    """Structured fact summary response."""
    id: int
    vendor_name: str
    product_name: str
    edition: Optional[str] = None
    version: Optional[str] = None
    fact_type: FactType
    fact_value: str
    normalized_value: str
    scope_type: ScopeType
    scope_value: str
    confidence: ExtractionConfidence
    confidence_score: float
    status: FactStatus
    evidence_text: str
    page_number: Optional[int] = None
    section_name: Optional[str] = None
    source_id: Optional[int] = None
    document_id: Optional[int] = None
    extracted_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FactDetailResponse(FactSummaryResponse):
    """Detailed fact with linked evidence records."""
    evidence_records: List[FactEvidenceResponse] = Field(default_factory=list)


class FactConflictItem(BaseModel):
    """Contradiction record between two sources/facts."""
    fact_type: FactType
    values: List[str]
    conflicting_fact_ids: List[int]
    reasons: List[str]
    explanation: Optional[str] = None


class ApplicationLicenseIntelligenceResponse(BaseModel):
    """Consolidated high-level licensing intelligence response for an application target."""
    vendor: str
    product: str
    edition: Optional[str] = None
    version: Optional[str] = None
    classification: Optional[str] = "UNKNOWN"
    license_required: Optional[str] = "UNKNOWN"
    license_model: Optional[str] = "UNKNOWN"
    license_metric: Optional[str] = "UNKNOWN"
    license_duration: Optional[str] = "UNKNOWN"
    commercial_use: Optional[str] = "UNKNOWN"
    educational_use: Optional[str] = "UNKNOWN"
    trial_available: Optional[str] = "UNKNOWN"
    overall_confidence: ExtractionConfidence = ExtractionConfidence.UNKNOWN
    facts: List[FactSummaryResponse] = Field(default_factory=list)
    conflicts: List[FactConflictItem] = Field(default_factory=list)
    status: str = "COMPLETED"
    message: Optional[str] = None
