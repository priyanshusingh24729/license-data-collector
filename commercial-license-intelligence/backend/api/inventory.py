"""FastAPI endpoints for Endpoint Inventory Ingestion and Identity Resolution."""

import io
import csv
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.connection import get_db
from backend.models.enums import (
    DeviceStatus,
    DetectedAppStatus,
    DetectionMethod,
    MatchType,
    ResolutionQueueStatus,
    ExtractionConfidence,
)
from backend.models.inventory import (
    Device,
    DetectedApplication,
    DeviceApplication,
    ApplicationResolutionQueue,
    InstallationLicenseResult,
)
from backend.models.application import Application
from backend.models.profile import LicenseProfile
from backend.inventory.detection.detection_result import (
    InventoryIngestRequest,
    InventoryIngestResponse,
    ResolutionQueueItemResponse,
    ResolutionCandidateDetail,
    ManualResolveRequest,
    InventoryCatalogAppSummary,
    DeviceDetailResponse,
    ApplicationIngestItem,
    DeviceIngestPayload,
    InstallationLicenseResultResponse,
    MachineInventorySummaryResponse,
)
from backend.inventory.detection.inventory_ingestor import InventoryIngestor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inventory", tags=["Endpoint Inventory & Identity Resolution"])


@router.post("/scan", status_code=status.HTTP_200_OK)
def trigger_fresh_windows_scan(
    dry_run: bool = Query(False, description="Scan Windows without committing DB mutations"),
    db: Session = Depends(get_db)
):
    """
    Triggers a fresh, live multi-source Windows discovery across Registry, AppX, Winget, and Start Menu.
    Synchronizes new and existing applications into the database.
    """
    from backend.inventory.detection.live_scanner import LiveWindowsScanner
    return LiveWindowsScanner.execute_fresh_scan(db=db, dry_run=dry_run)


@router.post("/ingest", response_model=InventoryIngestResponse, status_code=status.HTTP_200_OK)
def ingest_inventory_endpoint(
    request: InventoryIngestRequest,
    db: Session = Depends(get_db)
):
    """Ingests raw endpoint application inventory and performs automatic identity resolution."""
    ingestor = InventoryIngestor()
    return ingestor.ingest_inventory(db, request)


