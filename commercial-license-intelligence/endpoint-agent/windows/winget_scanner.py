"""
Safe, read-only Winget Package Scanner.
Queries installed packages via the Windows Package Manager CLI (winget list).
"""

import sys
import shutil
import logging
import subprocess
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class WindowsWingetScanner:
    """Read-only scanner for software installed via or registered with Winget."""

    def __init__(self):
        self.is_windows = sys.platform == "win32"
        self.winget_path = shutil.which("winget")

    def scan_packages(self) -> List[Dict[str, Any]]:
        """
        Executes read-only `winget list --accept-source-agreements` to discover installed software.
        Guarantees no installation, upgrade, or uninstall actions are performed.
        """
        if not self.is_windows or not self.winget_path:
            logger.debug("Winget is not available on this system; skipping Winget scan.")
            return []

        results: List[Dict[str, Any]] = []

        try:
            cmd = [
                self.winget_path,
                "list",
                "--accept-source-agreements",
                "--disable-interactivity"
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

            if proc.returncode != 0 and not proc.stdout.strip():
                logger.debug(f"Winget scan returned non-zero exit code {proc.returncode}")
                return []

            lines = proc.stdout.splitlines()
            if not lines:
                return []

            # Find header line and separator dashes
            header_idx = -1
            for i, line in enumerate(lines):
                if "Name" in line and "Id" in line and "Version" in line:
                    header_idx = i
                    break

            if header_idx == -1 or header_idx + 1 >= len(lines):
                return []

            header_line = lines[header_idx]
            sep_line = lines[header_idx + 1]

            # Calculate column slice offsets based on header and separator line
            # Typical format: Name (0..40), Id (40..80), Version (80..100), Available (100..120), Source (120..)
            id_pos = header_line.find("Id")
            ver_pos = header_line.find("Version")
            avail_pos = header_line.find("Available") if "Available" in header_line else -1
            src_pos = header_line.find("Source") if "Source" in header_line else -1

            data_lines = lines[header_idx + 2:]

            for line in data_lines:
                if not line.strip() or line.startswith("-") or "..." in line[:5]:
                    continue

                try:
                    if id_pos > 0 and ver_pos > id_pos:
                        raw_name = line[:id_pos].strip()
                        raw_id = line[id_pos:ver_pos].strip()
                        
                        if avail_pos > ver_pos:
                            raw_ver = line[ver_pos:avail_pos].strip()
                            if src_pos > avail_pos:
                                raw_source = line[src_pos:].strip()
                            else:
                                raw_source = None
                        elif src_pos > ver_pos:
                            raw_ver = line[ver_pos:src_pos].strip()
                            raw_source = line[src_pos:].strip()
                        else:
                            raw_ver = line[ver_pos:].strip()
                            raw_source = None
                    else:
                        # Fallback splitting by multiple spaces
                        parts = [p.strip() for p in line.split("  ") if p.strip()]
                        if len(parts) >= 2:
                            raw_name = parts[0]
                            raw_id = parts[1]
                            raw_ver = parts[2] if len(parts) >= 3 else None
                            raw_source = parts[3] if len(parts) >= 4 else None
                        else:
                            continue

                    if not raw_name:
                        continue

                    # Filter out progress bar artifacts
                    if any(c in raw_name for c in ["\x1b", "─", "│", "┌", "┐"]):
                        continue

                    results.append({
                        "registry_key": f"Winget_{raw_id or raw_name}",
                        "raw_name": raw_name,
                        "raw_version": raw_ver if raw_ver and raw_ver != "<" else None,
                        "raw_publisher": None,  # Winget typically embeds publisher in Id (e.g. Google.Chrome)
                        "package_identifier": raw_id,
                        "raw_install_location": None,
                        "raw_install_date": None,
                        "raw_uninstall_string": None,
                        "detection_method": "WINDOWS_WINGET",
                        "architecture": "x64",
                        "is_probable_application": True,
                        "filter_reason": None,
                        "source": raw_source or "winget",
                    })
                except Exception as ex:
                    logger.debug(f"Error parsing Winget output line '{line}': {ex}")

        except subprocess.TimeoutExpired:
            logger.warning("Winget package discovery timed out.")
        except Exception as e:
            logger.debug(f"Winget package scanner error: {e}")

        logger.debug(f"Winget scan discovered {len(results)} applications.")
        return results
