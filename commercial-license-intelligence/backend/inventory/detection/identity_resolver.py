"""
Identity Resolver Engine.
Coordinates matching against catalog, auto-accepting high-confidence matches,
and queuing ambiguous or low-confidence detections into ApplicationResolutionQueue for human review.
"""

from typing import Optional, Tuple, List
from sqlalchemy.orm import Session

from backend.models.enums import (
    MatchType,
    ResolutionQueueStatus,
    ExtractionConfidence,
)
from backend.models.inventory import DetectedApplication, ApplicationResolutionQueue
from backend.inventory.detection.matching_engine import MatchingEngine, ScoredCatalogCandidate


class IdentityResolver:
    """
    Resolves a detected application against catalog and manages the human review queue.
    """

    def __init__(self, matching_engine: Optional[MatchingEngine] = None):
        self.engine = matching_engine or MatchingEngine()

    def resolve_detection(
        self,
        db: Session,
        detected_app: DetectedApplication
    ) -> Tuple[MatchType, Optional[int], Optional[int]]:
        """
        Executes identity resolution for a detected application.
        Returns: (match_type, resolved_application_id, queue_id_if_queued)
        """
        match_type, best_app, score, confidence, candidates = self.engine.match_application(
            db=db,
            normalized_name=detected_app.normalized_name,
            normalized_publisher=detected_app.normalized_publisher,
            detected_version=detected_app.detected_version,
            major_version=detected_app.major_version,
            operating_system=detected_app.operating_system
        )

        detected_app.resolution_type = match_type
        detected_app.resolution_confidence = confidence

        # 1. High-Confidence Auto-Accept (Exact or High-scoring Normalized match with single clear candidate)
        if match_type in [MatchType.EXACT_MATCH, MatchType.NORMALIZED_MATCH] and confidence in [
            ExtractionConfidence.VERY_HIGH,
            ExtractionConfidence.HIGH
        ] and best_app:
            detected_app.resolved_application_id = best_app.id
            db.commit()
            return match_type, best_app.id, None

        # 2. Ambiguous, Fuzzy, or Low Confidence -> Route to Review Queue
        detected_app.resolved_application_id = None
        db.commit()

        # Remove existing pending queue entries for this detection to avoid stale duplicates
        db.query(ApplicationResolutionQueue).filter(
            ApplicationResolutionQueue.detected_application_id == detected_app.id
        ).delete()

        queue_id = None
        for cand in candidates[:5]:  # Store top 5 candidates
            queue_item = ApplicationResolutionQueue(
                detected_application_id=detected_app.id,
                candidate_application_id=cand.application.id,
                match_type=match_type,
                match_score=cand.score,
                confidence=cand.confidence,
                reason="; ".join(cand.reasons) if cand.reasons else "Fuzzy catalog match.",
                status=ResolutionQueueStatus.PENDING
            )
            db.add(queue_item)
            db.commit()
            db.refresh(queue_item)
            if queue_id is None:
                queue_id = queue_item.id

        if not candidates:
            # Add NO_MATCH entry
            queue_item = ApplicationResolutionQueue(
                detected_application_id=detected_app.id,
                candidate_application_id=None,
                match_type=MatchType.NO_MATCH,
                match_score=0.0,
                confidence=ExtractionConfidence.UNKNOWN,
                reason="No matching catalog entry found.",
                status=ResolutionQueueStatus.PENDING
            )
            db.add(queue_item)
            db.commit()
            db.refresh(queue_item)
            queue_id = queue_item.id

        return match_type, None, queue_id
