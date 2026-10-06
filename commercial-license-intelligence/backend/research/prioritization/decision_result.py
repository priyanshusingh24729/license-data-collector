"""
Pydantic response and schema definitions for Step 17 Research Prioritization.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from backend.models.enums import ResearchDecision, ResearchPriority, ResearchQueueStatus


class DecisionFactor(BaseModel):
    """Specific factor contributing to research decision and priority scoring."""
    factor_name: str
    description: str
    score_delta: int = 0
    category: str = "GENERAL"


class ResearchDecisionResult(BaseModel):
    """Complete evaluation outcome for an application candidate."""
    application_id: Optional[int] = None
    detected_application_id: Optional[int] = None
    display_name: str
    publisher: Optional[str] = None
    version: Optional[str] = None
    decision: ResearchDecision
    priority: ResearchPriority
    score: int
    reasons: List[str]
    factors: List[DecisionFactor] = Field(default_factory=list)
    quality_score: Optional[float] = None
    is_profile_fresh: bool = False
    source_change_detected: bool = False


class PrioritizationSummary(BaseModel):
    """Aggregated outcome of an inventory prioritization run."""
    total_evaluated: int = 0
    no_research_required: int = 0
    research_required: int = 0
    refresh_required: int = 0
    review_required: int = 0
    unknown: int = 0
    priority_distribution: Dict[str, int] = Field(
        default_factory=lambda: {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "NONE": 0
        }
    )
    enqueued_count: int = 0
    decisions: List[ResearchDecisionResult] = Field(default_factory=list)


class QueueItemResponse(BaseModel):
    """Detailed queue item representation for API and dashboard."""
    id: int
    application_id: Optional[int] = None
    detected_application_id: Optional[int] = None
    display_name: str
    publisher: Optional[str] = None
    version: Optional[str] = None
    decision: ResearchDecision
    priority: ResearchPriority
    priority_score: int
    reason: str
    decision_factors: Optional[List[Dict[str, Any]]] = None
    status: ResearchQueueStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    research_run_id: Optional[int] = None
    quality_score: Optional[float] = None
    profile_status: Optional[str] = None
    error_message: Optional[str] = None


class QueueProcessResponse(BaseModel):
    """Summary of batch queue execution against STEP 10 Research Orchestrator."""
    requested_limit: int
    processed_count: int
    successful_count: int
    failed_count: int
    skipped_count: int
    remaining_in_queue: int
    daily_budget_remaining: int
    executed_items: List[QueueItemResponse] = Field(default_factory=list)
