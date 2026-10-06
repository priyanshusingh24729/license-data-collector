"""
SQLAlchemy models for storing collected web/PDF documents, metadata, and page-level evidence.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    JSON,
    ForeignKey,
    Enum as SQLEnum,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from backend.database.connection import Base
from backend.models.enums import (
    CollectionStatus,
    DocumentClassification,
    DocumentCollectionStatus,
)


class CollectedDocument(Base):
    """
    Persisted record of collected webpage/PDF content, structured sections, and content hash.
    Forms the verifiable evidence baseline for subsequent license fact extraction (Step 7).
    """
    __tablename__ = "collected_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("license_sources.id", ondelete="SET NULL"), nullable=True, index=True)

    vendor_name = Column(String(255), nullable=False, index=True)
    requested_url = Column(Text, nullable=False)
    final_url = Column(Text, nullable=False)

    status = Column(
        SQLEnum(CollectionStatus, name="collection_status_enum"),
        nullable=False,
        default=CollectionStatus.COLLECTED,
        index=True
    )
    document_collection_status = Column(
        SQLEnum(DocumentCollectionStatus, name="document_collection_status_enum"),
        nullable=True,
        default=DocumentCollectionStatus.COLLECTED,
        index=True
    )

    document_classification = Column(
        SQLEnum(DocumentClassification, name="document_classification_enum"),
        nullable=False,
        default=DocumentClassification.UNKNOWN,
        index=True
    )

    http_status = Column(Integer, nullable=True)
    content_type = Column(String(100), nullable=True)
    content_length = Column(Integer, nullable=True)
    content_hash = Column(String(64), nullable=True, index=True)

    # Document & PDF specific metadata
    title = Column(Text, nullable=True)
    document_author = Column(String(255), nullable=True)
    document_subject = Column(String(255), nullable=True)
    page_count = Column(Integer, nullable=True, default=1)
    text_extractable = Column(Boolean, nullable=False, default=True)
    ocr_required = Column(Boolean, nullable=False, default=False)

    clean_text = Column(Text, nullable=True)
    structured_sections = Column(JSON, nullable=True)
    tables_data = Column(JSON, nullable=True)
    redirect_chain = Column(JSON, nullable=True)
    raw_storage_path = Column(Text, nullable=True)

    # Timestamps
    published_at = Column(DateTime(timezone=True), nullable=True)
    modified_at = Column(DateTime(timezone=True), nullable=True)
    retrieved_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_collected_vendor_hash", "vendor_name", "content_hash"),
    )

    def __repr__(self) -> str:
        return f"<CollectedDocument id={self.id} vendor='{self.vendor_name}' type='{self.document_classification}' status='{self.status}' hash='{self.content_hash[:8] if self.content_hash else None}'>"


class DocumentPage(Base):
    """
    Page-level text storage for multi-page documents (PDFs).
    Enables exact location citations (document_id + page_number) in Step 8.
    """
    __tablename__ = "document_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("collected_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False, index=True)
    text = Column(Text, nullable=False)
    character_count = Column(Integer, nullable=False, default=0)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    document = relationship("CollectedDocument", back_populates="pages")

    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_document_page_number"),
    )

    def __repr__(self) -> str:
        return f"<DocumentPage doc_id={self.document_id} page={self.page_number} chars={self.character_count}>"
