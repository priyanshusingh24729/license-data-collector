"""
High-level service interface for Source Monitoring, Alerts, and Changes.
"""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.enums import AlertStatus, AlertSeverity, MonitoringRunStatus
from backend.models.monitoring import SourceMonitor, MonitoringRun, LicenseFactChange, LicenseAlert
from backend.monitoring.monitoring_result import (
    SourceMonitorCreateRequest,
    SourceMonitorResponse,
    MonitoringRunResponse,
    LicenseFactChangeResponse,
    LicenseAlertResponse,
    MonitoringSummaryBlock,
)
from backend.monitoring.source_monitor import SourceMonitorRunner, compute_next_check_time
from backend.monitoring.monitoring_scheduler import MonitoringScheduler


class MonitorService:
    """
    Coordinator service for monitoring registrations, manual checks, alerts, and audit logs.
    """

    def __init__(self):
        self.runner = SourceMonitorRunner()
        self.scheduler = MonitoringScheduler()

    def configure_source_monitor(
        self,
        db: Session,
        req: SourceMonitorCreateRequest
    ) -> SourceMonitor:
        """Registers or updates scheduled monitoring preferences for a source."""
        monitor = self.runner.get_or_create_monitor(db, req.source_id)
        monitor.enabled = req.enabled
        monitor.monitor_frequency = req.monitor_frequency
        monitor.next_check_at = compute_next_check_time(req.monitor_frequency)
        db.commit()
        db.refresh(monitor)
        return monitor

    def check_source_now(
        self,
        db: Session,
        source_id: int
    ) -> MonitoringRun:
        """Executes an immediate manual check on a source."""
        return self.scheduler.run_check_for_source(db, source_id, force=True)

    def get_summary_metrics(self, db: Session) -> MonitoringSummaryBlock:
        """Calculates aggregate dashboard metrics."""
        total = db.query(SourceMonitor).count()
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        checked_today = db.query(MonitoringRun).filter(MonitoringRun.started_at >= today_start).count()
        changed = db.query(MonitoringRun).filter(MonitoringRun.change_detected == True).count()
        unchanged = db.query(MonitoringRun).filter(MonitoringRun.status == MonitoringRunStatus.UNCHANGED).count()
        failed = db.query(MonitoringRun).filter(MonitoringRun.status == MonitoringRunStatus.FAILED).count()
        alerts = db.query(LicenseAlert).filter(LicenseAlert.status == AlertStatus.NEW).count()

        return MonitoringSummaryBlock(
            total_monitored=total,
            checked_today=checked_today,
            changed_sources=changed,
            unchanged_sources=unchanged,
            failed_sources=failed,
            licensing_alerts_count=alerts
        )