@router.get("/applications", response_model=List[InventoryCatalogAppSummary])
def list_inventory_applications(
    vendor: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Lists catalog applications alongside their active installation count and licensing intelligence profile.
    Explicitly distinguishes between installation detection and license entitlement.
    """
    q = db.query(Application)
    if vendor:
        q = q.filter(func.lower(Application.vendor_name) == vendor.strip().lower())
    if search:
        s = f"%{search.strip().lower()}%"
        q = q.filter(func.lower(Application.product_name).like(s) | func.lower(Application.vendor_name).like(s))

    apps = q.order_by(Application.id.asc()).limit(limit).all()
    results = []

    for a in apps:
        # Count active installations referencing this resolved application
        inst_count = (
            db.query(DetectedApplication)
            .filter(
                DetectedApplication.resolved_application_id == a.id,
                DetectedApplication.status == DetectedAppStatus.ACTIVE
            )
            .count()
        )

        profile = db.query(LicenseProfile).filter(LicenseProfile.id == a.current_profile_id).first() if a.current_profile_id else None

        results.append(InventoryCatalogAppSummary(
            id=a.id,
            vendor_name=a.vendor_name,
            product_name=a.product_name,
            edition=a.edition,
            version=a.version,
            operating_system=a.operating_system,
            installed_count=inst_count,
            license_profile_id=profile.id if profile else None,
            license_classification=profile.license_classification if profile else "UNKNOWN",
            license_model=profile.license_model if profile else "UNKNOWN",
            license_metric=profile.license_metric if profile else "UNKNOWN",
            overall_confidence=profile.overall_confidence if profile else ExtractionConfidence.UNKNOWN,
            profile_status=profile.profile_status.value if profile else "NOT_RESEARCHED"
        ))

    return results


@router.get("/devices", response_model=List[DeviceDetailResponse])
def list_devices(
    status_filter: Optional[DeviceStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db)
):
    """Lists registered endpoint devices."""
    q = db.query(Device)
    if status_filter:
        q = q.filter(Device.status == status_filter)
    devices = q.order_by(Device.last_seen_at.desc()).all()

    res = []
    for d in devices:
        res.append(DeviceDetailResponse(
            id=d.id,
            device_key=d.device_key,
            hostname=d.hostname,
            operating_system=d.operating_system,
            os_version=d.os_version,
            architecture=d.architecture,
            status=d.status,
            last_seen_at=d.last_seen_at,
            installed_applications=[]
        ))
    return res


@router.get("/devices/{device_id}", response_model=DeviceDetailResponse)
def get_device_detail(
    device_id: int,
    db: Session = Depends(get_db)
):
    """Retrieves full device metadata and its installed application inventory."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device ID {device_id} not found.")

    det_apps = db.query(DetectedApplication).filter(
        DetectedApplication.device_id == device.id,
        DetectedApplication.status == DetectedAppStatus.ACTIVE
    ).all()

    app_details = []
    for da in det_apps:
        res_app = db.query(Application).filter(Application.id == da.resolved_application_id).first() if da.resolved_application_id else None
        prof = None
        if res_app and res_app.current_profile_id:
            prof = db.query(LicenseProfile).filter(LicenseProfile.id == res_app.current_profile_id).first()

        app_details.append({
            "id": da.id,
            "raw_name": da.raw_name,
            "normalized_name": da.normalized_name,
            "version": da.detected_version,
            "resolution_type": da.resolution_type.value,
            "resolution_confidence": da.resolution_confidence.value,
            "resolved_application": res_app.display_name if res_app else None,
            "license_model": prof.license_model if prof else "UNKNOWN",
            "license_metric": prof.license_metric if prof else "UNKNOWN",
            "first_seen_at": da.first_seen_at.strftime("%Y-%m-%d %H:%M"),
            "last_seen_at": da.last_seen_at.strftime("%Y-%m-%d %H:%M")
        })

    return DeviceDetailResponse(
        id=device.id,
        device_key=device.device_key,
        hostname=device.hostname,
        operating_system=device.operating_system,
        os_version=device.os_version,
        architecture=device.architecture,
        status=device.status,
        last_seen_at=device.last_seen_at,
        installed_applications=app_details
    )


@router.get("/unresolved", response_model=List[ResolutionQueueItemResponse])
def list_unresolved_queue(
    status_filter: Optional[ResolutionQueueStatus] = Query(ResolutionQueueStatus.PENDING, alias="status"),
    db: Session = Depends(get_db)
):
    """Retrieves items in the human review queue for ambiguous or low-confidence resolutions."""
    q = db.query(ApplicationResolutionQueue)
    if status_filter:
        q = q.filter(ApplicationResolutionQueue.status == status_filter)

    items = q.order_by(ApplicationResolutionQueue.id.desc()).all()

    # Group by detected_application_id to assemble candidate list
    grouped: dict = {}
    for it in items:
        det = db.query(DetectedApplication).filter(DetectedApplication.id == it.detected_application_id).first()
        if not det:
            continue
        dev = db.query(Device).filter(Device.id == det.device_id).first()

        cand_app = db.query(Application).filter(Application.id == it.candidate_application_id).first() if it.candidate_application_id else None

        cand_detail = None
        if cand_app:
            cand_detail = ResolutionCandidateDetail(
                candidate_id=cand_app.id,
                vendor_name=cand_app.vendor_name,
                product_name=cand_app.product_name,
                edition=cand_app.edition,
                version=cand_app.version,
                operating_system=cand_app.operating_system,
                match_score=it.match_score,
                confidence=it.confidence,
                reason=it.reason
            )

        if it.detected_application_id not in grouped:
            grouped[it.detected_application_id] = ResolutionQueueItemResponse(
                queue_id=it.id,
                detected_application_id=det.id,
                device_key=dev.device_key if dev else "UNKNOWN",
                hostname=dev.hostname if dev else None,
                raw_name=det.raw_name,
                raw_publisher=det.raw_publisher,
                raw_version=det.raw_version,
                normalized_name=det.normalized_name,
                operating_system=det.operating_system,
                match_type=it.match_type,
                match_score=it.match_score,
                confidence=it.confidence,
                status=it.status,
                created_at=it.created_at,
                candidates=[cand_detail] if cand_detail else []
            )
        elif cand_detail:
            grouped[it.detected_application_id].candidates.append(cand_detail)

    return list(grouped.values())


