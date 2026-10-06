"""
Safe, read-only Windows Start Menu Shortcut Scanner.
Used strictly for IDENTITY ENRICHMENT (resolving executable paths and friendly names).
Start Menu shortcuts DO NOT generate standalone application inventory records.
"""

import os
import sys
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Known helper/utility shortcut keywords to skip
_HELPER_KEYWORDS = [
    "uninstall", "documentation", "help", "readme", "release notes", "website",
    "manual", "license", "support", "online help", "configure", "modify"
]


class WindowsStartMenuScanner:
    """Read-only discovery of application shortcuts for metadata enrichment."""

    def __init__(self):
        self.is_windows = sys.platform == "win32"
        self.target_dirs = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        ]

    def get_enrichment_map(self) -> Dict[str, Dict[str, Any]]:
        """
        Scans Start Menu folders and returns a lookup dictionary keyed by normalized shortcut name.
        Used strictly to enrich genuine candidates with shortcut paths and metadata.
        """
        if not self.is_windows:
            return {}

        enrichment_map: Dict[str, Dict[str, Any]] = {}

        for base_dir in self.target_dirs:
            if not os.path.exists(base_dir):
                continue

            try:
                for root, _, files in os.walk(base_dir):
                    for f in files:
                        if not f.lower().endswith(".lnk"):
                            continue

                        shortcut_name = f[:-4].strip()
                        s_low = shortcut_name.lower()

                        if any(kw in s_low for kw in _HELPER_KEYWORDS):
                            continue

                        if s_low in enrichment_map:
                            continue

                        full_path = os.path.join(root, f)
                        enrichment_map[s_low] = {
                            "shortcut_name": shortcut_name,
                            "shortcut_path": full_path,
                            "folder": root,
                        }

            except Exception as e:
                logger.debug(f"Error scanning Start Menu directory '{base_dir}': {e}")

        return enrichment_map

    def scan_shortcuts(self) -> List[Dict[str, Any]]:
        """
        Returns empty list for standalone application inventory generation.
        Start Menu shortcuts are strictly secondary enrichment sources.
        """
        return []
