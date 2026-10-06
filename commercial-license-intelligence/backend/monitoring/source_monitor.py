"""
Core Source Monitor Engine.
Performs live check of registered sources using existing collectors (Web, PDF, API),
detects content changes via SHA-256 hash comparison, generates diffs, and manages error states.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from backend.models.enums import (
    CollectionMethod,
    CollectionStatus,
    DocumentCollectionStatus,
    ApiCollectionStatus,
    MonitorFrequency,
    MonitorStatus,
    MonitoringRunStatus,
    ChangeClassification,
)
from backend.models.source import LicenseSource
from backend.models.collection import CollectedDocument
from backend.models.monitoring import SourceMonitor, MonitoringRun
from backend.monitoring.change_detector import ChangeDetector
from backend.monitoring.change_classifier import ChangeClassifier
from backend.collectors.web.web_collector import WebCollector
from backend.collectors.documents.document_collector import DocumentCollector
from backend.collectors.api.api_collector import ApiCollector

logger = logging.getLogger(__name__)


def compute_next_check_time(frequency: MonitorFrequency) -> datetime:
    """Calculates the next scheduled check timestamp based on frequency."""
    now = datetime.now(timezone.utc)
    if frequency == MonitorFrequency.DAILY:
        return now + timedelta(days=1)
    elif frequency == MonitorFrequency.MONTHLY:
        return now + timedelta(days=30)
    elif frequency == MonitorFrequency.CUSTOM:
        return now + timedelta(days=3)
    else:  # WEEKLY default
        return now + timedelta(days=7)


class SourceMonitorRunner:
    """
    Executes single-source monitoring checks using official collectors.
    """

    def __init__(
        self,
        web_collector: Optional[WebCollector] = None,
        doc_collector: Optional[DocumentCollector] = None,
        api_collector: Optional[ApiCollector] = None,
    ):
        self.web_collector = web_collector or WebCollector()
        self.doc_collector = doc_collector or DocumentCollector()
        self.api_collector = api_collector or ApiCollector()

    def get_or_create_monitor(self, db: Session, source_id: int) -> SourceMonitor:
        """Retrieves or registers a SourceMonitor record for a given LicenseSource."""
        monitor = db.query(SourceMonitor).filter(SourceMonitor.source_id == source_id).first()
        if not monitor:
            monitor = SourceMonitor(
                source_id=source_id,
                enabled=True,
                monitor_frequency=MonitorFrequency.WEEKLY,
                last_status=MonitorStatus.ACTIVE,
                next_check_at=datetime.now(timezone.utc)
            )
            db.add(monitor)
            db.commit()
            db.refresh(monitor)
        return monitor

    def check_source(
        self,
        db: Session,
        source_id: int,
        force: bool = False
    ) -> Tuple[MonitoringRun, Optional[CollectedDocument]]:
        """
        Executes an immediate live content check for a monitored source.
        Returns the MonitoringRun record and the newly collected CollectedDocument (if any).
        """
        source = db.query(LicenseSource).filter(LicenseSource.id == source_id).first()
        if not source:
            raise ValueError(f"LicenseSource ID {source_id} not found.")

        monitor = self.get_or_create_monitor(db, source_id)
        start_time = datetime.now(timezone.utc)

        # Retrieve previous collected document to compare
        prev_doc = (
            db.query(CollectedDocument)
            .filter(CollectedDocument.source_id == source_id)
            .order_by(CollectedDocument.id.desc())
            .first()
        )
        prev_hash = monitor.last_content_hash or (prev_doc.content_hash if prev_doc else None)
        prev_text = prev_doc.clean_text if prev_doc else ""

        run = MonitoringRun(
            source_id=source_id,
            started_at=start_time,
            status=MonitoringRunStatus.RUNNING,
            previous_hash=prev_hash
        )
        db.add(run)
        db.commit()

        # Collect current content using existing collectors
        current_text = ""
        current_doc = None
        collection_success = False
        error_msg = None

        try:
            method = source.collection_method
            if method in [CollectionMethod.PDF, CollectionMethod.DOCUMENT] or source.source_url.lower().endswith(".pdf"):
                doc_res = self.doc_collector.collect_document(
                    db=db,
                    source_url=source.source_url,
                    source_id=source.id,
                    vendor_name=source.vendor_name
                )
                if doc_res.status in [DocumentCollectionStatus.COLLECTED, DocumentCollectionStatus.PARSED]:
                    collection_success = True
                    current_doc = db.query(CollectedDocument).filter(CollectedDocument.id == doc_res.id).first()
                    current_text = current_doc.clean_text if current_doc else ""
                else:
                    error_msg = f"Document collector returned status: {doc_res.status.value}"

            elif method == CollectionMethod.API:
                api_res = self.api_collector.collect_api(
                    db=db,
                    endpoint_url=source.source_url,
                    source_id=source.id,
                    vendor_name=source.vendor_name
                )
                if api_res.status == ApiCollectionStatus.COLLECTED:
                    collection_success = True
                    current_text = str(api_res.raw_payload)
                else:
                    error_msg = f"API collector returned status: {api_res.status.value}"

            else:  # WEB (Default)
                web_res = self.web_collector.collect_url(
                    db=db,
                    url=source.source_url,
                    source_id=source.id,
                    vendor_name=source.vendor_name
                )
                if web_res.status == CollectionStatus.COLLECTED:
                    collection_success = True
                    current_doc = db.query(CollectedDocument).filter(CollectedDocument.id == web_res.id).first()
                    current_text = current_doc.clean_text if current_doc else ""
                else:
                    error_msg = f"Web collector returned status: {web_res.status.value}"

        except Exception as exc:
            logger.error(f"Error checking source {source_id}: {exc}")
            error_msg = str(exc)
            collection_success = False

        # Process Results
        completed_time = datetime.now(timezone.utc)
        run.completed_at = completed_time

        if not collection_success:
            # Handle Failure: preserve last known facts, increment failure counter
            monitor.consecutive_failures += 1
            if monitor.consecutive_failures >= 3:
                monitor.last_status = MonitorStatus.ERROR
            monitor.last_checked_at = completed_time
            monitor.next_check_at = compute_next_check_time(monitor.monitor_frequency)

            run.status = MonitoringRunStatus.FAILED
            run.error_message = error_msg or "Failed to retrieve source content."
            db.commit()
            return run, None

        # Successful Collection: Calculate hash & detect changes
        current_hash = ChangeDetector.compute_hash(current_text)
        run.current_hash = current_hash
        monitor.consecutive_failures = 0
        monitor.last_status = MonitorStatus.ACTIVE
        monitor.last_checked_at = completed_time
        monitor.next_check_at = compute_next_check_time(monitor.monitor_frequency)

        if prev_hash and current_hash == prev_hash:
            run.status = MonitoringRunStatus.UNCHANGED
            run.change_detected = False
            run.change_classification = ChangeClassification.NO_CHANGE
        else:
            # Content changed or first baseline check
            run.status = MonitoringRunStatus.CHANGED
            run.change_detected = True
            diff_text = ChangeDetector.generate_diff(prev_text, current_text)
            run.diff_summary = diff_text
            run.change_classification = ChangeClassifier.classify_diff(diff_text, prev_text, current_text)

            monitor.last_content_hash = current_hash
            monitor.last_change_detected_at = completed_time

        db.commit()
        db.refresh(run)
        return run, current_doc
