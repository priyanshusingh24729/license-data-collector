"""
Batch Research Execution Engine.
Coordinates controlled concurrent research runs using ThreadPoolExecutor,
failure isolation, retry mechanisms, and real-time progress reporting.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from backend.config.settings import get_settings
from backend.database.connection import SessionLocal
from backend.models.enums import BatchStatus, BatchItemStatus, ApplicationResearchStatus
from backend.models.application import Application, ResearchBatch, ResearchBatchItem
from backend.schemas.application import (
    BatchResearchRequest,
    BatchResearchResponse,
    BatchItemDetail,
)
from backend.orchestration.research_orchestrator import ResearchOrchestrator

logger = logging.getLogger(__name__)
settings = get_settings()


class BatchResearchEngine:
    """
    Engine executing controlled, resilient batch research across cataloged applications.
    """

    def __init__(self, orchestrator: Optional[ResearchOrchestrator] = None):
        self.orchestrator = orchestrator or ResearchOrchestrator()

    def create_batch(
        self,
        db: Session,
        req: BatchResearchRequest
    ) -> ResearchBatch:
        """
        Creates a new ResearchBatch and associated ResearchBatchItem entries.
        """
        app_ids = list(set(req.application_ids))
        batch_name = req.name or f"Batch Research ({len(app_ids)} Apps) - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"

        batch = ResearchBatch(
            name=batch_name,
            total_applications=len(app_ids),
            queued=len(app_ids),
            running=0,
            completed=0,
            failed=0,
            partial=0,
            status=BatchStatus.QUEUED,
            started_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)

        for aid in app_ids:
            item = ResearchBatchItem(
                batch_id=batch.id,
                application_id=aid,
                status=BatchItemStatus.QUEUED
            )
            db.add(item)
            # Update app research status
            app_obj = db.query(Application).filter(Application.id == aid).first()
            if app_obj:
                app_obj.research_status = ApplicationResearchStatus.QUEUED

        db.commit()
        return batch

    def _process_item(
        self,
        batch_id: int,
        item_id: int,
        application_id: int,
        force_refresh: bool,
        db: Session
    ):
        """Processes a single application research task."""
        try:
            item = db.query(ResearchBatchItem).filter(ResearchBatchItem.id == item_id).first()
            if not item:
                return

            item.status = BatchItemStatus.RUNNING
            item.started_at = datetime.now(timezone.utc)
            db.commit()

            # Execute full pipeline
            profile = self.orchestrator.research_application(
                db=db,
                application_id=application_id,
                force_refresh=force_refresh
            )

            item = db.query(ResearchBatchItem).filter(ResearchBatchItem.id == item_id).first()
            if item:
                item.status = BatchItemStatus.COMPLETED
                item.completed_at = datetime.now(timezone.utc)
                db.commit()

        except Exception as exc:
            logger.error(f"Batch item {item_id} (App {application_id}) failed: {exc}")
            db.rollback()
            try:
                item = db.query(ResearchBatchItem).filter(ResearchBatchItem.id == item_id).first()
                if item:
                    item.status = BatchItemStatus.FAILED
                    item.error_message = str(exc)
                    item.completed_at = datetime.now(timezone.utc)
                    db.commit()
            except Exception as inner_err:
                logger.error(f"Failed to update error status for item {item_id}: {inner_err}")

    def run_batch_synchronous(
        self,
        db: Session,
        batch_id: int,
        force_refresh: bool = False,
        session_factory = None
    ) -> BatchResearchResponse:
        """
        Executes a batch job using controlled thread concurrency.
        """
        batch = db.query(ResearchBatch).filter(ResearchBatch.id == batch_id).first()
        if not batch:
            raise ValueError(f"Batch ID {batch_id} not found.")

        batch.status = BatchStatus.RUNNING
        db.commit()

        items = db.query(ResearchBatchItem).filter(
            ResearchBatchItem.batch_id == batch_id,
            ResearchBatchItem.status.in_([BatchItemStatus.QUEUED, BatchItemStatus.FAILED])
        ).all()

        max_workers = min(settings.MAX_CONCURRENT_RESEARCH, max(1, len(items)))

        if session_factory:
            # Multi-threaded execution with separate session per worker
            def worker_func(item_id, app_id):
                worker_db = session_factory()
                try:
                    self._process_item(batch_id, item_id, app_id, force_refresh, worker_db)
                finally:
                    worker_db.close()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(worker_func, it.id, it.application_id)
                    for it in items
                ]
                for f in as_completed(futures):
                    pass
        else:
            # Sequential / direct execution
            for it in items:
                self._process_item(batch_id, it.id, it.application_id, force_refresh, db)

        # Update batch summary
        db.refresh(batch)
        all_items = db.query(ResearchBatchItem).filter(ResearchBatchItem.batch_id == batch_id).all()
        comp = len([i for i in all_items if i.status == BatchItemStatus.COMPLETED])
        fail = len([i for i in all_items if i.status == BatchItemStatus.FAILED])
        running = len([i for i in all_items if i.status == BatchItemStatus.RUNNING])
        queued = len([i for i in all_items if i.status == BatchItemStatus.QUEUED])

        batch.completed = comp
        batch.failed = fail
        batch.running = running
        batch.queued = queued

        if fail == 0 and queued == 0 and running == 0:
            batch.status = BatchStatus.COMPLETED
        elif comp > 0 and fail > 0:
            batch.status = BatchStatus.PARTIAL
        elif fail > 0 and comp == 0:
            batch.status = BatchStatus.FAILED
        else:
            batch.status = BatchStatus.COMPLETED

        batch.completed_at = datetime.now(timezone.utc)
        db.commit()

        return self.get_batch_progress(db, batch_id)

    def run_batch_background(
        self,
        batch_id: int,
        force_refresh: bool = False,
        session_factory = None
    ):
        """Starts batch execution asynchronously in a background thread."""
        thread = threading.Thread(
            target=self._run_async_worker,
            args=(batch_id, force_refresh, session_factory),
            daemon=True
        )
        thread.start()

    def _run_async_worker(self, batch_id: int, force_refresh: bool, session_factory):
        factory = session_factory or SessionLocal
        db = factory()
        try:
            self.run_batch_synchronous(db, batch_id, force_refresh=force_refresh, session_factory=factory)
        except Exception as e:
            logger.error(f"Async batch runner failed for batch {batch_id}: {e}")
        finally:
            db.close()

    def get_batch_progress(
        self,
        db: Session,
        batch_id: int
    ) -> BatchResearchResponse:
        """Retrieves real-time progress and item-level details for a batch job."""
        batch = db.query(ResearchBatch).filter(ResearchBatch.id == batch_id).first()
        if not batch:
            raise ValueError(f"Batch ID {batch_id} not found.")

        items = db.query(ResearchBatchItem).filter(ResearchBatchItem.batch_id == batch_id).all()

        comp = len([i for i in items if i.status == BatchItemStatus.COMPLETED])
        fail = len([i for i in items if i.status == BatchItemStatus.FAILED])
        run = len([i for i in items if i.status == BatchItemStatus.RUNNING])
        q = len([i for i in items if i.status == BatchItemStatus.QUEUED])
        part = len([i for i in items if i.status == BatchItemStatus.PARTIAL])

        total = batch.total_applications or len(items)
        progress = round(((comp + fail + part) / max(1, total)) * 100, 1)

        item_details = []
        for it in items:
            app_obj = db.query(Application).filter(Application.id == it.application_id).first()
            item_details.append(BatchItemDetail(
                id=it.id,
                application_id=it.application_id,
                vendor_name=app_obj.vendor_name if app_obj else "UNKNOWN",
                product_name=app_obj.product_name if app_obj else "UNKNOWN",
                status=it.status,
                error_message=it.error_message,
                started_at=it.started_at,
                completed_at=it.completed_at
            ))

        return BatchResearchResponse(
            batch_id=batch.id,
            name=batch.name,
            total=total,
            queued=q,
            running=run,
            completed=comp,
            partial=part,
            failed=fail,
            status=batch.status,
            progress_percentage=progress,
            started_at=batch.started_at,
            completed_at=batch.completed_at,
            items=item_details
        )
