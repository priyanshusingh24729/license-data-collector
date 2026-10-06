"""
SQLAlchemy models for Data Quality Contradiction and Issue Tracking (Step 19).
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Enum as SQLEnum,
    Index,
)
from backend.database.connection import Base
from backend.models.enums import (
    ContradictionSeverity,
    IssueStatus,
)


class DataQualityIssue(Base):
    """
    Data quality contradiction or gap flagged on an application inventory record (Step 19).
    """
    __tablename__ = "data_quality_issues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, nullable=True, index=True)

    issue_type = Column(String(100), nullable=False, index=True)
    severity = Column(
        SQLEnum(ContradictionSeverity, name="contradiction_severity_enum", create_type=False),
        nullable=False,
        default=ContradictionSeverity.MEDIUM,
        index=True
    )
    current_value = Column(String(255), nullable=True)
    expected_value = Column(String(255), nullable=True)
    reason = Column(Text, nullable=False)
    status = Column(
        SQLEnum(IssueStatus, name="issue_status_enum", create_type=False),
        nullable=False,
        default=IssueStatus.ACTIVE,
        index=True
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<DataQualityIssue id={self.id} app={self.application_id} type='{self.issue_type}' sev='{self.severity.value}'>"
