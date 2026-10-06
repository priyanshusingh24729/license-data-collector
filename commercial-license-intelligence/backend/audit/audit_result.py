"""
Pydantic schemas and contracts for Evidence Lineage, Fact/Profile Explanations, Quality Scoring, and Audit Trails.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from backend.models.enums import (
    AuditEventType,
    QualityCategory,
    QualityIssueType,
    AlertSeverity,
    IssueStatus,
    FactType,
    FactStatus,
    ExtractionConfidence,
    AuthorityLevel,
    LicensePositionStatus,
)


class AuditEventResponse(BaseModel):
    """Immutable audit event log record."""
    id: int
    entity_type: str
    entity_id: int
    event_type: AuditEventType
    actor_type: str
    actor_id: Optional[str] = None
    description: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    created_at: datetime


class SupportingFactSummary(BaseModel):
    """Discrete verified fact anchoring a consolidated license profile field."""
    fact_id: int
    fact_type: FactType
    value: str
    confidence: ExtractionConfidence
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    authority_level: Optional[AuthorityLevel] = None
    document_id: Optional[int] = None
    page_number: Optional[int] = None
    evidence_text: Optional[str] = None
    verified_at: Optional[datetime] = None


class ProfileFieldExplanationResponse(BaseModel):
    """Complete evidence justification for a specific profile attribute."""
    profile_id: int
    field: str
    value: Optional[str] = None
    confidence: ExtractionConfidence
    status: str
    supporting_facts: List[SupportingFactSummary] = Field(default_factory=list)


class FactExplanationResponse(BaseModel):
    """Exhaustive drill-down of an individual licensing fact and its evidence lineage."""
    fact_id: int
    fact_type: FactType
    fact_value: str
    normalized_value: str
    status: FactStatus
    confidence: ExtractionConfidence
    confidence_score: float

    # Scope
    vendor_name: str
    product_name: Optional[str] = None
    edition: Optional[str] = None
    version: Optional[str] = None

    # Source & Evidence Lineage
    source_id: Optional[int] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    authority_level: Optional[AuthorityLevel] = None
    document_id: Optional[int] = None
    document_url: Optional[str] = None
    page_number: Optional[int] = None
    section_name: Optional[str] = None
    evidence_text: Optional[str] = None
    evidence_hash: Optional[str] = None

    # Validation Checks
    validation_checks: Dict[str, Any] = Field(default_factory=dict)
    validation_reasons: List[str] = Field(default_factory=list)

    extracted_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None


class EvidenceChainResponse(BaseModel):
    """Unified multi-hop evidence chain for an application."""
    application_id: int
    vendor_name: str
    product_name: str
    edition: Optional[str] = None
    version: Optional[str] = None
    operating_system: Optional[str] = None
    profile_id: Optional[int] = None
    profile_status: str

    sources_count: int
    documents_count: int
    total_facts_count: int
    validated_facts_count: int

    lineage: List[Dict[str, Any]] = Field(default_factory=list)


class ApplicationQualityScoreResponse(BaseModel):
    """Deterministic quality scoring breakdown and critical field coverage."""
    application_id: int
    vendor_name: str
    product_name: str
    edition: Optional[str] = None
    version: Optional[str] = None

    quality_score: float
    quality_category: QualityCategory

    # Critical Field Coverage
    license_required_status: str
    license_model_status: str
    license_metric_status: str
    license_classification_status: str
    critical_field_coverage_percent: float

    # Source Freshness
    last_source_checked_at: Optional[datetime] = None
    days_since_last_check: Optional[int] = None
    is_source_stale: bool = False

    positive_factors: List[str] = Field(default_factory=list)
    negative_factors: List[str] = Field(default_factory=list)


class QualityDashboardSummaryResponse(BaseModel):
    """Aggregate metrics across entire application intelligence catalog."""
    total_applications: int
    excellent_count: int
    good_count: int
    fair_count: int
    poor_count: int
    insufficient_count: int
    average_quality_score: float
    critical_issues_count: int
    stale_sources_count: int
    conflicting_applications_count: int


class QualityIssueResponse(BaseModel):
    """Actionable data quality issue record."""
    id: int
    application_id: int
    vendor_name: str
    product_name: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    issue_type: QualityIssueType
    severity: AlertSeverity
    description: str
    status: IssueStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None


class PositionAuditResponse(BaseModel):
    """Structured, step-by-step arithmetic explanation of a license position."""
    application_id: int
    vendor_name: str
    product_name: str
    metric: str
    entitled_quantity: float
    consumed_quantity: float
    installed_devices_count: int
    available_quantity: float
    overdeployment_quantity: float
    position_status: LicensePositionStatus
    calculation_formula: str
    status_explanation: str
    calculation_version: str
    calculated_at: datetime


class ApplicationAuditTimelineResponse(BaseModel):
    """Chronological lifecycle events for an application."""
    application_id: int
    vendor_name: str
    product_name: str
    edition: Optional[str] = None
    version: Optional[str] = None
    events: List[AuditEventResponse] = Field(default_factory=list)
