"""
License Position Calculation Engine.
Calculates available, consumed, and potential overdeployment quantities with metric compatibility checks,
persists current positions, and records immutable historical snapshots.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.enums import (
    EntitlementStatus,
    LicensePositionStatus,
    DetectedAppStatus,
)
from backend.models.application import Application
from backend.models.profile import LicenseProfile
from backend.models.inventory import DetectedApplication
from backend.models.entitlement import (
    LicenseEntitlement,
    LicenseConsumption,
    LicensePosition,
    LicensePositionHistory,
)
from backend.entitlement.position_result import LicensePositionResponse
from backend.entitlement.metric_rules import MetricRules

logger = logging.getLogger(__name__)
CALCULATION_VERSION = "1.0.0"


class LicensePositionEngine:
    """
    Core engine evaluating entitled licenses against measured consumption.
    """

    def calculate_position(
        self,
        db: Session,
        application_id: int
    ) -> LicensePositionResponse:
        """
        Executes deterministic license position calculation for an application.
        """
        now = datetime.now(timezone.utc)

        # 1. Fetch Application & Profile
        app_obj = db.query(Application).filter(Application.id == application_id).first()
        if not app_obj:
            raise ValueError(f"Application ID {application_id} not found.")

        profile = None
        prof_model = "UNKNOWN"
        prof_metric = "UNKNOWN"
        if app_obj.current_profile_id:
            profile = db.query(LicenseProfile).filter(LicenseProfile.id == app_obj.current_profile_id).first()
            if profile:
                prof_model = profile.license_model or "UNKNOWN"
                prof_metric = profile.license_metric or "UNKNOWN"

        # 2. Count Active Endpoint Installations
        inst_count = db.query(DetectedApplication).filter(
            DetectedApplication.resolved_application_id == app_obj.id,
            DetectedApplication.status == DetectedAppStatus.ACTIVE
        ).count()

        # 3. Gather Active Entitlements
        active_entitlements = db.query(LicenseEntitlement).filter(
            LicenseEntitlement.application_id == app_obj.id,
            LicenseEntitlement.status == EntitlementStatus.ACTIVE
        ).all()

        # Filter out expired entitlements based on date
        valid_entitlements = []
        for e in active_entitlements:
            if e.license_end_date:
                end_d = e.license_end_date
                if end_d.tzinfo is None:
                    end_d = end_d.replace(tzinfo=timezone.utc)
                if end_d < now:
                    e.status = EntitlementStatus.EXPIRED
                    continue
            valid_entitlements.append(e)
        db.commit()

        # 4. Evaluate Entitlement Quantity & Metric
        entitled_qty: Optional[float] = None
        entitled_metric: Optional[str] = None

        if valid_entitlements:
            entitled_qty = sum(e.quantity for e in valid_entitlements)
            entitled_metric = MetricRules.normalize_metric(valid_entitlements[0].metric)

        # 5. Gather Measured Consumption
        consumption_records = db.query(LicenseConsumption).filter(
            LicenseConsumption.application_id == app_obj.id,
            LicenseConsumption.status == "ACTIVE"
        ).all()

        consumed_qty: Optional[float] = None
        consumed_metric: Optional[str] = None

        if consumption_records:
            consumed_qty = sum(c.consumption_quantity for c in consumption_records)
            consumed_metric = MetricRules.normalize_metric(consumption_records[0].consumption_metric)
        else:
            # Check if consumption can be automatically derived from active installation counts
            target_metric = entitled_metric or (prof_metric if prof_metric != "UNKNOWN" else None)
            if target_metric and MetricRules.can_derive_consumption_from_installations(target_metric)[0]:
                consumed_qty = float(inst_count)
                consumed_metric = MetricRules.normalize_metric(target_metric)

        # 6. Reconcile Position
        pos_status = LicensePositionStatus.UNKNOWN_POSITION
        status_reason: Optional[str] = None
        available_qty: Optional[float] = None
        overdeployment_qty: Optional[float] = None
        final_metric = entitled_metric or consumed_metric or (prof_metric if prof_metric != "UNKNOWN" else None)

        if entitled_qty is None:
            pos_status = LicensePositionStatus.UNKNOWN_POSITION
            status_reason = "Entitlement quantity is not available. Entitlement must be explicitly entered or imported."
        elif consumed_qty is None:
            # Entitlement is known, but no consumption data is recorded
            pos_status = LicensePositionStatus.UNKNOWN_POSITION
            status_reason = (
                f"Consumption cannot be measured for license metric '{final_metric}'. "
                "Named-user assignments or telemetry must be recorded."
            )
        else:
            # Check metric compatibility
            is_compat, mismatch_reason = MetricRules.are_metrics_compatible(
                entitlement_metric=entitled_metric or "UNKNOWN",
                consumption_metric=consumed_metric or "UNKNOWN"
            )

            if not is_compat:
                pos_status = LicensePositionStatus.NOT_CALCULABLE
                status_reason = mismatch_reason
            else:
                available_qty = max(0.0, entitled_qty - consumed_qty)
                overdeployment_qty = max(0.0, consumed_qty - entitled_qty)

                if consumed_qty > entitled_qty:
                    pos_status = LicensePositionStatus.UNDER_LICENSED_POSITION
                    status_reason = f"Potential overdeployment of {overdeployment_qty:g} {final_metric} units."
                elif consumed_qty < entitled_qty:
                    pos_status = LicensePositionStatus.OVER_LICENSED_POSITION
                    status_reason = f"Surplus available licenses: {available_qty:g} {final_metric} units."
                else:
                    pos_status = LicensePositionStatus.COMPLIANT_POSITION
                    status_reason = f"Exact license balance: {entitled_qty:g} {final_metric} units entitled and consumed."

        # 7. Persist Current Position & History Snapshot
        current_pos = db.query(LicensePosition).filter(LicensePosition.application_id == app_obj.id).first()
        if not current_pos:
            current_pos = LicensePosition(
                application_id=app_obj.id,
                metric=final_metric,
                entitled_quantity=entitled_qty,
                consumed_quantity=consumed_qty,
                available_quantity=available_qty,
                overdeployment_quantity=overdeployment_qty,
                position_status=pos_status,
                status_reason=status_reason,
                calculated_at=now,
                calculation_version=CALCULATION_VERSION,
                created_at=now,
                updated_at=now
            )
            db.add(current_pos)
        else:
            current_pos.metric = final_metric
            current_pos.entitled_quantity = entitled_qty
            current_pos.consumed_quantity = consumed_qty
            current_pos.available_quantity = available_qty
            current_pos.overdeployment_quantity = overdeployment_qty
            current_pos.position_status = pos_status
            current_pos.status_reason = status_reason
            current_pos.calculated_at = now
            current_pos.calculation_version = CALCULATION_VERSION
            current_pos.updated_at = now

        # Append audit history snapshot
        history_snap = LicensePositionHistory(
            application_id=app_obj.id,
            metric=final_metric,
            entitled_quantity=entitled_qty,
            consumed_quantity=consumed_qty,
            available_quantity=available_qty,
            overdeployment_quantity=overdeployment_qty,
            position_status=pos_status,
            status_reason=status_reason,
            calculated_at=now,
            calculation_version=CALCULATION_VERSION,
            created_at=now
        )
        db.add(history_snap)
        db.commit()

        return LicensePositionResponse(
            application_id=app_obj.id,
            vendor_name=app_obj.vendor_name,
            product_name=app_obj.product_name,
            edition=app_obj.edition,
            version=app_obj.version,
            operating_system=app_obj.operating_system,
            profile_license_model=prof_model,
            profile_license_metric=prof_metric,
            metric=final_metric,
            entitled_quantity=entitled_qty,
            consumed_quantity=consumed_qty,
            installed_devices_count=inst_count,
            available_quantity=available_qty,
            overdeployment_quantity=overdeployment_qty,
            position_status=pos_status,
            status_reason=status_reason,
            calculated_at=now,
            calculation_version=CALCULATION_VERSION
        )
