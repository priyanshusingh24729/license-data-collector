"""
Configurable policies, thresholds, and weighting rules for Step 17 Research Prioritization.
Enforces daily research budgets, source freshness cutoffs, quality limits, and deterministic scoring.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class ResearchPolicy:
    """Configurable policy constraints and scoring weights for research evaluation."""

    # Freshness & Quality Thresholds
    min_profile_quality: int = int(os.getenv("POLICY_MIN_PROFILE_QUALITY", "75"))
    profile_freshness_days: int = int(os.getenv("POLICY_PROFILE_FRESHNESS_DAYS", "90"))

    # Cost & Execution Budgets
    max_daily_research_applications: int = int(os.getenv("POLICY_MAX_DAILY_RESEARCH", "50"))
    max_batch_research: int = int(os.getenv("POLICY_MAX_BATCH_RESEARCH", "20"))
    max_sources_per_application: int = int(os.getenv("POLICY_MAX_SOURCES_PER_APP", "5"))

    # Priority Rank Cutoffs (Score >= Threshold)
    critical_threshold: int = 75
    high_threshold: int = 45
    medium_threshold: int = 25
    low_threshold: int = 10

    # Deterministic Scoring Weights
    weight_missing_profile: int = 40
    weight_incomplete_profile: int = 25
    weight_critical_fields_unknown: int = 20
    weight_source_stale: int = 15
    weight_source_changed: int = 35
    weight_conflict: int = 30
    weight_low_confidence: int = 20
    weight_commercial_proprietary: int = 15
    weight_high_install_count: int = 10
    weight_version_change: int = 10
    weight_newly_discovered: int = 15

    # Installation Count Cutoff for High Installation Weight
    high_install_count_threshold: int = 5


# Default global policy singleton
DEFAULT_RESEARCH_POLICY = ResearchPolicy()
