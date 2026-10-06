"""
Deterministic Match Scoring & Confidence Calculator for Identity Resolution.
"""

from typing import Tuple, Optional
from backend.models.enums import ExtractionConfidence


class MatchConfidenceCalculator:
    """
    Evaluates attribute alignment between detected application and catalog entry.
    """

    @classmethod
    def calculate_score(
        cls,
        det_publisher: Optional[str],
        cat_vendor: str,
        det_name: str,
        cat_product: str,
        cat_edition: Optional[str] = None,
        det_version: Optional[str] = None,
        det_major: Optional[str] = None,
        cat_version: Optional[str] = None,
        det_os: Optional[str] = None,
        cat_os: Optional[str] = None,
    ) -> Tuple[float, ExtractionConfidence, list]:
        """
        Calculates a deterministic alignment score (0-100) and confidence tier.
        Returns: (score, confidence_tier, reasons)
        """
        score = 0.0
        reasons = []

        # 1. Publisher Alignment (+30 max)
        if det_publisher and cat_vendor:
            if det_publisher.strip().lower() == cat_vendor.strip().lower():
                score += 30.0
                reasons.append("Exact publisher match (+30)")
            elif cat_vendor.strip().lower() in det_publisher.strip().lower():
                score += 20.0
                reasons.append("Partial publisher match (+20)")

        # 2. Product Name Alignment (+35 max)
        norm_det_lower = det_name.strip().lower()
        cat_prod_lower = cat_product.strip().lower()

        if cat_prod_lower == norm_det_lower:
            score += 35.0
            reasons.append("Exact product name match (+35)")
        elif cat_prod_lower in norm_det_lower:
            score += 30.0
            reasons.append("Product name contained in detection (+30)")
        else:
            # Token overlap
            det_tokens = set(norm_det_lower.split())
            cat_tokens = set(cat_prod_lower.split())
            common = det_tokens.intersection(cat_tokens)
            if common:
                score += min(25.0, len(common) * 12.0)
                reasons.append(f"Product token overlap: {', '.join(common)} (+{min(25.0, len(common) * 12.0)})")

        # 3. Edition Alignment (+20 max, penalty for explicit mismatch)
        if cat_edition:
            ed_lower = cat_edition.strip().lower()
            if ed_lower in norm_det_lower:
                score += 20.0
                reasons.append(f"Edition '{cat_edition}' matched (+20)")
            else:
                # Check conflicting common editions (e.g. Reader vs Pro vs Standard)
                competing_editions = ["reader", "standard", "pro", "professional", "enterprise", "community", "ultimate"]
                present_competing = [ce for ce in competing_editions if ce in norm_det_lower and ce != ed_lower]
                if present_competing:
                    score -= 25.0
                    reasons.append(f"Edition conflict: detected '{present_competing[0]}' vs catalog '{cat_edition}' (-25)")
        else:
            score += 10.0  # Neutral edition bonus

        # 4. Version Alignment (+10 max)
        if cat_version and (det_version or det_major):
            cat_v = cat_version.strip().lower()
            if det_version and cat_v == det_version.strip().lower():
                score += 10.0
                reasons.append("Exact version match (+10)")
            elif det_major and (cat_v == det_major or cat_v.endswith(det_major)):
                score += 8.0
                reasons.append("Major version match (+8)")
            elif cat_v in (det_version or ""):
                score += 6.0
                reasons.append("Version substring match (+6)")
        else:
            score += 5.0  # Neutral version compatibility

        # 5. OS Alignment (+5 max)
        if cat_os and det_os:
            if cat_os.strip().lower() == det_os.strip().lower():
                score += 5.0
                reasons.append("OS match (+5)")
            else:
                score -= 10.0
                reasons.append(f"OS mismatch: '{det_os}' vs '{cat_os}' (-10)")
        else:
            score += 5.0

        score = max(0.0, min(100.0, score))

        # Determine confidence tier
        if score >= 90.0:
            tier = ExtractionConfidence.VERY_HIGH
        elif score >= 75.0:
            tier = ExtractionConfidence.HIGH
        elif score >= 50.0:
            tier = ExtractionConfidence.MEDIUM
        elif score > 0.0:
            tier = ExtractionConfidence.LOW
        else:
            tier = ExtractionConfidence.UNKNOWN

        return score, tier, reasons
