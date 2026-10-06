"""
Profile-Level Confidence & Status Calculator.
Evaluates consolidation completeness across critical licensing facts
(Classification, Required, Model, Metric) to assign overall profile status and confidence tier.
"""

from typing import Dict, List, Tuple
from backend.models.enums import ProfileStatus, ExtractionConfidence, FactType
from backend.consolidation.profile_schemas import FieldExplanation

CRITICAL_FACT_TYPES = [
    FactType.LICENSE_CLASSIFICATION,
    FactType.LICENSE_REQUIRED,
    FactType.LICENSE_MODEL,
    FactType.LICENSE_METRIC,
]


class ProfileConfidenceCalculator:
    """
    Computes overall profile confidence tier and status lifecycle enum.
    """

    def calculate(
        self,
        explanations: Dict[str, FieldExplanation],
        has_conflicts: bool,
        has_review_required: bool,
        validated_fact_count: int
    ) -> Tuple[ProfileStatus, ExtractionConfidence]:
        """
        Determines (ProfileStatus, ExtractionConfidence).
        """
        if validated_fact_count == 0:
            if has_review_required:
                return ProfileStatus.REVIEW_REQUIRED, ExtractionConfidence.LOW
            return ProfileStatus.UNKNOWN, ExtractionConfidence.UNKNOWN

        if has_conflicts:
            return ProfileStatus.CONFLICT, ExtractionConfidence.LOW

        # Evaluate critical facts
        critical_vals = [
            explanations.get(ft.value, FieldExplanation(value="UNKNOWN", confidence=ExtractionConfidence.UNKNOWN)).value
            for ft in CRITICAL_FACT_TYPES
        ]

        unknown_critical = [v for v in critical_vals if v == "UNKNOWN"]

        # If all 4 critical facts are known and validated
        if len(unknown_critical) == 0:
            # Check individual confidences
            conf_tiers = [
                explanations.get(ft.value, FieldExplanation(value="UNKNOWN", confidence=ExtractionConfidence.UNKNOWN)).confidence
                for ft in CRITICAL_FACT_TYPES
            ]
            if all(c == ExtractionConfidence.VERY_HIGH for c in conf_tiers):
                return ProfileStatus.VALIDATED, ExtractionConfidence.VERY_HIGH
            elif any(c in [ExtractionConfidence.VERY_HIGH, ExtractionConfidence.HIGH] for c in conf_tiers):
                return ProfileStatus.VALIDATED, ExtractionConfidence.HIGH
            else:
                return ProfileStatus.VALIDATED, ExtractionConfidence.MEDIUM

        # If some critical facts are validated, but some unknown
        elif len(unknown_critical) < len(CRITICAL_FACT_TYPES):
            if has_review_required:
                return ProfileStatus.REVIEW_REQUIRED, ExtractionConfidence.MEDIUM
            return ProfileStatus.PARTIALLY_VALIDATED, ExtractionConfidence.MEDIUM

        else:
            if has_review_required:
                return ProfileStatus.REVIEW_REQUIRED, ExtractionConfidence.LOW
            return ProfileStatus.PARTIALLY_VALIDATED, ExtractionConfidence.LOW
