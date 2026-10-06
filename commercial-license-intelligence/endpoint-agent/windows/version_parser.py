"""
Version and architecture parser for Windows applications.
Extracts clean version strings and architecture hints without modifying raw inputs.
"""

import re
from typing import Optional, Tuple

_ARCH_PATTERNS = [
    (re.compile(r"\b(64[- ]?bit|x64|amd64|win64)\b", re.IGNORECASE), "x64"),
    (re.compile(r"\b(32[- ]?bit|x86|win32|wow64)\b", re.IGNORECASE), "x86"),
    (re.compile(r"\b(arm64|aarch64)\b", re.IGNORECASE), "ARM64"),
]

_VERSION_CLEAN_RE = re.compile(r"^[vV]?(\d+(\.\d+)*([a-zA-Z0-9_\-\.]+)?)$")


class VersionParser:
    """Utility for extracting version numbers and architecture tags from strings."""

    @staticmethod
    def extract_architecture(name: str, fallback_arch: Optional[str] = None) -> Optional[str]:
        """Detects 64-bit / 32-bit / ARM64 from string, falling back to default."""
        for pattern, arch in _ARCH_PATTERNS:
            if pattern.search(name):
                return arch
        return fallback_arch

    @staticmethod
    def parse_semver_parts(version_str: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Parses major, minor, patch parts safely."""
        if not version_str:
            return None, None, None

        cleaned = version_str.strip().lstrip("vV")
        parts = re.split(r"[._\-]", cleaned)
        major = parts[0] if len(parts) > 0 and parts[0].isdigit() else None
        minor = parts[1] if len(parts) > 1 and parts[1].isdigit() else None
        patch = parts[2] if len(parts) > 2 and parts[2].isdigit() else None
        return major, minor, patch
