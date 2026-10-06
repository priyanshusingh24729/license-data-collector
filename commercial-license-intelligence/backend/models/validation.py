"""
SQLAlchemy models for Fact Validation Runs and Audit Trails.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    JSON,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from backend.database.connection import Base
from backend.models.enums import FactStatus, ExtractionConfidence


class FactValidationRun(Base):
    """
    Audit log of validation executions evaluating license facts.
    Preserves historical validation reasoning without overwriting previous runs.
    """
    __tablename__ = "fact_validation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    license_fact_id = Column(Integer, ForeignKey("license_facts.id", ondelete="CASCADE"), nullable=False, index=True)

    validation_status = Column(
        SQLEnum(FactStatus, name="fact_status_enum", create_type=False),
        nullable=False,
        index=True
    )
    quality = Column(
        SQLEnum(ExtractionConfidence, name="extraction_confidence_enum", create_type=False),
        nullable=False,
        index=True
    )
    validation_reason = Column(Text, nullable=True)
    checks_summary = Column(JSON, nullable=True)
    validator_version = Column(String(50), nullable=False, default="1.0.0")

    validated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_validation_fact_status", "license_fact_id", "validation_status"),
    )

    def __repr__(self) -> str:
        return (
            f"<FactValidationRun id={self.id} fact_id={self.license_fact_id} "
            f"status='{self.validation_status.value}' quality='{self.quality.value}'>"
        )
