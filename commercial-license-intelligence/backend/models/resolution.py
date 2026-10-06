"""
SQLAlchemy model for Step 17.7: Automatic Review Resolution Runs.
Persists historical resolution attempts, methods, evidence, and outcomes.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import relationship
from backend.database.connection import Base
from backend.models.enums import (
    ReviewReason,
    ResolutionMethod,
    FinalLicenseStatus,
    ExtractionConfidence,
)


class ReviewResolutionRun(Base):
    """
    Tracks review resolution attempts and outcomes for detected and catalog applications.
    """
    __tablename__ = "review_resolution_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True)
    detected_application_id = Column(Integer, ForeignKey("detected_applications.id", ondelete="CASCADE"), nullable=True, index=True)

    old_status = Column(String(100), nullable=False, default="REVIEW_REQUIRED")
    old_reason = Column(SQLEnum(ReviewReason, name="review_reason_enum", create_type=False), nullable=True)

    resolution_attempt = Column(Integer, nullable=False, default=1)
    resolution_method = Column(
        SQLEnum(ResolutionMethod, name="resolution_method_enum", create_type=False),
        nullable=False,
        default=ResolutionMethod.DETERMINISTIC_RULE
    )

    result = Column(Text, nullable=False)
    new_status = Column(
        SQLEnum(FinalLicenseStatus, name="final_license_status_enum", create_type=False),
        nullable=False
    )
    confidence = Column(
        SQLEnum(ExtractionConfidence, name="extraction_confidence_enum", create_type=False),
        nullable=False,
        default=ExtractionConfidence.HIGH
    )
    evidence = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    application = relationship("Application")
    detected_application = relationship("DetectedApplication")

    def __repr__(self) -> str:
        return f"<ReviewResolutionRun id={self.id} app_id={self.application_id} det_id={self.detected_application_id} method='{self.resolution_method.value}' new_status='{self.new_status.value}'>"
