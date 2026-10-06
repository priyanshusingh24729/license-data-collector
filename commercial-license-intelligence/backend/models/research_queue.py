"""
SQLAlchemy database models for Step 17: Intelligent License Research Prioritization.
Tracks research candidates, decisions, priorities, score breakdowns, and execution status.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    JSON,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import relationship
from backend.database.connection import Base
from backend.models.enums import ResearchDecision, ResearchPriority, ResearchQueueStatus


class LicenseResearchQueueItem(Base):
    """
    Queue item representing an application evaluated and prioritized for official licensing research.
    """
    __tablename__ = "license_research_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Application Catalog association (if resolved)
    application_id = Column(
        Integer,
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Detected Application on endpoint (if triggered from inventory discovery)
    detected_application_id = Column(
        Integer,
        ForeignKey("detected_applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Decision outcome
    decision = Column(
        SQLEnum(ResearchDecision, name="research_decision_enum"),
        nullable=False,
        index=True
    )

    # Priority rank
    priority = Column(
        SQLEnum(ResearchPriority, name="research_priority_enum"),
        nullable=False,
        index=True
    )

    # Deterministic priority score (0-100+)
    priority_score = Column(Integer, nullable=False, default=0)

    # Primary reason explanation
    reason = Column(String(500), nullable=False)

    # Detailed factor breakdown (list of reasons, score components, metrics)
    decision_factors = Column(JSON, nullable=True)

    # Queue lifecycle status
    status = Column(
        SQLEnum(ResearchQueueStatus, name="research_queue_status_enum"),
        nullable=False,
        default=ResearchQueueStatus.QUEUED,
        index=True
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Research execution linkages (STEP 10)
    research_run_id = Column(Integer, nullable=True)
    quality_score = Column(Float, nullable=True)
    profile_status = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    application = relationship("Application", backref="research_queue_items", foreign_keys=[application_id])
    detected_application = relationship("DetectedApplication", backref="research_queue_items", foreign_keys=[detected_application_id])

    __table_args__ = (
        Index("ix_res_queue_app_status", "application_id", "status"),
        Index("ix_res_queue_priority_score", "priority", "priority_score"),
    )

    def __repr__(self) -> str:
        return (
            f"<LicenseResearchQueueItem(id={self.id}, app_id={self.application_id}, "
            f"decision='{self.decision}', priority='{self.priority}', score={self.priority_score}, status='{self.status}')>"
        )
