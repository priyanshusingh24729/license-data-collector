"""SQLAlchemy ORM model for the License Source Registry."""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Float,
    DateTime,
    Enum as SQLEnum,
    Index,
    UniqueConstraint,
)
from backend.database.connection import Base
from backend.models.enums import (
    SourceType,
    AuthorityLevel,
    ScopeType,
    CollectionMethod,
    SourceStatus,
    AccessType,
    AuthenticationType,
    SourceOrigin,
    DiscoveryStatus,
)


class LicenseSource(Base):
    """
    Metadata representation of an authoritative licensing source for a software vendor or product.
    Acts as the single source of truth for where licensing intelligence should be collected.
    """
    __tablename__ = "license_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Vendor & Product Identity
    vendor_name = Column(String(255), nullable=False, index=True)
    product_name = Column(String(255), nullable=True, index=True)
    edition = Column(String(100), nullable=True)
    version = Column(String(100), nullable=True)

    # Hierarchy Scope & Identifier
    scope_type = Column(
        SQLEnum(ScopeType, name="scope_type_enum"),
        nullable=False,
        default=ScopeType.VENDOR,
        index=True
    )
    scope_identifier = Column(String(255), nullable=False, index=True)

    # Source Identification & Types
    source_name = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)
    source_type = Column(
        SQLEnum(SourceType, name="source_type_enum"),
        nullable=False,
        default=SourceType.OFFICIAL_WEB
    )
    authority_level = Column(
        SQLEnum(AuthorityLevel, name="authority_level_enum"),
        nullable=False,
        default=AuthorityLevel.OFFICIAL_VENDOR,
        index=True
    )

    # Retrieval URL & Domain Information
    source_url = Column(String(2048), nullable=False)
    normalized_url = Column(String(2048), nullable=False, index=True)
    base_domain = Column(String(255), nullable=True, index=True)
    official_domain = Column(String(255), nullable=True)

    # Collection & Access Protocol
    collection_method = Column(
        SQLEnum(CollectionMethod, name="collection_method_enum"),
        nullable=False,
        default=CollectionMethod.WEB
    )
    access_type = Column(
        SQLEnum(AccessType, name="access_type_enum"),
        nullable=False,
        default=AccessType.PUBLIC
    )
    authentication_type = Column(
        SQLEnum(AuthenticationType, name="authentication_type_enum"),
        nullable=False,
        default=AuthenticationType.NONE
    )
    is_public = Column(Boolean, nullable=False, default=True)

    # API Specific Details (Step 6)
    api_base_url = Column(String(255), nullable=True)
    api_endpoint = Column(String(255), nullable=True)
    api_version = Column(String(50), nullable=True)
    api_documentation_url = Column(String(500), nullable=True)
    http_method = Column(String(10), nullable=False, default="GET")

    # Priority & Lifecycle Status
    priority = Column(Integer, nullable=False, default=100)
    status = Column(
        SQLEnum(SourceStatus, name="source_status_enum"),
        nullable=False,
        default=SourceStatus.ACTIVE
    )
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    source_origin = Column(
        SQLEnum(SourceOrigin, name="source_origin_enum"),
        nullable=False,
        default=SourceOrigin.MANUAL
    )
    discovery_status = Column(
        SQLEnum(DiscoveryStatus, name="discovery_status_enum"),
        nullable=False,
        default=DiscoveryStatus.VERIFIED
    )
    discovery_method = Column(String(50), nullable=True)

    # Relevance & Confidence scoring
    relevance_score = Column(Integer, nullable=False, default=100)
    confidence_score = Column(Float, nullable=False, default=1.0)

    # Timestamps
    discovered_at = Column(DateTime(timezone=True), nullable=True)
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
    last_checked_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_source_lookup", "vendor_name", "product_name", "scope_type", "is_active"),
        Index("ix_source_normalized_url", "normalized_url"),
        UniqueConstraint("normalized_url", "scope_identifier", name="uq_source_normalized_scope"),
    )

    def __repr__(self) -> str:
        return (
            f"<LicenseSource id={self.id} vendor='{self.vendor_name}' "
            f"scope='{self.scope_type.value}:{self.scope_identifier}' "
            f"authority='{self.authority_level.value}' active={self.is_active}>"
        )
