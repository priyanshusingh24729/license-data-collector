"""SQLAlchemy model for tracking discovery execution runs."""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Enum as SQLEnum,
)
from backend.database.connection import Base
from backend.models.enums import DiscoveryRunStatus


class DiscoveryRun(Base):
    """
    Tracks execution history and metrics for automated source discovery operations.
    """
    __tablename__ = "discovery_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    vendor_name = Column(String(255), nullable=False, index=True)
    product_name = Column(String(255), nullable=True, index=True)
    edition = Column(String(255), nullable=True)
    version = Column(String(255), nullable=True)
    os = Column(String(50), nullable=True)

    status = Column(
        SQLEnum(DiscoveryRunStatus, name="discovery_run_status_enum"),
        nullable=False,
        default=DiscoveryRunStatus.RUNNING,
        index=True
    )

    queries_executed = Column(Integer, nullable=False, default=0)
    sources_found = Column(Integer, nullable=False, default=0)
    sources_accepted = Column(Integer, nullable=False, default=0)
    sources_rejected = Column(Integer, nullable=False, default=0)

    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)
    details = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<DiscoveryRun id={self.id} vendor='{self.vendor_name}' product='{self.product_name}' status='{self.status}'>"
