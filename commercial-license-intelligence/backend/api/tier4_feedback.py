"""FastAPI router for Tier 4 Human-in-the-Loop Resolution & Catalog Feedback Loop."""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from backend.database.connection import get_db
from backend.models.tier4_feedback import PendingCatalogRule, CatalogAuditLog
from backend.inventory.feedback.tier4_loop_service import Tier4Resolution, Tier4LoopService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/tier4",
    tags=["Tier 4 Resolution Loop"]
)


class PromoteRuleRequest(BaseModel):
    approved_by: str = Field(..., description="Name or identifier of reviewer approving the promotion")


class RejectRuleRequest(BaseModel):
    rejected_by: str = Field(..., description="Name or identifier of reviewer rejecting the rule")
    reason: str = Field(..., description="Reason for rejection")


@router.get("/queue", response_model=List[Dict[str, Any]])
def get_unresolved_queue(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Returns a frequency-weighted queue of unresolved Tier 4 applications sorted by fleet occurrence count.
    """
    return Tier4LoopService.get_tier4_queue(db=db, limit=limit)


@router.post("/resolve")
def resolve_tier4_item(
    resolution: Tier4Resolution,
    db: Session = Depends(get_db)
):
    """
    Submits a structured resolution for an unresolved Tier 4 application:
    1. Stages the rule in pending_catalog_rules.
    2. Immediately updates all matching rows in the inventory database.
    3. Records an entry in catalog_audit_log.
    4. Auto-promotes if exact match + high confidence + auto_promote=True.
    """
    try:
        result = Tier4LoopService.submit_resolution(resolution, db)
        return result
    except Exception as e:
        logger.error(f"Failed to submit Tier 4 resolution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending", response_model=List[Dict[str, Any]])
def get_pending_rules(
    status: Optional[str] = Query("pending_review", description="Filter by status: pending_review | approved | merged | rejected | all"),
    db: Session = Depends(get_db)
):
    """
    Lists staged catalog rules awaiting review and promotion.
    """
    query = db.query(PendingCatalogRule)
    if status and status != "all":
        query = query.filter(PendingCatalogRule.status == status)
    
    rules = query.order_by(PendingCatalogRule.occurrence_count.desc(), PendingCatalogRule.resolved_at.desc()).all()
    return [r.to_dict() for r in rules]


@router.get("/diff/{rule_id}")
def get_rule_diff_preview(
    rule_id: str,
    db: Session = Depends(get_db)
):
    """
    Returns code diff preview for an individual pending rule.
    """
    rule = db.query(PendingCatalogRule).filter(PendingCatalogRule.rule_id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found.")
    
    return {
        "rule_id": rule.rule_id,
        "canonical_name": rule.canonical_name,
        "vendor": rule.vendor,
        "diff_preview": rule.diff_preview or Tier4LoopService.generate_catalog_py_entry(rule),
        "status": rule.status,
    }


@router.post("/promote/{rule_id}")
def promote_rule(
    rule_id: str,
    req: PromoteRuleRequest,
    db: Session = Depends(get_db)
):
    """
    Promotes a staged pending rule to permanent status:
    - Appends entry into catalog.py.
    - Injects entry into runtime memory RECOGNITION_RULES.
    - Appends to regression test fixtures.
    - Marks rule status as 'merged'.
    """
    try:
        result = Tier4LoopService.promote_to_catalog(rule_id, approved_by=req.approved_by, db=db)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to promote rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reject/{rule_id}")
def reject_rule(
    rule_id: str,
    req: RejectRuleRequest,
    db: Session = Depends(get_db)
):
    """
    Rejects a staged pending rule.
    """
    try:
        result = Tier4LoopService.reject_rule(rule_id, rejected_by=req.rejected_by, reason=req.reason, db=db)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to reject rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-log", response_model=List[Dict[str, Any]])
def get_audit_log(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Returns audit trail of all catalog modifications, resolutions, and promotions.
    """
    entries = db.query(CatalogAuditLog).order_by(CatalogAuditLog.timestamp.desc()).limit(limit).all()
    return [e.to_dict() for e in entries]
