"""FastAPI endpoints for License Entitlements, Consumption, and License Position Calculations."""

import io
import csv
import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.connection import get_db
from backend.models.enums import EntitlementStatus, EntitlementType, EntitlementSourceType
from backend.models.entitlement import (
    LicenseEntitlement,
    LicenseConsumption,
    LicensePosition,
    LicensePositionHistory,
)
from backend.models.application import Application
from backend.entitlement.position_result import (
    EntitlementCreateRequest,
    EntitlementResponse,
    ConsumptionCreateRequest,
    ConsumptionResponse,
    LicensePositionResponse,
    LicensePositionHistoryResponse,
)
from backend.entitlement.entitlement_service import EntitlementService
from backend.entitlement.consumption_service import ConsumptionService
from backend.entitlement.position_engine import LicensePositionEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["License Entitlements & Position Engine"])


# -------------------------------------------------------------
# Entitlement Endpoints
# -------------------------------------------------------------

@router.post("/api/entitlements", response_model=EntitlementResponse, status_code=status.HTTP_201_CREATED)
def create_entitlement_endpoint(
    request: EntitlementCreateRequest,
    db: Session = Depends(get_db)
):
    """Registers an official software license entitlement."""
    svc = EntitlementService()
    try:
        ent = svc.create_entitlement(db, request)
        return ent
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.get("/api/entitlements", response_model=List[EntitlementResponse])
def list_entitlements_endpoint(
    application_id: Optional[int] = Query(None),
    vendor: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    status: Optional[EntitlementStatus] = Query(None),
    db: Session = Depends(get_db)
):
    """Lists registered license entitlements with optional filters."""
    svc = EntitlementService()
    return svc.list_entitlements(db, application_id=application_id, vendor=vendor, product=product, status=status)


@router.get("/api/entitlements/{id}", response_model=EntitlementResponse)
def get_entitlement_detail(
    id: int,
    db: Session = Depends(get_db)
):
    """Retrieves single entitlement record."""
    ent = db.query(LicenseEntitlement).filter(LicenseEntitlement.id == id).first()
    if not ent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Entitlement ID {id} not found.")
    return ent


@router.post("/api/entitlements/import", response_model=List[EntitlementResponse])
async def import_entitlements_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Imports license entitlements from CSV.
    Expected headers: vendor, product, edition, version, quantity, metric, start_date, end_date, entitlement_type, source_type, source_reference.
    """
    content = await file.read()
    csv_text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(csv_text))

    svc = EntitlementService()
    created_list = []

    for row in reader:
        row_norm = {k.strip().lower(): v.strip() for k, v in row.items() if k and v}
        vendor = row_norm.get("vendor") or row_norm.get("vendor_name")
        product = row_norm.get("product") or row_norm.get("product_name")
        qty_str = row_norm.get("quantity") or row_norm.get("qty") or "1"
        metric = row_norm.get("metric") or "NAMED_USER"

        if not vendor or not product:
            continue

        try:
            qty = float(qty_str)
        except ValueError:
            qty = 1.0

        start_d = None
        if row_norm.get("start_date"):
            try:
                start_d = datetime.fromisoformat(row_norm["start_date"])
            except ValueError:
                pass

        end_d = None
        if row_norm.get("end_date"):
            try:
                end_d = datetime.fromisoformat(row_norm["end_date"])
            except ValueError:
                pass

        req = EntitlementCreateRequest(
            vendor_name=vendor,
            product_name=product,
            edition=row_norm.get("edition"),
            version=row_norm.get("version"),
            quantity=qty,
            metric=metric,
            license_start_date=start_d,
            license_end_date=end_d,
            agreement_id=row_norm.get("agreement_id"),
            contract_reference=row_norm.get("contract_reference") or row_norm.get("contract"),
            source_type=EntitlementSourceType.CSV_IMPORT,
            source_reference=row_norm.get("source_reference")
        )

        try:
            ent = svc.create_entitlement(db, req)
            created_list.append(ent)
        except Exception as e:
            logger.warning(f"Skipping CSV row {vendor} {product}: {e}")

    return created_list


# -------------------------------------------------------------
# Consumption Endpoints
# -------------------------------------------------------------

@router.post("/api/consumption", response_model=ConsumptionResponse, status_code=status.HTTP_201_CREATED)
def record_consumption_endpoint(
    request: ConsumptionCreateRequest,
    db: Session = Depends(get_db)
):
    """Records measured license consumption."""
    svc = ConsumptionService()
    try:
        return svc.record_consumption(db, request)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.get("/api/consumption", response_model=List[ConsumptionResponse])
def list_consumption_endpoint(
    application_id: Optional[int] = Query(None),
    metric: Optional[str] = Query(None),
    device_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Lists active license consumption records."""
    svc = ConsumptionService()
    return svc.list_consumption(db, application_id=application_id, metric=metric, device_id=device_id)


# -------------------------------------------------------------
# License Position Endpoints
# -------------------------------------------------------------

@router.post("/api/license-position/{application_id}/calculate", response_model=LicensePositionResponse)
def calculate_license_position(
    application_id: int,
    db: Session = Depends(get_db)
):
    """Calculates or refreshes the license reconciliation position for an application."""
    engine = LicensePositionEngine()
    try:
        return engine.calculate_position(db, application_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get("/api/license-position/{application_id}", response_model=LicensePositionResponse)
def get_license_position(
    application_id: int,
    db: Session = Depends(get_db)
):
    """Retrieves the latest calculated license position for an application."""
    engine = LicensePositionEngine()
    pos = db.query(LicensePosition).filter(LicensePosition.application_id == application_id).first()
    if not pos:
        return engine.calculate_position(db, application_id)

    app_obj = db.query(Application).filter(Application.id == application_id).first()
    prof = None
    if app_obj and app_obj.current_profile_id:
        from backend.models.profile import LicenseProfile
        prof = db.query(LicenseProfile).filter(LicenseProfile.id == app_obj.current_profile_id).first()

    inst_cnt = 0
    from backend.models.inventory import DetectedApplication
    from backend.models.enums import DetectedAppStatus
    inst_cnt = db.query(DetectedApplication).filter(
        DetectedApplication.resolved_application_id == application_id,
        DetectedApplication.status == DetectedAppStatus.ACTIVE
    ).count()

    return LicensePositionResponse(
        application_id=app_obj.id,
        vendor_name=app_obj.vendor_name,
        product_name=app_obj.product_name,
        edition=app_obj.edition,
        version=app_obj.version,
        operating_system=app_obj.operating_system,
        profile_license_model=prof.license_model if prof else "UNKNOWN",
        profile_license_metric=prof.license_metric if prof else "UNKNOWN",
        metric=pos.metric,
        entitled_quantity=pos.entitled_quantity,
        consumed_quantity=pos.consumed_quantity,
        installed_devices_count=inst_cnt,
        available_quantity=pos.available_quantity,
        overdeployment_quantity=pos.overdeployment_quantity,
        position_status=pos.position_status,
        status_reason=pos.status_reason,
        calculated_at=pos.calculated_at,
        calculation_version=pos.calculation_version
    )


@router.get("/api/license-position/{application_id}/history", response_model=List[LicensePositionHistoryResponse])
def get_license_position_history(
    application_id: int,
    db: Session = Depends(get_db)
):
    """Retrieves immutable historical calculation snapshots for auditability."""
    history = db.query(LicensePositionHistory).filter(
        LicensePositionHistory.application_id == application_id
    ).order_by(LicensePositionHistory.id.desc()).all()
    return history
