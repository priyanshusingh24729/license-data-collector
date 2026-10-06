"""
SQLAlchemy models for Application Catalog, Canonical Identity, and Batch Research Jobs.
"""

import re
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
    ApplicationStatus,
    ApplicationResearchStatus,
    BatchStatus,
    BatchItemStatus,
)


def compute_canonical_application_key(
    vendor: str,
    product: str,
    edition: str | None = None,
    version: str | None = None,
    operating_system: str | None = None
) -> str:
    """
    Computes a deterministic canonical key for duplicate prevention.
    Example: ADOBE|ACROBAT|PRO|2025|WINDOWS
    """
    def clean(val: str | None) -> str:
        if not val or val.strip().lower() in ["none", "null", "unknown", ""]:
            return "ANY"
        # Normalize whitespace, strip punctuation, uppercase
        s = " ".join(val.strip().split()).upper()
        # Keep alphanumeric, spaces, and periods/hyphens
        return s

    v = clean(vendor)
    p = clean(product)
    e = clean(edition)
    ver = clean(version)
    os_name = clean(operating_system)

    return f"{v}|{p}|{e}|{ver}|{os_name}"


class Application(Base):
    """
    Managed commercial software application identity in the central intelligence catalog.
    """
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Core Identity Fields
    vendor_name = Column(String(255), nullable=False, index=True)
    product_name = Column(String(255), nullable=False, index=True)
    display_name = Column(String(255), nullable=True)

    edition = Column(String(100), nullable=True, index=True)
    version = Column(String(100), nullable=True, index=True)
    operating_system = Column(String(100), nullable=True, index=True)
    architecture = Column(String(50), nullable=True)
    publisher = Column(String(255), nullable=True)
    product_identifier = Column(String(255), nullable=True)

    # Canonical Deterministic Key
    application_key = Column(String(255), unique=True, nullable=False, index=True)

    # Operational & Research Status
    status = Column(
        SQLEnum(ApplicationStatus, name="application_status_enum"),
        nullable=False,
        default=ApplicationStatus.ACTIVE,
        index=True
    )
    research_status = Column(
        SQLEnum(ApplicationResearchStatus, name="application_research_status_enum"),
        nullable=False,
        default=ApplicationResearchStatus.NOT_RESEARCHED,
        index=True
    )

    # Active Consolidated Profile Link
    current_profile_id = Column(Integer, ForeignKey("license_profiles.id", ondelete="SET NULL"), nullable=True)

    # Timestamps
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

    # Relationships
    current_profile = relationship("LicenseProfile")
    batch_items = relationship("ResearchBatchItem", back_populates="application", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_app_search", "vendor_name", "product_name", "version", "operating_system"),
    )

    def __repr__(self) -> str:
        return f"<Application id={self.id} key='{self.application_key}' status='{self.research_status.value}'>"


class ResearchBatch(Base):
    """
    Batch research job coordinator managing controlled multi-application licensing research.
    """
    __tablename__ = "research_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)

    total_applications = Column(Integer, nullable=False, default=0)
    queued = Column(Integer, nullable=False, default=0)
    running = Column(Integer, nullable=False, default=0)
    completed = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    partial = Column(Integer, nullable=False, default=0)

    status = Column(
        SQLEnum(BatchStatus, name="batch_status_enum"),
        nullable=False,
        default=BatchStatus.QUEUED,
        index=True
    )

    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    items = relationship("ResearchBatchItem", back_populates="batch", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ResearchBatch id={self.id} name='{self.name}' status='{self.status.value}' total={self.total_applications}>"


class ResearchBatchItem(Base):
    """
    Individual application execution state within a batch research job.
    """
    __tablename__ = "research_batch_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("research_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    research_run_id = Column(Integer, nullable=True)

    status = Column(
        SQLEnum(BatchItemStatus, name="batch_item_status_enum"),
        nullable=False,
        default=BatchItemStatus.QUEUED,
        index=True
    )

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    batch = relationship("ResearchBatch", back_populates="items")
    application = relationship("Application", back_populates="batch_items")

    def __repr__(self) -> str:
        return f"<ResearchBatchItem id={self.id} batch={self.batch_id} app={self.application_id} status='{self.status.value}'>"
