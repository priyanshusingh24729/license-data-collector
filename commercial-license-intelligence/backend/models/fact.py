"""
SQLAlchemy models for License Facts, Traceable Source Evidence, and Extraction Runs.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    JSON,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import relationship
from backend.database.connection import Base
from backend.models.enums import (
    FactType,
    FactStatus,
    EvidenceType,
    ExtractionConfidence,
    ExtractionRunStatus,
    ScopeType,
    SourceAuthorityTier,
)


class LicenseFact(Base):
    """
    Individual, verifiable licensing fact tied directly to primary source evidence.
    Forms the granular building block of the commercial licensing intelligence database.
    """
    __tablename__ = "license_facts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, nullable=True, index=True)

    # Software Identity & Scope
    vendor_name = Column(String(255), nullable=False, index=True)
    product_name = Column(String(255), nullable=False, index=True)
    edition = Column(String(100), nullable=True, index=True)
    version = Column(String(100), nullable=True, index=True)
    operating_system = Column(String(100), nullable=True)

    # Fact Identity & Values
    fact_type = Column(
        SQLEnum(FactType, name="fact_type_enum"),
        nullable=False,
        index=True
    )
    fact_value = Column(String(255), nullable=False)
    normalized_value = Column(String(255), nullable=False, index=True)

    scope_type = Column(
        SQLEnum(ScopeType, name="fact_scope_type_enum"),
        nullable=False,
        default=ScopeType.PRODUCT,
        index=True
    )
    scope_value = Column(String(255), nullable=False, default="ALL")
    scope_json = Column(JSON, nullable=True)

    # Confidence & Validation Status
    confidence = Column(
        SQLEnum(ExtractionConfidence, name="extraction_confidence_enum"),
        nullable=False,
        default=ExtractionConfidence.UNKNOWN,
        index=True
    )
    confidence_score = Column(Float, nullable=False, default=0.5)
    status = Column(
        SQLEnum(FactStatus, name="fact_status_enum"),
        nullable=False,
        default=FactStatus.EXTRACTED,
        index=True
    )
    validation_status = Column(String(50), nullable=True)

    # Evidence Anchor References
    source_id = Column(Integer, ForeignKey("license_sources.id", ondelete="SET NULL"), nullable=True, index=True)
    document_id = Column(Integer, ForeignKey("collected_documents.id", ondelete="SET NULL"), nullable=True, index=True)
    page_number = Column(Integer, nullable=True)
    section_name = Column(String(255), nullable=True)
    evidence_text = Column(Text, nullable=False)
    evidence_hash = Column(String(64), nullable=False, index=True)
    evidence_type = Column(
        SQLEnum(EvidenceType, name="evidence_type_enum"),
        nullable=False,
        default=EvidenceType.DIRECT_STATEMENT
    )

    # Effective Dates & Timestamps
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    extracted_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    verified_at = Column(DateTime(timezone=True), nullable=True)
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
    evidence_records = relationship("LicenseEvidence", back_populates="license_fact", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_fact_lookup", "vendor_name", "product_name", "fact_type", "status"),
        Index("ix_fact_evidence_hash", "evidence_hash"),
    )

    def __repr__(self) -> str:
        return (
            f"<LicenseFact id={self.id} {self.vendor_name} {self.product_name} "
            f"type='{self.fact_type.value}' val='{self.normalized_value}' "
            f"conf='{self.confidence.value}' status='{self.status.value}'>"
        )


class LicenseEvidence(Base):
    """
    Granular supporting evidence snippets linked to specific licensing facts.
    Maintains exact traceability to source, document ID, page number, and section.
    """
    __tablename__ = "license_evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    license_fact_id = Column(Integer, ForeignKey("license_facts.id", ondelete="CASCADE"), nullable=False, index=True)

    source_id = Column(Integer, ForeignKey("license_sources.id", ondelete="SET NULL"), nullable=True, index=True)
    document_id = Column(Integer, ForeignKey("collected_documents.id", ondelete="SET NULL"), nullable=True, index=True)
    page_number = Column(Integer, nullable=True)
    section = Column(String(255), nullable=True)

    source_url = Column(String(2048), nullable=True)
    source_domain = Column(String(255), nullable=True, index=True)
    source_type = Column(String(100), nullable=True)
    document_title = Column(String(255), nullable=True)

    evidence_text = Column(Text, nullable=False)
    evidence_hash = Column(String(64), nullable=False, index=True)
    evidence_type = Column(
        SQLEnum(EvidenceType, name="evidence_record_type_enum"),
        nullable=False,
        default=EvidenceType.DIRECT_STATEMENT
    )
    authority_level = Column(
        SQLEnum(SourceAuthorityTier, name="source_authority_tier_enum", create_type=False),
        nullable=True
    )

    collected_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    published_at = Column(DateTime(timezone=True), nullable=True)
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    license_fact = relationship("LicenseFact", back_populates="evidence_records")

    def __repr__(self) -> str:
        return f"<LicenseEvidence id={self.id} fact_id={self.license_fact_id} doc={self.document_id} page={self.page_number}>"


class ExtractionRun(Base):
    """
    Execution trace for fact extraction jobs.
    Tracks statistics, runtime, candidate counts, validated facts, and conflicts.
    """
    __tablename__ = "extraction_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_document_id = Column(Integer, ForeignKey("collected_documents.id", ondelete="SET NULL"), nullable=True, index=True)

    vendor_name = Column(String(255), nullable=False, index=True)
    product_name = Column(String(255), nullable=True)
    edition = Column(String(100), nullable=True)
    version = Column(String(100), nullable=True)

    status = Column(
        SQLEnum(ExtractionRunStatus, name="extraction_run_status_enum"),
        nullable=False,
        default=ExtractionRunStatus.RUNNING,
        index=True
    )
    facts_found = Column(Integer, nullable=False, default=0)
    facts_validated = Column(Integer, nullable=False, default=0)
    facts_rejected = Column(Integer, nullable=False, default=0)
    conflicts_found = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)

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

    def __repr__(self) -> str:
        return f"<ExtractionRun id={self.id} vendor='{self.vendor_name}' status='{self.status.value}' found={self.facts_found}>"
