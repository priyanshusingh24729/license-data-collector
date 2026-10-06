"""
Edition Boundary Validator.
Ensures licensing facts for one edition (e.g. Acrobat Reader or Standard)
are not erroneously applied to another edition (e.g. Acrobat Pro).
"""

from typing import Tuple, Optional
from backend.models.fact import LicenseFact


class EditionValidator:
    """
    Validates that edition scopes align between target and evidence.
    """

    def validate_edition(
        self,
        fact: LicenseFact,
        target_edition: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates edition alignment.
        Returns: (is_valid, reason_if_invalid)
        """
        if not target_edition or not target_edition.strip():
            return True, None

        target_clean = target_edition.strip().lower()
        fact_ed = (fact.edition or "").strip().lower()
        ev_lower = fact.evidence_text.lower()

        # If fact has an explicit edition that differs
        if fact_ed and fact_ed != target_clean and fact_ed not in target_clean:
            return False, f"EDITION_MISMATCH: Fact edition '{fact.edition}' does not match target edition '{target_edition}'."

        # Check explicit sibling edition evidence
        if target_clean == "pro":
            if "acrobat reader" in ev_lower or "acrobat standard" in ev_lower:
                if "pro" not in ev_lower:
                    return False, f"EDITION_MISMATCH: Evidence strictly references Standard/Reader, not '{target_edition}'."

        return True, None
