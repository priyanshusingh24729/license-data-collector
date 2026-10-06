"""
SQLAlchemy models for Endpoint Devices, Detected Applications, Installation Tracking, and Identity Resolution Queue.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import relationship
from backend.database.connection import Base
from backend.models.enums import (
    DeviceStatus,
    DetectedAppStatus,
    DetectionMethod,
    MatchType,
    ResolutionQueueStatus,
    ExtractionConfidence,
)


class Device(Base):
    """
    Managed hardware endpoint reporting application inventory.
    """
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_key = Column(String(100), unique=True, nullable=False, index=True)
    hostname = Column(String(255), nullable=True)
    operating_system = Column(String(100), nullable=True)
    os_version = Column(String(50), nullable=True)
    architecture = Column(String(50), nullable=True)
    agent_version = Column(String(50), nullable=True)

    last_seen_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    status = Column(
        SQLEnum(DeviceStatus, name="device_status_enum"),
        nullable=False,
        default=DeviceStatus.ACTIVE,
        index=True
    )

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

    detected_applications = relationship("DetectedApplication", back_populates="device", cascade="all, delete-orphan")
    device_applications = relationship("DeviceApplication", back_populates="device", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Device id={self.id} key='{self.device_key}' hostname='{self.hostname}'>"


class DetectedApplication(Base):
    """
    Software package detected on an endpoint with raw and normalized properties.
    """
    __tablename__ = "detected_applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)

    # Raw Preserved Data
    raw_name = Column(String(255), nullable=False)
    raw_publisher = Column(String(255), nullable=True)
    raw_version = Column(String(100), nullable=True)
    raw_package_name = Column(String(255), nullable=True)
    raw_publisher_id = Column(String(255), nullable=True)
    raw_display_name = Column(String(255), nullable=True)

    # Normalized Identity Data (Step 18)
    normalized_name = Column(String(255), nullable=False, index=True)
    normalized_publisher = Column(String(255), nullable=True, index=True)
    canonical_product = Column(String(255), nullable=True, index=True)
    detected_version = Column(String(100), nullable=True)
    major_version = Column(String(20), nullable=True)
    minor_version = Column(String(20), nullable=True)
    patch_version = Column(String(20), nullable=True)

    operating_system = Column(String(100), nullable=True)
    install_location = Column(String(500), nullable=True)
    install_source = Column(String(255), nullable=True)
    architecture = Column(String(50), nullable=True)

    detection_method = Column(
        SQLEnum(DetectionMethod, name="detection_method_enum"),
        nullable=False,
        default=DetectionMethod.WINDOWS_REGISTRY
    )

    # Resolved Catalog Link
    resolved_application_id = Column(Integer, ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True)
    resolution_type = Column(
        SQLEnum(MatchType, name="match_type_enum"),
        nullable=False,
        default=MatchType.NO_MATCH,
        index=True
    )
    resolution_confidence = Column(
        SQLEnum(ExtractionConfidence, name="extraction_confidence_enum", create_type=False),
        nullable=False,
        default=ExtractionConfidence.UNKNOWN
    )

    detected_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    first_seen_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    last_seen_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    status = Column(
        SQLEnum(DetectedAppStatus, name="detected_app_status_enum"),
        nullable=False,
        default=DetectedAppStatus.ACTIVE,
        index=True
    )

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

    device = relationship("Device", back_populates="detected_applications")
    resolved_application = relationship("Application")
    queue_items = relationship("ApplicationResolutionQueue", back_populates="detected_application", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<DetectedApplication id={self.id} raw='{self.raw_name}' norm='{self.normalized_name}' res='{self.resolution_type.value}'>"


class DeviceApplication(Base):
    """
    Device-to-Application installation association link.
    """
    __tablename__ = "device_applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    detected_application_id = Column(Integer, ForeignKey("detected_applications.id", ondelete="CASCADE"), nullable=False, index=True)

    first_seen_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    last_seen_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    status = Column(
        SQLEnum(DetectedAppStatus, name="detected_app_status_enum", create_type=False),
        nullable=False,
        default=DetectedAppStatus.ACTIVE
    )

    device = relationship("Device", back_populates="device_applications")
    detected_application = relationship("DetectedApplication")


class ApplicationResolutionQueue(Base):
    """
    Unresolved or ambiguous identity resolution queue for human review.
    """
    __tablename__ = "application_resolution_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    detected_application_id = Column(Integer, ForeignKey("detected_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_application_id = Column(Integer, ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True)

    match_type = Column(
        SQLEnum(MatchType, name="match_type_enum", create_type=False),
        nullable=False
    )
    match_score = Column(Float, nullable=False, default=0.0)
    confidence = Column(
        SQLEnum(ExtractionConfidence, name="extraction_confidence_enum", create_type=False),
        nullable=False,
        default=ExtractionConfidence.UNKNOWN
    )
    reason = Column(Text, nullable=True)

    status = Column(
        SQLEnum(ResolutionQueueStatus, name="resolution_queue_status_enum"),
        nullable=False,
        default=ResolutionQueueStatus.PENDING,
        index=True
    )

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

    detected_application = relationship("DetectedApplication", back_populates="queue_items")
    candidate_application = relationship("Application")

    def __repr__(self) -> str:
        return f"<ApplicationResolutionQueue id={self.id} detected_app={self.detected_application_id} type='{self.match_type.value}' status='{self.status.value}'>"


class InstallationLicenseResult(Base):
    """
    Isolated installation inventory intelligence results table.
    Stores machine-specific software inventory and license intelligence.
    """
    __tablename__ = "installation_license_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    unique_id = Column(String(100), nullable=False, index=True)
    hostname = Column(String(255), nullable=True)
    serial = Column(String(100), nullable=True)
    ip_address = Column(String(100), nullable=True)

    raw_application_name = Column(String(255), nullable=False)
    raw_vendor = Column(String(255), nullable=True)
    raw_version = Column(String(100), nullable=True)
    install_date = Column(String(100), nullable=True)
    install_source = Column(String(255), nullable=True)
    install_location = Column(String(500), nullable=True)

    canonical_product = Column(String(255), nullable=True, index=True)
    canonical_vendor = Column(String(255), nullable=True, index=True)

    classification = Column(String(100), nullable=True)
    license_requirement = Column(String(100), nullable=True)
    license_model = Column(String(100), nullable=True)
    license_metric = Column(String(100), nullable=True)

    evidence_status = Column(String(50), nullable=True)
    confidence = Column(String(50), nullable=True)
    reliability_score = Column(Float, nullable=True)

    evidence_source = Column(String(255), nullable=True)
    evidence_url = Column(String(1000), nullable=True)

    research_status = Column(String(50), nullable=True)
    processed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        return f"<InstallationLicenseResult id={self.id} machine='{self.unique_id}' app='{self.raw_application_name}' product='{self.canonical_product}'>"

