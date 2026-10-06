"""
Microsoft Evidence Validator & Safe Override System (Step 20).
Enforces:
1. Evidence Quality Tiers (Tier 1–5)
2. OS_BUNDLED Evidence Requirements
3. No-Evidence Rule (Reduces reliability score, retains previous baseline or sets UNKNOWN)
4. Safe Override System (Baseline preservation unless strong official evidence justifies override)
5. Strict Confidence Capping (No HIGH/VERY_HIGH on MISSING evidence)
6. Change Audit Logging
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from backend.models.enums import SourceAuthorityTier, EvidenceType, ReliabilityBand
from backend.validation.reliability_score import (
    ReliabilityScoreEngine,
    ReliabilityBreakdown,
    UNRESOLVED_RELIABILITY_SCORE,
)
from backend.inventory.recognition.microsoft_identity_resolver import (
    ResolvedMicrosoftIdentity,
    WindowsProductCategory,
)
from backend.research.windows_product_adapter import WindowsResearchResult

logger = logging.getLogger(__name__)


@dataclass
class ChangeAuditRecord:
    """Audit trail record for application license classification modifications (Part 19)."""
    application_id: Optional[int]
    raw_name: str
    canonical_name: str
    previous_classification: str
    new_classification: str
    previous_license_required: str
    new_license_required: str
    previous_metric: str
    new_metric: str
    reason: str
    evidence_url: str
    evidence_tier: str
    evidence_summary: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MicrosoftEvidenceValidator:
    """
    Validates official Microsoft evidence, computes 6-component reliability scores,
    and applies the Safe Override System with strict confidence validation.
    """

    # In-memory Change Audit Trail (Part 19)
    _CHANGE_AUDIT_LOG: List[ChangeAuditRecord] = []

    @classmethod
    def get_audit_log(cls) -> List[ChangeAuditRecord]:
        """Returns the full history of changed applications."""
        return cls._CHANGE_AUDIT_LOG

    @classmethod
    def clear_audit_log(cls):
        """Clears audit records for fresh test runs."""
        cls._CHANGE_AUDIT_LOG.clear()

    @classmethod
    def validate_and_score(
        cls,
        app_id: Optional[int],
        identity: ResolvedMicrosoftIdentity,
        research_result: WindowsResearchResult,
        prev_classification: str,
        prev_license_required: str,
        prev_metric: str,
        prev_confidence: str = "HIGH",
    ) -> Dict[str, Any]:
        """
        Validates evidence, applies Safe Override System, calculates transparent reliability,
        enforces strict confidence capping (no MISSING + HIGH), and logs audit trail.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        has_official_evidence = (
            research_result.evidence_status in ["VERIFIED", "PARTIAL"] and
            research_result.evidence_tier_name in ["TIER_1", "TIER_2", "TIER_3", "TIER_4"]
        )

        # -------------------------------------------------------------
        # 1. Evaluate Safe Override Conditions (Part 18)
        # -------------------------------------------------------------
        target_class = research_result.classification
        target_req = research_result.license_required
        target_metric = research_result.license_metric
        target_avail = research_result.availability
        target_model = research_result.license_model

        # Check if change is justified
        should_override = False
        override_reason = ""

        # Case A: Explicitly confirmed Commercial Component (e.g. M365Companions, OfficePushNotificationUtility)
        if identity.product_type == WindowsProductCategory.COMMERCIAL_COMPONENT:
            should_override = True
            override_reason = f"Confirmed commercial component covered under parent suite ({research_result.parent_product or 'Microsoft 365'})."

        # Case B: Confirmed Commercial Application (Teams, Power Automate, SQL Server)
        elif identity.product_type == WindowsProductCategory.COMMERCIAL_APPLICATION:
            should_override = True
            override_reason = f"Confirmed commercial software application with verified licensing model: {target_model}."

        # Case C: Confirmed Open Source Application (VS Code, Dev Home, Windows Terminal)
        elif identity.product_type == WindowsProductCategory.OPEN_SOURCE_APPLICATION:
            should_override = True
            override_reason = "Confirmed open-source or free developer tool with permissive licensing."

        # Case D: Confirmed Media Codec / Store App (HEVC, Codecs)
        elif identity.product_type == WindowsProductCategory.MICROSOFT_STORE_APP:
            should_override = True
            override_reason = "Confirmed Microsoft Store application / codec extension."

        # Case E: Confirmed Framework Runtime / System Dependency (WinAppRuntime, VC++)
        elif identity.product_type in [WindowsProductCategory.FRAMEWORK_RUNTIME, WindowsProductCategory.SYSTEM_DEPENDENCY]:
            should_override = True
            override_reason = "Confirmed redistributable system runtime / dependency."

        # Case F: Confirmed OS_BUNDLED, Windows Inbox App, or Optional Feature
        elif (
            identity.product_type in [WindowsProductCategory.WINDOWS_OS_COMPONENT, WindowsProductCategory.WINDOWS_INBOX_APP, WindowsProductCategory.OPTIONAL_WINDOWS_FEATURE]
            or research_result.is_os_bundled_proven
        ):
            should_override = True
            if identity.product_type == WindowsProductCategory.WINDOWS_OS_COMPONENT:
                target_class = "OS_BUNDLED"
                target_req = "NO"
                target_metric = "NOT_APPLICABLE"
                target_avail = "BUNDLED"
                target_model = "Operating System Internal Component"
                override_reason = "Identified as Windows internal operating system component."
            else:
                override_reason = f"Identified as Windows operating system inbox app / feature ({target_model})."

        # Case G: No official product-specific evidence -> Part 7: Keep previous result or UNKNOWN
        else:
            should_override = False
            override_reason = "Insufficient product-specific official evidence to justify override. Retaining baseline classification."

        # -------------------------------------------------------------
        # 2. Final Value Resolution
        # -------------------------------------------------------------
        if should_override:
            final_class = target_class
            final_req = target_req
            final_metric = target_metric
            final_avail = target_avail
            final_model = target_model
            final_ev_status = research_result.evidence_status
            final_ev_quote = research_result.evidence_quote
        else:
            # Fallback handling: DO NOT default to FREEWARE!
            if prev_classification in ("OPEN_SOURCE / FREEWARE", "FREEWARE", "UNKNOWN", None):
                final_class = "UNKNOWN"
                final_req = "UNKNOWN"
                final_metric = "UNKNOWN"
                final_avail = "UNKNOWN"
                final_model = "UNKNOWN"
                final_ev_status = "MISSING"
                final_ev_quote = "No product-specific official licensing terms found."
            else:
                final_class = prev_classification
                final_req = prev_license_required
                final_metric = prev_metric if prev_metric != "NOT_APPLICABLE" else "UNKNOWN"
                final_avail = "UNKNOWN"
                final_model = "UNKNOWN"
                final_ev_status = "PARTIAL" if has_official_evidence else "MISSING"
                final_ev_quote = "Retained baseline classification under No-Evidence Rule."

        # -------------------------------------------------------------
        # 3. Strict Confidence Capping (PROHIBIT MISSING + HIGH/VERY_HIGH)
        # -------------------------------------------------------------
        if final_class == "UNKNOWN" or identity.canonical_name == "UNRESOLVED":
            final_confidence = "UNKNOWN"
        elif final_ev_status == "MISSING":
            final_confidence = "LOW"
        elif identity.product_type == WindowsProductCategory.WINDOWS_OS_COMPONENT:
            final_confidence = "LOW"
        elif prev_confidence in ("HIGH", "VERY_HIGH", "MEDIUM", "LOW"):
            final_confidence = prev_confidence
        else:
            final_confidence = "MEDIUM"

        # -------------------------------------------------------------
        # 4. Transparent Reliability Scoring (Section 20)
        # -------------------------------------------------------------
        from backend.validation.product_scope_matcher import ProductScopeMatcher

        scope_res = ProductScopeMatcher.evaluate_scope(
            canonical_product=identity.canonical_name,
            canonical_vendor=identity.canonical_vendor,
            source_title=research_result.canonical_name,
            source_url=research_result.source_url or "",
            evidence_text=final_ev_quote,
            parent_product=research_result.parent_product,
            product_family=identity.product_family,
        )

        has_ev = bool(has_official_evidence and final_ev_status == "VERIFIED" and identity.canonical_name != "UNRESOLVED")

        # Identity Tier mapping
        if identity.identity_confidence == "HIGH":
            id_tier = "EXACT_VENDOR_CONFIRMED"
        elif identity.identity_confidence == "MEDIUM":
            id_tier = "NORMALIZED_ONLY"
        elif identity.identity_confidence == "LOW":
            id_tier = "PARTIAL_TOKEN"
        else:
            id_tier = "UNRESOLVED"

        # Evidence directness mapping
        if research_result.evidence_tier_name == "TIER_1":
            ev_direct = "DIRECT_STATEMENT"
            src_type = "TERMS"
        elif research_result.is_os_bundled_proven:
            ev_direct = "OS_BUNDLED_CONFIRMED"
            src_type = "DOCS"
        elif identity.product_type == WindowsProductCategory.WINDOWS_OS_COMPONENT:
            ev_direct = "SYSTEM_COMPONENT"
            src_type = "DOCS"
        elif final_ev_status == "PARTIAL":
            ev_direct = "PARTIAL"
            src_type = "SUPPORT"
        else:
            ev_direct = "NONE"
            src_type = "NONE"

        breakdown = ReliabilityScoreEngine.calculate_reliability(
            identity_tier=id_tier,
            source_type=src_type,
            evidence_directness_tier=ev_direct,
            scope_tier=scope_res.match_tier.value,
            classification_valid=bool(final_class and final_class != "UNKNOWN"),
            license_metric_valid=bool(final_metric and final_metric != "UNKNOWN"),
            has_evidence=has_ev,
            is_partial_evidence=(final_ev_status == "PARTIAL"),
            evidence_text_len=len(final_ev_quote),
            has_exact_version=bool(identity.detected_version and identity.detected_version != "N/A"),
            is_conflict=False,
        )

        score = breakdown.overall
        if not has_ev or final_ev_status == "MISSING":
            score = min(score, 42.0 if final_class != "UNKNOWN" else UNRESOLVED_RELIABILITY_SCORE)
        elif final_ev_status == "PARTIAL":
            score = min(score, 75.0)
        elif research_result.evidence_tier_name in ["TIER_2", "TIER_3"]:
            score = min(max(score, 80.0), 94.0)
        elif research_result.evidence_tier_name == "TIER_1":
            score = min(max(score, 95.0), 100.0)

        reliability_str = f"{score:.0f}%"

        # -------------------------------------------------------------
        # 5. Change Audit Recording (Part 19)
        # -------------------------------------------------------------
        is_changed = (
            final_class != prev_classification or
            final_req != prev_license_required or
            final_metric != prev_metric
        )

        if is_changed:
            audit_entry = ChangeAuditRecord(
                application_id=app_id,
                raw_name=identity.raw_name,
                canonical_name=identity.canonical_name,
                previous_classification=prev_classification,
                new_classification=final_class,
                previous_license_required=prev_license_required,
                new_license_required=final_req,
                previous_metric=prev_metric,
                new_metric=final_metric,
                reason=override_reason,
                evidence_url=research_result.source_url,
                evidence_tier=research_result.evidence_tier_name,
                evidence_summary=final_ev_quote,
                timestamp=now_iso,
            )
            cls._CHANGE_AUDIT_LOG.append(audit_entry)

        return {
            "application": identity.raw_name,
            "canonical_name": identity.canonical_name,
            "vendor": identity.canonical_vendor,
            "version": identity.detected_version or "N/A",
            "prev_classification": prev_classification,
            "prev_license_required": prev_license_required,
            "classification": final_class,
            "availability": final_avail,
            "license_required": final_req,
            "license_model": final_model,
            "metric": final_metric,
            "parent_product": research_result.parent_product or identity.parent_product,
            "confidence": final_confidence,
            "reliability_score": score,
            "reliability_str": reliability_str,
            "evidence_status": final_ev_status,
            "evidence_quote": final_ev_quote,
            "source_url": research_result.source_url,
            "evidence_tier": research_result.evidence_tier_name,
            "product_type": identity.product_type.value,
            "product_family": identity.product_family,
            "override_reason": override_reason if should_override else None,
        }
