"""
SQLAlchemy models for Source Monitoring, Change Detection, Fact Evolution & Licensing Alerts.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import relationship
from backend.database.connection import Base
from backend.models.enums import (
    MonitorFrequency,
    MonitorStatus,
    MonitoringRunStatus,
    ChangeClassification,
    FactChangeType,
    AlertType,
    AlertSeverity,
    AlertStatus,
    FactType,
    ExtractionConfidence,
)


class SourceMonitor(Base):
    """
    Scheduled monitoring registration for an authoritative licensing source.
    """
    __tablename__ = "source_monitors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("license_sources.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    enabled = Column(Boolean, nullable=False, default=True)
    monitor_frequency = Column(
        SQLEnum(MonitorFrequency, name="monitor_frequency_enum"),
        nullable=False,
        default=MonitorFrequency.WEEKLY
    )

    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    next_check_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    last_status = Column(
        SQLEnum(MonitorStatus, name="monitor_status_enum"),
        nullable=False,
        default=MonitorStatus.ACTIVE,
        index=True
    )
    last_content_hash = Column(String(64), nullable=True)
    last_change_detected_at = Column(DateTime(timezone=True), nullable=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    source = relationship("LicenseSource")

    def __repr__(self) -> str:
        return f"<SourceMonitor id={self.id} source_id={self.source_id} freq='{self.monitor_frequency.value}' status='{self.last_status.value}'>"


class MonitoringRun(Base):
    """
    Audit log of individual source check executions.
    """
    __tablename__ = "monitoring_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("license_sources.id", ondelete="CASCADE"), nullable=False, index=True)

    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(
        SQLEnum(MonitoringRunStatus, name="monitoring_run_status_enum"),
        nullable=False,
        default=MonitoringRunStatus.RUNNING,
        index=True
    )
    previous_hash = Column(String(64), nullable=True)
    current_hash = Column(String(64), nullable=True)
    change_detected = Column(Boolean, nullable=False, default=False)
    change_classification = Column(
        SQLEnum(ChangeClassification, name="change_classification_enum"),
        nullable=False,
        default=ChangeClassification.NO_CHANGE
    )
    diff_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    source = relationship("LicenseSource")

    def __repr__(self) -> str:
        return f"<MonitoringRun id={self.id} source_id={self.source_id} status='{self.status.value}' changed={self.change_detected}>"


class LicenseFactChange(Base):
    """
    Granular audit of verified licensing fact transitions (e.g. PERPETUAL -> SUBSCRIPTION).
    """
    __tablename__ = "license_fact_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True)
    old_fact_id = Column(Integer, ForeignKey("license_facts.id", ondelete="SET NULL"), nullable=True)
    new_fact_id = Column(Integer, ForeignKey("license_facts.id", ondelete="SET NULL"), nullable=True)

    fact_type = Column(
        SQLEnum(FactType, name="fact_type_enum", create_type=False),
        nullable=False,
        index=True
    )
    old_value = Column(String(255), nullable=True)
    new_value = Column(String(255), nullable=True)

    change_type = Column(
        SQLEnum(FactChangeType, name="fact_change_type_enum"),
        nullable=False,
        default=FactChangeType.UNCHANGED,
        index=True
    )
    detected_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    source_id = Column(Integer, ForeignKey("license_sources.id", ondelete="SET NULL"), nullable=True)
    document_id = Column(Integer, ForeignKey("collected_documents.id", ondelete="SET NULL"), nullable=True)
    confidence = Column(
        SQLEnum(ExtractionConfidence, name="extraction_confidence_enum", create_type=False),
        nullable=False,
        default=ExtractionConfidence.UNKNOWN
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        return f"<LicenseFactChange id={self.id} type='{self.fact_type.value}' {self.old_value}->{self.new_value}>"


class LicenseAlert(Base):
    """
    High-priority actionable alert generated when validated licensing facts evolve.
    """
    __tablename__ = "license_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True)
    source_id = Column(Integer, ForeignKey("license_sources.id", ondelete="SET NULL"), nullable=True)
    document_id = Column(Integer, ForeignKey("collected_documents.id", ondelete="SET NULL"), nullable=True)

    alert_type = Column(
        SQLEnum(AlertType, name="alert_type_enum"),
        nullable=False,
        index=True
    )
    severity = Column(
        SQLEnum(AlertSeverity, name="alert_severity_enum"),
        nullable=False,
        default=AlertSeverity.INFO,
        index=True
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    old_value = Column(String(255), nullable=True)
    new_value = Column(String(255), nullable=True)

    status = Column(
        SQLEnum(AlertStatus, name="alert_status_enum"),
        nullable=False,
        default=AlertStatus.NEW,
        index=True
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_alert_dedup", "application_id", "source_id", "alert_type", "new_value", "status"),
    )

    def __repr__(self) -> str:
        return f"<LicenseAlert id={self.id} sev='{self.severity.value}' title='{self.title}' status='{self.status.value}'>"
