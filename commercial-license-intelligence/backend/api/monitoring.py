"""FastAPI endpoints for License Source Monitoring, Change Detection, and Alerts."""

import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.models.enums import AlertStatus, AlertSeverity, MonitorStatus
from backend.models.source import LicenseSource
from backend.models.monitoring import SourceMonitor, MonitoringRun, LicenseFactChange, LicenseAlert
from backend.monitoring.monitoring_result import (
    SourceMonitorCreateRequest,
    SourceMonitorResponse,
    MonitoringRunResponse,
    LicenseFactChangeResponse,
    LicenseAlertResponse,
    MonitoringSummaryBlock,
)
from backend.monitoring.monitor_service import MonitorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["License Source Monitoring & Change Detection"])


@router.post("/sources/{source_id}", response_model=SourceMonitorResponse)
def configure_monitoring(
    source_id: int,
    request: SourceMonitorCreateRequest,
    db: Session = Depends(get_db)
):
    """Register or update scheduled monitoring preferences for an official license source."""
    if source_id != request.source_id:
        request.source_id = source_id
    svc = MonitorService()
    return svc.configure_source_monitor(db, request)


@router.post("/sources/{source_id}/check", response_model=MonitoringRunResponse)
def trigger_immediate_source_check(
    source_id: int,
    db: Session = Depends(get_db)
):
    """Executes an immediate live content check on a source without altering schedule."""
    source = db.query(LicenseSource).filter(LicenseSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Source ID {source_id} not found.")

    svc = MonitorService()
    return svc.check_source_now(db, source_id)


@router.get("/sources", response_model=List[SourceMonitorResponse])
def list_monitored_sources(
    status_filter: Optional[MonitorStatus] = Query(None, alias="status"),
    enabled: Optional[bool] = Query(None),
    db: Session = Depends(get_db)
):
    """Lists all configured source monitors."""
    q = db.query(SourceMonitor)
    if status_filter:
        q = q.filter(SourceMonitor.last_status == status_filter)
    if enabled is not None:
        q = q.filter(SourceMonitor.enabled == enabled)
    return q.order_by(SourceMonitor.id.desc()).all()


@router.get("/runs/{run_id}", response_model=MonitoringRunResponse)
def get_monitoring_run(
    run_id: int,
    db: Session = Depends(get_db)
):
    """Retrieves execution outcome and content diff for a specific monitoring run."""
    run = db.query(MonitoringRun).filter(MonitoringRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"MonitoringRun ID {run_id} not found.")
    return run


@router.get("/changes", response_model=List[LicenseFactChangeResponse])
def list_fact_changes(
    application_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Retrieves granular audit trail of detected licensing fact transitions."""
    q = db.query(LicenseFactChange)
    if application_id:
        q = q.filter(LicenseFactChange.application_id == application_id)
    return q.order_by(LicenseFactChange.id.desc()).limit(limit).all()


@router.get("/alerts", response_model=List[LicenseAlertResponse])
def list_licensing_alerts(
    severity: Optional[AlertSeverity] = Query(None),
    status_filter: Optional[AlertStatus] = Query(None, alias="status"),
    application_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Retrieves high-priority actionable licensing change alerts."""
    q = db.query(LicenseAlert)
    if severity:
        q = q.filter(LicenseAlert.severity == severity)
    if status_filter:
        q = q.filter(LicenseAlert.status == status_filter)
    if application_id:
        q = q.filter(LicenseAlert.application_id == application_id)
    return q.order_by(LicenseAlert.id.desc()).limit(limit).all()


@router.post("/alerts/{alert_id}/acknowledge", response_model=LicenseAlertResponse)
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db)
):
    """Marks a licensing change alert as acknowledged by user."""
    alert = db.query(LicenseAlert).filter(LicenseAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert ID {alert_id} not found.")
    alert.status = AlertStatus.ACKNOWLEDGED
    db.commit()
    db.refresh(alert)
    return alert


@router.post("/alerts/{alert_id}/resolve", response_model=LicenseAlertResponse)
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db)
):
    """Marks a licensing change alert as resolved."""
    alert = db.query(LicenseAlert).filter(LicenseAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert ID {alert_id} not found.")
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert


@router.get("/summary", response_model=MonitoringSummaryBlock)
def get_monitoring_summary(db: Session = Depends(get_db)):
    """Retrieves aggregate monitoring metrics."""
    svc = MonitorService()
    return svc.get_summary_metrics(db)
