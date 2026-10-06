"""
Deterministic Priority Scoring Engine for Step 17 Research Prioritization.
Calculates integer priority scores and ranks candidates without black-box or non-deterministic mechanisms.
"""

from typing import Tuple, List
from backend.models.enums import ResearchPriority, ResearchDecision
from .research_policy import ResearchPolicy
from .research_candidate import ResearchCandidate
from .decision_result import DecisionFactor


class PriorityScoreEngine:
    """Calculates deterministic score and priority rank based on configurable policy weights."""

    def __init__(self, policy: ResearchPolicy):
        self.policy = policy

    def calculate_score(
        self,
        candidate: ResearchCandidate,
        decision: ResearchDecision
    ) -> Tuple[int, ResearchPriority, List[DecisionFactor]]:
        """
        Computes deterministic integer score, priority rank, and detailed factor breakdown.
        """
        # NO_RESEARCH_REQUIRED immediately gets priority NONE and score 0 (or minimal score)
        if decision == ResearchDecision.NO_RESEARCH_REQUIRED:
            factor = DecisionFactor(
                factor_name="VALIDATED_AND_FRESH",
                description="Profile is validated, complete, fresh, and meets quality standards.",
                score_delta=0,
                category="PROFILE"
            )
            return 0, ResearchPriority.NONE, [factor]

        # REVIEW_REQUIRED for unresolved or ambiguous identity gets baseline triage priority
        if decision == ResearchDecision.REVIEW_REQUIRED and (candidate.is_unresolved or candidate.is_ambiguous_match):
            factors = [
                DecisionFactor(
                    factor_name="IDENTITY_REVIEW_REQUIRED",
                    description=f"Identity resolution state: {candidate.resolution_status or 'UNRESOLVED'}. Awaiting human review before research.",
                    score_delta=15,
                    category="IDENTITY"
                )
            ]
            return 15, ResearchPriority.LOW, factors

        score = 0
        factors: List[DecisionFactor] = []

        # 1. No License Profile (+40)
        if not candidate.has_profile:
            score += self.policy.weight_missing_profile
            factors.append(DecisionFactor(
                factor_name="MISSING_LICENSE_PROFILE",
                description="No validated license profile exists in the application catalog.",
                score_delta=self.policy.weight_missing_profile,
                category="PROFILE"
            ))

        # 2. Incomplete Profile (+25)
        elif not candidate.is_profile_complete:
            score += self.policy.weight_incomplete_profile
            factors.append(DecisionFactor(
                factor_name="INCOMPLETE_LICENSE_PROFILE",
                description="Existing profile lacks full validation across core licensing dimensions.",
                score_delta=self.policy.weight_incomplete_profile,
                category="PROFILE"
            ))

        # 3. Critical Fields Unknown (+20)
        if candidate.critical_fields_unknown:
            score += self.policy.weight_critical_fields_unknown
            unknown_str = ", ".join(candidate.critical_fields_unknown)
            factors.append(DecisionFactor(
                factor_name="CRITICAL_FIELDS_UNKNOWN",
                description=f"Core licensing fields are UNKNOWN ({unknown_str}).",
                score_delta=self.policy.weight_critical_fields_unknown,
                category="LICENSING"
            ))

        # 4. Source Stale (+15)
        if candidate.is_source_stale:
            score += self.policy.weight_source_stale
            days_str = f"{candidate.source_last_checked_days_ago} days ago" if candidate.source_last_checked_days_ago else ">90 days ago"
            factors.append(DecisionFactor(
                factor_name="SOURCE_STALE",
                description=f"Official licensing documentation has not been checked in {days_str}.",
                score_delta=self.policy.weight_source_stale,
                category="FRESHNESS"
            ))

        # 5. Source Changed (+25)
        if candidate.has_source_changed:
            score += self.policy.weight_source_changed
            details = candidate.source_change_details or "Licensing documentation content changed"
            factors.append(DecisionFactor(
                factor_name="SOURCE_CHANGED",
                description=f"Monitoring detected vendor licensing change: {details}.",
                score_delta=self.policy.weight_source_changed,
                category="MONITORING"
            ))

        # 6. License Conflict (+30)
        if candidate.has_license_conflict:
            score += self.policy.weight_conflict
            factors.append(DecisionFactor(
                factor_name="LICENSE_CONFLICT",
                description="Contradictory licensing evidence detected across vendor sources.",
                score_delta=self.policy.weight_conflict,
                category="QUALITY"
            ))

        # 7. Low Quality / Low Confidence (+20)
        if candidate.profile_quality_score is not None and candidate.profile_quality_score < self.policy.min_profile_quality:
            score += self.policy.weight_low_confidence
            factors.append(DecisionFactor(
                factor_name="LOW_QUALITY_SCORE",
                description=f"Profile quality score ({candidate.profile_quality_score:.1f}) is below target threshold ({self.policy.min_profile_quality}).",
                score_delta=self.policy.weight_low_confidence,
                category="QUALITY"
            ))

        # 8. Commercial / Proprietary Indication (+15)
        if candidate.is_commercial_or_proprietary:
            score += self.policy.weight_commercial_proprietary
            factors.append(DecisionFactor(
                factor_name="COMMERCIAL_PROPRIETARY",
                description="Application is designated as commercial/proprietary software.",
                score_delta=self.policy.weight_commercial_proprietary,
                category="CLASSIFICATION"
            ))

        # 9. High Installation Count (+10)
        if candidate.installation_count >= self.policy.high_install_count_threshold:
            score += self.policy.weight_high_install_count
            factors.append(DecisionFactor(
                factor_name="HIGH_INSTALL_COUNT",
                description=f"Installed on {candidate.installation_count} endpoint devices (>= {self.policy.high_install_count_threshold}).",
                score_delta=self.policy.weight_high_install_count,
                category="ENDPOINT"
            ))

        # 10. Recent Version Change (+10)
        if candidate.has_version_changed:
            score += self.policy.weight_version_change
            factors.append(DecisionFactor(
                factor_name="VERSION_CHANGED",
                description=f"New version ({candidate.version}) detected on endpoint differing from validated profile.",
                score_delta=self.policy.weight_version_change,
                category="ENDPOINT"
            ))

        # 11. Newly Discovered Application (+15)
        if candidate.is_newly_discovered:
            score += self.policy.weight_newly_discovered
            factors.append(DecisionFactor(
                factor_name="NEWLY_DISCOVERED",
                description="Application was newly discovered from endpoint inventory without prior research history.",
                score_delta=self.policy.weight_newly_discovered,
                category="DISCOVERY"
            ))

        # 12. Freeware / Open Source Mitigation
        if candidate.is_freeware_or_open_source and candidate.is_profile_complete and not candidate.has_source_changed:
            # If freeware is already complete and unchanged, reduce score
            reduction = min(30, score)
            score -= reduction
            factors.append(DecisionFactor(
                factor_name="FREE_OPEN_SOURCE_MITIGATION",
                description="Application is verified freeware/open source with complete licensing profile.",
                score_delta=-reduction,
                category="CLASSIFICATION"
            ))

        # Determine Priority Rank from Cutoffs
        if score >= self.policy.critical_threshold:
            priority = ResearchPriority.CRITICAL
        elif score >= self.policy.high_threshold:
            priority = ResearchPriority.HIGH
        elif score >= self.policy.medium_threshold:
            priority = ResearchPriority.MEDIUM
        elif score >= self.policy.low_threshold:
            priority = ResearchPriority.LOW
        else:
            priority = ResearchPriority.NONE

        return score, priority, factors
