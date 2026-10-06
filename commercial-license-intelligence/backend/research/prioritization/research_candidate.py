"""
Data models representing an evaluation candidate for license research prioritization.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class ResearchCandidate:
    """Consolidated state snapshot of an application evaluated for research priority."""

    # Identifiers
    application_id: Optional[int] = None
    detected_application_id: Optional[int] = None
    display_name: str = ""
    publisher: Optional[str] = None
    version: Optional[str] = None

    # Identity Resolution State (STEP 13)
    has_identity_match: bool = True
    is_ambiguous_match: bool = False
    is_unresolved: bool = False
    resolution_status: Optional[str] = None

    # License Profile State (STEP 9 & STEP 15)
    has_profile: bool = False
    profile_id: Optional[int] = None
    profile_status: Optional[str] = None
    profile_quality_score: Optional[float] = None
    is_profile_complete: bool = False
    critical_fields_unknown: List[str] = field(default_factory=list)

    # Source Freshness & Monitoring State (STEP 12)
    is_source_stale: bool = False
    source_last_checked_days_ago: Optional[int] = None
    has_source_changed: bool = False
    source_change_details: Optional[str] = None

    # Licensing Invariants & Attributes
    has_license_conflict: bool = False
    is_commercial_or_proprietary: bool = False
    is_freeware_or_open_source: bool = False
    is_trial: bool = False

    # Endpoint & Installation Dynamics (STEP 16)
    has_version_changed: bool = False
    is_newly_discovered: bool = False
    installation_count: int = 1
    device_names: List[str] = field(default_factory=list)
