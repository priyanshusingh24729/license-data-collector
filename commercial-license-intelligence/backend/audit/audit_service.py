"""
Audit Service for Immutable Logging, Timeline Assembly, and Position Explanations.
"""

import io
import csv
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.enums import AuditEventType, LicensePositionStatus
from backend.models.audit import AuditEvent
from backend.models.application import Application
from backend.models.entitlement import LicensePosition, LicenseEntitlement, LicenseConsumption
from backend.audit.audit_result import (
    AuditEventResponse,
    ApplicationAuditTimelineResponse,
    PositionAuditResponse,
)

logger = logging.getLogger(__name__)


class AuditService:
    """
    Manages append-only audit event logs, chronological application history, and position explanations.
    """

    @classmethod
    def record_event(
        cls,
        db: Session,
        entity_type: str,
        entity_id: int,
        event_type: AuditEventType,
        description: str,
        actor_type: str = "SYSTEM",
        actor_id: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """
        Appends an immutable audit event record.
        """
        import json
        meta_str = json.dumps(metadata) if metadata else None
        event = AuditEvent(
            entity_type=entity_type.upper(),
            entity_id=entity_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            description=description,
            old_value=old_value,
            new_value=new_value,
            metadata_json=meta_str,
            created_at=datetime.now(timezone.utc)
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def get_application_timeline(
        self,
        db: Session,
        application_id: int
    ) -> ApplicationAuditTimelineResponse:
        """
        Retrieves the complete chronological lifecycle audit timeline for an application.
        """
        app_obj = db.query(Application).filter(Application.id == application_id).first()
        if not app_obj:
            raise ValueError(f"Application ID {application_id} not found.")

        # Query events related to this application
        events = db.query(AuditEvent).filter(
            (AuditEvent.entity_type == "APPLICATION") & (AuditEvent.entity_id == application_id)
        ).order_by(AuditEvent.created_at.asc()).all()

        # Also retrieve events from child entities (if referenced)
        ev_responses = [
            AuditEventResponse(
                id=e.id,
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                event_type=e.event_type,
                actor_type=e.actor_type,
                actor_id=e.actor_id,
                description=e.description,
                old_value=e.old_value,
                new_value=e.new_value,
                created_at=e.created_at
            ) for e in events
        ]

        return ApplicationAuditTimelineResponse(
            application_id=app_obj.id,
            vendor_name=app_obj.vendor_name,
            product_name=app_obj.product_name,
            edition=app_obj.edition,
            version=app_obj.version,
            events=ev_responses
        )

    def explain_position(
        self,
        db: Session,
        application_id: int
    ) -> PositionAuditResponse:
        """
        Returns structured, step-by-step arithmetic and factual explanation of a license position.
        """
        app_obj = db.query(Application).filter(Application.id == application_id).first()
        if not app_obj:
            raise ValueError(f"Application ID {application_id} not found.")

        pos = db.query(LicensePosition).filter(LicensePosition.application_id == application_id).first()
        if not pos:
            from backend.entitlement.position_engine import LicensePositionEngine
            pos_resp = LicensePositionEngine().calculate_position(db, application_id)
            pos = db.query(LicensePosition).filter(LicensePosition.application_id == application_id).first()

        metric = pos.metric or "UNKNOWN"
        ent = pos.entitled_quantity or 0.0
        con = pos.consumed_quantity or 0.0
        avail = pos.available_quantity or 0.0
        over = pos.overdeployment_quantity or 0.0

        formula = f"{ent:g} - {con:g} = {ent - con:g} {metric}"
        if pos.position_status == LicensePositionStatus.UNKNOWN_POSITION:
            explanation = "Entitlement quantity is not available. Position cannot be calculated."
        elif pos.position_status == LicensePositionStatus.NOT_CALCULABLE:
            explanation = pos.status_reason or "Metric mismatch between entitlement and consumption."
        elif pos.position_status == LicensePositionStatus.UNDER_LICENSED_POSITION:
            explanation = f"Potential overdeployment of {over:g} {metric} units."
        elif pos.position_status == LicensePositionStatus.OVER_LICENSED_POSITION:
            explanation = f"Surplus of {avail:g} {metric} available licenses."
        else:
            explanation = f"Exact balance: {ent:g} {metric} licenses entitled and consumed."

        inst_cnt = 0
        from backend.models.inventory import DetectedApplication
        from backend.models.enums import DetectedAppStatus
        inst_cnt = db.query(DetectedApplication).filter(
            DetectedApplication.resolved_application_id == application_id,
            DetectedApplication.status == DetectedAppStatus.ACTIVE
        ).count()

        return PositionAuditResponse(
            application_id=app_obj.id,
            vendor_name=app_obj.vendor_name,
            product_name=app_obj.product_name,
            metric=metric,
            entitled_quantity=ent,
            consumed_quantity=con,
            installed_devices_count=inst_cnt,
            available_quantity=avail,
            overdeployment_quantity=over,
            position_status=pos.position_status,
            calculation_formula=formula,
            status_explanation=explanation,
            calculation_version=pos.calculation_version,
            calculated_at=pos.calculated_at
        )

    def export_audit_csv(self, db: Session) -> str:
        """
        Generates comprehensive CSV export of all verified licensing facts, evidence snippets, and sources.
        """
        from backend.models.fact import LicenseFact
        from backend.models.source import LicenseSource
        from backend.models.collection import CollectedDocument

        facts = db.query(LicenseFact).all()
        sources_dict = {s.id: s for s in db.query(LicenseSource).all()}
        docs_dict = {d.id: d for d in db.query(CollectedDocument).all()}

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Application / Vendor", "Product", "Edition", "Version",
            "Fact Type", "Fact Value", "Status", "Confidence", "Quality Score",
            "Source Name", "Source URL", "Authority Level", "Document Page", "Evidence Text", "Verified At"
        ])

        for f in facts:
            src = sources_dict.get(f.source_id)
            writer.writerow([
                f.vendor_name,
                f.product_name or "",
                f.edition or "",
                f.version or "",
                f.fact_type.value,
                f.normalized_value,
                f.status.value,
                f.confidence.value,
                f.confidence_score,
                src.source_name if src else "",
                src.source_url if src else "",
                src.authority_level.value if src else "",
                f.page_number or "",
                f.evidence_text or "",
                f.verified_at.strftime("%Y-%m-%d %H:%M") if f.verified_at else ""
            ])

        return output.getvalue()