@router.post("/resolve/{queue_id}", response_model=ResolutionQueueItemResponse)
def resolve_queue_item(
    queue_id: int,
    request: ManualResolveRequest,
    db: Session = Depends(get_db)
):
    """Manually resolves an ambiguous detection by selecting an accepted catalog candidate."""
    item = db.query(ApplicationResolutionQueue).filter(ApplicationResolutionQueue.id == queue_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Queue item {queue_id} not found.")

    det_app = db.query(DetectedApplication).filter(DetectedApplication.id == item.detected_application_id).first()
    if not det_app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detected application not found.")

    if request.action == ResolutionQueueStatus.ACCEPTED and request.accepted_application_id:
        target_app = db.query(Application).filter(Application.id == request.accepted_application_id).first()
        if not target_app:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target catalog application not found.")
        det_app.resolved_application_id = target_app.id
        det_app.resolution_type = MatchType.MANUAL_MATCH
        det_app.resolution_confidence = ExtractionConfidence.VERY_HIGH

        item.status = ResolutionQueueStatus.ACCEPTED
        item.candidate_application_id = target_app.id
    elif request.action == ResolutionQueueStatus.REJECTED:
        det_app.resolved_application_id = None
        det_app.resolution_type = MatchType.NO_MATCH
        item.status = ResolutionQueueStatus.REJECTED

    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)

    dev = db.query(Device).filter(Device.id == det_app.device_id).first()
    return ResolutionQueueItemResponse(
        queue_id=item.id,
        detected_application_id=det_app.id,
        device_key=dev.device_key if dev else "UNKNOWN",
        hostname=dev.hostname if dev else None,
        raw_name=det_app.raw_name,
        raw_publisher=det_app.raw_publisher,
        raw_version=det_app.raw_version,
        normalized_name=det_app.normalized_name,
        operating_system=det_app.operating_system,
        match_type=item.match_type,
        match_score=item.match_score,
        confidence=item.confidence,
        status=item.status,
        created_at=item.created_at,
        candidates=[]
    )


@router.post("/import", response_model=InventoryIngestResponse)
async def import_inventory_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Imports inventory from a CSV file (columns: device_key, hostname, operating_system, application_name, publisher, version)."""
    content = await file.read()
    csv_text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(csv_text))

    device_map: dict = {}
    for row in reader:
        row_norm = {k.strip().lower(): v.strip() for k, v in row.items() if k and v}
        d_key = row_norm.get("device_key") or "UNKNOWN_DEVICE"
        app_name = row_norm.get("application_name") or row_norm.get("name") or row_norm.get("product")
        if not app_name:
            continue

        if d_key not in device_map:
            device_map[d_key] = {
                "device": DeviceIngestPayload(
                    device_key=d_key,
                    hostname=row_norm.get("hostname"),
                    operating_system=row_norm.get("operating_system") or row_norm.get("os"),
                    os_version=row_norm.get("os_version"),
                    architecture=row_norm.get("architecture")
                ),
                "apps": []
            }

        device_map[d_key]["apps"].append(ApplicationIngestItem(
            name=app_name,
            publisher=row_norm.get("publisher") or row_norm.get("vendor"),
            version=row_norm.get("version"),
            install_location=row_norm.get("install_location"),
            detection_method=DetectionMethod.MANUAL_IMPORT
        ))

    ingestor = InventoryIngestor()
    total_reported = 0
    total_resolved = 0
    total_unresolved = 0
    last_res = None

    for d_key, data in device_map.items():
        req = InventoryIngestRequest(device=data["device"], applications=data["apps"])
        res = ingestor.ingest_inventory(db, req)
        total_reported += res.total_reported
        total_resolved += res.resolved_count
        total_unresolved += res.unresolved_count
        last_res = res

    if not last_res:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid inventory records found in CSV.")

    return InventoryIngestResponse(
        device_id=last_res.device_id,
        device_key="BATCH_CSV_IMPORT",
        total_reported=total_reported,
        resolved_count=total_resolved,
        unresolved_count=total_unresolved,
        applications=last_res.applications
    )


@router.get("/installation-results", response_model=List[InstallationLicenseResultResponse])
def get_installation_license_results(
    unique_id: Optional[str] = Query(None, description="Filter by machine Unique_ID (e.g. PF490A36_LAPTOP-TTASCMUO)"),
    hostname: Optional[str] = Query(None, description="Filter by Hostname"),
    serial: Optional[str] = Query(None, description="Filter by Serial number"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Retrieves processed license intelligence results for a specific machine installation inventory.
    Preserves strict data isolation from the main detected_applications baseline.
    """
    q = db.query(InstallationLicenseResult)
    if unique_id:
        q = q.filter(func.lower(InstallationLicenseResult.unique_id) == unique_id.strip().lower())
    if hostname:
        q = q.filter(func.lower(InstallationLicenseResult.hostname) == hostname.strip().lower())
    if serial:
        q = q.filter(func.lower(InstallationLicenseResult.serial) == serial.strip().lower())

    results = q.order_by(InstallationLicenseResult.id.asc()).offset(offset).limit(limit).all()
    return results


