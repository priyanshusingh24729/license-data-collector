"""
Application Catalog Matching Engine.
Evaluates detected software against catalog entries and identifies Exact, Normalized, Fuzzy, and Ambiguous matches.
"""

from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.enums import MatchType, ExtractionConfidence
from backend.models.application import Application, compute_canonical_application_key
from backend.inventory.detection.match_confidence import MatchConfidenceCalculator


class ScoredCatalogCandidate:
    """A scored candidate catalog application with alignment details."""
    def __init__(
        self,
        application: Application,
        score: float,
        confidence: ExtractionConfidence,
        reasons: list
    ):
        self.application = application
        self.score = score
        self.confidence = confidence
        self.reasons = reasons


class MatchingEngine:
    """
    Core engine matching endpoint detections against the canonical Application Catalog.
    """

    def __init__(self, confidence_calc: Optional[MatchConfidenceCalculator] = None):
        self.calc = confidence_calc or MatchConfidenceCalculator()

    def match_application(
        self,
        db: Session,
        normalized_name: str,
        normalized_publisher: Optional[str] = None,
        detected_version: Optional[str] = None,
        major_version: Optional[str] = None,
        operating_system: Optional[str] = None
    ) -> Tuple[MatchType, Optional[Application], float, ExtractionConfidence, List[ScoredCatalogCandidate]]:
        """
        Evaluates detected software against the catalog.
        Returns: (match_type, best_candidate, best_score, confidence, all_candidates)
        """
        # 1. Check exact canonical application key match
        canonical_key = compute_canonical_application_key(
            vendor=normalized_publisher or "",
            product=normalized_name,
            edition=None,
            version=detected_version or major_version,
            operating_system=operating_system
        )
        exact_app = db.query(Application).filter(Application.application_key == canonical_key).first()
        if exact_app:
            cand = ScoredCatalogCandidate(exact_app, 100.0, ExtractionConfidence.VERY_HIGH, ["Exact canonical key match"])
            return MatchType.EXACT_MATCH, exact_app, 100.0, ExtractionConfidence.VERY_HIGH, [cand]

        # 2. Query candidate applications (filter by vendor or name tokens)
        query = db.query(Application)
        candidates_query = []
        if normalized_publisher:
            candidates_query = query.filter(
                func.lower(Application.vendor_name) == normalized_publisher.strip().lower()
            ).all()

        if not candidates_query:
            # Fallback to search by product name tokens
            name_tokens = [t.lower() for t in normalized_name.split() if len(t) > 2]
            if name_tokens:
                filter_conds = [func.lower(Application.product_name).like(f"%{t}%") for t in name_tokens]
                candidates_query = db.query(Application).filter(*filter_conds).all()

        if not candidates_query:
            # Fallback to all applications if catalog is small
            candidates_query = db.query(Application).limit(100).all()

        # 3. Score all potential candidates
        scored_list: List[ScoredCatalogCandidate] = []
        for app in candidates_query:
            score, conf, reasons = self.calc.calculate_score(
                det_publisher=normalized_publisher,
                cat_vendor=app.vendor_name,
                det_name=normalized_name,
                cat_product=app.product_name,
                cat_edition=app.edition,
                det_version=detected_version,
                det_major=major_version,
                cat_version=app.version,
                det_os=operating_system,
                cat_os=app.operating_system
            )
            if score >= 35.0:
                scored_list.append(ScoredCatalogCandidate(app, score, conf, reasons))

        if not scored_list:
            return MatchType.NO_MATCH, None, 0.0, ExtractionConfidence.UNKNOWN, []

        # Sort candidates descending by score
        scored_list.sort(key=lambda c: c.score, reverse=True)
        top = scored_list[0]

        # 4. Check Ambiguity: If multiple top candidates have nearly identical high scores
        if len(scored_list) > 1:
            second = scored_list[1]
            if top.score >= 60.0 and (top.score - second.score) <= 5.0 and top.application.product_name != second.application.product_name:
                # Ambiguous detection (e.g. Acrobat Reader vs Acrobat Pro)
                return MatchType.AMBIGUOUS_MATCH, None, top.score, ExtractionConfidence.MEDIUM, scored_list

        # 5. Evaluate Match Type
        if top.score >= 95.0:
            return MatchType.EXACT_MATCH, top.application, top.score, top.confidence, scored_list
        elif top.score >= 80.0:
            return MatchType.NORMALIZED_MATCH, top.application, top.score, top.confidence, scored_list
        elif top.score >= 60.0:
            return MatchType.FUZZY_MATCH, top.application, top.score, top.confidence, scored_list
        else:
            return MatchType.NO_MATCH, None, top.score, top.confidence, scored_list
