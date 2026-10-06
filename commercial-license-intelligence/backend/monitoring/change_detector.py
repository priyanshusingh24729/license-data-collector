"""
Content Normalization, Content Hashing, and Text Difference Engine for Source Monitoring.
"""

import re
import hashlib
import difflib
from typing import Optional


class ChangeDetector:
    """
    Computes robust content hashes and human-readable text diffs for monitored sources.
    """

    @staticmethod
    def normalize_content(text: Optional[str]) -> str:
        """
        Normalizes text content by collapsing whitespace, blank lines, and formatting
        while preserving all meaningful software and licensing statements.
        """
        if not text:
            return ""

        # Normalize line endings
        s = text.replace("\r\n", "\n").replace("\r", "\n")
        # Strip inline whitespace per line and remove completely blank lines
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in s.split("\n")]
        non_empty = [l for l in lines if l]
        return "\n".join(non_empty)

    @classmethod
    def compute_hash(cls, text: Optional[str]) -> str:
        """
        Generates deterministic SHA-256 hash over normalized text content.
        """
        normalized = cls.normalize_content(text)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @classmethod
    def generate_diff(
        cls,
        old_text: Optional[str],
        new_text: Optional[str],
        from_label: str = "previous_version",
        to_label: str = "current_version"
    ) -> str:
        """
        Calculates a clean unified diff between two text versions.
        """
        old_norm = cls.normalize_content(old_text).splitlines(keepends=True)
        new_norm = cls.normalize_content(new_text).splitlines(keepends=True)

        diff_lines = list(difflib.unified_diff(
            old_norm,
            new_norm,
            fromfile=from_label,
            tofile=to_label,
            n=3
        ))
        return "".join(diff_lines)
