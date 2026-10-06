"""
Safe, read-only scanner for Windows Modern Packages (AppX / MSIX).
Discovers packaged modern applications via Get-AppxPackage and Windows Store Application Model Repository.
"""

import sys
import json
import subprocess
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Known Publisher ID to Human-Readable Vendor Mappings
KNOWN_PUBLISHERS = {
    "50BDFD77-8903-4850-9FFE-6E8522F64D5B": "OpenAI",
    "453637B3-4E12-4CDF-B0D3-2A3C863BF6EF": "Spotify AB",
    "614A9D21-6F29-4C9D-9F7D-FF59321D9E5F": "PDF Technologies",
    "5319275A": "Meta Platforms, Inc.",
}


class WindowsPackageScanner:
    """Read-only discovery of installed Windows AppX / MSIX packages."""

    def __init__(self):
        self.is_windows = sys.platform == "win32"

    def scan_packages(self) -> List[Dict[str, Any]]:
        """
        Runs safe read-only package enumeration.
        Combines Get-AppxPackage with Windows Store AUMID discovery.
        """
        if not self.is_windows:
            return []

        results: List[Dict[str, Any]] = []
        seen_pkg_families = set()

        # 1. Query AppX / MSIX Packages via Get-AppxPackage
        try:
            ps_script = (
                "Get-AppxPackage -ErrorAction SilentlyContinue | "
                "Where-Object { -not $_.IsFramework } | "
                "Select-Object Name, Publisher, Version, Architecture, InstallLocation, PackageFamilyName | "
                "ConvertTo-Json -Compress"
            )

            cmd = [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-Command",
                ps_script
            ]

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=25,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            )

            if proc.returncode == 0 and proc.stdout.strip():
                try:
                    data = json.loads(proc.stdout.strip())
                    if isinstance(data, dict):
                        data = [data]

                    for pkg in data:
                        raw_name = pkg.get("Name")
                        if not raw_name or not str(raw_name).strip():
                            continue

                        raw_name_str = str(raw_name).strip()
                        # Filter out internal Windows platform GUID packages
                        if raw_name_str.startswith("1527c705-") or raw_name_str.startswith("c5e2524a-") or raw_name_str.startswith("E2A4F912-"):
                            continue

                        # Filter out runtime / framework dependency packages
                        try:
                            from backend.inventory.detection.qualification_filter import WindowsRuntimeFrameworkFilter
                            is_rt, _ = WindowsRuntimeFrameworkFilter.is_runtime_or_framework(raw_name_str, raw_name_str, pkg_fam)
                            if is_rt:
                                continue
                        except Exception:
                            pass

                        raw_version = str(pkg.get("Version")).strip() if pkg.get("Version") else None
                        raw_pub = str(pkg.get("Publisher")).strip() if pkg.get("Publisher") else None
                        pkg_fam = str(pkg.get("PackageFamilyName")).strip() if pkg.get("PackageFamilyName") else None

                        if raw_pub and "CN=" in raw_pub:
                            import re
                            cn_match = re.search(r"CN=([^,]+)", raw_pub)
                            if cn_match:
                                raw_pub = cn_match.group(1).strip()

                        if raw_pub in KNOWN_PUBLISHERS:
                            raw_pub = KNOWN_PUBLISHERS[raw_pub]
                        elif "openai" in raw_name_str.lower():
                            raw_pub = "OpenAI"
                        elif "spotify" in raw_name_str.lower():
                            raw_pub = "Spotify AB"
                        elif "pdfx" in raw_name_str.lower() or "ngpdflab" in raw_name_str.lower():
                            raw_pub = "PDF Technologies"
                        elif "whatsapp" in raw_name_str.lower():
                            raw_pub = "Meta Platforms, Inc."

                        raw_loc = str(pkg.get("InstallLocation")).strip() if pkg.get("InstallLocation") else None
                        arch = str(pkg.get("Architecture")).strip() if pkg.get("Architecture") else None

                        if pkg_fam:
                            seen_pkg_families.add(pkg_fam.lower())

                        results.append({
                            "registry_key": f"AppX_{raw_name_str}",
                            "raw_name": raw_name_str,
                            "raw_package_name": raw_name_str,
                            "raw_version": raw_version,
                            "raw_publisher": raw_pub,
                            "raw_install_location": raw_loc,
                            "package_family_name": pkg_fam,
                            "raw_install_date": None,
                            "raw_uninstall_string": None,
                            "detection_method": "WINDOWS_APPX",
                            "architecture": arch or "x64",
                            "is_probable_application": True,
                            "filter_reason": None
                        })
                except json.JSONDecodeError:
                    logger.debug("Could not parse AppX output JSON.")

        except subprocess.TimeoutExpired:
            logger.warning("AppX package query timed out.")
        except Exception as e:
            logger.debug(f"AppX package scanning skipped or unavailable: {e}")

        # 2. Query Windows Application Model Repository via Get-StartApps for packaged Store Apps
        try:
            ps_startapps = (
                "Get-StartApps | Where-Object { $_.AppID -match '!' } | "
                "Select-Object Name, AppID | "
                "ConvertTo-Json -Compress"
            )

            proc2 = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy", "Bypass",
                    "-Command",
                    ps_startapps
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            )

            if proc2.returncode == 0 and proc2.stdout.strip():
                try:
                    data2 = json.loads(proc2.stdout.strip())
                    if isinstance(data2, dict):
                        data2 = [data2]

                    for item in data2:
                        friendly_name = str(item.get("Name") or "").strip()
                        appid = str(item.get("AppID") or "").strip()
                        if not friendly_name or not appid or "!" not in appid:
                            continue

                        pkg_fam = appid.split("!")[0].strip()
                        pkg_base = pkg_fam.split("_")[0] if "_" in pkg_fam else pkg_fam

                        # Filter out runtime / framework dependency packages
                        try:
                            from backend.inventory.detection.qualification_filter import WindowsRuntimeFrameworkFilter
                            is_rt, _ = WindowsRuntimeFrameworkFilter.is_runtime_or_framework(friendly_name, pkg_base, pkg_fam)
                            if is_rt:
                                continue
                        except Exception:
                            pass

                        # Check if this package family was already captured
                        if pkg_fam.lower() in seen_pkg_families:
                            continue

                        # Resolve publisher
                        raw_pub = None
                        if "whatsapp" in friendly_name.lower() or "whatsapp" in pkg_fam.lower():
                            raw_pub = "Meta Platforms, Inc."
                        elif "spotify" in friendly_name.lower() or "spotify" in pkg_fam.lower():
                            raw_pub = "Spotify AB"
                        elif "pdf" in friendly_name.lower() or "ngpdflab" in pkg_fam.lower():
                            raw_pub = "PDF Technologies"
                        elif "chatgpt" in friendly_name.lower() or "codex" in pkg_fam.lower():
                            raw_pub = "OpenAI"

                        seen_pkg_families.add(pkg_fam.lower())

                        results.append({
                            "registry_key": f"AppX_{pkg_base}",
                            "raw_name": friendly_name,
                            "raw_package_name": pkg_base,
                            "raw_version": None,
                            "raw_publisher": raw_pub,
                            "raw_install_location": None,
                            "package_family_name": pkg_fam,
                            "raw_install_date": None,
                            "raw_uninstall_string": None,
                            "detection_method": "WINDOWS_APPX",
                            "architecture": "x64",
                            "is_probable_application": True,
                            "filter_reason": None
                        })
                except json.JSONDecodeError:
                    logger.debug("Could not parse StartApps JSON.")

        except Exception as e:
            logger.debug(f"StartApps modern app discovery failed: {e}")

        return results
