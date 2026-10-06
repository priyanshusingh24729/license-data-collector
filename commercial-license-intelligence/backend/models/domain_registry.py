"""
SQLAlchemy model for Step 18: Official Domain Registry.
Stores authoritative vendor domain definitions, preventing lookalikes and third-party snippet leakage.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    JSON,
    DateTime,
    Index,
)
from backend.database.connection import Base


class OfficialDomainRegistry(Base):
    """
    Registry of verified official root domains and alternate valid domains for software vendors.
    """
    __tablename__ = "official_domain_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vendor = Column(String(255), unique=True, nullable=False, index=True)
    official_domain = Column(String(255), nullable=False)
    alternate_domains = Column(JSON, nullable=False, default=list)
    enabled = Column(Boolean, nullable=False, default=True, index=True)

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

    def __repr__(self) -> str:
        return f"<OfficialDomainRegistry id={self.id} vendor='{self.vendor}' domain='{self.official_domain}'>"
