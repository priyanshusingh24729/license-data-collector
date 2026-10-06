"""
Endpoint Inventory Ingestion Coordinator.
Processes device metadata and detected application payloads, normalizes strings,
resolves catalog identities, and updates installation relationships.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from backend.models.enums import DeviceStatus, DetectedAppStatus, MatchType
from backend.models.inventory import Device, DetectedApplication, DeviceApplication, ApplicationResolutionQueue
from backend.models.application import Application
from backend.inventory.detection.detection_normalizer import DetectionNormalizer
from backend.inventory.detection.identity_resolver import IdentityResolver
from backend.inventory.detection.detection_result import (
    InventoryIngestRequest,
    InventoryIngestResponse,
    IngestedApplicationSummary,
)

logger = logging.getLogger(__name__)


class InventoryIngestor:
    """
    Ingests and processes raw application inventory reports from endpoint devices.
    """

    def __init__(self, resolver: Optional[IdentityResolver] = None):
        self.resolver = resolver or IdentityResolver()
        self.normalizer = DetectionNormalizer()

    def ingest_inventory(
        self,
        db: Session,
        req: InventoryIngestRequest
    ) -> InventoryIngestResponse:
        """
        Ingests endpoint inventory, updates device records, and performs identity resolution.
        """
        now = datetime.now(timezone.utc)
        d_payload = req.device

        # 1. Get or create Device
        device = db.query(Device).filter(Device.device_key == d_payload.device_key).first()
        if not device:
            device = Device(
                device_key=d_payload.device_key,
                hostname=d_payload.hostname,
                operating_system=d_payload.operating_system,
                os_version=d_payload.os_version,
                architecture=d_payload.architecture,
                agent_version=d_payload.agent_version,
                status=DeviceStatus.ACTIVE,
                last_seen_at=now,
                created_at=now,
                updated_at=now
            )
            db.add(device)
            db.commit()
            db.refresh(device)
        else:
            device.hostname = d_payload.hostname or device.hostname
            device.operating_system = d_payload.operating_system or device.operating_system
            device.os_version = d_payload.os_version or device.os_version
            device.architecture = d_payload.architecture or device.architecture
            device.agent_version = d_payload.agent_version or device.agent_version
            device.last_seen_at = now
            device.status = DeviceStatus.ACTIVE
            db.commit()

        resolved_count = 0
        unresolved_count = 0
        summaries: List[IngestedApplicationSummary] = []

        from backend.inventory.detection.qualification_filter import ApplicationQualificationFilter

        # 2. Process each detected application
        for item in req.applications:
            # Check qualification
            candidate_dict = {
                "raw_name": item.name,
                "raw_publisher": item.publisher,
                "raw_version": item.version,
                "raw_install_location": item.install_location,
                "install_source": str(item.install_source) if item.install_source else str(item.detection_method),
                "detection_method": str(item.detection_method) if item.detection_method else "MANUAL_IMPORT",
            }
            is_qual, qual_reason, _ = ApplicationQualificationFilter.qualify_candidate(candidate_dict)
            if not is_qual:
                logger.debug(f"Ingestion candidate '{item.name}' disqualified: {qual_reason}")
                continue

            norm_name = self.normalizer.normalize_name(item.name)
            norm_pub = self.normalizer.normalize_publisher(item.publisher)
            raw_v, maj_v, min_v, pat_v = self.normalizer.normalize_version(item.version)

            # Check if this application is already detected on this device
            detected_app = db.query(DetectedApplication).filter(
                DetectedApplication.device_id == device.id,
                DetectedApplication.normalized_name == norm_name
            ).first()

            if not detected_app:
                detected_app = DetectedApplication(
                    device_id=device.id,
                    raw_name=item.name,
                    raw_publisher=item.publisher,
                    raw_version=item.version,
                    normalized_name=norm_name,
                    normalized_publisher=norm_pub,
                    detected_version=raw_v,
                    major_version=maj_v,
                    minor_version=min_v,
                    patch_version=pat_v,
                    operating_system=d_payload.operating_system,
                    install_location=item.install_location,
                    install_source=item.install_source,
                    architecture=item.architecture,
                    detection_method=item.detection_method,
                    detected_at=now,
                    first_seen_at=now,
                    last_seen_at=now,
                    status=DetectedAppStatus.ACTIVE,
                    created_at=now,
                    updated_at=now
                )
                db.add(detected_app)
                db.commit()
                db.refresh(detected_app)

                # Create DeviceApplication association link
                dev_app = DeviceApplication(
                    device_id=device.id,
                    detected_application_id=detected_app.id,
                    first_seen_at=now,
                    last_seen_at=now,
                    status=DetectedAppStatus.ACTIVE
                )
                db.add(dev_app)
                db.commit()
            else:
                # Update existing detection
                detected_app.last_seen_at = now
                detected_app.status = DetectedAppStatus.ACTIVE
                detected_app.detected_version = raw_v
                detected_app.major_version = maj_v
                detected_app.minor_version = min_v
                detected_app.patch_version = pat_v
                db.commit()

            # 3. Resolve Identity against catalog
            m_type, res_app_id, queue_id = self.resolver.resolve_detection(db, detected_app)

            disp_name = None
            if res_app_id:
                resolved_count += 1
                app_cat = db.query(Application).filter(Application.id == res_app_id).first()
                if app_cat:
                    disp_name = app_cat.display_name or f"{app_cat.vendor_name} {app_cat.product_name}"
            else:
                unresolved_count += 1

            summaries.append(IngestedApplicationSummary(
                raw_name=item.name,
                normalized_name=norm_name,
                normalized_publisher=norm_pub,
                detected_version=raw_v,
                resolution_type=detected_app.resolution_type,
                resolution_confidence=detected_app.resolution_confidence,
                resolved_application_id=res_app_id,
                resolved_display_name=disp_name,
                queue_id=queue_id
            ))

        return InventoryIngestResponse(
            device_id=device.id,
            device_key=device.device_key,
            total_reported=len(req.applications),
            resolved_count=resolved_count,
            unresolved_count=unresolved_count,
            applications=summaries
        )
