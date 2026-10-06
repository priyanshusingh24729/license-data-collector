"""
Safe, read-only Windows Registry Scanner.
Iterates machine and user uninstall subkeys using standard Python winreg.
"""

import sys
import logging
from typing import Tuple, List, Dict, Any, Optional
try:
    from .uninstall_scanner import UninstallEntryParser
except (ImportError, ValueError):
    from uninstall_scanner import UninstallEntryParser

try:
    import winreg
except ImportError:
    winreg = None

logger = logging.getLogger(__name__)

# Registry roots to scan
REGISTRY_TARGETS = [
    # (Hive label, Hive const name, Subkey path, WOW flag name, Detection Method, Arch)
    ("HKLM_64", "HKEY_LOCAL_MACHINE", r"Software\Microsoft\Windows\CurrentVersion\Uninstall", "KEY_WOW64_64KEY", "WINDOWS_REGISTRY_64", "x64"),
    ("HKLM_32", "HKEY_LOCAL_MACHINE", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", "KEY_WOW64_32KEY", "WINDOWS_REGISTRY_32", "x86"),
    ("HKCU", "HKEY_CURRENT_USER", r"Software\Microsoft\Windows\CurrentVersion\Uninstall", None, "WINDOWS_USER_REGISTRY", None),
]


class WindowsRegistryScanner:
    """Read-only scanner for Windows uninstall registry hives."""

    def __init__(self):
        self.is_windows = sys.platform == "win32" and winreg is not None

    def scan_all_hives(self) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        Executes read-only scan across 64-bit, 32-bit machine and current user registry locations.
        Returns list of parsed application entries and source counters.
        """
        if not self.is_windows or not winreg:
            logger.info("Non-Windows platform or winreg unavailable; registry scanning skipped.")
            return [], {}

        results: List[Dict[str, Any]] = []
        counts: Dict[str, int] = {
            "registry_machine_64": 0,
            "registry_machine_32": 0,
            "registry_user": 0,
        }

        hive_map = {
            "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
            "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
        }

        for target_label, hive_name, subkey_path, wow_flag_name, det_method, arch in REGISTRY_TARGETS:
            hive = hive_map.get(hive_name)
            if not hive:
                continue

            access_flags = winreg.KEY_READ
            if wow_flag_name and hasattr(winreg, wow_flag_name):
                access_flags |= getattr(winreg, wow_flag_name)

            try:
                with winreg.OpenKey(hive, subkey_path, 0, access_flags) as parent_key:
                    num_subkeys, _, _ = winreg.QueryInfoKey(parent_key)
                    logger.debug(f"Scanning {target_label} ({num_subkeys} subkeys)...")

                    for i in range(num_subkeys):
                        try:
                            subkey_name = winreg.EnumKey(parent_key, i)
                            with winreg.OpenKey(parent_key, subkey_name, 0, winreg.KEY_READ) as subkey:
                                num_values = winreg.QueryInfoKey(subkey)[1]
                                values_dict: Dict[str, Any] = {}
                                for j in range(num_values):
                                    try:
                                        val_name, val_data, _ = winreg.EnumValue(subkey, j)
                                        values_dict[val_name] = val_data
                                    except Exception:
                                        continue

                                parsed = UninstallEntryParser.parse_entry(
                                    key_name=subkey_name,
                                    values=values_dict,
                                    detection_method=det_method,
                                    architecture=arch
                                )
                                if parsed:
                                    results.append(parsed)
                                    if target_label == "HKLM_64":
                                        counts["registry_machine_64"] += 1
                                    elif target_label == "HKLM_32":
                                        counts["registry_machine_32"] += 1
                                    elif target_label == "HKCU":
                                        counts["registry_user"] += 1

                        except Exception as e:
                            logger.debug(f"Error reading subkey {i} in {target_label}: {e}")

            except FileNotFoundError:
                logger.debug(f"Registry path not found: {hive_name}\\{subkey_path}")
            except PermissionError:
                logger.warning(f"Permission denied reading registry root: {hive_name}\\{subkey_path}")
            except Exception as ex:
                logger.warning(f"Failed scanning {target_label}: {ex}")

        return results, counts
