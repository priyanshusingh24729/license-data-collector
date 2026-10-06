"""
SQLAlchemy model for cross-upload persistent resolved product intelligence cache.
Provides global, upload-independent memory of all resolved applications,
preventing repeat web searches and guaranteeing consistent licensing answers.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    Index,
    UniqueConstraint,
)
from backend.database.connection import Base

ENGINE_VERSION = "v1.2.0"


class ResolvedProductCache(Base):
    """
    Global persistent cache of resolved application software licenses.
    Eliminates redundant SearXNG/YaCy search calls across distinct uploads.
    """
    __tablename__ = "resolved_products_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    normalized_name = Column(String(255), nullable=False, index=True)
    normalized_vendor = Column(String(255), nullable=True, index=True)
    version_bucket = Column(String(50), nullable=True, default="ANY")

    # Canonical identification
    canonical_product = Column(String(255), nullable=False, index=True)
    canonical_vendor = Column(String(255), nullable=False)

    # Licensing decisions
    classification = Column(String(100), nullable=False, index=True)
    availability = Column(String(100), nullable=True)
    license_required = Column(String(100), nullable=False)
    license_model = Column(String(255), nullable=True)
    license_metric = Column(String(100), nullable=True)
    metric = Column(String(100), nullable=True)
    parent_product = Column(String(255), nullable=True)

    # Confidence & reliability metrics
    confidence = Column(String(50), nullable=True)
    reliability_score = Column(Float, nullable=True, default=0.0)
    reliability_str = Column(String(50), nullable=True)

    # Evidence & provenance
    evidence_source = Column(String(50), nullable=False)  # BASELINE, CATALOG, VENDOR_RESOLVER, SEARXNG, YACY, TIER4_REVIEW
    evidence_status = Column(String(50), nullable=False, default="VERIFIED")
    evidence_url = Column(String(1000), nullable=True)
    evidence_quote = Column(Text, nullable=True)
    override_reason = Column(Text, nullable=True)

    # Audit & freshness tracking
    resolution_engine_version = Column(String(50), nullable=False, default=ENGINE_VERSION)
    first_resolved_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_validated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    validation_count = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint("normalized_name", "normalized_vendor", "version_bucket", name="uq_resolved_product_key"),
        Index("ix_resolved_lookup", "normalized_name", "normalized_vendor"),
    )

    def to_dict(self) -> dict:
        return {
            "application": self.canonical_product,
            "vendor": self.canonical_vendor,
            "classification": self.classification,
            "availability": self.availability,
            "license_required": self.license_required,
            "license_model": self.license_model,
            "metric": self.metric or self.license_metric,
            "license_metric": self.license_metric or self.metric,
            "parent_product": self.parent_product,
            "confidence": self.confidence,
            "reliability_score": self.reliability_score,
            "reliability_str": self.reliability_str,
            "evidence_status": self.evidence_status,
            "evidence_source": self.evidence_source,
            "evidence_url": self.evidence_url,
            "source_url": self.evidence_url,
            "primary_source_url": self.evidence_url,
            "evidence_quote": self.evidence_quote,
            "override_reason": self.override_reason,
            "resolution_engine_version": self.resolution_engine_version,
            "last_validated_at": self.last_validated_at.isoformat() if self.last_validated_at else None,
            "is_cached": True,
        }

    def __repr__(self) -> str:
        return f"<ResolvedProductCache id={self.id} app='{self.canonical_product}' vendor='{self.canonical_vendor}' class='{self.classification}'>"