@router.get("/main-applications")
def get_main_application_inventory(
    search: Optional[str] = Query(None),
    classification: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Retrieves the main application inventory (detected_applications baseline) with full license intelligence resolution.
    Strictly isolated from machine-specific installation results.
    """
    from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine

    detected_apps = db.query(DetectedApplication).order_by(DetectedApplication.id.asc()).offset(offset).limit(limit).all()
    results = []
    for da in detected_apps:
        h_rec = HybridLicenseEngine.resolve_hybrid_record(
            app_id=da.id,
            name=da.raw_name or da.normalized_name,
            publisher=da.normalized_publisher or da.raw_publisher,
            version=da.detected_version or da.raw_version,
            raw_package_name=da.raw_name,
            install_location=da.install_location,
        )
        item = {
            "id": da.id,
            "application": h_rec["application"],
            "vendor": h_rec["vendor"],
            "version": h_rec["version"],
            "classification": h_rec["classification"],
            "availability": h_rec["availability"],
            "license_required": h_rec["license_required"],
            "license_model": h_rec["license_model"],
            "metric": h_rec["metric"],
            "confidence": h_rec["confidence"],
            "reliability_score": h_rec.get("reliability_score", 0.0),
            "reliability_str": h_rec["reliability_str"],
            "evidence_status": h_rec["evidence_status"],
            "raw_name": da.raw_name,
            "raw_publisher": da.raw_publisher,
            "install_source": da.install_source,
            "detection_method": da.detection_method.value if hasattr(da.detection_method, "value") else str(da.detection_method),
        }
        if classification and classification != "ALL":
            if item["classification"].upper() != classification.strip().upper():
                continue
        if search:
            sq = search.strip().lower()
            if not (
                sq in item["application"].lower()
                or sq in (item["vendor"] or "").lower()
                or sq in (item["version"] or "").lower()
                or sq in item["classification"].lower()
            ):
                continue
        results.append(item)

    return results


@router.get("/main-applications/export")
def export_main_application_inventory_csv(
    db: Session = Depends(get_db)
):
    """
    Exports the main application inventory (detected_applications baseline) as a deduplicated, validated CSV file.
    """
    from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
    from backend.validation.export_validator import ExportValidator

    detected_apps = db.query(DetectedApplication).order_by(DetectedApplication.id.asc()).all()
    
    raw_rows = []
    for da in detected_apps:
        h_rec = HybridLicenseEngine.resolve_hybrid_record(
            app_id=da.id,
            name=da.raw_name or da.normalized_name,
            publisher=da.normalized_publisher or da.raw_publisher,
            version=da.detected_version or da.raw_version,
            raw_package_name=da.raw_name,
            install_location=da.install_location,
        )
        raw_rows.append({
            "ID": da.id,
            "Application": h_rec["application"],
            "Vendor": h_rec["vendor"],
            "Version": h_rec["version"],
            "Classification": h_rec["classification"],
            "Availability": h_rec["availability"],
            "License Required": h_rec["license_required"],
            "License Model": h_rec["license_model"],
            "Metric": h_rec["metric"],
            "Confidence": h_rec["confidence"],
            "Reliability": h_rec["reliability_str"],
            "Evidence Status": h_rec["evidence_status"],
            "Detection Method": da.detection_method.value if hasattr(da.detection_method, "value") else str(da.detection_method),
        })

    # Apply quality pipeline: Dedup, Fix Schema, Enforce Evidence Consistency
    deduped_rows = ExportValidator.deduplicate_records(raw_rows)
    ExportValidator.fix_schema_violations(deduped_rows)
    ExportValidator.enforce_evidence_consistency(deduped_rows)

    output = io.StringIO()
    # Write UTF-8 BOM for Excel compatibility
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Application", "Vendor", "Version", "Classification", "Availability",
        "License Required", "License Model", "Metric", "Confidence", "Reliability",
        "Evidence Status", "Detection Method"
    ])

    for row in deduped_rows:
        writer.writerow([
            row["ID"],
            row["Application"],
            row["Vendor"],
            row["Version"],
            row["Classification"],
            row["Availability"],
            row["License Required"],
            row["License Model"],
            row["Metric"],
            row["Confidence"],
            row["Reliability"],
            row["Evidence Status"],
            row["Detection Method"],
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=main_application_inventory.csv"}
    )


@router.get("/installation-results/export")
def export_installation_results_csv(
    unique_id: Optional[str] = Query(None, description="Filter by machine Unique_ID"),
    db: Session = Depends(get_db)
):
    """
    Exports machine installation license results as an isolated, validated CSV file.
    """
    from backend.validation.export_validator import ExportValidator

    q = db.query(InstallationLicenseResult)
    if unique_id:
        q = q.filter(func.lower(InstallationLicenseResult.unique_id) == unique_id.strip().lower())

    records = q.order_by(InstallationLicenseResult.id.asc()).all()
    
    # Deduplicate machine records by (Hostname, Canonical_Product, Raw_Version, Canonical_Vendor)
    seen_keys = set()
    deduped_records = []
    for r in records:
        key = (
            (r.hostname or "").strip().lower(),
            (r.canonical_product or r.raw_application_name or "").strip().lower(),
            (r.raw_version or "").strip().lower(),
            (r.canonical_vendor or r.raw_vendor or "").strip().lower(),
        )
        if key not in seen_keys:
            seen_keys.add(key)
            deduped_records.append(r)

    output = io.StringIO()
    # Write UTF-8 BOM for Excel compatibility
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Unique_ID", "Hostname", "Serial", "IP_Address", "Raw_Application_Name",
        "Raw_Vendor", "Raw_Version", "Install_Date", "Install_Source", "Install_Location",
        "Canonical_Product", "Canonical_Vendor", "Classification", "License_Requirement",
        "License_Model", "License_Metric", "Evidence_Status", "Confidence", "Reliability_Score",
        "Evidence_Source", "Evidence_URL", "Research_Status", "Processed_At"
    ])

    for r in deduped_records:
        req = r.license_requirement
        if req == "NOT_APPLICABLE":
            req = "NO"

        ev_status = r.evidence_status
        if ev_status == "VERIFIED" and (not r.raw_version or r.raw_version in ("N/A", "UNKNOWN")):
            ev_status = "PARTIAL"

        writer.writerow([
            r.id,
            r.unique_id,
            r.hostname,
            r.serial,
            r.ip_address,
            r.raw_application_name,
            r.raw_vendor,
            r.raw_version,
            r.install_date,
            r.install_source,
            r.install_location,
            r.canonical_product,
            r.canonical_vendor,
            r.classification,
            req,
            r.license_model,
            r.license_metric,
            ev_status,
            r.confidence,
            f"{r.reliability_score}%" if r.reliability_score is not None else "",
            r.evidence_source,
            r.evidence_url,
            r.research_status,
            r.processed_at.isoformat() if r.processed_at else ""
        ])

    csv_data = output.getvalue()
    filename = f"{unique_id or 'all_machines'}_installation_results.csv"
    return Response(
        content=csv_data.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


