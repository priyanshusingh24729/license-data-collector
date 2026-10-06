"""
SQLAlchemy models for License Intelligence Profiles, Fact Associations, and Historical Version Snapshots.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    Float,
    Boolean,
    String,
    Text,
    DateTime,
    JSON,
    ForeignKey,
    Enum as SQLEnum,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from backend.database.connection import Base
from backend.models.enums import ProfileStatus, ExtractionConfidence


class LicenseProfile(Base):
    """
    Consolidated, application-level license intelligence profile scoped by (vendor, product, edition, version).
    """
    __tablename__ = "license_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Software Identity & Scope
    vendor_name = Column(String(255), nullable=False, index=True)
    product_name = Column(String(255), nullable=False, index=True)
    edition = Column(String(100), nullable=True, index=True)
    version = Column(String(100), nullable=True, index=True)

    # Consolidated Licensing Facts (Step 18 Decoupled Dimensions)
    license_classification = Column(String(100), nullable=False, default="UNKNOWN")
    availability_model = Column(String(100), nullable=False, default="UNKNOWN")
    license_required = Column(String(50), nullable=False, default="UNKNOWN")
    license_model = Column(String(100), nullable=False, default="UNKNOWN")
    license_metric = Column(String(100), nullable=False, default="UNKNOWN")
    license_duration = Column(String(100), nullable=False, default="UNKNOWN")
    commercial_use = Column(String(50), nullable=False, default="UNKNOWN")
    educational_use = Column(String(50), nullable=False, default="UNKNOWN")
    trial_available = Column(String(50), nullable=False, default="UNKNOWN")
    parent_product = Column(String(255), nullable=True)

    # Profile Status & Confidence
    overall_confidence = Column(
        SQLEnum(ExtractionConfidence, name="extraction_confidence_enum", create_type=False),
        nullable=False,
        default=ExtractionConfidence.UNKNOWN,
        index=True
    )
    profile_status = Column(
        SQLEnum(ProfileStatus, name="profile_status_enum"),
        nullable=False,
        default=ProfileStatus.UNKNOWN,
        index=True
    )

    # Quality & Reliability Metrics (Step 18 & 19 Granular Scoring)
    reliability_score = Column(Float, nullable=False, default=50.0)
    identity_quality_score = Column(Float, nullable=False, default=0.0)
    source_authority_score = Column(Float, nullable=False, default=0.0)
    evidence_directness_score = Column(Float, nullable=False, default=0.0)
    scope_quality_score = Column(Float, nullable=False, default=0.0)
    validation_score = Column(Float, nullable=False, default=0.0)
    freshness_score = Column(Float, nullable=False, default=0.0)
    reliability_band = Column(String(50), nullable=False, default="MEDIUM")
    data_quality_status = Column(String(50), nullable=False, default="UNKNOWN")

    reliability_breakdown_json = Column(JSON, nullable=True)
    validated_fact_count = Column(Integer, nullable=False, default=0)
    review_fact_count = Column(Integer, nullable=False, default=0)
    conflict_fact_count = Column(Integer, nullable=False, default=0)
    unknown_fact_count = Column(Integer, nullable=False, default=0)

    # Content Hash & Explanations
    profile_hash = Column(String(64), nullable=False, index=True)
    explanation_json = Column(JSON, nullable=True)

    # Timestamps
    generated_at = Column(
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
    profile_facts = relationship("LicenseProfileFact", back_populates="profile", cascade="all, delete-orphan")
    versions = relationship("ProfileVersion", back_populates="profile", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_profile_lookup", "vendor_name", "product_name", "edition", "version"),
    )

    def __repr__(self) -> str:
        return (
            f"<LicenseProfile id={self.id} {self.vendor_name} {self.product_name} "
            f"ed='{self.edition}' ver='{self.version}' status='{self.profile_status.value}'>"
        )


class LicenseProfileFact(Base):
    """
    Many-to-Many association linking a LicenseProfile to supporting validated LicenseFacts.
    Guarantees 100% provenance back to original evidence.
    """
    __tablename__ = "license_profile_facts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("license_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    license_fact_id = Column(Integer, ForeignKey("license_facts.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    profile = relationship("LicenseProfile", back_populates="profile_facts")
    fact = relationship("LicenseFact")

    def __repr__(self) -> str:
        return f"<LicenseProfileFact profile_id={self.profile_id} fact_id={self.license_fact_id}>"


class ProfileVersion(Base):
    """
    Historical snapshot archive of license profiles whenever facts change and profile_hash updates.
    """
    __tablename__ = "profile_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("license_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_hash = Column(String(64), nullable=False, index=True)
    profile_data = Column(JSON, nullable=False)
    generated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    profile = relationship("LicenseProfile", back_populates="versions")

    def __repr__(self) -> str:
        return f"<ProfileVersion id={self.id} profile_id={self.profile_id} hash='{self.profile_hash[:8]}'>"
