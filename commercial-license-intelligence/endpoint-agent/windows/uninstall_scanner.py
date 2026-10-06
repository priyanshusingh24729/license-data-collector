"""
Safe, read-only metadata extractor for Windows Uninstall registry keys.
Guarantees UninstallString and other commands are treated strictly as data and NEVER executed.
"""

import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Heuristics for system components and patches (non-standalone apps)
_SYSTEM_COMPONENT_RE = re.compile(
    r"^(KB\d+|Security Update for|Update for |Hotfix for|Windows (Feature Experience|Subsystem|SDK|Driver)|Microsoft Visual C\+\+ \d{4} (x86|x64) (Minimum|Additional) Runtime)",
    re.IGNORECASE
)


class UninstallEntryParser:
    """Parses raw registry value dictionaries into structured application metadata records."""

    @staticmethod
    def parse_entry(
        key_name: str,
        values: Dict[str, Any],
        detection_method: str,
        architecture: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Parses a registry subkey into a raw application metadata record.
        Returns None if key has no DisplayName or is explicitly marked SystemComponent.
        """
        raw_name = values.get("DisplayName")
        if not raw_name or not str(raw_name).strip():
            # Keys without DisplayName are internal Windows installers/patches
            return None

        raw_name_str = str(raw_name).strip()
        raw_version = str(values.get("DisplayVersion")).strip() if values.get("DisplayVersion") else None
        raw_publisher = str(values.get("Publisher")).strip() if values.get("Publisher") else None
        raw_location = str(values.get("InstallLocation")).strip() if values.get("InstallLocation") else None
        raw_date = str(values.get("InstallDate")).strip() if values.get("InstallDate") else None

        # UninstallString is read as text METADATA ONLY. NEVER EXECUTED.
        raw_uninstall_string = str(values.get("UninstallString")).strip() if values.get("UninstallString") else None

        # SystemComponent flag check
        is_system = bool(values.get("SystemComponent", 0) == 1)
        is_update = bool(values.get("ReleaseType") == "Update" or "ParentKeyName" in values)
        has_kb_name = bool(_SYSTEM_COMPONENT_RE.search(raw_name_str))

        is_probable_app = not (is_system or is_update or has_kb_name)
        filter_reason = None
        if is_system:
            filter_reason = "SYSTEM_COMPONENT_FLAG"
        elif is_update:
            filter_reason = "WINDOWS_UPDATE_PACKAGE"
        elif has_kb_name:
            filter_reason = "WINDOWS_HOTFIX_OR_RUNTIME"

        return {
            "registry_key": key_name,
            "raw_name": raw_name_str,
            "raw_version": raw_version,
            "raw_publisher": raw_publisher,
            "raw_install_location": raw_location,
            "raw_install_date": raw_date,
            "raw_uninstall_string": raw_uninstall_string,
            "detection_method": detection_method,
            "architecture": architecture or ("x64" if "64" in detection_method else "x86"),
            "is_probable_application": is_probable_app,
            "filter_reason": filter_reason
        }
