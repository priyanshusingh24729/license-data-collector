"""
Pydantic schemas for Step 17.7: Automatic Review Resolution API.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from backend.models.enums import (
    ReviewReason,
    ResolutionMethod,
    FinalLicenseStatus,
    ExtractionConfidence,
)


class ResolveReviewRequest(BaseModel):
    limit: int = Field(20, ge=1, le=200, description="Number of applications to process in this batch")
    detected_application_ids: Optional[List[int]] = Field(None, description="Optional specific IDs to resolve")


class ResolutionItemResponse(BaseModel):
    detected_application_id: Optional[int] = None
    application_id: Optional[int] = None
    old_status: str
    old_reason: Optional[ReviewReason] = None
    new_status: FinalLicenseStatus
    review_reason: Optional[ReviewReason] = None
    method: ResolutionMethod
    confidence: ExtractionConfidence
    result: str
    evidence: Optional[str] = None
    terms_summary: Optional[str] = None
    primary_url: Optional[str] = None
    canonical_name: Optional[str] = None
    canonical_vendor: Optional[str] = None


class BatchResolutionResponse(BaseModel):
    total_processed: int
    resolved_no: int
    resolved_yes: int
    research_required: int
    review_required: int
    items: List[ResolutionItemResponse]


class ReviewResolutionSummaryResponse(BaseModel):
    total_inventory: int
    before_review_required: int
    after_review_required: int
    automatically_resolved: int
    research_required: int
    still_review_required: int
    reduction_percentage: float
    top_remaining_reasons: Dict[str, int]
