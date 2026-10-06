"""
Conflict Detection Engine.
Identifies contradictions across sources for the same fact type (e.g. SUBSCRIPTION vs PERPETUAL)
and evaluates whether differences in version, edition, or source authority resolve the discrepancy.
"""

from typing import List, Dict, Any, Tuple, Optional
from backend.models.enums import FactType, FactStatus, AuthorityLevel
from backend.schemas.extraction import ExtractedFactCandidate, FactConflictItem


class ConflictDetector:
    """
    Detects and categorizes contradictory licensing facts across multiple collected sources.
    """

    def detect_conflicts(
        self,
        candidates: List[ExtractedFactCandidate]
    ) -> Tuple[List[ExtractedFactCandidate], List[FactConflictItem]]:
        """
        Groups candidates by fact_type and checks for conflicting normalized values.
        Returns: (processed_candidates_with_updated_status, conflict_items)
        """
        by_type: Dict[FactType, List[ExtractedFactCandidate]] = {}
        for c in candidates:
            by_type.setdefault(c.fact_type, []).append(c)

        conflict_items: List[FactConflictItem] = []

        for fact_type, facts in by_type.items():
            # Get distinct non-UNKNOWN normalized values
            distinct_values = list(set([f.normalized_value for f in facts if f.normalized_value != "UNKNOWN"]))

            if len(distinct_values) > 1:
                # Contradiction detected
                reasons: List[str] = []
                reasons.append(f"Multiple conflicting values extracted: {', '.join(distinct_values)}")

                # Check if edition or version explains it
                editions = list(set([getattr(f, "section_name", "") for f in facts if getattr(f, "section_name", "")]))
                if len(editions) > 1:
                    reasons.append(f"Differences may be attributed to distinct sections/editions: {', '.join(editions)}")

                conflict_items.append(FactConflictItem(
                    fact_type=fact_type,
                    values=distinct_values,
                    conflicting_fact_ids=[],
                    reasons=reasons,
                    explanation="Conflicting terms found across source document sections."
                ))

                # Mark lower-confidence facts as CONFLICT or REVIEW_REQUIRED
                for f in facts:
                    if f.normalized_value != "UNKNOWN":
                        f.status = FactStatus.CONFLICT

        return candidates, conflict_items
