"""
FastAPI route definitions for Step 17: Intelligent License Research Prioritization.
Provides endpoints for inventory analysis, queue management, prioritization review, and batch processing.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database.connection import get_db
from backend.models.enums import ResearchDecision, ResearchPriority, ResearchQueueStatus
from backend.models.research_queue import LicenseResearchQueueItem
from backend.models.application import Application
from backend.research.prioritization import (
    ResearchPrioritizationEngine,
    ResearchDecisionResult,
    PrioritizationSummary,
    QueueItemResponse,
    QueueProcessResponse,
    DEFAULT_RESEARCH_POLICY,
)

router = APIRouter(prefix="/api/research", tags=["Research Prioritization"])


@router.post("/prioritize", response_model=PrioritizationSummary)
def prioritize_inventory(
    device_id: Optional[int] = Query(None, description="Optional target device ID filter"),
    scan_id: Optional[str] = Query(None, description="Optional scan ID filter"),
    db: Session = Depends(get_db)
):
    """
    Evaluates detected software inventory, computes deterministic decisions & priority scores,
    and enqueues candidates requiring licensing research.
    """
    engine = ResearchPrioritizationEngine()
    return engine.prioritize_inventory(db, device_id=device_id, scan_id=scan_id)


@router.get("/queue", response_model=List[QueueItemResponse])
def list_research_queue(
    priority: Optional[ResearchPriority] = Query(None, description="Filter by priority rank"),
    decision: Optional[ResearchDecision] = Query(None, description="Filter by decision type"),
    status: Optional[ResearchQueueStatus] = Query(None, description="Filter by queue status"),
    vendor: Optional[str] = Query(None, description="Filter by vendor/publisher"),
    application: Optional[str] = Query(None, description="Filter by application name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Retrieves list of prioritized research queue items with optional filtering.
    """
    query = db.query(LicenseResearchQueueItem)

    if priority:
        query = query.filter(LicenseResearchQueueItem.priority == priority)
    if decision:
        query = query.filter(LicenseResearchQueueItem.decision == decision)
    if status:
        query = query.filter(LicenseResearchQueueItem.status == status)

    if vendor or application:
        query = query.outerjoin(Application, LicenseResearchQueueItem.application_id == Application.id)
        if vendor:
            query = query.filter(Application.publisher.ilike(f"%{vendor}%"))
        if application:
            query = query.filter(Application.display_name.ilike(f"%{application}%"))

    items = query.order_by(
        desc(LicenseResearchQueueItem.priority_score),
        desc(LicenseResearchQueueItem.created_at)
    ).offset(offset).limit(limit).all()

    output = []
    for it in items:
        app = it.application
        output.append(
            QueueItemResponse(
                id=it.id,
                application_id=it.application_id,
                detected_application_id=it.detected_application_id,
                display_name=app.display_name if app else (it.reason or "Unknown"),
                publisher=app.publisher if app else None,
                version=app.version if app else None,
                decision=it.decision,
                priority=it.priority,
                priority_score=it.priority_score,
                reason=it.reason,
                decision_factors=it.decision_factors,
                status=it.status,
                created_at=it.created_at,
                started_at=it.started_at,
                completed_at=it.completed_at,
                research_run_id=it.research_run_id,
                quality_score=it.quality_score,
                profile_status=it.profile_status,
                error_message=it.error_message
            )
        )

    return output


@router.get("/queue/{item_id}", response_model=QueueItemResponse)
def get_queue_item(item_id: int, db: Session = Depends(get_db)):
    """
    Retrieves details for a specific research queue item including factors and explanations.
    """
    it = db.query(LicenseResearchQueueItem).filter(LicenseResearchQueueItem.id == item_id).first()
    if not it:
        raise HTTPException(status_code=404, detail=f"Queue item {item_id} not found")

    app = it.application
    return QueueItemResponse(
        id=it.id,
        application_id=it.application_id,
        detected_application_id=it.detected_application_id,
        display_name=app.display_name if app else (it.reason or "Unknown"),
        publisher=app.publisher if app else None,
        version=app.version if app else None,
        decision=it.decision,
        priority=it.priority,
        priority_score=it.priority_score,
        reason=it.reason,
        decision_factors=it.decision_factors,
        status=it.status,
        created_at=it.created_at,
        started_at=it.started_at,
        completed_at=it.completed_at,
        research_run_id=it.research_run_id,
        quality_score=it.quality_score,
        profile_status=it.profile_status,
        error_message=it.error_message
    )


@router.post("/queue/process", response_model=QueueProcessResponse)
def process_research_queue(
    limit: int = Query(10, ge=1, le=50, description="Maximum number of candidates to process in this batch"),
    db: Session = Depends(get_db)
):
    """
    Dispatches top prioritized queue candidates to STEP 10 Research Orchestrator.
    Enforces daily research budget and updates queue lifecycle states.
    """
    engine = ResearchPrioritizationEngine()
    return engine.process_queue(db, limit=limit)


