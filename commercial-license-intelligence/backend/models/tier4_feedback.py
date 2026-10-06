"""SQLAlchemy models for Tier 4 Human-in-the-Loop Resolution & Feedback Loop."""

import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean

from backend.database.connection import Base


class PendingCatalogRule(Base):
    """
    Staging table for human-resolved Tier 4 items before promotion to catalog.py.
    """
    __tablename__ = "pending_catalog_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(100), unique=True, nullable=False, index=True)
    signature_id = Column(String(500), nullable=False, index=True)
    matched_pattern = Column(String(500), nullable=False, index=True)
    canonical_name = Column(String(255), nullable=False)
    vendor = Column(String(255), nullable=False)
    license_type = Column(String(100), nullable=False)  # COMMERCIAL | FREEWARE | OPEN_SOURCE | FREE_AND_PAID
    license_required = Column(String(50), nullable=False)  # YES | NO | CONTEXT_DEPENDENT
    metric = Column(String(100), nullable=False, default="NOT_APPLICABLE")  # USER | DEVICE | EMPLOYEE | NOT_APPLICABLE
    tier = Column(Integer, nullable=False, default=2)  # 1, 2, 3
    evidence_url = Column(String(1000), nullable=True)
    evidence_quote = Column(Text, nullable=True)
    resolved_by = Column(String(100), nullable=False, default="auditor")
    resolved_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    confidence = Column(String(50), nullable=False, default="auditor_confirmed")  # auditor_confirmed | auditor_guess
    scope = Column(String(50), nullable=False, default="exact_match")  # exact_match | vendor_wide | pattern_family
    status = Column(String(50), nullable=False, default="pending_review", index=True)  # pending_review | approved | merged | rejected
    occurrence_count = Column(Integer, nullable=False, default=1)
    diff_preview = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    approved_by = Column(String(100), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "signature_id": self.signature_id,
            "matched_pattern": self.matched_pattern,
            "canonical_name": self.canonical_name,
            "vendor": self.vendor,
            "license_type": self.license_type,
            "license_required": self.license_required,
            "metric": self.metric,
            "tier": self.tier,
            "evidence_url": self.evidence_url,
            "evidence_quote": self.evidence_quote,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "confidence": self.confidence,
            "scope": self.scope,
            "status": self.status,
            "occurrence_count": self.occurrence_count,
            "diff_preview": self.diff_preview,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
        }

    def __repr__(self) -> str:
        return f"<PendingCatalogRule id={self.id} rule_id='{self.rule_id}' name='{self.canonical_name}' status='{self.status}'>"


class CatalogAuditLog(Base):
    """
    Audit log for actions taken on the catalog (staged, approved, merged, rejected, inventory updated).
    """
    __tablename__ = "catalog_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(100), nullable=False, index=True)  # rule_staged | rule_approved | rule_merged | rule_rejected | inventory_updated
    rule_id = Column(String(100), nullable=True, index=True)
    rule_json = Column(Text, nullable=True)
    performed_by = Column(String(100), nullable=False)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    source_resolutions_count = Column(Integer, nullable=False, default=0)
    details = Column(Text, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "rule_id": self.rule_id,
            "rule_data": json.loads(self.rule_json) if self.rule_json else {},
            "performed_by": self.performed_by,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "source_resolutions_count": self.source_resolutions_count,
            "details": self.details,
        }

    def __repr__(self) -> str:
        return f"<CatalogAuditLog id={self.id} action='{self.action}' rule='{self.rule_id}'>"
