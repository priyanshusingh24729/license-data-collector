"""
SQLAlchemy models for Immutable Audit Events and License Intelligence Quality Issues.
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
    AuditEventType,
    QualityIssueType,
    AlertSeverity,
    IssueStatus,
)


class AuditEvent(Base):
    """
    Immutable, append-only log of significant events across the software intelligence lifecycle.
    """
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)

    event_type = Column(
        SQLEnum(AuditEventType, name="audit_event_type_enum"),
        nullable=False,
        index=True
    )
    actor_type = Column(String(50), nullable=False, default="SYSTEM")
    actor_id = Column(String(100), nullable=True)

    description = Column(Text, nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    def __repr__(self) -> str:
        return f"<AuditEvent id={self.id} type='{self.event_type.value}' entity='{self.entity_type}:{self.entity_id}'>"


class QualityIssue(Base):
    """
    Data quality gap or rule violation flagged on an application or fact.
    """
    __tablename__ = "quality_issues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)

    entity_type = Column(String(100), nullable=True)
    entity_id = Column(Integer, nullable=True)

    issue_type = Column(
        SQLEnum(QualityIssueType, name="quality_issue_type_enum"),
        nullable=False,
        index=True
    )
    severity = Column(
        SQLEnum(AlertSeverity, name="alert_severity_enum", create_type=False),
        nullable=False,
        default=AlertSeverity.MEDIUM,
        index=True
    )
    description = Column(Text, nullable=False)
    status = Column(
        SQLEnum(IssueStatus, name="issue_status_enum"),
        nullable=False,
        default=IssueStatus.ACTIVE,
        index=True
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    application = relationship("Application")

    def __repr__(self) -> str:
        return f"<QualityIssue id={self.id} app={self.application_id} type='{self.issue_type.value}' status='{self.status.value}'>"
