"""
Product Scope Matcher (Post Step 21 Quality System).
Evaluates whether a discovered licensing source / text passage refers to the
exact canonical product, its product family, a parent component, or a weak/unrelated entity.
"""

import re
from enum import Enum
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass


class ProductScopeMatchTier(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    FAMILY_MATCH = "FAMILY_MATCH"
    COMPONENT_MATCH = "COMPONENT_MATCH"
    WEAK_MATCH = "WEAK_MATCH"
    NO_MATCH = "NO_MATCH"


# Scope Match Score Weights (0–15 points, Section 20)
SCOPE_SCORES: Dict[ProductScopeMatchTier, float] = {
    ProductScopeMatchTier.EXACT_MATCH: 15.0,
    ProductScopeMatchTier.FAMILY_MATCH: 12.0,
    ProductScopeMatchTier.COMPONENT_MATCH: 10.0,
    ProductScopeMatchTier.WEAK_MATCH: 4.0,
    ProductScopeMatchTier.NO_MATCH: 0.0,
}


@dataclass
class ProductScopeResult:
    """Evaluation result for evidence scope matching."""
    match_tier: ProductScopeMatchTier
    score: float  # 0–15
    matched_target: str
    is_authoritative: bool
    explanation: str


class ProductScopeMatcher:
    """
    Deterministic rule-based product scope matching engine.
    Prevents generic mentions of vendors or OS names from creating false evidence connections.
    """

    @classmethod
    def evaluate_scope(
        cls,
        canonical_product: str,
        canonical_vendor: Optional[str],
        source_title: str,
        source_url: str,
        evidence_text: str,
        parent_product: Optional[str] = None,
        product_family: Optional[str] = None,
    ) -> ProductScopeResult:
        """
        Determines the degree of alignment between the canonical product and the evidence citation.
        """
        p_clean = (canonical_product or "").strip()
        p_low = p_clean.lower()
        v_low = (canonical_vendor or "").strip().lower()
        title_low = (source_title or "").strip().lower()
        url_low = (source_url or "").strip().lower()
        text_low = (evidence_text or "").strip().lower()
        combined_text = f"{title_low} {url_low} {text_low}"

        if not p_clean or p_clean.upper() in ["UNKNOWN", "UNRESOLVED"]:
            return ProductScopeResult(
                match_tier=ProductScopeMatchTier.NO_MATCH,
                score=SCOPE_SCORES[ProductScopeMatchTier.NO_MATCH],
                matched_target="NONE",
                is_authoritative=False,
                explanation="Canonical product identity is unresolved; cannot establish product scope match.",
            )

        # 1. Exact Product Match
        # Check if the exact product name or core token sequence appears in the source
        # Normalize punctuation for token matching
        tokens = [t for t in re.split(r"[\s\-_.:]+", p_low) if len(t) > 2 and t not in ["the", "app", "for", "and", "windows", "microsoft"]]
        if p_low in title_low or p_low in url_low or p_low in text_low:
            return ProductScopeResult(
                match_tier=ProductScopeMatchTier.EXACT_MATCH,
                score=SCOPE_SCORES[ProductScopeMatchTier.EXACT_MATCH],
                matched_target=p_clean,
                is_authoritative=True,
                explanation=f"Exact product name '{p_clean}' is directly referenced in official source passage.",
            )

        # If all core distinctive tokens appear in the text
        if tokens and all(t in combined_text for t in tokens):
            return ProductScopeResult(
                match_tier=ProductScopeMatchTier.EXACT_MATCH,
                score=SCOPE_SCORES[ProductScopeMatchTier.EXACT_MATCH] - 1.0,  # 14.0
                matched_target=p_clean,
                is_authoritative=True,
                explanation=f"All key distinctive tokens of '{p_clean}' match the evidence text.",
            )

        # 2. Parent Product / Component Match
        if parent_product:
            par_low = parent_product.strip().lower()
            if par_low in combined_text:
                return ProductScopeResult(
                    match_tier=ProductScopeMatchTier.COMPONENT_MATCH,
                    score=SCOPE_SCORES[ProductScopeMatchTier.COMPONENT_MATCH],
                    matched_target=parent_product,
                    is_authoritative=True,
                    explanation=f"Evidence directly covers parent product '{parent_product}' of which '{p_clean}' is a component.",
                )

        # 3. Product Family Match
        if product_family:
            fam_low = product_family.strip().lower()
            if fam_low in combined_text:
                return ProductScopeResult(
                    match_tier=ProductScopeMatchTier.FAMILY_MATCH,
                    score=SCOPE_SCORES[ProductScopeMatchTier.FAMILY_MATCH],
                    matched_target=product_family,
                    is_authoritative=True,
                    explanation=f"Evidence covers product family '{product_family}'.",
                )

        # 4. Weak / Partial Match
        # Only some tokens matched or generic vendor match
        matched_tokens = [t for t in tokens if t in combined_text]
        if matched_tokens and len(matched_tokens) >= max(1, len(tokens) // 2):
            return ProductScopeResult(
                match_tier=ProductScopeMatchTier.WEAK_MATCH,
                score=SCOPE_SCORES[ProductScopeMatchTier.WEAK_MATCH],
                matched_target=", ".join(matched_tokens),
                is_authoritative=False,
                explanation=f"Partial token match ({', '.join(matched_tokens)}) without full product confirmation.",
            )

        # 5. No Match
        return ProductScopeResult(
            match_tier=ProductScopeMatchTier.NO_MATCH,
            score=SCOPE_SCORES[ProductScopeMatchTier.NO_MATCH],
            matched_target="NONE",
            is_authoritative=False,
            explanation="Evidence source does not refer to the specified product, family, or parent component.",
        )
