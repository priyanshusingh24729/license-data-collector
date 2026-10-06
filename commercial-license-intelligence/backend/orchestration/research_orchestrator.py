"""
Automatic License Intelligence Research Orchestrator.
Orchestrates the entire multi-step pipeline for an application target:
Discovery -> Collection -> Extraction -> Validation -> Profile Consolidation.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.enums import (
    ApplicationResearchStatus,
    ProfileStatus,
    ExtractionConfidence,
)
from backend.models.application import Application
from backend.models.profile import LicenseProfile
from backend.sources.discovery.discovery_engine import SourceDiscoveryEngine
from backend.schemas.discovery import DiscoveryTargetRequest
from backend.collectors.web.web_collector import WebCollector
from backend.collectors.documents.document_collector import DocumentCollector
from backend.extraction.license_extractor import LicenseExtractor
from backend.validation.fact_validator import FactValidator
from backend.consolidation.profile_consolidator import LicenseProfileConsolidator
from backend.consolidation.profile_schemas import LicenseProfileResponse

logger = logging.getLogger(__name__)


class ResearchOrchestrator:
    """
    Executes automated end-to-end license research for an application target.
    """

    def __init__(
        self,
        discovery_engine: Optional[SourceDiscoveryEngine] = None,
        web_collector: Optional[WebCollector] = None,
        doc_collector: Optional[DocumentCollector] = None,
        extractor: Optional[LicenseExtractor] = None,
        validator: Optional[FactValidator] = None,
        consolidator: Optional[LicenseProfileConsolidator] = None,
    ):
        self.discovery = discovery_engine or SourceDiscoveryEngine()
        self.web_collector = web_collector or WebCollector()
        self.doc_collector = doc_collector or DocumentCollector()
        self.extractor = extractor or LicenseExtractor()
        self.validator = validator or FactValidator()
        self.consolidator = consolidator or LicenseProfileConsolidator()

    def research_application(
        self,
        db: Session,
        application_id: int,
        force_refresh: bool = False
    ) -> LicenseProfileResponse:
        """
        Runs automated licensing research pipeline for a cataloged application.
        """
        app_obj = db.query(Application).filter(Application.id == application_id).first()
        if not app_obj:
            raise ValueError(f"Application ID {application_id} not found in catalog.")

        v = app_obj.vendor_name
        p = app_obj.product_name
        ed = app_obj.edition
        ver = app_obj.version

        # 1. Check Cache
        if not force_refresh and app_obj.current_profile_id:
            existing_p = db.query(LicenseProfile).filter(LicenseProfile.id == app_obj.current_profile_id).first()
            if existing_p and existing_p.profile_status in [ProfileStatus.VALIDATED, ProfileStatus.PARTIALLY_VALIDATED]:
                logger.info(f"Reusing cached license profile for {v} {p} (App ID: {application_id}).")
                return self.consolidator.consolidate_profile(db, v, p, ed, ver)

        app_obj.research_status = ApplicationResearchStatus.RESEARCHING
        db.commit()

        try:
            # 2. Discovery (Step 3)
            try:
                target_req = DiscoveryTargetRequest(
                    vendor=v,
                    product=p,
                    version=ver,
                    edition=ed
                )
                self.discovery.discover_sources(db, target_req)
            except Exception as disc_err:
                logger.warning(f"Discovery step warning for {v} {p}: {disc_err}")

            # 3. Extraction (Step 7)
            self.extractor.extract_for_application(
                db=db,
                vendor=v,
                product=p,
                edition=ed,
                version=ver
            )

            # 4. Validation (Step 8)
            self.validator.validate_application_target(
                db=db,
                vendor=v,
                product=p,
                edition=ed,
                version=ver
            )

            # 5. Consolidation (Step 9)
            profile_res = self.consolidator.consolidate_profile(
                db=db,
                vendor=v,
                product=p,
                edition=ed,
                version=ver
            )

            # 6. Update Application entity
            app_obj.current_profile_id = profile_res.id
            if profile_res.profile_status in [ProfileStatus.VALIDATED, ProfileStatus.PARTIALLY_VALIDATED]:
                app_obj.research_status = ApplicationResearchStatus.COMPLETED
            elif profile_res.profile_status in [ProfileStatus.REVIEW_REQUIRED, ProfileStatus.CONFLICT]:
                app_obj.research_status = ApplicationResearchStatus.REVIEW_REQUIRED
            elif profile_res.validated_fact_count > 0:
                app_obj.research_status = ApplicationResearchStatus.PARTIAL
            else:
                app_obj.research_status = ApplicationResearchStatus.COMPLETED

            app_obj.updated_at = datetime.now(timezone.utc)
            db.commit()

            return profile_res

        except Exception as exc:
            logger.error(f"Research execution failed for application {application_id}: {exc}")
            app_obj.research_status = ApplicationResearchStatus.FAILED
            app_obj.updated_at = datetime.now(timezone.utc)
            db.commit()
            raise exc
