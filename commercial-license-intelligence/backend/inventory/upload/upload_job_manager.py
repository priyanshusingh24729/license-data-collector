"""
Asynchronous Upload Job Coordinator & Live Progress Tracking Manager.
"""

import uuid
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import pandas as pd

from backend.database.connection import SessionLocal
from backend.models.inventory_upload import (
    InventoryUpload,
    UploadLicenseResult,
)
from backend.inventory.upload.bulk_upload_processor import BulkUploadProcessor

logger = logging.getLogger(__name__)


class UploadJobManager:
    """
    Manages asynchronous background execution of inventory upload jobs.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="UploadJobWorker")
        self.job_progress: Dict[str, Dict[str, Any]] = {}
        self.futures: Dict[str, Any] = {}

    @classmethod
    def get_instance(cls) -> "UploadJobManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def create_and_submit_job(
        self,
        file_name: str,
        file_type: str,
        df: pd.DataFrame,
        column_mapping: Dict[str, Optional[str]],
    ) -> str:
        """
        Creates an upload job record and starts background processing.
        Returns: upload_id
        """
        upload_id = f"upl_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        total_rows = len(df)
        self.job_progress[upload_id] = {
            "upload_id": upload_id,
            "file_name": file_name,
            "file_type": file_type,
            "status": "QUEUED",
            "total_rows": total_rows,
            "processed_rows": 0,
            "unique_applications": 0,
            "unique_machines": 0,
            "resolved_count": 0,
            "unresolved_count": 0,
            "cache_hits": 0,
            "new_researched": 0,
            "progress_percent": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Initialize in database
        db = SessionLocal()
        try:
            up_rec = InventoryUpload(
                upload_id=upload_id,
                file_name=file_name,
                file_type=file_type,
                total_rows=total_rows,
                status="QUEUED",
                column_mapping=column_mapping,
                created_at=datetime.now(timezone.utc),
            )
            db.add(up_rec)
            db.commit()
        finally:
            db.close()

        def _progress_cb(status_dict: Dict[str, Any]):
            with self._lock:
                if upload_id in self.job_progress:
                    self.job_progress[upload_id].update(status_dict)

        def _worker():
            try:
                BulkUploadProcessor.process_upload_dataframe(
                    upload_id=upload_id,
                    file_name=file_name,
                    file_type=file_type,
                    df=df,
                    column_mapping=column_mapping,
                    progress_callback=_progress_cb,
                )
            except Exception as exc:
                logger.exception(f"Background upload job {upload_id} failed: {exc}")
                with self._lock:
                    if upload_id in self.job_progress:
                        self.job_progress[upload_id]["status"] = "FAILED"
                        self.job_progress[upload_id]["error"] = str(exc)

        future = self.executor.submit(_worker)
        self.futures[upload_id] = future
        return upload_id

    def get_job_status(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves real-time progress from memory or falls back to database record.
        """
        with self._lock:
            if upload_id in self.job_progress:
                return dict(self.job_progress[upload_id])

        db = SessionLocal()
        try:
            up = db.query(InventoryUpload).filter(InventoryUpload.upload_id == upload_id).first()
            if not up:
                return None
            
            percent = 100 if up.status == "COMPLETED" else int((up.processed_rows / up.total_rows) * 100) if up.total_rows > 0 else 0
            res = {
                "upload_id": up.upload_id,
                "file_name": up.file_name,
                "file_type": up.file_type,
                "status": up.status,
                "total_rows": up.total_rows,
                "processed_rows": up.processed_rows,
                "unique_applications": up.unique_applications,
                "unique_machines": up.unique_machines,
                "resolved_count": up.resolved_count,
                "unresolved_count": up.unresolved_count,
                "cache_hits": up.cache_hits,
                "new_researched": up.new_researched,
                "progress_percent": percent,
                "error_message": up.error_message,
                "created_at": up.created_at.isoformat() if up.created_at else None,
                "completed_at": up.completed_at.isoformat() if up.completed_at else None,
            }
            return res
        finally:
            db.close()

    def list_recent_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Lists past upload jobs ordered by most recent.
        """
        db = SessionLocal()
        try:
            uploads = db.query(InventoryUpload).order_by(InventoryUpload.created_at.desc()).limit(limit).all()
            results = []
            for u in uploads:
                results.append({
                    "upload_id": u.upload_id,
                    "file_name": u.file_name,
                    "file_type": u.file_type,
                    "status": u.status,
                    "total_rows": u.total_rows,
                    "processed_rows": u.processed_rows,
                    "resolved_count": u.resolved_count,
                    "unresolved_count": u.unresolved_count,
                    "created_at": u.created_at.strftime("%Y-%m-%d %H:%M:%S") if u.created_at else "N/A",
                })
            return results
        finally:
            db.close()
