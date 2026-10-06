"""
Evidence Lineage & Explainability Engine.
Traverses full multi-hop chains from Profile Attributes down to exact primary source citations.
"""

import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.enums import FactType, FactStatus, ExtractionConfidence
from backend.models.application import Application
from backend.models.profile import LicenseProfile, LicenseProfileFact
from backend.models.fact import LicenseFact, LicenseEvidence
from backend.models.source import LicenseSource
from backend.models.collection import CollectedDocument, DocumentPage
from backend.models.validation import FactValidationRun
from backend.audit.audit_result import (
    FactExplanationResponse,
    ProfileFieldExplanationResponse,
    SupportingFactSummary,
    EvidenceChainResponse,
)

logger = logging.getLogger(__name__)


class EvidenceLineageService:
    """
    Constructs explainable evidence lineage chains connecting high-level profiles to verbatim source proof.
    """

    def get_evidence_chain_for_application(
        self,
        db: Session,
        application_id: int
    ) -> EvidenceChainResponse:
        """
        Retrieves the complete evidence chain for an application.
        """
        app_obj = db.query(Application).filter(Application.id == application_id).first()
        if not app_obj:
            raise ValueError(f"Application ID {application_id} not found.")

        v = app_obj.vendor_name.strip()
        p = app_obj.product_name.strip()

        profile = None
        if app_obj.current_profile_id:
            profile = db.query(LicenseProfile).filter(LicenseProfile.id == app_obj.current_profile_id).first()

        sources = db.query(LicenseSource).filter(
            func.lower(LicenseSource.vendor_name) == v.lower()
        ).all()

        documents = db.query(CollectedDocument).filter(
            func.lower(CollectedDocument.vendor_name) == v.lower()
        ).all()

        facts = db.query(LicenseFact).filter(
            func.lower(LicenseFact.vendor_name) == v.lower(),
            func.lower(LicenseFact.product_name) == p.lower()
        ).all()

        validated_facts = [f for f in facts if f.status == FactStatus.VALIDATED]

        lineage_items = []
        sources_dict = {s.id: s for s in sources}
        docs_dict = {d.id: d for d in documents}

        for f in facts:
            src = sources_dict.get(f.source_id) if f.source_id else None
            doc = docs_dict.get(f.document_id) if f.document_id else None

            # Get validation run
            v_run = db.query(FactValidationRun).filter(
                FactValidationRun.license_fact_id == f.id
            ).order_by(FactValidationRun.id.desc()).first()

            lineage_items.append({
                "fact_id": f.id,
                "fact_type": f.fact_type.value,
                "value": f.normalized_value,
                "status": f.status.value,
                "confidence": f.confidence.value,
                "confidence_score": f.confidence_score,
                "source": {
                    "id": src.id if src else None,
                    "name": src.source_name if src else "UNKNOWN_SOURCE",
                    "url": src.source_url if src else None,
                    "authority": src.authority_level.value if src else "UNKNOWN",
                },
                "document": {
                    "id": doc.id if doc else None,
                    "url": doc.final_url if doc else None,
                    "page_number": f.page_number,
                    "section": f.section_name,
                    "collected_at": doc.retrieved_at.isoformat() if doc and doc.retrieved_at else None,
                },
                "evidence_text": f.evidence_text,
                "validation": {
                    "status": v_run.validation_status.value if v_run else f.status.value,
                    "reason": v_run.validation_reason if v_run else "Default validation",
                    "checks": v_run.checks_summary if v_run else {},
                    "validated_at": v_run.validated_at.isoformat() if v_run and v_run.validated_at else None,
                }
            })

        return EvidenceChainResponse(
            application_id=app_obj.id,
            vendor_name=app_obj.vendor_name,
            product_name=app_obj.product_name,
            edition=app_obj.edition,
            version=app_obj.version,
            operating_system=app_obj.operating_system,
            profile_id=profile.id if profile else None,
            profile_status=profile.profile_status.value if profile else "NOT_RESEARCHED",
            sources_count=len(sources),
            documents_count=len(documents),
            total_facts_count=len(facts),
            validated_facts_count=len(validated_facts),
            lineage=lineage_items
        )

    def explain_fact(
        self,
        db: Session,
        fact_id: int
    ) -> FactExplanationResponse:
        """
        Provides detailed evidence, source, and audit trail behind a single fact.
        """
        fact = db.query(LicenseFact).filter(LicenseFact.id == fact_id).first()
        if not fact:
            raise ValueError(f"LicenseFact ID {fact_id} not found.")

        src = db.query(LicenseSource).filter(LicenseSource.id == fact.source_id).first() if fact.source_id else None
        doc = db.query(CollectedDocument).filter(CollectedDocument.id == fact.document_id).first() if fact.document_id else None

        v_run = db.query(FactValidationRun).filter(
            FactValidationRun.license_fact_id == fact.id
        ).order_by(FactValidationRun.id.desc()).first()

        checks_dict = v_run.checks_summary if (v_run and v_run.checks_summary) else {}
        reasons_list = [v_run.validation_reason] if (v_run and v_run.validation_reason) else []

        return FactExplanationResponse(
            fact_id=fact.id,
            fact_type=fact.fact_type,
            fact_value=fact.fact_value,
            normalized_value=fact.normalized_value,
            status=fact.status,
            confidence=fact.confidence,
            confidence_score=fact.confidence_score,
            vendor_name=fact.vendor_name,
            product_name=fact.product_name,
            edition=fact.edition,
            version=fact.version,
            source_id=src.id if src else None,
            source_name=src.source_name if src else None,
            source_url=src.source_url if src else None,
            authority_level=src.authority_level if src else None,
            document_id=doc.id if doc else None,
            document_url=doc.final_url if doc else None,
            page_number=fact.page_number,
            section_name=fact.section_name,
            evidence_text=fact.evidence_text,
            evidence_hash=fact.evidence_hash,
            validation_checks=checks_dict,
            validation_reasons=reasons_list,
            extracted_at=fact.extracted_at,
            verified_at=fact.verified_at
        )

    def explain_profile_field(
        self,
        db: Session,
        profile_id: int,
        field_name: str
    ) -> ProfileFieldExplanationResponse:
        """
        Explains which exact verified facts support a consolidated profile field.
        """
        profile = db.query(LicenseProfile).filter(LicenseProfile.id == profile_id).first()
        if not profile:
            raise ValueError(f"LicenseProfile ID {profile_id} not found.")

        field_clean = field_name.strip().lower()
        val = getattr(profile, field_clean, None)

        # Map field string to FactType
        ft_map = {
            "license_model": FactType.LICENSE_MODEL,
            "license_metric": FactType.LICENSE_METRIC,
            "license_required": FactType.LICENSE_REQUIRED,
            "license_classification": FactType.LICENSE_CLASSIFICATION,
            "commercial_use": FactType.COMMERCIAL_USE,
            "educational_use": FactType.EDUCATIONAL_USE,
            "trial_available": FactType.TRIAL_AVAILABLE,
            "license_duration": FactType.LICENSE_DURATION,
        }
        target_ft = ft_map.get(field_clean)

        supporting_facts: List[SupportingFactSummary] = []
        if target_ft:
            facts = db.query(LicenseFact).filter(
                func.lower(LicenseFact.vendor_name) == profile.vendor_name.strip().lower(),
                func.lower(LicenseFact.product_name) == profile.product_name.strip().lower(),
                LicenseFact.fact_type == target_ft,
                LicenseFact.status == FactStatus.VALIDATED
            ).all()

            for f in facts:
                src = db.query(LicenseSource).filter(LicenseSource.id == f.source_id).first() if f.source_id else None
                supporting_facts.append(SupportingFactSummary(
                    fact_id=f.id,
                    fact_type=f.fact_type,
                    value=f.normalized_value,
                    confidence=f.confidence,
                    source_name=src.source_name if src else "Primary Evidence",
                    source_url=src.source_url if src else None,
                    authority_level=src.authority_level if src else None,
                    document_id=f.document_id,
                    page_number=f.page_number,
                    evidence_text=f.evidence_text,
                    verified_at=f.verified_at
                ))

        return ProfileFieldExplanationResponse(
            profile_id=profile.id,
            field=field_clean,
            value=val,
            confidence=profile.overall_confidence,
            status=profile.profile_status.value,
            supporting_facts=supporting_facts
        )
