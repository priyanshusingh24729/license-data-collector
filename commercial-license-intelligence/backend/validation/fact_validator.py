"""
Main Fact Validation Coordinator.
Orchestrates multi-dimensional evidence verification, semantic rules checking,
quality scoring, conflict resolution, and persists audit logs to fact_validation_runs.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.enums import (
    FactStatus,
    ExtractionConfidence,
    AuthorityLevel,
    SourceAuthorityTier,
    FactType,
)
from backend.models.fact import LicenseFact
from backend.models.source import LicenseSource
from backend.models.collection import CollectedDocument
from backend.models.validation import FactValidationRun
from backend.validation.validation_result import (
    ValidationChecks,
    FactValidationResult,
    ApplicationValidationSummaryResponse,
)
from backend.validation.evidence_validator import EvidenceValidator
from backend.validation.product_validator import ProductValidator
from backend.validation.edition_validator import EditionValidator
from backend.validation.version_validator import VersionValidator
from backend.validation.source_authority import SourceAuthorityValidator
from backend.validation.quality_engine import QualityEngine
from backend.validation.conflict_detector import ValidationConflictDetector

logger = logging.getLogger(__name__)
VALIDATOR_VERSION = "1.0.0"


class FactValidator:
    """
    Evaluates licensing facts against evidence integrity, semantic rules, and scope boundaries.
    """

    def __init__(
        self,
        evidence_validator: Optional[EvidenceValidator] = None,
        product_validator: Optional[ProductValidator] = None,
        edition_validator: Optional[EditionValidator] = None,
        version_validator: Optional[VersionValidator] = None,
        authority_validator: Optional[SourceAuthorityValidator] = None,
        quality_engine: Optional[QualityEngine] = None,
        conflict_detector: Optional[ValidationConflictDetector] = None,
    ):
        self.evidence_validator = evidence_validator or EvidenceValidator()
        self.product_validator = product_validator or ProductValidator()
        self.edition_validator = edition_validator or EditionValidator()
        self.version_validator = version_validator or VersionValidator()
        self.authority_validator = authority_validator or SourceAuthorityValidator()
        self.quality_engine = quality_engine or QualityEngine()
        self.conflict_detector = conflict_detector or ValidationConflictDetector()

    def validate_fact(
        self,
        db: Session,
        fact: LicenseFact,
        target_vendor: Optional[str] = None,
        target_product: Optional[str] = None,
        target_edition: Optional[str] = None,
        target_version: Optional[str] = None,
    ) -> FactValidationResult:
        """
        Executes comprehensive validation of an extracted fact against primary source evidence.
        """
        reasons: List[str] = []
        checks = ValidationChecks()

        t_vendor = target_vendor or fact.vendor_name
        t_product = target_product or fact.product_name
        t_edition = target_edition or fact.edition
        t_version = target_version or fact.version

        # 1. Evidence Existence & Text Match
        ev_exists, text_matched, ev_fail_reason = self.evidence_validator.validate_evidence(db, fact)
        checks.evidence_exists = ev_exists
        checks.evidence_text_matched = text_matched
        if ev_fail_reason:
            reasons.append(ev_fail_reason)

        # 2. Product Match
        prod_ok, prod_fail_reason = self.product_validator.validate_product(fact, t_vendor, t_product)
        checks.product_match = prod_ok
        if prod_fail_reason:
            reasons.append(prod_fail_reason)

        # 3. Edition Match
        ed_ok, ed_fail_reason = self.edition_validator.validate_edition(fact, t_edition)
        checks.edition_match = ed_ok
        if ed_fail_reason:
            reasons.append(ed_fail_reason)

        # 4. Version Match
        ver_ok, ver_fail_reason = self.version_validator.validate_version(fact, t_version)
        checks.version_match = ver_ok
        if ver_fail_reason:
            reasons.append(ver_fail_reason)

        # 5. Source Authority & Domain Match (Step 18 Hierarchy)
        is_official, authority_tier, auth_reason = self.authority_validator.validate_authority(db, fact)
        checks.source_authority = is_official
        if auth_reason:
            reasons.append(auth_reason)

        # 6. Fact-Specific Semantic Rule Verification
        semantic_ok, semantic_reasons = self.quality_engine.validate_fact_semantics(fact)
        if not semantic_ok:
            reasons.extend(semantic_reasons)

        # 7. Effective Date Validation (Step 18)
        now = datetime.now(timezone.utc)
        date_ok = True
        if fact.effective_to:
            eff_to = fact.effective_to
            if eff_to.tzinfo is None:
                eff_to = eff_to.replace(tzinfo=timezone.utc)
            if eff_to < now:
                date_ok = False
                reasons.append(f"EXPIRED_EVIDENCE: Licensing statement expired on {fact.effective_to.strftime('%Y-%m-%d')}.")

        # 8. Conflict Detection (Step 18 - Disagreement between authoritative sources)
        has_conflict, conflicting_facts = self.conflict_detector.detect_fact_conflicts(db, fact)
        if has_conflict:
            reasons.append(f"LICENSE_FACT_CONFLICT: Disagreement with {len(conflicting_facts)} existing verified facts.")

        # 9. Quality Scoring & Reliability Assessment
        quality_score, quality_tier = self.quality_engine.compute_quality_score(
            checks=checks,
            authority=AuthorityLevel.OFFICIAL_VENDOR if is_official else AuthorityLevel.UNKNOWN,
            is_semantic_supported=semantic_ok
        )

        # Snippet Rejection Rule: Search snippets (TIER_5) can never create HIGH/VERY_HIGH facts
        is_tier_5 = (
            str(authority_tier) in ["TIER_5", "SourceAuthorityTier.TIER_5"]
            or authority_tier == SourceAuthorityTier.TIER_5
            or (hasattr(authority_tier, "value") and authority_tier.value == "TIER_5")
        )
        if is_tier_5:
            quality_tier = ExtractionConfidence.LOW
            quality_score = min(quality_score, 0.35)

        # 10. Determine Final Fact Status
        if not checks.evidence_exists or not checks.evidence_text_matched:
            final_status = FactStatus.REJECTED
        elif not checks.product_match:
            final_status = FactStatus.REJECTED
        elif not date_ok:
            final_status = FactStatus.REJECTED
        elif has_conflict:
            final_status = FactStatus.CONFLICT
        elif str(authority_tier) == "TIER_5" or authority_tier == SourceAuthorityTier.TIER_5:
            final_status = FactStatus.REVIEW_REQUIRED
        elif not semantic_ok:
            final_status = FactStatus.REVIEW_REQUIRED
        elif not checks.edition_match or not checks.version_match:
            final_status = FactStatus.REVIEW_REQUIRED
        elif quality_score >= 0.70:
            final_status = FactStatus.VALIDATED
        else:
            final_status = FactStatus.REVIEW_REQUIRED

        # Update Fact row
        fact.status = final_status
        fact.confidence = quality_tier
        fact.confidence_score = quality_score
        fact.validation_status = final_status.value
        if final_status == FactStatus.VALIDATED:
            fact.verified_at = datetime.now(timezone.utc)
        db.commit()

        # 11. Create FactValidationRun Audit Record
        validation_run = FactValidationRun(
            license_fact_id=fact.id,
            validation_status=final_status,
            quality=quality_tier,
            validation_reason="; ".join(reasons) if reasons else "All validation checks passed.",
            checks_summary=checks.model_dump(),
            validator_version=VALIDATOR_VERSION,
            validated_at=datetime.now(timezone.utc)
        )
        db.add(validation_run)
        db.commit()

        return FactValidationResult(
            fact_id=fact.id,
            status=final_status,
            quality=quality_tier,
            quality_score=quality_score,
            checks=checks,
            reasons=reasons,
            validator_version=VALIDATOR_VERSION,
            validated_at=validation_run.validated_at
        )

    def validate_document_facts(
        self,
        db: Session,
        document_id: int
    ) -> List[FactValidationResult]:
        """Validates all extracted facts referencing a specific document."""
        facts = db.query(LicenseFact).filter(LicenseFact.document_id == document_id).all()
        return [self.validate_fact(db, f) for f in facts]

    def validate_application_target(
        self,
        db: Session,
        vendor: str,
        product: str,
        edition: Optional[str] = None,
        version: Optional[str] = None
    ) -> ApplicationValidationSummaryResponse:
        """
        Validates all applicable facts for a software application target.
        """
        clean_v = vendor.strip()
        clean_p = product.strip()

        facts = db.query(LicenseFact).filter(
            func.lower(LicenseFact.vendor_name) == clean_v.lower(),
            func.lower(LicenseFact.product_name) == clean_p.lower()
        ).all()

        results: List[FactValidationResult] = []
        for f in facts:
            res = self.validate_fact(
                db=db,
                fact=f,
                target_vendor=clean_v,
                target_product=clean_p,
                target_edition=edition,
                target_version=version
            )
            results.append(res)

        # Multi-source conflict check
        self.conflict_detector.analyze_conflicts(facts)
        db.commit()

        # Aggregate counts
        validated_cnt = len([f for f in facts if f.status == FactStatus.VALIDATED])
        review_cnt = len([f for f in facts if f.status == FactStatus.REVIEW_REQUIRED])
        conflict_cnt = len([f for f in facts if f.status == FactStatus.CONFLICT])
        rejected_cnt = len([f for f in facts if f.status == FactStatus.REJECTED])
        superseded_cnt = len([f for f in facts if f.status == FactStatus.SUPERSEDED])
        unknown_cnt = len([f for f in facts if f.normalized_value == "UNKNOWN"])

        # Determine overall quality
        scores = [f.confidence_score for f in facts]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        if avg_score >= 0.8:
            overall_q = ExtractionConfidence.VERY_HIGH
        elif avg_score >= 0.65:
            overall_q = ExtractionConfidence.HIGH
        elif avg_score >= 0.45:
            overall_q = ExtractionConfidence.MEDIUM
        elif avg_score > 0.0:
            overall_q = ExtractionConfidence.LOW
        else:
            overall_q = ExtractionConfidence.UNKNOWN

        facts_summary = [{
            "id": f.id,
            "fact_type": f.fact_type.value,
            "value": f.normalized_value,
            "status": f.status.value,
            "confidence": f.confidence.value,
            "evidence_text": f.evidence_text,
            "page_number": f.page_number
        } for f in facts]

        review_queue = [{
            "id": f.id,
            "fact_type": f.fact_type.value,
            "value": f.normalized_value,
            "status": f.status.value,
            "evidence_text": f.evidence_text,
            "page_number": f.page_number
        } for f in facts if f.status in [FactStatus.REVIEW_REQUIRED, FactStatus.CONFLICT]]

        return ApplicationValidationSummaryResponse(
            vendor=clean_v,
            product=clean_p,
            edition=edition,
            version=version,
            total_facts=len(facts),
            validated=validated_cnt,
            review_required=review_cnt,
            conflicts=conflict_cnt,
            rejected=rejected_cnt,
            superseded=superseded_cnt,
            unknown=unknown_cnt,
            overall_quality=overall_q,
            facts_summary=facts_summary,
            review_queue=review_queue
        )
