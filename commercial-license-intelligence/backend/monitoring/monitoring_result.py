"""
Pydantic schemas and contracts for Source Monitoring, Change Detection, and Alerts.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from backend.models.enums import (
    MonitorFrequency,
    MonitorStatus,
    MonitoringRunStatus,
    ChangeClassification,
    FactChangeType,
    AlertType,
    AlertSeverity,
    AlertStatus,
    FactType,
    ExtractionConfidence,
)


class SourceMonitorCreateRequest(BaseModel):
    """Payload to register or update a source for scheduled monitoring."""
    source_id: int
    enabled: bool = True
    monitor_frequency: MonitorFrequency = MonitorFrequency.WEEKLY


class SourceMonitorResponse(BaseModel):
    """Response representing a registered source monitor."""
    id: int
    source_id: int
    enabled: bool
    monitor_frequency: MonitorFrequency
    last_checked_at: Optional[datetime] = None
    next_check_at: datetime
    last_status: MonitorStatus
    last_content_hash: Optional[str] = None
    last_change_detected_at: Optional[datetime] = None
    consecutive_failures: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MonitoringRunResponse(BaseModel):
    """Response representing the outcome of a single source check execution."""
    id: int
    source_id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: MonitoringRunStatus
    previous_hash: Optional[str] = None
    current_hash: Optional[str] = None
    change_detected: bool
    change_classification: ChangeClassification
    diff_summary: Optional[str] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class LicenseFactChangeResponse(BaseModel):
    """Detailed audit record of a verified licensing fact change."""
    id: int
    application_id: Optional[int] = None
    old_fact_id: Optional[int] = None
    new_fact_id: Optional[int] = None
    fact_type: FactType
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    change_type: FactChangeType
    detected_at: datetime
    source_id: Optional[int] = None
    document_id: Optional[int] = None
    confidence: ExtractionConfidence

    model_config = ConfigDict(from_attributes=True)


class LicenseAlertResponse(BaseModel):
    """Actionable alert generated when licensing intelligence changes."""
    id: int
    application_id: Optional[int] = None
    source_id: Optional[int] = None
    document_id: Optional[int] = None
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    status: AlertStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MonitoringSummaryBlock(BaseModel):
    """High-level metrics summary for monitoring dashboard."""
    total_monitored: int = 0
    checked_today: int = 0
    changed_sources: int = 0
    unchanged_sources: int = 0
    failed_sources: int = 0
    licensing_alerts_count: int = 0
