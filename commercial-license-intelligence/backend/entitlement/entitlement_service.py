"""
Entitlement Management Service.
Handles CRUD, deduplication, CSV batch import, and active/expired status evaluation.
"""

import io
import csv
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.enums import EntitlementStatus, EntitlementType, EntitlementSourceType
from backend.models.entitlement import LicenseEntitlement
from backend.models.application import Application
from backend.entitlement.position_result import EntitlementCreateRequest, EntitlementResponse
from backend.entitlement.entitlement_validator import EntitlementValidator
from backend.entitlement.metric_rules import MetricRules

logger = logging.getLogger(__name__)


class EntitlementService:
    """
    Coordinates creation, validation, deduplication, and retrieval of license entitlements.
    """

    def __init__(self, validator: Optional[EntitlementValidator] = None):
        self.validator = validator or EntitlementValidator()

    def create_entitlement(
        self,
        db: Session,
        req: EntitlementCreateRequest
    ) -> LicenseEntitlement:
        """
        Validates, deduplicates, and creates a license entitlement.
        """
        is_valid, app_id, errors = self.validator.validate_and_bind_application(db, req)
        if not is_valid or not app_id:
            raise ValueError("; ".join(errors))

        # Check expired status
        status = self.validator.evaluate_status(req.license_end_date, EntitlementStatus.ACTIVE)

        # Compute deduplication key
        ent_key = self.validator.compute_entitlement_key(
            app_id=app_id,
            vendor=req.vendor_name,
            product=req.product_name,
            edition=req.edition,
            version=req.version,
            metric=req.metric,
            agreement_id=req.agreement_id,
            source_ref=req.source_reference,
            start_date=req.license_start_date,
            end_date=req.license_end_date,
        )

        existing = db.query(LicenseEntitlement).filter(LicenseEntitlement.entitlement_key == ent_key).first()
        if existing:
            # Update quantity or return existing
            existing.quantity = req.quantity
            existing.status = status
            existing.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing)
            return existing

        entitlement = LicenseEntitlement(
            application_id=app_id,
            vendor_name=req.vendor_name.strip(),
            product_name=req.product_name.strip(),
            edition=req.edition.strip() if req.edition else None,
            version=req.version.strip() if req.version else None,
            entitlement_type=req.entitlement_type,
            quantity=req.quantity,
            metric=MetricRules.normalize_metric(req.metric),
            license_start_date=req.license_start_date,
            license_end_date=req.license_end_date,
            agreement_id=req.agreement_id.strip() if req.agreement_id else None,
            contract_reference=req.contract_reference.strip() if req.contract_reference else None,
            source_type=req.source_type,
            source_reference=req.source_reference.strip() if req.source_reference else None,
            status=status,
            entitlement_key=ent_key,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(entitlement)
        db.commit()
        db.refresh(entitlement)
        return entitlement

    def list_entitlements(
        self,
        db: Session,
        application_id: Optional[int] = None,
        vendor: Optional[str] = None,
        product: Optional[str] = None,
        status: Optional[EntitlementStatus] = None,
    ) -> List[LicenseEntitlement]:
        """Queries entitlements with optional filtering."""
        q = db.query(LicenseEntitlement)
        if application_id:
            q = q.filter(LicenseEntitlement.application_id == application_id)
        if vendor:
            q = q.filter(func.lower(LicenseEntitlement.vendor_name) == vendor.strip().lower())
        if product:
            q = q.filter(func.lower(LicenseEntitlement.product_name) == product.strip().lower())
        if status:
            q = q.filter(LicenseEntitlement.status == status)

        entitlements = q.order_by(LicenseEntitlement.id.desc()).all()

        # Re-evaluate expired statuses on read
        now = datetime.now(timezone.utc)
        for e in entitlements:
            if e.license_end_date and e.status == EntitlementStatus.ACTIVE:
                end_d = e.license_end_date
                if end_d.tzinfo is None:
                    end_d = end_d.replace(tzinfo=timezone.utc)
                if end_d < now:
                    e.status = EntitlementStatus.EXPIRED
        db.commit()

        return entitlements
