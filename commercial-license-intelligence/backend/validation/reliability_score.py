"""
Reliability Scoring Engine (Post Step 21 Quality System - Section 20).
Computes evidence-based 0–100 reliability across 6 specific dimensions:
1. Identity Quality (0–25)
2. Source Authority (0–20)
3. Evidence Directness (0–25)
4. Product Scope Match (0–15)
5. Classification Validation (0–10)
6. License Validation (0–5)

Enforces strict anti-gaming and evidence bounds:
- No evidence: Max 50
- Partial evidence: Max 75
- Strong official evidence: 80–94
- Direct official product-specific terms: 95–100
- Eliminates hardcoded or template-based score clustering (e.g., repeated 91%, 98%).
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from backend.models.enums import (
    SourceAuthorityTier,
    EvidenceType,
    ReliabilityBand,
)
from backend.validation.product_scope_matcher import ProductScopeMatchTier, SCOPE_SCORES

# Baseline / default reliability score for UNRESOLVED or UNKNOWN products
UNRESOLVED_RELIABILITY_SCORE: float = 17.0


@dataclass
class ReliabilityBreakdown:
    """
    Sub-scores composing the overall 0–100 reliability metric across the 6 dimensions.
    """
    identity_quality_score: float      # 0–25 (Section 20.1)
    source_authority_score: float      # 0–20 (Section 20.2)
    evidence_directness_score: float   # 0–25 (Section 20.3)
    product_scope_score: float         # 0–15 (Section 20.4)
    classification_score: float        # 0–10 (Section 20.5)
    license_validation_score: float    # 0–5  (Section 20.6)
    overall: float                     # 0–100 composite sum with caps
    band: ReliabilityBand              # VERY_HIGH, HIGH, MEDIUM, LOW, VERY_LOW

    # Backward compatibility properties
    @property
    def identity_quality(self) -> float:
        return self.identity_quality_score

    @property
    def source_authority(self) -> float:
        return self.source_authority_score

    @property
    def evidence_directness(self) -> float:
        return self.evidence_directness_score

    @property
    def scope_quality(self) -> float:
        return self.product_scope_score

    @property
    def scope_quality_score(self) -> float:
        return self.product_scope_score

    @property
    def validation_quality(self) -> float:
        return self.classification_score

    @property
    def validation_score(self) -> float:
        return self.classification_score

    @property
    def freshness(self) -> float:
        return self.license_validation_score

    @property
    def freshness_score(self) -> float:
        return self.license_validation_score

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["band"] = self.band.value if isinstance(self.band, ReliabilityBand) else str(self.band)
        d["identity_quality"] = self.identity_quality_score
        d["source_authority"] = self.source_authority_score
        d["evidence_directness"] = self.evidence_directness_score
        d["scope_quality"] = self.product_scope_score
        d["validation_quality"] = self.classification_score
        d["license_validation"] = self.license_validation_score
        return d


class ReliabilityScoreEngine:
    """
    Evaluates evidence quality and produces granular, evidence-based reliability ratings.
    """

    @classmethod
    def get_reliability_band(cls, score: float) -> ReliabilityBand:
        """Determines the categorical reliability band (Section 20)."""
        if score >= 95.0:
            return ReliabilityBand.VERY_HIGH
        if score >= 80.0:
            return ReliabilityBand.HIGH
        if score >= 60.0:
            return ReliabilityBand.MEDIUM
        if score >= 40.0:
            return ReliabilityBand.LOW
        return ReliabilityBand.VERY_LOW

    @classmethod
    def calculate_reliability(
        cls,
        identity_tier: str = "EXACT_VENDOR_CONFIRMED",                     # EXACT_VENDOR_CONFIRMED, PACKAGE_FAMILY_CONFIRMED, EXECUTABLE_CONFIRMED, ALIAS_CONFIRMED, NORMALIZED_ONLY, UNRESOLVED
        source_type: str = "TERMS",                       # TERMS (Level 1), DOCS (Level 2), SUPPORT (Level 3), REPUTABLE, NONE
        evidence_directness_tier: str = "DIRECT_STATEMENT",          # DIRECT_STATEMENT, OS_BUNDLED_CONFIRMED, STRONG_AVAILABILITY, SYSTEM_COMPONENT, INDIRECT, NONE
        scope_tier: str = "EXACT_MATCH",                        # EXACT_MATCH, FAMILY_MATCH, COMPONENT_MATCH, WEAK_MATCH, NO_MATCH
        classification_valid: bool = True,      # Model fits without contradictions
        license_metric_valid: bool = True,      # Discrete metric confirmed
        has_evidence: bool = True,
        is_partial_evidence: bool = False,
        evidence_text_len: int = 0,             # Natural variance parameter
        has_exact_version: bool = False,        # Natural variance parameter
        is_conflict: bool = False,
        **kwargs,
    ) -> ReliabilityBreakdown:
        """
        Calculates exact multi-dimensional reliability score according to Section 20 dimensions.
        Includes backward-compatible parameter mapping for legacy callers.
        """
        # Handle legacy kwargs mapping
        if "has_exact_identity" in kwargs and kwargs["has_exact_identity"]:
            identity_tier = "EXACT_VENDOR_CONFIRMED"
        if "authority_tier" in kwargs and kwargs["authority_tier"]:
            auth_val = kwargs["authority_tier"]
            source_type = getattr(auth_val, "name", str(auth_val))
        if "evidence_type" in kwargs and kwargs["evidence_type"]:
            ev_val = kwargs["evidence_type"]
            evidence_directness_tier = getattr(ev_val, "name", str(ev_val))
        if "is_exact_version" in kwargs:
            has_exact_version = bool(kwargs["is_exact_version"])
        if "is_partial" in kwargs:
            is_partial_evidence = bool(kwargs["is_partial"])
        # -------------------------------------------------------------
        # 1. Identity Quality (0–25 Points)
        # -------------------------------------------------------------
        id_score = 0.0
        if identity_tier == "EXACT_VENDOR_CONFIRMED":
            id_score = 25.0 if has_exact_version else 24.0
        elif identity_tier == "PACKAGE_FAMILY_CONFIRMED":
            id_score = 23.0
        elif identity_tier == "EXECUTABLE_CONFIRMED":
            id_score = 22.0
        elif identity_tier == "ALIAS_CONFIRMED":
            id_score = 20.0
        elif identity_tier == "NORMALIZED_ONLY":
            id_score = 15.0
        elif identity_tier == "PARTIAL_TOKEN":
            id_score = 8.0
        else:  # UNRESOLVED
            id_score = 0.0

        # -------------------------------------------------------------
        # 2. Source Authority (0–20 Points)
        # -------------------------------------------------------------
        auth_score = 0.0
        s_upper = (source_type or "").upper()
        if "TERMS" in s_upper or "EULA" in s_upper or "TIER_1" in s_upper or "OFFICIAL_PRIMARY" in s_upper:
            auth_score = 20.0
        elif "DOCS" in s_upper or "LEARN" in s_upper or "TIER_2" in s_upper or "OFFICIAL_SECONDARY" in s_upper:
            auth_score = 16.5
        elif "SUPPORT" in s_upper or "PRICING" in s_upper or "TIER_3" in s_upper:
            auth_score = 13.5
        elif "PRODUCT_PAGE" in s_upper or "TIER_4" in s_upper or "REPUTABLE" in s_upper:
            auth_score = 10.0
        elif "COMMUNITY" in s_upper:
            auth_score = 4.0
        else:
            auth_score = 0.0

        # -------------------------------------------------------------
        # 3. Evidence Directness (0–25 Points)
        # -------------------------------------------------------------
        ev_score = 0.0
        ev_upper = (evidence_directness_tier or "").upper()
        if "DIRECT_STATEMENT" in ev_upper or "EXPLICIT_TERMS" in ev_upper:
            ev_score = 25.0
        elif "OS_BUNDLED_CONFIRMED" in ev_upper or "INBOX_APP" in ev_upper:
            ev_score = 23.0
        elif "STRONG_AVAILABILITY" in ev_upper or "SYSTEM_COMPONENT" in ev_upper:
            ev_score = 20.0
        elif "COMMERCIAL_COMPONENT" in ev_upper or "FREEWARE_RUNTIME" in ev_upper:
            ev_score = 18.0
        elif "INDIRECT" in ev_upper or "PARTIAL" in ev_upper:
            ev_score = 10.0
        else:
            ev_score = 0.0

        # Natural variance for quote quality / length (0.0 to 1.5 points)
        if evidence_text_len > 150:
            ev_score = min(25.0, ev_score + 1.0)
        elif evidence_text_len > 60:
            ev_score = min(25.0, ev_score + 0.5)

        # -------------------------------------------------------------
        # 4. Product Scope Match (0–15 Points)
        # -------------------------------------------------------------
        scope_score = 0.0
        sc_upper = (scope_tier or "").upper()
        if "EXACT" in sc_upper:
            scope_score = 15.0
        elif "FAMILY" in sc_upper:
            scope_score = 12.0
        elif "COMPONENT" in sc_upper:
            scope_score = 10.0
        elif "WEAK" in sc_upper:
            scope_score = 4.0
        else:
            scope_score = 0.0

        # -------------------------------------------------------------
        # 5. Classification Validation (0–10 Points)
        # -------------------------------------------------------------
        class_score = 0.0
        if classification_valid and not is_conflict:
            class_score = 10.0
        elif classification_valid and is_conflict:
            class_score = 3.0
        else:
            class_score = 0.0

        # -------------------------------------------------------------
        # 6. License Validation (0–5 Points)
        # -------------------------------------------------------------
        lic_score = 0.0
        if license_metric_valid and not is_conflict:
            lic_score = 5.0
        elif is_conflict:
            lic_score = 1.0
        else:
            lic_score = 2.0

        # Raw Composite Sum (0–100)
        raw_composite = id_score + auth_score + ev_score + scope_score + class_score + lic_score

        # -------------------------------------------------------------
        # Strict Rule Caps (Section 20 Rules)
        # -------------------------------------------------------------
        final_score = raw_composite

        if not has_evidence or identity_tier == "UNRESOLVED":
            # No evidence / Unresolved -> Maximum 50
            final_score = min(48.0, final_score)
        elif auth_score == 0.0 or ev_score == 0.0:
            # Missing source authority or evidence directness -> Maximum 60
            final_score = min(60.0, final_score)
        elif is_partial_evidence:
            # Partial evidence -> Maximum 75
            final_score = min(74.0, final_score)
        elif is_conflict:
            # Conflict detected -> Lower reliability
            final_score = min(58.0, final_score)
        elif auth_score < 18.0 and final_score >= 95.0:
            # Only direct Level 1 terms can reach 95-100
            final_score = min(94.0, final_score)

        final_score = round(max(0.0, min(100.0, final_score)), 1)
        band = cls.get_reliability_band(final_score)

        return ReliabilityBreakdown(
            identity_quality_score=round(id_score, 1),
            source_authority_score=round(auth_score, 1),
            evidence_directness_score=round(ev_score, 1),
            product_scope_score=round(scope_score, 1),
            classification_score=round(class_score, 1),
            license_validation_score=round(lic_score, 1),
            overall=final_score,
            band=band,
        )
