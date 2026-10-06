"""
Version Applicability & Temporal Range Validator.
Ensures licensing facts from older or newer versions (e.g. Acrobat 2017 vs 2025)
are not blindly applied across incompatible version boundaries.
"""

import re
from typing import Tuple, Optional
from backend.models.fact import LicenseFact


class VersionValidator:
    """
    Validates version scope compatibility and temporal applicability.
    """

    def validate_version(
        self,
        fact: LicenseFact,
        target_version: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates version alignment.
        Returns: (is_valid, reason_if_invalid)
        """
        if not target_version or not target_version.strip():
            return True, None

        target_clean = target_version.strip().lower()
        fact_ver = (fact.version or "").strip().lower()
        ev_lower = fact.evidence_text.lower()

        # If evidence explicitly establishes universal version scope
        if "all versions" in ev_lower or "all current versions" in ev_lower:
            return True, None

        # Check explicit year / version match
        if fact_ver and fact_ver != target_clean:
            # Check if major version numbers differ significantly (e.g. 2017 vs 2025)
            fact_nums = re.findall(r"\b\d{4}\b", fact_ver)
            target_nums = re.findall(r"\b\d{4}\b", target_clean)
            if fact_nums and target_nums and fact_nums[0] != target_nums[0]:
                return False, f"VERSION_MISMATCH: Evidence applies to version '{fact_ver}', which differs from target '{target_version}'."

        # Check evidence text years
        ev_years = re.findall(r"\b(201\d|202\d)\b", ev_lower)
        target_years = re.findall(r"\b(201\d|202\d)\b", target_clean)
        if ev_years and target_years:
            if target_years[0] not in ev_years and "all versions" not in ev_lower:
                return False, f"VERSION_MISMATCH: Evidence explicitly references release year '{ev_years[0]}' instead of target '{target_years[0]}'."

        return True, None
