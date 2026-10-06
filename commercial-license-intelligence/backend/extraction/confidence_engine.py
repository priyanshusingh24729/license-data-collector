"""
Deterministic Confidence Engine.
Scores extracted licensing facts based on Source Authority, Product Match Precision,
Edition & Version Alignment, and Evidence Directness.
"""

from typing import Optional, Tuple
from backend.models.enums import (
    AuthorityLevel,
    EvidenceType,
    ExtractionConfidence,
    ScopeType,
)


class ConfidenceEngine:
    """
    Computes mathematical confidence score (0.0 - 1.0) and discrete tier (VERY_HIGH, HIGH, MEDIUM, LOW, UNKNOWN).
    """

    def calculate_confidence(
        self,
        authority: AuthorityLevel,
        product_matched: bool,
        edition_matched: bool,
        version_matched: bool,
        evidence_type: EvidenceType,
        is_scope_universal: bool = False,
        document_date_matched: bool = True,
    ) -> Tuple[float, ExtractionConfidence]:
        """
        Calculates composite confidence score and maps to categorical tier.
        """
        score = 0.0

        # 1. Source Authority (Max 0.35)
        if authority in [
            AuthorityLevel.OFFICIAL_VENDOR,
            AuthorityLevel.OFFICIAL_VENDOR_TERMS,
            AuthorityLevel.OFFICIAL_VENDOR_EULA,
            AuthorityLevel.OFFICIAL_VENDOR_DOCUMENT
        ]:
            score += 0.35
        elif authority in [AuthorityLevel.OFFICIAL_VENDOR_DOCUMENTATION, AuthorityLevel.OFFICIAL_DISTRIBUTOR]:
            score += 0.25
        elif authority == AuthorityLevel.TRUSTED_SECONDARY:
            score += 0.15
        else:
            score += 0.05

        # 2. Product Match (Max 0.25)
        if product_matched:
            score += 0.25
        elif is_scope_universal:
            score += 0.10
        else:
            score += 0.0

        # 3. Edition Match (Max 0.15)
        if edition_matched:
            score += 0.15
        elif is_scope_universal:
            score += 0.10
        else:
            score += 0.05

        # 4. Version Match (Max 0.15)
        if version_matched:
            score += 0.15
        elif is_scope_universal:
            score += 0.10
        else:
            score += 0.05

        # 5. Evidence Directness (Max 0.10)
        if evidence_type in [
            EvidenceType.DIRECT_STATEMENT,
            EvidenceType.STRUCTURED_FIELD,
            EvidenceType.TABLE
        ]:
            score += 0.10
        elif evidence_type == EvidenceType.METADATA:
            score += 0.05
        else:
            score += 0.0  # Inferred receives 0 bonus

        # Penalize if document date is known to conflict with version release window
        if not document_date_matched:
            score -= 0.15

        # Cap score between 0.0 and 1.0
        final_score = max(0.0, min(1.0, round(score, 2)))

        # Tier mapping
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
