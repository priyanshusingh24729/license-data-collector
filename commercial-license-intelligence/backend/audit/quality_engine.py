"""
Deterministic Application-Level Quality Scoring & Freshness Evaluation Engine.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.enums import (
    QualityCategory,
    FactType,
    FactStatus,
    AuthorityLevel,
    ExtractionConfidence,
)
from backend.models.application import Application
from backend.models.profile import LicenseProfile
from backend.models.fact import LicenseFact
from backend.models.source import LicenseSource
from backend.models.collection import CollectedDocument
from backend.models.monitoring import SourceMonitor
from backend.audit.audit_result import ApplicationQualityScoreResponse

logger = logging.getLogger(__name__)
DEFAULT_SOURCE_FRESHNESS_DAYS = 90


class ApplicationQualityEngine:
    """
    Evaluates evidence authority, completeness, scope alignment, and freshness into a 0-100 quality score.
    """

    def __init__(self, freshness_days: int = DEFAULT_SOURCE_FRESHNESS_DAYS):
        self.freshness_days = freshness_days

    def evaluate_application_quality(
        self,
        db: Session,
        application_id: int
    ) -> ApplicationQualityScoreResponse:
        """
        Calculates deterministic quality score, category, coverage, and factor explanations.
        """
        now = datetime.now(timezone.utc)
        app_obj = db.query(Application).filter(Application.id == application_id).first()
        if not app_obj:
            raise ValueError(f"Application ID {application_id} not found.")

        v = app_obj.vendor_name.strip()
        p = app_obj.product_name.strip()

        # 1. Fetch Validated Profile
        profile = None
        if app_obj.current_profile_id:
            profile = db.query(LicenseProfile).filter(LicenseProfile.id == app_obj.current_profile_id).first()

        # 2. Fetch all facts for this vendor/product scope
        facts = db.query(LicenseFact).filter(
            func.lower(LicenseFact.vendor_name) == v.lower(),
            func.lower(LicenseFact.product_name) == p.lower()
        ).all()

        validated_facts = [f for f in facts if f.status == FactStatus.VALIDATED]
        conflict_facts = [f for f in facts if f.status == FactStatus.CONFLICT]
        review_facts = [f for f in facts if f.status == FactStatus.REVIEW_REQUIRED]

        score = 0.0
        positives: List[str] = []
        negatives: List[str] = []

        # 3. Critical Field Coverage (40 points max)
        def get_field_status(ft: FactType, val: Optional[str]) -> Tuple[str, bool]:
            if val and val != "UNKNOWN" and val != "CONFLICT":
                return val, True
            # Check if any validated fact exists
            vf = [f for f in validated_facts if f.fact_type == ft and f.normalized_value != "UNKNOWN"]
            if vf:
                return vf[0].normalized_value, True
            return "UNKNOWN", False

        req_val, req_ok = get_field_status(FactType.LICENSE_REQUIRED, profile.license_required if profile else None)
        mod_val, mod_ok = get_field_status(FactType.LICENSE_MODEL, profile.license_model if profile else None)
        met_val, met_ok = get_field_status(FactType.LICENSE_METRIC, profile.license_metric if profile else None)
        cla_val, cla_ok = get_field_status(FactType.LICENSE_CLASSIFICATION, profile.license_classification if profile else None)

        covered_count = sum([req_ok, mod_ok, met_ok, cla_ok])
        coverage_pct = (covered_count / 4.0) * 100.0
        score += covered_count * 10.0  # +10 each

        if req_ok:
            positives.append(f"License Required verified ({req_val})")
        else:
            negatives.append("License Required status is UNKNOWN")

        if mod_ok:
            positives.append(f"License Model verified ({mod_val})")
        else:
            negatives.append("License Model is UNKNOWN")

        if met_ok:
            positives.append(f"License Metric verified ({met_val})")
        else:
            negatives.append("License Metric is UNKNOWN")

        if cla_ok:
            positives.append(f"Classification verified ({cla_val})")
        else:
            negatives.append("License Classification is UNKNOWN")

        # 4. Source Authority Alignment (20 points max)
        sources = db.query(LicenseSource).filter(
            func.lower(LicenseSource.vendor_name) == v.lower()
        ).all()

        has_official_source = any(
            s.authority_level in [
                AuthorityLevel.OFFICIAL_VENDOR,
                AuthorityLevel.OFFICIAL_VENDOR_TERMS,
                AuthorityLevel.OFFICIAL_VENDOR_DOCUMENT,
                AuthorityLevel.OFFICIAL_VENDOR_EULA,
                AuthorityLevel.OFFICIAL_VENDOR_DOCUMENTATION,
            ] for s in sources
        )

        if has_official_source:
            score += 20.0
            positives.append("Supported by primary official vendor documentation")
        elif sources:
            score += 10.0
            positives.append("Supported by secondary or distributor sources")
        else:
            negatives.append("No primary or registered official vendor source found")

        # 5. Direct Evidence Attachment (15 points max)
        has_direct_evidence = any(
            f.evidence_text and len(f.evidence_text.strip()) > 10 for f in validated_facts
        )
        if has_direct_evidence:
            score += 15.0
            positives.append("Evidence anchored directly to collected source documents")
        else:
            negatives.append("Lacks direct verbatim text evidence anchoring")

        # 6. Scope Alignment (15 points max)
        product_matched = any(f.product_name and f.product_name.lower() == p.lower() for f in validated_facts)
        if product_matched:
            score += 15.0
            positives.append(f"Exact product scope verified for '{p}'")
        else:
            negatives.append(f"Facts rely on generic vendor-level scope without exact product '{p}' anchor")

        # 7. Source Freshness (10 points max)
        last_checked = None
        monitors = db.query(SourceMonitor).filter(
            SourceMonitor.source_id.in_([s.id for s in sources])
        ).all()
        if monitors:
            check_dates = [m.last_checked_at for m in monitors if m.last_checked_at]
            if check_dates:
                last_checked = max(check_dates)

        days_since_check = None
        is_stale = False
        if last_checked:
            if last_checked.tzinfo is None:
                last_checked = last_checked.replace(tzinfo=timezone.utc)
            days_since_check = (now - last_checked).days
            if days_since_check <= self.freshness_days:
                score += 10.0
                positives.append(f"Source verified fresh ({days_since_check} days ago)")
            else:
                is_stale = True
                negatives.append(f"Source verification is STALE (last checked {days_since_check} days ago > {self.freshness_days}d threshold)")
        else:
            # Check document created_at dates
            docs = db.query(CollectedDocument).filter(
                func.lower(CollectedDocument.vendor_name) == v.lower()
            ).all()
            if docs:
                doc_dates = [d.created_at for d in docs if d.created_at]
                if doc_dates:
                    last_checked = max(doc_dates)
                    if last_checked.tzinfo is None:
                        last_checked = last_checked.replace(tzinfo=timezone.utc)
                    days_since_check = (now - last_checked).days
                    if days_since_check <= self.freshness_days:
                        score += 10.0
                        positives.append(f"Document collected recently ({days_since_check} days ago)")
                    else:
                        is_stale = True
                        negatives.append(f"Collected document is STALE ({days_since_check} days old)")

        # 8. Penalties for active conflicts or unvalidated items
        if conflict_facts:
            score -= 30.0
            negatives.append(f"Active licensing conflict detected on {len(conflict_facts)} fact(s)")
        if review_facts:
            score -= 15.0
            negatives.append(f"{len(review_facts)} fact(s) currently require human review")

        score = max(0.0, min(100.0, score))

        # 9. Assign Quality Category
        if score >= 90.0:
            category = QualityCategory.EXCELLENT
        elif score >= 75.0:
            category = QualityCategory.GOOD
        elif score >= 50.0:
            category = QualityCategory.FAIR
        elif score >= 25.0:
            category = QualityCategory.POOR
        else:
            category = QualityCategory.INSUFFICIENT

        return ApplicationQualityScoreResponse(
            application_id=app_obj.id,
            vendor_name=app_obj.vendor_name,
            product_name=app_obj.product_name,
            edition=app_obj.edition,
            version=app_obj.version,
            quality_score=score,
            quality_category=category,
            license_required_status=req_val,
            license_model_status=mod_val,
            license_metric_status=met_val,
            license_classification_status=cla_val,
            critical_field_coverage_percent=coverage_pct,
            last_source_checked_at=last_checked,
            days_since_last_check=days_since_check,
            is_source_stale=is_stale,
            positive_factors=positives,
            negative_factors=negatives
        )
