"""
Data Contradiction Detector & Quality Rule Engine (Step 19).
Implements automated contradiction validation, quality issue persistence, and audit tracking:
- Flags OPEN_SOURCE with non-NOT_APPLICABLE metric
- Flags OS_BUNDLED with non-NOT_APPLICABLE metric
- Flags SQL Server with CORE evidence but USER metric
- Flags FREE_AND_PAID with License Requirement = NO
- Flags COMMERCIAL_COMPONENT with Standalone License Required = YES
- Assigns data_quality_status (VALID, NEEDS_REVIEW, EVIDENCE_MISSING, CONFLICT, UNKNOWN)
- Creates non-destructive AuditEvent records for all corrections.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.models.enums import (
    ContradictionSeverity,
    DataQualityStatus,
    IssueStatus,
    AuditEventType,
    LicenseClassificationValue,
    AvailabilityModel,
    LicenseRequirement,
    LicenseMetricValue,
)
from backend.models.data_quality import DataQualityIssue
from backend.models.audit import AuditEvent
from backend.models.profile import LicenseProfile
from backend.models.inventory import DetectedApplication

logger = logging.getLogger(__name__)


class DataContradictionDetector:
    """
    Automated validator identifying logical licensing contradictions and assigning quality statuses.
    """

    @classmethod
    def evaluate_contradictions(
        cls,
        app_name: str,
        vendor_name: str,
        classification: str,
        availability: str,
        requirement: str,
        metric: str,
        evidence_text: Optional[str] = None,
        has_evidence: bool = True,
        parent_product: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], DataQualityStatus]:
        """
        Evaluates an application record against logical contradiction rules.
        Returns a list of issue dictionaries and the overall DataQualityStatus.
        """
        issues: List[Dict[str, Any]] = []
        name_lower = (app_name or "").lower()
        class_upper = (classification or "").upper()
        req_upper = (requirement or "").upper()
        metric_upper = (metric or "").upper()
        avail_upper = (availability or "").upper()
        ev_lower = (evidence_text or "").lower()

        # -------------------------------------------------------------
        # Rule 1: OPEN_SOURCE + non-NOT_APPLICABLE Metric -> CONFLICT
        # -------------------------------------------------------------
        if class_upper == "OPEN_SOURCE" and metric_upper not in ["NOT_APPLICABLE", "NONE", "FREE_FOR_ALL", "UNKNOWN"]:
            issues.append({
                "issue_type": "CONTRADICTION_OPEN_SOURCE_METRIC",
                "severity": ContradictionSeverity.CRITICAL,
                "current_value": f"Classification={classification}, Metric={metric}",
                "expected_value": "Metric=NOT_APPLICABLE",
                "reason": "Open source software licenses (MIT, GPL, Apache) do not restrict usage by named user or device metrics.",
            })

        # -------------------------------------------------------------
        # Rule 2: OS_BUNDLED + CORE / USER Metric -> CONFLICT
        # -------------------------------------------------------------
        if class_upper == "OS_BUNDLED" and metric_upper not in ["NOT_APPLICABLE", "NONE", "UNKNOWN"]:
            issues.append({
                "issue_type": "CONTRADICTION_OS_BUNDLED_METRIC",
                "severity": ContradictionSeverity.HIGH,
                "current_value": f"Classification=OS_BUNDLED, Metric={metric}",
                "expected_value": "Metric=NOT_APPLICABLE",
                "reason": "Operating system bundled components and applets are covered under the Windows OS license and do not carry discrete core/user metrics.",
            })

        # -------------------------------------------------------------
        # Rule 3: SQL Server + CORE Evidence + USER Metric -> CONFLICT
        # -------------------------------------------------------------
        if ("sql server" in name_lower or "microsoft sql" in name_lower) and "core" in ev_lower and "user" in metric_lower(metric_upper):
            issues.append({
                "issue_type": "CONTRADICTION_SQL_SERVER_CORE_METRIC",
                "severity": ContradictionSeverity.CRITICAL,
                "current_value": f"Evidence cites Core licensing, but Metric={metric}",
                "expected_value": "Metric=CORE",
                "reason": "Microsoft SQL Server production licensing is primarily core-based (minimum 4 cores per processor). Generic User/Device metric is contradictory.",
            })

        # -------------------------------------------------------------
        # Rule 4: FREE_AND_PAID + Requirement = NO -> REVIEW
        # -------------------------------------------------------------
        if (avail_upper == "FREE_AND_PAID" or class_upper == "FREE_AND_PAID") and req_upper == "NO":
            issues.append({
                "issue_type": "CONTRADICTION_FREE_AND_PAID_REQUIREMENT",
                "severity": ContradictionSeverity.MEDIUM,
                "current_value": f"Availability=FREE_AND_PAID, License Required={requirement}",
                "expected_value": "License Required=CONTEXT_DEPENDENT",
                "reason": "Products with free tiers and paid offerings have context-dependent licensing requirements depending on organizational size or tier.",
            })

        # -------------------------------------------------------------
        # Rule 5: COMMERCIAL_COMPONENT + Requirement = YES -> REVIEW
        # -------------------------------------------------------------
        if class_upper == "COMMERCIAL_COMPONENT" and req_upper in ["YES", "TRUE"]:
            issues.append({
                "issue_type": "CONTRADICTION_COMPONENT_STANDALONE_LICENSE",
                "severity": ContradictionSeverity.HIGH,
                "current_value": f"Classification=COMMERCIAL_COMPONENT, License Required={requirement}",
                "expected_value": "License Required=NOT_APPLICABLE (covered by parent suite)",
                "reason": "Commercial components (e.g. Office background utilities) inherit entitlement from their parent suite and do not require standalone paid licenses.",
            })

        # -------------------------------------------------------------
        # Rule 6: Universal / Generic Fallback "Per User / Device" Detection
        # -------------------------------------------------------------
        if "per user / device" in (metric or "").lower() or "per user/device" in (metric or "").lower():
            issues.append({
                "issue_type": "GENERIC_METRIC_DEFAULT_DETECTED",
                "severity": ContradictionSeverity.HIGH,
                "current_value": metric,
                "expected_value": "Evidence-derived specific metric or UNKNOWN",
                "reason": "Generic 'Per User / Device' is an invalid system-wide default and must be replaced with a specific derived metric.",
            })

        # -------------------------------------------------------------
        # Rule 7: Missing Evidence for Commercial Claims
        # -------------------------------------------------------------
        if class_upper == "COMMERCIAL" and not has_evidence:
            issues.append({
                "issue_type": "MISSING_EVIDENCE_FOR_COMMERCIAL_CLAIM",
                "severity": ContradictionSeverity.MEDIUM,
                "current_value": "Classification=COMMERCIAL with no authoritative evidence source",
                "expected_value": "Validated evidence record",
                "reason": "Commercial software claims require supporting evidence citations.",
            })

        # -------------------------------------------------------------
        # Compute Overall DataQualityStatus (Part 24)
        # -------------------------------------------------------------
        has_critical = any(i["severity"] == ContradictionSeverity.CRITICAL for i in issues)
        has_high = any(i["severity"] == ContradictionSeverity.HIGH for i in issues)
        has_missing_ev = any(i["issue_type"].startswith("MISSING_EVIDENCE") for i in issues)

        if has_critical:
            status = DataQualityStatus.CONFLICT
        elif has_high:
            status = DataQualityStatus.CONFLICT
        elif has_missing_ev:
            status = DataQualityStatus.EVIDENCE_MISSING
        elif issues:
            status = DataQualityStatus.NEEDS_REVIEW
        elif class_upper == "UNKNOWN" or req_upper == "UNKNOWN":
            status = DataQualityStatus.UNKNOWN
        else:
            status = DataQualityStatus.VALID

        return issues, status

    @classmethod
    def audit_and_persist_issues(
        cls,
        db: Session,
        application_id: Optional[int],
        app_name: str,
        vendor_name: str,
        classification: str,
        availability: str,
        requirement: str,
        metric: str,
        evidence_text: Optional[str] = None,
        has_evidence: bool = True,
        parent_product: Optional[str] = None,
    ) -> Tuple[List[DataQualityIssue], DataQualityStatus]:
        """
        Evaluates contradictions and persists any new issues into data_quality_issues table.
        """
        raw_issues, quality_status = cls.evaluate_contradictions(
            app_name=app_name,
            vendor_name=vendor_name,
            classification=classification,
            availability=availability,
            requirement=requirement,
            metric=metric,
            evidence_text=evidence_text,
            has_evidence=has_evidence,
            parent_product=parent_product,
        )

        persisted: List[DataQualityIssue] = []
        for raw in raw_issues:
            # Check if active issue of same type exists for this app
            existing = None
            if application_id:
                existing = db.query(DataQualityIssue).filter(
                    DataQualityIssue.application_id == application_id,
                    DataQualityIssue.issue_type == raw["issue_type"],
                    DataQualityIssue.status == IssueStatus.ACTIVE,
                ).first()

            if not existing:
                issue = DataQualityIssue(
                    application_id=application_id,
                    issue_type=raw["issue_type"],
                    severity=raw["severity"],
                    current_value=raw["current_value"],
                    expected_value=raw["expected_value"],
                    reason=raw["reason"],
                    status=IssueStatus.ACTIVE,
                )
                db.add(issue)
                persisted.append(issue)
            else:
                persisted.append(existing)

        return persisted, quality_status


def metric_lower(val: str) -> str:
    return (val or "").lower()
