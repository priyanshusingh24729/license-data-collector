"""
Pydantic schemas for Step 18 Evidence Validation and Explanation.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class EvidenceLineageResponse(BaseModel):
    """Evidence record with complete audit lineage."""
    id: int
    fact_id: int
    source_url: Optional[str] = None
    source_domain: Optional[str] = None
    source_type: Optional[str] = None
    document_title: Optional[str] = None
    page_number: Optional[int] = None
    section: Optional[str] = None
    evidence_text: str
    authority_level: Optional[str] = None
    collected_at: Optional[datetime] = None
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    validation_status: Optional[str] = None


class ReliabilityBreakdownResponse(BaseModel):
    """Granular 6-dimension reliability sub-scores."""
    identity_quality: float = Field(..., description="0-100 score on product identity clarity")
    source_authority: float = Field(..., description="0-100 score on vendor source authority tier")
    evidence_directness: float = Field(..., description="0-100 score on directness of licensing citation")
    scope_quality: float = Field(..., description="0-100 score on edition and version applicability")
    validation_quality: float = Field(..., description="0-100 score on 8-point rule verification")
    freshness: float = Field(..., description="0-100 score on document date freshness")
    overall: float = Field(..., description="0-100 weighted composite reliability metric")


class ApplicationEvidenceDetailResponse(BaseModel):
    """Consolidated profile with all attached evidence facts and reliability breakdown."""
    product_name: str
    vendor_name: str
    edition: Optional[str] = None
    version: Optional[str] = None
    license_classification: str
    availability_model: str
    license_required: str
    license_model: str
    license_metric: str
    parent_product: Optional[str] = None
    overall_confidence: str
    profile_status: str
    reliability: ReliabilityBreakdownResponse
    evidence_records: List[EvidenceLineageResponse]


class ExplainDecisionRequest(BaseModel):
    vendor_name: str
    product_name: str


class DecisionExplanationFinding(BaseModel):
    fact_type: str
    finding: str
    evidence_quote: str
    source_citation: str


class DecisionExplanationResponse(BaseModel):
    """Structured deterministic explanation of license decision."""
    product_name: str
    vendor_name: str
    question: str
    license_requirement: str
    license_classification: str
    availability_model: str
    parent_product: Optional[str] = None
    findings: List[DecisionExplanationFinding]
    conclusion: str
    reliability_score: float


class QualityDashboardResponse(BaseModel):
    """Step 18 Quality Dashboard metrics."""
    total_applications: int
    resolved_count: int
    research_required_count: int
    review_required_count: int
    evidence_backed_count: int
    evidence_missing_count: int
    high_reliability_count: int
    medium_reliability_count: int
    low_reliability_count: int
    conflicting_facts_count: int
