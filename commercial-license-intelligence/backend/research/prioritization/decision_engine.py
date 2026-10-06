"""
Deterministic Decision Engine for Step 17 Research Prioritization.
Evaluates application identity, profile completeness, source freshness, changes, and conflicts
to output unambiguous categorical decisions.
"""

from typing import List, Tuple
from backend.models.enums import ResearchDecision
from .research_policy import ResearchPolicy
from .research_candidate import ResearchCandidate


class ResearchDecisionEngine:
    """Evaluates candidate attributes to determine the categorical research decision."""

    def __init__(self, policy: ResearchPolicy):
        self.policy = policy

    def evaluate_decision(self, candidate: ResearchCandidate) -> Tuple[ResearchDecision, List[str]]:
        """
        Applies deterministic policy hierarchy to determine research necessity.
        Returns categorical decision and human-readable explanation reasons.
        """
        reasons: List[str] = []

        # -------------------------------------------------------------
        # Rule 1: Unresolved or Ambiguous Identity (STEP 13)
        # -------------------------------------------------------------
        if candidate.is_ambiguous_match:
            reasons.append("Application identity is ambiguous across multiple catalog products. Manual review required.")
            return ResearchDecision.REVIEW_REQUIRED, reasons

        if candidate.is_unresolved:
            reasons.append("Application identity is unresolved (NO_MATCH). Awaiting manual review.")
            return ResearchDecision.REVIEW_REQUIRED, reasons

        # -------------------------------------------------------------
        # Rule 2: Evidence Conflicts (STEP 8 / STEP 15)
        # -------------------------------------------------------------
        if candidate.has_license_conflict or candidate.profile_status == "CONFLICT":
            reasons.append("License profile contains unresolved evidence conflicts across official sources.")
            return ResearchDecision.REVIEW_REQUIRED, reasons

        # -------------------------------------------------------------
        # Rule 3: Missing License Profile
        # -------------------------------------------------------------
        if not candidate.has_profile:
            reasons.append("No validated license profile exists in the application catalog.")
            if candidate.is_newly_discovered:
                reasons.append("Application was newly discovered on endpoint.")
            if candidate.is_commercial_or_proprietary:
                reasons.append("Application is indicated as commercial/proprietary software.")
            return ResearchDecision.RESEARCH_REQUIRED, reasons

        # -------------------------------------------------------------
        # Rule 4: Source Changed (STEP 12 Monitoring Alert)
        # -------------------------------------------------------------
        if candidate.has_source_changed:
            reasons.append(f"Official vendor licensing source changed: {candidate.source_change_details or 'Content change detected'}.")
            return ResearchDecision.REFRESH_REQUIRED, reasons

        # -------------------------------------------------------------
        # Rule 5: Version Mismatch (Detected new major version)
        # -------------------------------------------------------------
        if candidate.has_version_changed:
            reasons.append(f"Detected version ({candidate.version}) differs from validated profile version.")
            return ResearchDecision.REFRESH_REQUIRED, reasons

        # -------------------------------------------------------------
        # Rule 6: Incomplete Critical Licensing Fields
        # -------------------------------------------------------------
        if not candidate.is_profile_complete or candidate.critical_fields_unknown:
            unknown_fields = ", ".join(candidate.critical_fields_unknown) if candidate.critical_fields_unknown else "core licensing terms"
            reasons.append(f"License profile is incomplete (UNKNOWN: {unknown_fields}). Deeper research required.")
            return ResearchDecision.RESEARCH_REQUIRED, reasons

        # -------------------------------------------------------------
        # Rule 7: Low Profile Quality Score (< Threshold)
        # -------------------------------------------------------------
        if candidate.profile_quality_score is not None and candidate.profile_quality_score < self.policy.min_profile_quality:
            reasons.append(f"Profile quality score ({candidate.profile_quality_score:.1f}) is below minimum threshold ({self.policy.min_profile_quality}).")
            return ResearchDecision.RESEARCH_REQUIRED, reasons

        # -------------------------------------------------------------
        # Rule 8: Stale Source (> Freshness Threshold)
        # -------------------------------------------------------------
        if candidate.is_source_stale:
            days = candidate.source_last_checked_days_ago or ">90"
            reasons.append(f"Official documentation has not been verified in {days} days. Periodic refresh required.")
            return ResearchDecision.REFRESH_REQUIRED, reasons

        # -------------------------------------------------------------
        # Rule 9: Validated, High-Quality, Complete, and Fresh
        # -------------------------------------------------------------
        reasons.append("Existing license profile is validated, complete, and verified fresh.")
        if candidate.profile_quality_score is not None:
            reasons.append(f"Quality Score: {candidate.profile_quality_score:.1f}/100.")
        if candidate.source_last_checked_days_ago is not None:
            reasons.append(f"Source verified {candidate.source_last_checked_days_ago} days ago (within {self.policy.profile_freshness_days}-day window).")
        reasons.append("No official vendor documentation changes reported.")

        return ResearchDecision.NO_RESEARCH_REQUIRED, reasons
