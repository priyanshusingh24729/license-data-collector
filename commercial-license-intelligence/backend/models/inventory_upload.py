"""
SQLAlchemy models for Bulk CSV/Excel Inventory Uploads and Isolated License Intelligence Results.
Preserves strict data isolation from detected_applications and installation_license_results.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from backend.database.connection import Base


class InventoryUpload(Base):
    """
    Tracks an uploaded inventory file, its parsing/processing job status, and summary metrics.
    """
    __tablename__ = "inventory_uploads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    upload_id = Column(String(100), unique=True, nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False, default="CSV")  # CSV, XLSX, XLS
    file_size_bytes = Column(Integer, nullable=True, default=0)
    total_raw_rows = Column(Integer, nullable=False, default=0)
    total_rows = Column(Integer, nullable=False, default=0)
    unique_applications = Column(Integer, nullable=False, default=0)
    unique_machines = Column(Integer, nullable=False, default=0)

    # Progress & Processing metrics
    processed_rows = Column(Integer, nullable=False, default=0)
    resolved_count = Column(Integer, nullable=False, default=0)
    unresolved_count = Column(Integer, nullable=False, default=0)
    cache_hits = Column(Integer, nullable=False, default=0)
    new_researched = Column(Integer, nullable=False, default=0)

    # Status: QUEUED, PROCESSING, COMPLETED, FAILED
    status = Column(String(50), nullable=False, default="QUEUED", index=True)
    progress_json = Column(Text, nullable=True)
    summary_json = Column(Text, nullable=True)
    column_mapping_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    upload_rows = relationship("InventoryUploadRow", back_populates="upload", cascade="all, delete-orphan")
    license_results = relationship("UploadLicenseResult", back_populates="upload", cascade="all, delete-orphan")
    rows = relationship("InventoryUploadRow", back_populates="upload", overlaps="upload_rows")
    results = relationship("UploadLicenseResult", back_populates="upload", overlaps="license_results")

    @property
    def column_mapping(self) -> Dict[str, Any]:
        if self.column_mapping_json:
            try:
                return json.loads(self.column_mapping_json)
            except Exception:
                return {}
        return {}

    @column_mapping.setter
    def column_mapping(self, val: Optional[Dict[str, Any]]):
        if val is not None:
            self.column_mapping_json = json.dumps(val)
        else:
            self.column_mapping_json = None

    def __repr__(self) -> str:
        return f"<InventoryUpload id={self.id} upload_id='{self.upload_id}' file='{self.file_name}' status='{self.status}'>"


class InventoryUploadRow(Base):
    """
    Preserves raw ingested row data per upload with normalization links and deduplication flags.
    """
    __tablename__ = "inventory_upload_rows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    upload_id = Column(String(100), ForeignKey("inventory_uploads.upload_id", ondelete="CASCADE"), nullable=False, index=True)
    row_index = Column(Integer, nullable=False, default=0)

    # Raw extracted fields
    hostname = Column(String(255), nullable=True, index=True)
    device_id = Column(String(100), nullable=True)
    raw_application = Column(String(500), nullable=False, index=True)
    raw_vendor = Column(String(255), nullable=True)
    raw_version = Column(String(100), nullable=True)
    raw_install_date = Column(String(100), nullable=True)
    raw_install_location = Column(String(500), nullable=True)
    raw_data_json = Column(Text, nullable=True)

    canonical_product = Column(String(255), nullable=True, index=True)
    canonical_vendor = Column(String(255), nullable=True, index=True)

    is_duplicate = Column(Boolean, nullable=False, default=False)
    is_disqualified = Column(Boolean, nullable=False, default=False)
    disqualification_reason = Column(String(255), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    upload = relationship("InventoryUpload", back_populates="upload_rows")

    @property
    def raw_data(self) -> Dict[str, Any]:
        if self.raw_data_json:
            try:
                return json.loads(self.raw_data_json)
            except Exception:
                return {}
        return {}

    @raw_data.setter
    def raw_data(self, val: Optional[Dict[str, Any]]):
        if val is not None:
            self.raw_data_json = json.dumps(val)
        else:
            self.raw_data_json = None

    def __repr__(self) -> str:
        return f"<InventoryUploadRow id={self.id} upload='{self.upload_id}' app='{self.raw_application}'>"


class UploadLicenseResult(Base):
    """
    Stores isolated license intelligence results for an uploaded inventory dataset.
    """
    __tablename__ = "upload_license_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    upload_id = Column(String(100), ForeignKey("inventory_uploads.upload_id", ondelete="CASCADE"), nullable=False, index=True)
    row_id = Column(Integer, ForeignKey("inventory_upload_rows.id", ondelete="SET NULL"), nullable=True)
    row_index = Column(Integer, nullable=False, default=0)

    # Machine Context
    hostname = Column(String(255), nullable=True, index=True)
    device_id = Column(String(100), nullable=True)

    # Application & Canonical Identity
    raw_application = Column(String(500), nullable=False)
    raw_vendor = Column(String(255), nullable=True)
    raw_version = Column(String(100), nullable=True)
    canonical_product = Column(String(255), nullable=True, index=True)
    canonical_vendor = Column(String(255), nullable=True, index=True)
    canonical_edition = Column(String(100), nullable=True)
    version = Column(String(100), nullable=True)

    # License Intelligence
    classification = Column(String(100), nullable=True, index=True)
    availability = Column(String(100), nullable=True)
    license_required = Column(String(100), nullable=True)
    license_model = Column(String(255), nullable=True)
    license_metric = Column(String(100), nullable=True)
    metric = Column(String(100), nullable=True)

    # Evidence & Quality Metrics
    evidence_status = Column(String(50), nullable=True, index=True)
    confidence = Column(String(50), nullable=True)
    reliability_score = Column(Float, nullable=True)
    reliability_str = Column(String(50), nullable=True)

    # WinGet & Installer Metadata
    installer_url = Column(String(1000), nullable=True)
    installer_sha256 = Column(String(100), nullable=True)
    winget_package_id = Column(String(255), nullable=True)

    # Lifecycle Support
    is_end_of_life = Column(Integer, nullable=True)
    is_end_of_support = Column(Integer, nullable=True)

    # Conflict & Consensus Status
    conflict_status = Column(String(100), nullable=True)
    consensus_status = Column(String(100), nullable=True)

    # SPDX & Version-Inflection Intelligence
    spdx_id = Column(String(100), nullable=True)
    version_rule_applied = Column(String(255), nullable=True)

    # Source & Audit Trail
    evidence_source = Column(String(255), nullable=True)
    evidence_url = Column(String(1000), nullable=True)
    evidence_quote = Column(Text, nullable=True)
    override_reason = Column(Text, nullable=True)
    research_status = Column(String(50), nullable=True)
    processing_result = Column(String(50), nullable=False, default="SUCCESS")
    resolution_engine_version = Column(String(50), nullable=False, default="v1.3.0")

    processed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    upload = relationship("InventoryUpload", back_populates="license_results")

    __table_args__ = (
        Index("ix_upload_results_filter", "upload_id", "classification"),
        Index("ix_upload_results_product", "upload_id", "canonical_product"),
    )

    def __repr__(self) -> str:
        return f"<UploadLicenseResult id={self.id} upload='{self.upload_id}' product='{self.canonical_product}' class='{self.classification}'>"
