"""
Deterministic License Intelligence Quality Engine.
Calculates mathematical quality score and assigns discrete quality tiers.
Validates fact-specific semantic evidence rules to prevent weak inferences from being validated.
"""

import re
from typing import Tuple, List
from backend.models.enums import (
    FactType,
    ExtractionConfidence,
    AuthorityLevel,
    EvidenceType,
)
from backend.models.fact import LicenseFact
from backend.validation.validation_result import ValidationChecks


class QualityEngine:
    """
    Evaluates evidence quality and computes multi-factor quality scores.
    """

    def validate_fact_semantics(self, fact: LicenseFact) -> Tuple[bool, List[str]]:
        """
        Validates fact-specific semantic requirements against evidence text.
        Returns: (is_supported, failure_reasons)
        """
        ev_lower = fact.evidence_text.lower()
        ft = fact.fact_type
        val = fact.normalized_value
        reasons: List[str] = []

        # 1. SUBSCRIPTION semantic check
        if ft == FactType.LICENSE_MODEL and val == "SUBSCRIPTION":
            if not any(k in ev_lower for k in ["subscription", "monthly", "annual", "recurring", "saas", "term license"]):
                reasons.append("INSUFFICIENT_EVIDENCE: 'Sign in' or account login alone does not establish a subscription license model.")
                return False, reasons

        # 2. NAMED_USER semantic check
        if ft == FactType.LICENSE_METRIC and val == "NAMED_USER":
            if not any(k in ev_lower for k in ["named user", "named-user", "assigned user", "individual user", "identified user"]):
                reasons.append("INSUFFICIENT_EVIDENCE: General login or user mention alone does not establish a named user licensing metric.")
                return False, reasons

        # 3. LICENSE_REQUIRED = TRUE semantic check
        if ft == FactType.LICENSE_REQUIRED and val == "TRUE":
            if not any(k in ev_lower for k in ["requires a license", "license is required", "must purchase", "separate license", "valid license", "licensed under"]):
                reasons.append("INSUFFICIENT_EVIDENCE: 'Proprietary software' alone does not establish an explicit licensing requirement.")
                return False, reasons

        # 4. TRIAL semantic check
        if ft == FactType.TRIAL_AVAILABLE and val == "TRUE":
            if not any(k in ev_lower for k in ["trial", "evaluation", "eval", "demo"]):
                reasons.append("INSUFFICIENT_EVIDENCE: Evidence text does not mention evaluation or trial availability.")
                return False, reasons

        return True, reasons

    def compute_quality_score(
        self,
        checks: ValidationChecks,
        authority: AuthorityLevel,
        is_semantic_supported: bool
    ) -> Tuple[float, ExtractionConfidence]:
        """
        Calculates mathematical composite quality score and assigns tier.
        """
        if not checks.evidence_exists or not checks.evidence_text_matched:
            return 0.0, ExtractionConfidence.UNKNOWN

        score = 0.0

        # Authority (0.30)
        if authority in [
            AuthorityLevel.OFFICIAL_VENDOR,
            AuthorityLevel.OFFICIAL_VENDOR_TERMS,
            AuthorityLevel.OFFICIAL_VENDOR_EULA,
            AuthorityLevel.OFFICIAL_VENDOR_DOCUMENT
        ]:
            score += 0.30
        elif authority in [AuthorityLevel.OFFICIAL_VENDOR_DOCUMENTATION, AuthorityLevel.OFFICIAL_DISTRIBUTOR]:
            score += 0.20
        elif authority == AuthorityLevel.TRUSTED_SECONDARY:
            score += 0.10
        else:
            score += 0.05

        # Product Match (0.25)
        if checks.product_match:
            score += 0.25

        # Edition Match (0.15)
        if checks.edition_match:
            score += 0.15

        # Version Match (0.15)
        if checks.version_match:
            score += 0.15

        # Semantic & Direct Evidence Alignment (0.15)
        if is_semantic_supported and checks.direct_evidence:
            score += 0.15
        elif is_semantic_supported:
            score += 0.05

        final_score = max(0.0, min(1.0, round(score, 2)))

        if final_score >= 0.85:
            tier = ExtractionConfidence.VERY_HIGH
        elif final_score >= 0.70:
            tier = ExtractionConfidence.HIGH
        elif final_score >= 0.50:
            tier = ExtractionConfidence.MEDIUM
        elif final_score > 0.0:
            tier = ExtractionConfidence.LOW
        else:
            tier = ExtractionConfidence.UNKNOWN

        return final_score, tier
