"""FastAPI endpoints for License Intelligence Audit, Evidence Lineage, and Quality Dashboard."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.models.enums import AlertSeverity, QualityIssueType, IssueStatus
from backend.models.application import Application
from backend.audit.audit_result import (
    ApplicationAuditTimelineResponse,
    PositionAuditResponse,
    EvidenceChainResponse,
    FactExplanationResponse,
    ProfileFieldExplanationResponse,
    ApplicationQualityScoreResponse,
    QualityDashboardSummaryResponse,
    QualityIssueResponse,
)
from backend.audit.audit_service import AuditService
from backend.audit.evidence_lineage import EvidenceLineageService
from backend.audit.quality_engine import ApplicationQualityEngine
from backend.audit.quality_service import QualityService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["License Intelligence Audit & Quality Dashboard"])


# -------------------------------------------------------------
# 1. Complete Application & Position Audit Endpoints
# -------------------------------------------------------------

@router.get("/api/audit/application/{application_id}", response_model=ApplicationAuditTimelineResponse)
def get_application_audit_timeline(
    application_id: int,
    db: Session = Depends(get_db)
):
    """Retrieves full chronological audit timeline of lifecycle events for an application."""
    svc = AuditService()
    try:
        return svc.get_application_timeline(db, application_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get("/api/audit/position/{application_id}", response_model=PositionAuditResponse)
def get_position_audit_explanation(
    application_id: int,
    db: Session = Depends(get_db)
):
    """Provides structured arithmetic explanation and factual reconciliation for a license position."""
    svc = AuditService()
    try:
        return svc.explain_position(db, application_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get("/api/audit/export/csv")
def export_audit_csv_endpoint(
    db: Session = Depends(get_db)
):
    """Exports full audit matrix of verified facts, supporting text snippets, and source citations."""
    svc = AuditService()
    csv_data = svc.export_audit_csv(db)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=license_intelligence_audit.csv"}
    )


# -------------------------------------------------------------
# 2. Evidence Lineage & Explanation Endpoints
# -------------------------------------------------------------

@router.get("/api/evidence/application/{application_id}", response_model=EvidenceChainResponse)
def get_application_evidence_chain(
    application_id: int,
    db: Session = Depends(get_db)
):
    """Retrieves complete multi-hop evidence chain from application down to exact text snippets and sources."""
    lineage_svc = EvidenceLineageService()
    try:
        return lineage_svc.get_evidence_chain_for_application(db, application_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get("/api/evidence/fact/{fact_id}", response_model=FactExplanationResponse)
def explain_fact_endpoint(
    fact_id: int,
    db: Session = Depends(get_db)
):
    """Provides exhaustive evidence, document, page, and validation audit drill-down for a single fact."""
    lineage_svc = EvidenceLineageService()
    try:
        return lineage_svc.explain_fact(db, fact_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get("/api/evidence/profile/{profile_id}/{field_name}", response_model=ProfileFieldExplanationResponse)
def explain_profile_field_endpoint(
    profile_id: int,
    field_name: str,
    db: Session = Depends(get_db)
):
    """Explains which exact verified facts and source citations anchor a consolidated license profile field."""
    lineage_svc = EvidenceLineageService()
    try:
        return lineage_svc.explain_profile_field(db, profile_id, field_name)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


# -------------------------------------------------------------
# 3. Quality Scoring & Issues Endpoints
# -------------------------------------------------------------

@router.get("/api/quality/applications", response_model=List[ApplicationQualityScoreResponse])
def list_applications_quality(
    db: Session = Depends(get_db)
):
    """Calculates deterministic quality scores and critical field coverage for all catalog applications."""
    engine = ApplicationQualityEngine()
    apps = db.query(Application).all()
    return [engine.evaluate_application_quality(db, a.id) for a in apps]


@router.get("/api/quality/summary", response_model=QualityDashboardSummaryResponse)
def get_quality_summary(
    db: Session = Depends(get_db)
):
    """Aggregates catalog-wide quality metrics, categories, critical issues, and stale sources."""
    svc = QualityService()
    return svc.get_quality_dashboard_summary(db)


@router.get("/api/quality/issues", response_model=List[QualityIssueResponse])
def list_quality_issues_endpoint(
    application_id: Optional[int] = Query(None),
    severity: Optional[AlertSeverity] = Query(None),
    issue_type: Optional[QualityIssueType] = Query(None),
    status: Optional[IssueStatus] = Query(IssueStatus.ACTIVE),
    db: Session = Depends(get_db)
):
    """Lists data quality issues, evidence gaps, conflicts, and stale sources."""
    svc = QualityService()
    return svc.list_quality_issues(db, application_id=application_id, severity=severity, issue_type=issue_type, status=status)


@router.post("/api/quality/issues/{id}/resolve", response_model=QualityIssueResponse)
def resolve_quality_issue(
    id: int,
    db: Session = Depends(get_db)
):
    """Marks a quality issue as resolved."""
    svc = QualityService()
    try:
        return svc.resolve_issue(db, id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
