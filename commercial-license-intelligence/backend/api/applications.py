"""FastAPI endpoints for Application Catalog, CSV Import/Export, and Batch Research."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.connection import get_db
from backend.models.enums import ApplicationStatus, ApplicationResearchStatus, BatchStatus
from backend.models.application import Application, ResearchBatch, ResearchBatchItem
from backend.models.profile import LicenseProfile
from backend.schemas.application import (
    ApplicationCreateRequest,
    ApplicationResponse,
    CsvImportPreviewResponse,
    CsvImportExecuteRequest,
    BatchResearchRequest,
    BatchResearchResponse,
)
from backend.consolidation.profile_schemas import LicenseProfileResponse, FieldExplanation, ProfileSummaryBlock
from backend.services.application_service import ApplicationService
from backend.services.batch_research_engine import BatchResearchEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Application Catalog & Batch Research Engine"])


# -------------------------------------------------------------
# 1. Application Catalog Endpoints
# -------------------------------------------------------------

@router.post("/applications", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_application(
    request: ApplicationCreateRequest,
    db: Session = Depends(get_db)
):
    """Register a new software application or retrieve existing entity if canonical key matches."""
    svc = ApplicationService()
    return svc.create_or_get_application(db, request)


@router.get("/applications", response_model=List[ApplicationResponse])
def list_applications(
    vendor: Optional[str] = Query(None, description="Filter by vendor"),
    product: Optional[str] = Query(None, description="Filter by product name"),
    version: Optional[str] = Query(None, description="Filter by version"),
    operating_system: Optional[str] = Query(None, description="Filter by OS"),
    status_filter: Optional[ApplicationStatus] = Query(None, alias="status"),
    research_status: Optional[ApplicationResearchStatus] = Query(None),
    search: Optional[str] = Query(None, description="Partial search query across vendor, product, display name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Retrieve filtered list of cataloged applications."""
    query = db.query(Application)

    if vendor:
        query = query.filter(func.lower(Application.vendor_name) == vendor.strip().lower())
    if product:
        query = query.filter(func.lower(Application.product_name) == product.strip().lower())
    if version:
        query = query.filter(func.lower(Application.version) == version.strip().lower())
    if operating_system:
        query = query.filter(func.lower(Application.operating_system) == operating_system.strip().lower())
    if status_filter:
        query = query.filter(Application.status == status_filter)
    if research_status:
        query = query.filter(Application.research_status == research_status)

    if search:
        s = f"%{search.strip().lower()}%"
        query = query.filter(
            func.lower(Application.vendor_name).like(s) |
            func.lower(Application.product_name).like(s) |
            func.lower(Application.display_name).like(s) |
            func.lower(Application.application_key).like(s)
        )

    return query.order_by(Application.id.desc()).offset(skip).limit(limit).all()


@router.get("/applications/{app_id}", response_model=ApplicationResponse)
def get_application_detail(app_id: int, db: Session = Depends(get_db)):
    """Retrieve application identity and research state by ID."""
    app_obj = db.query(Application).filter(Application.id == app_id).first()
    if not app_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application ID {app_id} not found in catalog."
        )
    return app_obj


@router.get("/applications/{app_id}/license-profile", response_model=Optional[LicenseProfileResponse])
def get_application_license_profile(app_id: int, db: Session = Depends(get_db)):
    """Retrieve the active consolidated license profile for this application."""
    app_obj = db.query(Application).filter(Application.id == app_id).first()
    if not app_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application {app_id} not found.")

    if not app_obj.current_profile_id:
        return None

    p = db.query(LicenseProfile).filter(LicenseProfile.id == app_obj.current_profile_id).first()
    if not p:
        return None

    exp_dict = {}
    if p.explanation_json:
        for k, v in p.explanation_json.items():
            exp_dict[k] = FieldExplanation(**v)

    summary_block = ProfileSummaryBlock(
        required=p.license_required,
        classification=p.license_classification,
        model=p.license_model,
        metric=p.license_metric,
        duration=p.license_duration
    )

    return LicenseProfileResponse(
        id=p.id,
        vendor=p.vendor_name,
        product=p.product_name,
        edition=p.edition,
        version=p.version,
        license_classification=p.license_classification,
        license_required=p.license_required,
        license_model=p.license_model,
        license_metric=p.license_metric,
        license_duration=p.license_duration,
        commercial_use=p.commercial_use,
        educational_use=p.educational_use,
        trial_available=p.trial_available,
        overall_confidence=p.overall_confidence,
        profile_status=p.profile_status,
        validated_fact_count=p.validated_fact_count,
        review_fact_count=p.review_fact_count,
        conflict_fact_count=p.conflict_fact_count,
        unknown_fact_count=p.unknown_fact_count,
        profile_hash=p.profile_hash,
        explanations=exp_dict,
        license_summary=summary_block,
        generated_at=p.generated_at
    )


# -------------------------------------------------------------
# 2. CSV Import / Export Endpoints
# -------------------------------------------------------------

@router.post("/applications/import/preview", response_model=CsvImportPreviewResponse)
async def preview_csv_import_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Preview uploaded CSV records and validate data integrity before importing."""
    content = await file.read()
    csv_text = content.decode("utf-8", errors="replace")
    svc = ApplicationService()
    return svc.preview_csv_import(db, csv_text)


@router.post("/applications/import/csv", response_model=List[ApplicationResponse])
def execute_csv_import_endpoint(
    request: CsvImportExecuteRequest,
    db: Session = Depends(get_db)
):
    """Imports validated application records into the persistent catalog."""
    svc = ApplicationService()
    return svc.execute_csv_import(db, request.records)


@router.get("/applications/export/csv")
def export_catalog_csv_endpoint(db: Session = Depends(get_db)):
    """Exports all cataloged applications with their consolidated license profiles as a downloadable CSV."""
    svc = ApplicationService()
    csv_data = svc.export_catalog_csv(db)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=application_license_catalog.csv"}
    )


# -------------------------------------------------------------
# 3. Batch Research Endpoints
# -------------------------------------------------------------

@router.post("/research/batch", response_model=BatchResearchResponse, status_code=status.HTTP_200_OK)
def start_batch_research(
    request: BatchResearchRequest,
    db: Session = Depends(get_db)
):
    """
    Launches a controlled batch research job across specified application IDs.
    """
    engine = BatchResearchEngine()
    batch = engine.create_batch(db, request)
    # Run synchronously or background
    return engine.run_batch_synchronous(db, batch.id, force_refresh=request.force_refresh)


@router.get("/research/batch/{batch_id}", response_model=BatchResearchResponse)
def get_batch_progress_endpoint(
    batch_id: int,
    db: Session = Depends(get_db)
):
    """Retrieves real-time execution progress, item statuses, and metrics for a batch research job."""
    engine = BatchResearchEngine()
    return engine.get_batch_progress(db, batch_id)


@router.post("/research/batch/{batch_id}/retry-failed", response_model=BatchResearchResponse)
def retry_failed_batch_items(
    batch_id: int,
    db: Session = Depends(get_db)
):
    """Retries all failed application research items in a batch."""
    engine = BatchResearchEngine()
    return engine.run_batch_synchronous(db, batch_id, force_refresh=True)
