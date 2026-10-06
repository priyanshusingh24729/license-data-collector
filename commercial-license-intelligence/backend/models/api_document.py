"""
SQLAlchemy model for persisting raw API responses, structured JSON/XML data, and collection evidence.
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
from backend.models.enums import ApiCollectionStatus


class ApiDocument(Base):
    """
    Evidence record of an API call to an official vendor API endpoint.
    Preserves raw response payloads, parsed structures, and deterministic SHA-256 hashes.
    """
    __tablename__ = "api_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("license_sources.id", ondelete="SET NULL"), nullable=True, index=True)

    vendor_name = Column(String(255), nullable=False, index=True)
    request_url = Column(Text, nullable=False)
    http_method = Column(String(10), nullable=False, default="GET")

    response_status = Column(Integer, nullable=True)
    content_type = Column(String(100), nullable=True)
    response_size = Column(Integer, nullable=True)
    response_hash = Column(String(64), nullable=True, index=True)

    # Payload Storage (Never contains credentials or tokens)
    response_body = Column(Text, nullable=True)
    parsed_json = Column(JSON, nullable=True)

    collection_status = Column(
        SQLEnum(ApiCollectionStatus, name="api_collection_status_enum"),
        nullable=False,
        default=ApiCollectionStatus.COLLECTED,
        index=True
    )
    error_message = Column(Text, nullable=True)

    # Timestamps
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

    __table_args__ = (
        Index("ix_api_doc_vendor_hash", "vendor_name", "response_hash"),
    )

    def __repr__(self) -> str:
        return (
            f"<ApiDocument id={self.id} vendor='{self.vendor_name}' "
            f"status='{self.collection_status.value}' http={self.response_status} "
            f"hash='{self.response_hash[:8] if self.response_hash else None}'>"
        )
