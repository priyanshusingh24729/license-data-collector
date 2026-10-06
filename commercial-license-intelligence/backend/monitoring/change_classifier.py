"""
Classification of detected content diffs to determine licensing significance.
"""

import re
from typing import Optional
from backend.models.enums import ChangeClassification

LICENSING_SIGNIFICANT_KEYWORDS = [
    "license",
    "licensing",
    "licensed",
    "subscription",
    "perpetual",
    "term",
    "named user",
    "per user",
    "per device",
    "concurrent",
    "floating",
    "commercial",
    "non-commercial",
    "educational",
    "academic",
    "trial",
    "evaluation",
    "freeware",
    "proprietary",
    "open source",
    "eula",
    "product terms",
    "usage rights",
    "virtualization",
    "secondary install",
    "core",
    "socket",
    "server",
    "maintenance",
]

METADATA_PATTERNS = [
    r"copyright\s+\d{4}",
    r"last\s+(?:updated|modified):\s*",
    r"published\s+on\s*",
    r"version\s+\d+\.\d+\s+build",
    r"all\s+rights\s+reserved",
]


class ChangeClassifier:
    """
    Evaluates text diffs to classify whether a change is potentially licensing-relevant.
    """

    @classmethod
    def classify_diff(
        cls,
        diff_text: Optional[str],
        old_text: Optional[str] = None,
        new_text: Optional[str] = None
    ) -> ChangeClassification:
        """
        Classifies the significance of a text diff.
        """
        if not diff_text or diff_text.strip() == "":
            return ChangeClassification.NO_CHANGE

        # Extract only added (+) or removed (-) lines from unified diff
        diff_lines = [
            line[1:].strip().lower()
            for line in diff_text.splitlines()
            if (line.startswith("+") or line.startswith("-"))
            and not line.startswith("+++")
            and not line.startswith("---")
        ]

        if not diff_lines:
            return ChangeClassification.NO_CHANGE

        changed_corpus = " ".join(diff_lines)

        # 1. Check for licensing-significant terms
        for kw in LICENSING_SIGNIFICANT_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", changed_corpus):
                return ChangeClassification.LICENSING_RELEVANT_CHANGE

        # 2. Check if change is only document metadata / timestamps
        is_metadata_only = True
        for line in diff_lines:
            if not any(re.search(pat, line) for pat in METADATA_PATTERNS):
                is_metadata_only = False
                break

        if is_metadata_only:
            return ChangeClassification.DOCUMENT_METADATA_CHANGE

        return ChangeClassification.CONTENT_CHANGE
