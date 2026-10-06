"""
Scheduled Source Monitoring Execution & Dispatch Engine.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from backend.config.settings import get_settings
from backend.database.connection import SessionLocal
from backend.models.enums import MonitorStatus, ChangeClassification
from backend.models.monitoring import SourceMonitor, MonitoringRun
from backend.monitoring.source_monitor import SourceMonitorRunner
from backend.monitoring.refresh_manager import TargetedRefreshManager

logger = logging.getLogger(__name__)
settings = get_settings()


class MonitoringScheduler:
    """
    Identifies and executes scheduled source checks with controlled concurrency.
    """

    def __init__(
        self,
        runner: Optional[SourceMonitorRunner] = None,
        refresh_mgr: Optional[TargetedRefreshManager] = None,
    ):
        self.runner = runner or SourceMonitorRunner()
        self.refresh_mgr = refresh_mgr or TargetedRefreshManager()

    def get_due_monitors(self, db: Session) -> List[SourceMonitor]:
        """Queries active monitors where next_check_at is due."""
        now = datetime.now(timezone.utc)
        return (
            db.query(SourceMonitor)
            .filter(
                SourceMonitor.enabled == True,
                SourceMonitor.last_status != MonitorStatus.DISABLED,
                SourceMonitor.next_check_at <= now
            )
            .all()
        )

    def run_check_for_source(
        self,
        db: Session,
        source_id: int,
        force: bool = False
    ) -> MonitoringRun:
        """Runs an individual source check and triggers targeted refresh if licensing content changed."""
        run, doc = self.runner.check_source(db, source_id, force=force)
        if run.change_detected and doc and run.change_classification == ChangeClassification.LICENSING_RELEVANT_CHANGE:
            try:
                self.refresh_mgr.process_source_change(db, source_id, doc.id)
            except Exception as e:
                logger.error(f"Targeted refresh failed for source {source_id}: {e}")
        return run

    def run_due_checks_synchronous(
        self,
        db: Session,
        session_factory = None
    ) -> List[MonitoringRun]:
        """Executes all due monitoring checks with thread pool concurrency control."""
        due_monitors = self.get_due_monitors(db)
        if not due_monitors:
            return []

        results: List[MonitoringRun] = []
        max_workers = min(settings.MAX_CONCURRENT_MONITORS, max(1, len(due_monitors)))

        if session_factory:
            def worker(source_id: int):
                worker_db = session_factory()
                try:
                    return self.run_check_for_source(worker_db, source_id)
                finally:
                    worker_db.close()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(worker, m.source_id) for m in due_monitors]
                for f in as_completed(futures):
                    try:
                        results.append(f.result())
                    except Exception as e:
                        logger.error(f"Worker check execution error: {e}")
        else:
            for m in due_monitors:
                res = self.run_check_for_source(db, m.source_id)
                results.append(res)

        return results
