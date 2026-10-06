"""
SQLAlchemy models for License Entitlements, Consumption Tracking, and License Positions.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    Date,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import relationship
from backend.database.connection import Base
from backend.models.enums import (
    EntitlementType,
    EntitlementStatus,
    EntitlementSourceType,
    LicensePositionStatus,
)


class LicenseEntitlement(Base):
    """
    Acquired software license entitlement record.
    """
    __tablename__ = "license_entitlements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)

    vendor_name = Column(String(255), nullable=False)
    product_name = Column(String(255), nullable=False)
    edition = Column(String(100), nullable=True)
    version = Column(String(100), nullable=True)

    entitlement_type = Column(
        SQLEnum(EntitlementType, name="entitlement_type_enum"),
        nullable=False,
        default=EntitlementType.PURCHASED
    )
    quantity = Column(Float, nullable=False, default=0.0)
    metric = Column(String(100), nullable=False)  # e.g. NAMED_USER, DEVICE, INSTALLATION, CORE

    license_start_date = Column(DateTime(timezone=True), nullable=True)
    license_end_date = Column(DateTime(timezone=True), nullable=True)

    agreement_id = Column(String(100), nullable=True)
    contract_reference = Column(String(255), nullable=True)

    source_type = Column(
        SQLEnum(EntitlementSourceType, name="entitlement_source_type_enum"),
        nullable=False,
        default=EntitlementSourceType.MANUAL_ENTRY
    )
    source_reference = Column(String(255), nullable=True)

    status = Column(
        SQLEnum(EntitlementStatus, name="entitlement_status_enum"),
        nullable=False,
        default=EntitlementStatus.ACTIVE,
        index=True
    )

    entitlement_key = Column(String(255), nullable=True, index=True)

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

    application = relationship("Application")

    def __repr__(self) -> str:
        return f"<LicenseEntitlement id={self.id} app={self.application_id} qty={self.quantity} metric='{self.metric}' status='{self.status.value}'>"


class LicenseConsumption(Base):
    """
    Measured license utilization (named user, device, core, or instance assignment).
    """
    __tablename__ = "license_consumption"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
    detected_application_id = Column(Integer, ForeignKey("detected_applications.id", ondelete="SET NULL"), nullable=True)

    consumption_metric = Column(String(100), nullable=False)
    consumption_quantity = Column(Float, nullable=False, default=1.0)

    user_reference = Column(String(100), nullable=True)  # e.g. "USER-001" (pseudonymous)
    device_reference = Column(String(100), nullable=True)

    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)

    source_type = Column(String(100), nullable=False, default="DETECTION_MAPPING")
    source_reference = Column(String(255), nullable=True)

    status = Column(String(50), nullable=False, default="ACTIVE")

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

    application = relationship("Application")
    device = relationship("Device")
    detected_application = relationship("DetectedApplication")

    def __repr__(self) -> str:
        return f"<LicenseConsumption id={self.id} app={self.application_id} metric='{self.consumption_metric}' qty={self.consumption_quantity}>"


class LicensePosition(Base):
    """
    Current calculated license reconciliation position for an application.
    """
    __tablename__ = "license_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    metric = Column(String(100), nullable=True)
    entitled_quantity = Column(Float, nullable=True)
    consumed_quantity = Column(Float, nullable=True)
    available_quantity = Column(Float, nullable=True)
    overdeployment_quantity = Column(Float, nullable=True)

    position_status = Column(
        SQLEnum(LicensePositionStatus, name="license_position_status_enum"),
        nullable=False,
        default=LicensePositionStatus.UNKNOWN_POSITION,
        index=True
    )
    status_reason = Column(Text, nullable=True)

    calculated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    calculation_version = Column(String(20), nullable=False, default="1.0.0")

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

    application = relationship("Application")

    def __repr__(self) -> str:
        return f"<LicensePosition app={self.application_id} entitled={self.entitled_quantity} consumed={self.consumed_quantity} status='{self.position_status.value}'>"


class LicensePositionHistory(Base):
    """
    Immutable audit snapshot of license position calculations over time.
    """
    __tablename__ = "license_position_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)

    metric = Column(String(100), nullable=True)
    entitled_quantity = Column(Float, nullable=True)
    consumed_quantity = Column(Float, nullable=True)
    available_quantity = Column(Float, nullable=True)
    overdeployment_quantity = Column(Float, nullable=True)

    position_status = Column(
        SQLEnum(LicensePositionStatus, name="license_position_status_enum", create_type=False),
        nullable=False
    )
    status_reason = Column(Text, nullable=True)

    calculated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    calculation_version = Column(String(20), nullable=False, default="1.0.0")

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    application = relationship("Application")
