"""
Targeted Refresh & Impact Manager.
When a monitored source changes, coordinates:
Impact Analysis -> Re-extraction -> Validation -> Fact Comparison -> Profile Update -> Alert Generation.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.enums import (
    FactType,
    FactStatus,
    FactChangeType,
    AlertType,
    AlertSeverity,
    AlertStatus,
    ProfileStatus,
    ExtractionConfidence,
)
from backend.models.source import LicenseSource
from backend.models.collection import CollectedDocument
from backend.models.fact import LicenseFact
from backend.models.profile import LicenseProfile
from backend.models.application import Application
from backend.models.monitoring import LicenseFactChange, LicenseAlert
from backend.extraction.license_extractor import LicenseExtractor
from backend.validation.fact_validator import FactValidator
from backend.consolidation.profile_consolidator import LicenseProfileConsolidator

logger = logging.getLogger(__name__)


def map_fact_to_alert_type(fact_type: FactType) -> AlertType:
    """Maps a changed fact type to its corresponding alert category."""
    if fact_type == FactType.LICENSE_MODEL:
        return AlertType.LICENSE_MODEL_CHANGED
    elif fact_type == FactType.LICENSE_METRIC:
        return AlertType.LICENSE_METRIC_CHANGED
    elif fact_type == FactType.LICENSE_REQUIRED:
        return AlertType.LICENSE_REQUIREMENT_CHANGED
    elif fact_type == FactType.LICENSE_CLASSIFICATION:
        return AlertType.LICENSE_CLASSIFICATION_CHANGED
    elif fact_type == FactType.TRIAL_AVAILABLE:
        return AlertType.TRIAL_CHANGED
    else:
        return AlertType.LICENSE_FACT_CHANGED


def get_fact_change_severity(fact_type: FactType) -> AlertSeverity:
    """Determines alert severity based on licensing criticality."""
    if fact_type in [
        FactType.LICENSE_MODEL,
        FactType.LICENSE_METRIC,
        FactType.LICENSE_REQUIRED,
        FactType.LICENSE_CLASSIFICATION,
    ]:
        return AlertSeverity.HIGH
    elif fact_type in [FactType.TRIAL_AVAILABLE, FactType.LICENSE_DURATION]:
        return AlertSeverity.MEDIUM
    else:
        return AlertSeverity.LOW


class TargetedRefreshManager:
    """
    Coordinates targeted re-extraction, validation, and alert generation following source changes.
    """

    def __init__(
        self,
        extractor: Optional[LicenseExtractor] = None,
        validator: Optional[FactValidator] = None,
        consolidator: Optional[LicenseProfileConsolidator] = None,
    ):
        self.extractor = extractor or LicenseExtractor()
        self.validator = validator or FactValidator()
        self.consolidator = consolidator or LicenseProfileConsolidator()

    def process_source_change(
        self,
        db: Session,
        source_id: int,
        document_id: Optional[int]
    ) -> List[LicenseAlert]:
        """
        Executes targeted re-extraction, validation, fact evolution tracking, and profile update.
        """
        source = db.query(LicenseSource).filter(LicenseSource.id == source_id).first()
        if not source or not document_id:
            return []

        doc = db.query(CollectedDocument).filter(CollectedDocument.id == document_id).first()
        if not doc:
            return []

        # 1. Identify affected applications
        vendor_name = source.vendor_name
        affected_apps = db.query(Application).filter(
            func.lower(Application.vendor_name) == vendor_name.strip().lower()
        ).all()

        # If source has specific product scope, narrow down affected apps
        if source.product_name:
            p_name = source.product_name.strip().lower()
            affected_apps = [a for a in affected_apps if a.product_name.strip().lower() == p_name]

        # 2. Targeted Re-Extraction from the new document
        target_prod = source.product_name or (affected_apps[0].product_name if affected_apps else None)
        target_ed = source.edition or (affected_apps[0].edition if affected_apps else None)
        target_ver = source.version or (affected_apps[0].version if affected_apps else None)

        extracted_facts = self.extractor.extract_from_document(
            db=db,
            document_id=document_id,
            target_product=target_prod,
            target_edition=target_ed,
            target_version=target_ver
        )

        # Mark older facts from this same source as superseded so new facts take precedence
        old_source_facts = db.query(LicenseFact).filter(
            LicenseFact.source_id == source_id,
            LicenseFact.id.notin_([f.id for f in extracted_facts]),
            LicenseFact.status == FactStatus.VALIDATED
        ).all()
        for of in old_source_facts:
            of.status = FactStatus.SUPERSEDED
        db.commit()

        # 3. Targeted Validation on newly extracted facts
        for f in extracted_facts:
            self.validator.validate_fact(db, f)

        generated_alerts: List[LicenseAlert] = []

        # 4. Compare Facts & Update Profiles for each affected application
        for app_obj in affected_apps:
            v = app_obj.vendor_name
            p = app_obj.product_name
            ed = app_obj.edition
            ver = app_obj.version

            # Snapshot previous profile values BEFORE consolidating new profile
            current_profile = None
            if app_obj.current_profile_id:
                current_profile = db.query(LicenseProfile).filter(LicenseProfile.id == app_obj.current_profile_id).first()

            old_model = current_profile.license_model if current_profile else None
            old_metric = current_profile.license_metric if current_profile else None
            old_req = current_profile.license_required if current_profile else None
            old_class = current_profile.license_classification if current_profile else None
            old_trial = current_profile.trial_available if current_profile else None

            # Consolidate new profile with newly validated facts
            new_profile = self.consolidator.consolidate_profile(db, v, p, ed, ver)
            app_obj.current_profile_id = new_profile.id
            db.commit()

            # Compare core licensing attributes
            fact_comparisons = [
                (FactType.LICENSE_MODEL, old_model, new_profile.license_model),
                (FactType.LICENSE_METRIC, old_metric, new_profile.license_metric),
                (FactType.LICENSE_REQUIRED, old_req, new_profile.license_required),
                (FactType.LICENSE_CLASSIFICATION, old_class, new_profile.license_classification),
                (FactType.TRIAL_AVAILABLE, old_trial, new_profile.trial_available),
            ]

            for ft, old_val, new_val in fact_comparisons:
                if old_val and new_val and old_val != new_val and new_val != "UNKNOWN":
                    # Record Fact Change
                    change_record = LicenseFactChange(
                        application_id=app_obj.id,
                        fact_type=ft,
                        old_value=old_val,
                        new_value=new_val,
                        change_type=FactChangeType.MODIFIED,
                        source_id=source_id,
                        document_id=document_id,
                        confidence=new_profile.overall_confidence,
                        detected_at=datetime.now(timezone.utc)
                    )
                    db.add(change_record)

                    # Generate Alert (with deduplication)
                    alert_type = map_fact_to_alert_type(ft)
                    severity = get_fact_change_severity(ft)

                    existing_alert = db.query(LicenseAlert).filter(
                        LicenseAlert.application_id == app_obj.id,
                        LicenseAlert.source_id == source_id,
                        LicenseAlert.alert_type == alert_type,
                        LicenseAlert.new_value == new_val,
                        LicenseAlert.status.in_([AlertStatus.NEW, AlertStatus.ACKNOWLEDGED])
                    ).first()

                    if not existing_alert:
                        alert = LicenseAlert(
                            application_id=app_obj.id,
                            source_id=source_id,
                            document_id=document_id,
                            alert_type=alert_type,
                            severity=severity,
                            title=f"{app_obj.vendor_name} {app_obj.product_name} {ft.value} Changed",
                            description=(
                                f"Licensing fact '{ft.value}' for {app_obj.vendor_name} {app_obj.product_name} "
                                f"changed from '{old_val}' to '{new_val}' based on updated official source."
                            ),
                            old_value=old_val,
                            new_value=new_val,
                            status=AlertStatus.NEW,
                            created_at=datetime.now(timezone.utc)
                        )
                        db.add(alert)
                        generated_alerts.append(alert)

            db.commit()

        return generated_alerts
