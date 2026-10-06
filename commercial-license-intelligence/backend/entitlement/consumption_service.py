"""
License Consumption Tracking Service.
Manages assigned named user, device, core, and instance consumption records.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.entitlement import LicenseConsumption
from backend.models.application import Application
from backend.entitlement.position_result import ConsumptionCreateRequest
from backend.entitlement.metric_rules import MetricRules

logger = logging.getLogger(__name__)


class ConsumptionService:
    """
    Records and retrieves measured license consumption.
    """

    def record_consumption(
        self,
        db: Session,
        req: ConsumptionCreateRequest
    ) -> LicenseConsumption:
        """
        Records a measured license consumption unit.
        """
        app_obj = db.query(Application).filter(Application.id == req.application_id).first()
        if not app_obj:
            raise ValueError(f"Application ID {req.application_id} not found.")

        norm_m = MetricRules.normalize_metric(req.consumption_metric)

        # Check for existing duplicate active consumption for same user or device
        if req.user_reference:
            existing = db.query(LicenseConsumption).filter(
                LicenseConsumption.application_id == req.application_id,
                LicenseConsumption.user_reference == req.user_reference.strip(),
                LicenseConsumption.status == "ACTIVE"
            ).first()
            if existing:
                existing.consumption_quantity = req.consumption_quantity
                existing.updated_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(existing)
                return existing

        consumption = LicenseConsumption(
            application_id=req.application_id,
            device_id=req.device_id,
            detected_application_id=req.detected_application_id,
            consumption_metric=norm_m,
            consumption_quantity=req.consumption_quantity,
            user_reference=req.user_reference.strip() if req.user_reference else None,
            device_reference=req.device_reference.strip() if req.device_reference else None,
            source_type=req.source_type,
            source_reference=req.source_reference.strip() if req.source_reference else None,
            status="ACTIVE",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(consumption)
        db.commit()
        db.refresh(consumption)
        return consumption

    def list_consumption(
        self,
        db: Session,
        application_id: Optional[int] = None,
        metric: Optional[str] = None,
        device_id: Optional[int] = None,
    ) -> List[LicenseConsumption]:
        """Lists active consumption records."""
        q = db.query(LicenseConsumption).filter(LicenseConsumption.status == "ACTIVE")
        if application_id:
            q = q.filter(LicenseConsumption.application_id == application_id)
        if metric:
            q = q.filter(LicenseConsumption.consumption_metric == MetricRules.normalize_metric(metric))
        if device_id:
            q = q.filter(LicenseConsumption.device_id == device_id)
        return q.order_by(LicenseConsumption.id.desc()).all()
