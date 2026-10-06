"""
FastAPI Router for Bulk CSV/Excel Software Inventory Uploads & Processing.
Provides isolated preview, start, progress monitoring, results exploration, and export endpoints.
"""

import json
import logging
from typing import Optional, Dict, Any, List
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    UploadFile,
    File,
    Form,
    status,
    Response,
)
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.inventory.processing.bulk_upload_service import BulkInventoryUploadService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inventory/upload", tags=["Bulk Inventory Upload & Intelligence"])


@router.post("/preview", status_code=status.HTTP_200_OK)
async def preview_uploaded_file(
    file: UploadFile = File(...),
):
    """
    Parses headers, detects column mappings, and returns a 10-row preview of an uploaded CSV or Excel file.
    """
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

        preview_data = BulkInventoryUploadService.preview_file(
            file_bytes=content,
            file_name=file.filename or "uploaded_inventory.csv",
        )
        return preview_data
    except Exception as e:
        logger.error(f"File preview failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File preview failed: {str(e)}")


@router.post("/start", status_code=status.HTTP_202_ACCEPTED)
@router.post("/process", status_code=status.HTTP_200_OK)
async def start_bulk_upload_job(
    file: UploadFile = File(...),
    column_mapping: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Initiates an asynchronous background License Intelligence job on the uploaded inventory file.
    """
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

        mapping_dict = {}
        if column_mapping:
            try:
                mapping_dict = json.loads(column_mapping)
            except Exception:
                logger.warning(f"Could not parse custom column_mapping: {column_mapping}")

        # If no mapping was provided, auto-detect mapping
        if not mapping_dict:
            preview = BulkInventoryUploadService.preview_file(
                file_bytes=content,
                file_name=file.filename or "uploaded_inventory.csv",
            )
            mapping_dict = preview.get("detected_mapping", {})

        job_info = BulkInventoryUploadService.start_upload_job(
            file_bytes=content,
            file_name=file.filename or "uploaded_inventory.csv",
            column_mapping=mapping_dict,
            run_async=True,
            db_session=db,
        )
        return job_info
    except Exception as e:
        logger.error(f"Job start failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to start job: {str(e)}")


@router.get("/jobs", status_code=status.HTTP_200_OK)
def list_upload_jobs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Lists all historical and ongoing inventory upload jobs."""
    return BulkInventoryUploadService.list_upload_jobs(limit=limit, db_session=db)


@router.get("/jobs/{upload_id}", status_code=status.HTTP_200_OK)
def get_upload_job_progress(
    upload_id: str,
    db: Session = Depends(get_db),
):
    """Retrieves real-time processing progress and status of a specific upload job."""
    progress = BulkInventoryUploadService.get_live_progress(upload_id=upload_id, db=db)
    return progress


@router.get("/jobs/{upload_id}/results", status_code=status.HTTP_200_OK)
def get_upload_results(
    upload_id: str,
    search: Optional[str] = Query(None, description="Search keyword"),
    classification: Optional[str] = Query(None, description="Filter by classification"),
    evidence_status: Optional[str] = Query(None, description="Filter by evidence status"),
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieves paginated and filtered license intelligence results for an upload."""
    results = BulkInventoryUploadService.get_upload_results(
        upload_id=upload_id,
        search=search,
        classification=classification,
        evidence_status=evidence_status,
        limit=limit,
        offset=offset,
        db_session=db,
    )
    return results


@router.get("/jobs/{upload_id}/export/csv")
def export_upload_results_csv(
    upload_id: str,
    db: Session = Depends(get_db),
):
    """Exports upload results as a CSV file with UTF-8 BOM."""
    csv_str = BulkInventoryUploadService.export_results_csv(upload_id=upload_id, db_session=db)
    if not csv_str:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No results found for export.")

    filename = f"{upload_id}_results.csv"
    return Response(
        content=csv_str.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/jobs/{upload_id}/export/excel")
def export_upload_results_excel(
    upload_id: str,
    db: Session = Depends(get_db),
):
    """Exports upload results as an Excel (.xlsx) file."""
    excel_bytes = BulkInventoryUploadService.export_results_excel(upload_id=upload_id, db_session=db)
    if not excel_bytes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No results found for export.")

    filename = f"{upload_id}_results.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.delete("/jobs/{upload_id}", status_code=status.HTTP_200_OK)
def delete_upload_job(
    upload_id: str,
    db: Session = Depends(get_db),
):
    """Deletes an upload job and its isolated results."""
    success = BulkInventoryUploadService.delete_upload_job(upload_id=upload_id, db_session=db)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload job not found.")
    return {"status": "DELETED", "upload_id": upload_id}
