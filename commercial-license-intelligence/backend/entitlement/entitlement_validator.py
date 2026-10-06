"""
Entitlement Record Validation & Deduplication Key Engine.
"""

from datetime import datetime, timezone
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.enums import EntitlementStatus
from backend.models.application import Application
from backend.entitlement.position_result import EntitlementCreateRequest
from backend.entitlement.metric_rules import MetricRules


class EntitlementValidator:
    """
    Validates entitlement business rules, dates, application binding, and computes deduplication keys.
    """

    @classmethod
    def compute_entitlement_key(
        cls,
        app_id: int,
        vendor: str,
        product: str,
        edition: Optional[str],
        version: Optional[str],
        metric: str,
        agreement_id: Optional[str],
        source_ref: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> str:
        """Computes a deterministic key for an entitlement purchase to prevent duplicate records."""
        parts = [
            str(app_id),
            vendor.strip().upper(),
            product.strip().upper(),
            (edition or "ANY").strip().upper(),
            (version or "ANY").strip().upper(),
            MetricRules.normalize_metric(metric),
            (agreement_id or "NONE").strip().upper(),
            (source_ref or "NONE").strip().upper(),
            start_date.strftime("%Y%m%d") if start_date else "NONE",
            end_date.strftime("%Y%m%d") if end_date else "NONE",
        ]
        return "|".join(parts)

    @classmethod
    def validate_and_bind_application(
        cls,
        db: Session,
        req: EntitlementCreateRequest
    ) -> Tuple[bool, Optional[int], List[str]]:
        """
        Validates entitlement parameters and resolves target Application catalog ID.
        Returns: (is_valid, resolved_app_id, validation_errors)
        """
        errors: List[str] = []

        # 1. Quantity check
        if req.quantity < 0:
            errors.append("Entitlement quantity cannot be negative.")

        # 2. Date checks
        if req.license_start_date and req.license_end_date:
            if req.license_start_date > req.license_end_date:
                errors.append("license_start_date cannot be later than license_end_date.")

        # 3. Application binding
        app_id = req.application_id
        if app_id:
            app_obj = db.query(Application).filter(Application.id == app_id).first()
            if not app_obj:
                errors.append(f"Referenced Application ID {app_id} does not exist in catalog.")
        else:
            # Attempt lookup by vendor and product
            query = db.query(Application).filter(
                func.lower(Application.vendor_name) == req.vendor_name.strip().lower(),
                func.lower(Application.product_name) == req.product_name.strip().lower()
            )
            if req.edition:
                query = query.filter(func.lower(Application.edition) == req.edition.strip().lower())
            if req.version:
                query = query.filter(func.lower(Application.version) == req.version.strip().lower())

            match = query.first()
            if match:
                app_id = match.id
            else:
                errors.append(
                    f"No matching Application found in catalog for '{req.vendor_name} {req.product_name}'. "
                    "Create or import application into catalog first."
                )

        return len(errors) == 0, app_id, errors

    @classmethod
    def evaluate_status(
        cls,
        end_date: Optional[datetime],
        current_status: EntitlementStatus = EntitlementStatus.ACTIVE
    ) -> EntitlementStatus:
        """Checks if an entitlement has expired based on current timestamp."""
        if current_status == EntitlementStatus.CANCELLED:
            return EntitlementStatus.CANCELLED
        if end_date:
            now = datetime.now(timezone.utc)
            # Make sure end_date is timezone-aware for comparison
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
            if end_date < now:
                return EntitlementStatus.EXPIRED
        return EntitlementStatus.ACTIVE