@router.get("/evaluation/{application_id}", response_model=ResearchDecisionResult)
def evaluate_single_application(application_id: int, db: Session = Depends(get_db)):
    """
    Evaluates on-demand research necessity and deterministic priority for an application.
    """
    engine = ResearchPrioritizationEngine()
    res = engine.evaluate_application(db, application_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
    return res


@router.get("/budget")
def get_research_budget(db: Session = Depends(get_db)):
    """
    Returns current daily research budget, executions today, and policy limits.
    """
    engine = ResearchPrioritizationEngine()
    done_today = engine.get_daily_processed_count(db)
    remaining = max(0, engine.policy.max_daily_research_applications - done_today)

    return {
        "max_daily_research_applications": engine.policy.max_daily_research_applications,
        "processed_today": done_today,
        "remaining_today": remaining,
        "profile_freshness_days": engine.policy.profile_freshness_days,
        "min_profile_quality": engine.policy.min_profile_quality,
        "max_batch_research": engine.policy.max_batch_research
    }


# -------------------------------------------------------------------------------------------------
# STEP 17.7: Automatic Review Resolution Endpoints
# -------------------------------------------------------------------------------------------------

from backend.inventory.recognition.resolver import AutomaticReviewResolver
from backend.models.resolution import ReviewResolutionRun
from backend.models.inventory import DetectedApplication
from backend.schemas.resolution import (
    ResolveReviewRequest,
    BatchResolutionResponse,
    ResolutionItemResponse,
    ReviewResolutionSummaryResponse,
)


@router.post("/resolve-review", response_model=BatchResolutionResponse)
def resolve_review_applications(
    request: ResolveReviewRequest = ResolveReviewRequest(),
    db: Session = Depends(get_db)
):
    """
    Step 17.7: Evaluates a batch of Review Required applications through the Automatic Review Resolver.
    Uses canonical recognition catalog, deterministic open-source & OS rules, and knowledge base.
    """
    resolver = AutomaticReviewResolver()
    results = resolver.resolve_batch(
        db=db,
        limit=request.limit,
        detected_app_ids=request.detected_application_ids
    )

    resolved_no = 0
    resolved_yes = 0
    research_req = 0
    review_req = 0
    items = []

    for r in results:
        if r.new_status == "LICENSE_REQUIRED_NO":
            resolved_no += 1
        elif r.new_status == "LICENSE_REQUIRED_YES":
            resolved_yes += 1
        elif r.new_status == "RESEARCH_REQUIRED":
            research_req += 1
        else:
            review_req += 1

        items.append(
            ResolutionItemResponse(
                detected_application_id=r.detected_application_id,
                application_id=r.application_id,
                old_status=r.old_status,
                old_reason=r.old_reason,
                new_status=r.new_status,
                review_reason=r.review_reason,
                method=r.method,
                confidence=r.confidence,
                result=r.result_message,
                evidence=r.evidence,
                terms_summary=r.terms_summary,
                primary_url=r.primary_url,
                canonical_name=r.canonical_name,
                canonical_vendor=r.canonical_vendor
            )
        )

    return BatchResolutionResponse(
        total_processed=len(results),
        resolved_no=resolved_no,
        resolved_yes=resolved_yes,
        research_required=research_req,
        review_required=review_req,
        items=items
    )


@router.get("/review-summary", response_model=ReviewResolutionSummaryResponse)
def get_review_resolution_summary(db: Session = Depends(get_db)):
    """
    Step 17.7: Provides a complete Before vs After summary of review resolution across total inventory.
    """
    total_apps = db.query(DetectedApplication).count()
    if total_apps == 0:
        return ReviewResolutionSummaryResponse(
            total_inventory=0,
            before_review_required=0,
            after_review_required=0,
            automatically_resolved=0,
            research_required=0,
            still_review_required=0,
            reduction_percentage=0.0,
            top_remaining_reasons={}
        )

    resolver = AutomaticReviewResolver()
    all_apps = db.query(DetectedApplication).all()
    
    before_review = len(all_apps)
    auto_resolved = 0
    research_req = 0
    still_review = 0
    reasons_count = {}

    for app in all_apps:
        res = resolver.resolve_application(db, detected_app=app)
        if res.new_status in ["LICENSE_REQUIRED_NO", "LICENSE_REQUIRED_YES"]:
            auto_resolved += 1
        elif res.new_status == "RESEARCH_REQUIRED":
            research_req += 1
        else:
            still_review += 1
            reason_str = res.review_reason.value if res.review_reason else "UNKNOWN_IDENTITY"
            reasons_count[reason_str] = reasons_count.get(reason_str, 0) + 1

    after_review = still_review
    reduction = ((before_review - after_review) / before_review * 100.0) if before_review > 0 else 0.0

    return ReviewResolutionSummaryResponse(
        total_inventory=total_apps,
        before_review_required=before_review,
        after_review_required=after_review,
        automatically_resolved=auto_resolved,
        research_required=research_req,
        still_review_required=still_review,
        reduction_percentage=round(reduction, 1),
        top_remaining_reasons=reasons_count
    )


@router.get("/review-runs")
def list_review_resolution_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Step 17.7: Retrieves historical review resolution runs and audit traces.
    """
    runs = db.query(ReviewResolutionRun).order_by(
        desc(ReviewResolutionRun.created_at)
    ).offset(offset).limit(limit).all()

    return [
        {
            "id": r.id,
            "detected_application_id": r.detected_application_id,
            "application_id": r.application_id,
            "old_status": r.old_status,
            "old_reason": r.old_reason.value if r.old_reason else None,
            "resolution_method": r.resolution_method.value if r.resolution_method else None,
            "new_status": r.new_status.value if r.new_status else None,
            "confidence": r.confidence.value if r.confidence else None,
            "result": r.result,
            "evidence": r.evidence,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in runs
    ]

