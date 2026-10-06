"""
Quality Issues Management & Dashboard Aggregation Service.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.enums import (
    QualityCategory,
    QualityIssueType,
    AlertSeverity,
    IssueStatus,
    FactType,
    FactStatus,
)
from backend.models.audit import QualityIssue
from backend.models.application import Application
from backend.models.profile import LicenseProfile
from backend.models.fact import LicenseFact
from backend.models.source import LicenseSource
from backend.audit.quality_engine import ApplicationQualityEngine
from backend.audit.audit_result import (
    QualityIssueResponse,
    QualityDashboardSummaryResponse,
    ApplicationQualityScoreResponse,
)

logger = logging.getLogger(__name__)


class QualityService:
    """
    Manages quality issues lifecycle, automated scans, and aggregate dashboard metrics.
    """

    def __init__(self, quality_engine: Optional[ApplicationQualityEngine] = None):
        self.quality_engine = quality_engine or ApplicationQualityEngine()

    def scan_application_issues(
        self,
        db: Session,
        application_id: int
    ) -> List[QualityIssue]:
        """
        Scans an application for evidence gaps, conflicts, unknown core fields, and stale sources.
        """
        app_obj = db.query(Application).filter(Application.id == application_id).first()
        if not app_obj:
            return []

        eval_res = self.quality_engine.evaluate_application_quality(db, application_id)
        issues: List[QualityIssue] = []
        now = datetime.now(timezone.utc)

        # Helper to avoid creating duplicate active issue
        def add_issue_if_missing(itype: QualityIssueType, sev: AlertSeverity, desc: str):
            existing = db.query(QualityIssue).filter(
                QualityIssue.application_id == application_id,
                QualityIssue.issue_type == itype,
                QualityIssue.status == IssueStatus.ACTIVE
            ).first()
            if not existing:
                iss = QualityIssue(
                    application_id=application_id,
                    issue_type=itype,
                    severity=sev,
                    description=desc,
                    status=IssueStatus.ACTIVE,
                    created_at=now
                )
                db.add(iss)
                issues.append(iss)

        # 1. Check Missing/Stale Sources
        if eval_res.is_source_stale:
            add_issue_if_missing(
                QualityIssueType.STALE_SOURCE,
                AlertSeverity.MEDIUM,
                f"Source documentation not checked for {eval_res.days_since_last_check} days (Threshold: 90 days)."
            )

        # 2. Check Unknown Core Fields
        if eval_res.license_model_status == "UNKNOWN":
            add_issue_if_missing(
                QualityIssueType.UNKNOWN_LICENSE_MODEL,
                AlertSeverity.HIGH,
                f"License Model is UNKNOWN for {app_obj.vendor_name} {app_obj.product_name}."
            )
        if eval_res.license_metric_status == "UNKNOWN":
            add_issue_if_missing(
                QualityIssueType.UNKNOWN_LICENSE_METRIC,
                AlertSeverity.MEDIUM,
                f"License Metric is UNKNOWN for {app_obj.vendor_name} {app_obj.product_name}."
            )

        # 3. Check Conflicts
        facts = db.query(LicenseFact).filter(
            func.lower(LicenseFact.vendor_name) == app_obj.vendor_name.strip().lower(),
            func.lower(LicenseFact.product_name) == app_obj.product_name.strip().lower(),
            LicenseFact.status == FactStatus.CONFLICT
        ).all()
        if facts:
            add_issue_if_missing(
                QualityIssueType.CONFLICT,
                AlertSeverity.HIGH,
                f"Active licensing conflict detected across {len(facts)} fact records."
            )

        db.commit()
        return issues

    def list_quality_issues(
        self,
        db: Session,
        application_id: Optional[int] = None,
        severity: Optional[AlertSeverity] = None,
        issue_type: Optional[QualityIssueType] = None,
        status: Optional[IssueStatus] = IssueStatus.ACTIVE,
    ) -> List[QualityIssueResponse]:
        """Queries quality issues with filtering."""
        q = db.query(QualityIssue)
        if application_id:
            q = q.filter(QualityIssue.application_id == application_id)
        if severity:
            q = q.filter(QualityIssue.severity == severity)
        if issue_type:
            q = q.filter(QualityIssue.issue_type == issue_type)
        if status:
            q = q.filter(QualityIssue.status == status)

        issues = q.order_by(QualityIssue.id.desc()).all()
        apps_dict = {a.id: a for a in db.query(Application).all()}

        res = []
        for it in issues:
            app = apps_dict.get(it.application_id)
            res.append(QualityIssueResponse(
                id=it.id,
                application_id=it.application_id,
                vendor_name=app.vendor_name if app else "UNKNOWN",
                product_name=app.product_name if app else "UNKNOWN",
                entity_type=it.entity_type,
                entity_id=it.entity_id,
                issue_type=it.issue_type,
                severity=it.severity,
                description=it.description,
                status=it.status,
                created_at=it.created_at,
                resolved_at=it.resolved_at
            ))
        return res

    def resolve_issue(
        self,
        db: Session,
        issue_id: int
    ) -> QualityIssueResponse:
        """Marks a quality issue as resolved."""
        iss = db.query(QualityIssue).filter(QualityIssue.id == issue_id).first()
        if not iss:
            raise ValueError(f"QualityIssue ID {issue_id} not found.")

        iss.status = IssueStatus.RESOLVED
        iss.resolved_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(iss)

        app = db.query(Application).filter(Application.id == iss.application_id).first()
        return QualityIssueResponse(
            id=iss.id,
            application_id=iss.application_id,
            vendor_name=app.vendor_name if app else "UNKNOWN",
            product_name=app.product_name if app else "UNKNOWN",
            entity_type=iss.entity_type,
            entity_id=iss.entity_id,
            issue_type=iss.issue_type,
            severity=iss.severity,
            description=iss.description,
            status=iss.status,
            created_at=iss.created_at,
            resolved_at=iss.resolved_at
        )

    def get_quality_dashboard_summary(
        self,
        db: Session
    ) -> QualityDashboardSummaryResponse:
        """Aggregates catalog-wide quality metrics."""
        apps = db.query(Application).all()
        total_apps = len(apps)

        cat_counts = {
            QualityCategory.EXCELLENT: 0,
            QualityCategory.GOOD: 0,
            QualityCategory.FAIR: 0,
            QualityCategory.POOR: 0,
            QualityCategory.INSUFFICIENT: 0,
        }
        scores: List[float] = []

        for a in apps:
            q_res = self.quality_engine.evaluate_application_quality(db, a.id)
            cat_counts[q_res.quality_category] += 1
            scores.append(q_res.quality_score)

        avg_score = sum(scores) / total_apps if total_apps > 0 else 0.0

        crit_issues = db.query(QualityIssue).filter(
            QualityIssue.severity.in_([AlertSeverity.HIGH, AlertSeverity.CRITICAL]),
            QualityIssue.status == IssueStatus.ACTIVE
        ).count()

        stale_count = db.query(QualityIssue).filter(
            QualityIssue.issue_type == QualityIssueType.STALE_SOURCE,
            QualityIssue.status == IssueStatus.ACTIVE
        ).count()

        conflicts_count = db.query(QualityIssue).filter(
            QualityIssue.issue_type == QualityIssueType.CONFLICT,
            QualityIssue.status == IssueStatus.ACTIVE
        ).count()

        return QualityDashboardSummaryResponse(
            total_applications=total_apps,
            excellent_count=cat_counts[QualityCategory.EXCELLENT],
            good_count=cat_counts[QualityCategory.GOOD],
            fair_count=cat_counts[QualityCategory.FAIR],
            poor_count=cat_counts[QualityCategory.POOR],
            insufficient_count=cat_counts[QualityCategory.INSUFFICIENT],
            average_quality_score=avg_score,
            critical_issues_count=crit_issues,
            stale_sources_count=stale_count,
            conflicting_applications_count=conflicts_count
        )
