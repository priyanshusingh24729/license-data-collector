"""
Inventory Builder and Deduplication Engine for Windows Endpoint Agent.
Gathers stable device metadata, normalizes records, applies deduplication, and creates ingestion payloads.
"""

import os
import uuid
import socket
import platform
import logging
from typing import Dict, Any, List, Optional, Tuple
try:
    from .config import AgentConfig
    from .publisher_normalizer import PublisherNormalizer
    from .version_parser import VersionParser
except (ImportError, ValueError):
    from config import AgentConfig
    from publisher_normalizer import PublisherNormalizer
    from version_parser import VersionParser

logger = logging.getLogger(__name__)


class InventoryBuilder:
    """Constructs device metadata and deduplicated application inventory payloads."""

    def __init__(self, config: AgentConfig):
        self.config = config

    def get_or_create_device_key(self) -> str:
        """Retrieves or persists a stable local device identifier."""
        key_path = os.path.abspath(self.config.device_key_file)
        if os.path.exists(key_path):
            try:
                with open(key_path, "r", encoding="utf-8") as f:
                    stored = f.read().strip()
                    if stored:
                        return stored
            except Exception as e:
                logger.debug(f"Could not read device key file: {e}")

        # Generate a stable UUID based on hostname + node
        new_key = f"WIN-{uuid.uuid5(uuid.NAMESPACE_DNS, socket.gethostname() + str(uuid.getnode())).hex[:16].upper()}"
        try:
            with open(key_path, "w", encoding="utf-8") as f:
                f.write(new_key)
        except Exception as e:
            logger.debug(f"Could not save device key file: {e}")

        return new_key

    def gather_device_metadata(self) -> Dict[str, Any]:
        """Gathers local machine hardware and OS metadata safely."""
        dev_key = self.get_or_create_device_key()
        host = socket.gethostname()
        os_sys = platform.system() or "Windows"
        os_rel = platform.release()
        os_ver = f"{os_rel} ({platform.version()})"
        raw_arch = platform.machine()
        arch = "x64" if "64" in raw_arch else ("ARM64" if "arm" in raw_arch.lower() else "x86")

        return {
            "device_key": dev_key,
            "hostname": host,
            "operating_system": os_sys,
            "os_version": os_ver,
            "architecture": arch,
            "agent_version": self.config.agent_version
        }

    def deduplicate_applications(self, raw_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicates application records across Registry, AppX, Winget, and Start Menu.
        Follows identity key priority:
        1. Package Family Name / Full Name (AppX)
        2. Registry Key / Uninstall Identifier
        3. Winget Package ID
        4. Normalized Clean Name + Version + Publisher
        Merges missing metadata (publisher, version, location) across sources.
        """
        output: List[Dict[str, Any]] = []
        app_by_pkg_family: Dict[str, Dict[str, Any]] = {}
        app_by_reg_key: Dict[str, Dict[str, Any]] = {}
        app_by_winget_id: Dict[str, Dict[str, Any]] = {}
        app_by_canonical: Dict[Tuple[str, str], Dict[str, Any]] = {}
        app_by_name_ver: Dict[Tuple[str, str], Dict[str, Any]] = {}

        for entry in raw_entries:
            if not entry.get("is_probable_application", True):
                continue

            raw_name = (entry.get("raw_name") or "").strip()
            if not raw_name:
                continue

            pkg_family = (entry.get("package_family_name") or "").strip().lower()
            reg_key = (entry.get("registry_key") or "").strip().lower()
            winget_id = (entry.get("package_identifier") or "").strip().lower()

            # Filter out runtime / framework dependency packages
            try:
                from backend.inventory.detection.qualification_filter import WindowsRuntimeFrameworkFilter
                is_rt, _ = WindowsRuntimeFrameworkFilter.is_runtime_or_framework(raw_name, winget_id or entry.get("raw_package_name"), pkg_family)
                if is_rt:
                    continue
            except Exception:
                pass

            raw_pub = (entry.get("raw_publisher") or "").strip()
            raw_ver = (entry.get("raw_version") or "").strip()
            raw_loc = (entry.get("raw_install_location") or "").strip()

            # If Winget package is MSIX, derive package family / base name
            if winget_id.startswith("msix\\"):
                clean_msix = winget_id.replace("msix\\", "")
                parts = clean_msix.split("_")
                if len(parts) >= 1:
                    base_pkg_name = parts[0]
                    if "__" in clean_msix:
                        derived_pub_id = clean_msix.split("__")[-1]
                        derived_family = f"{base_pkg_name}_{derived_pub_id}"
                        if not pkg_family:
                            pkg_family = derived_family

            norm_name = raw_name.lower()
            clean_name = norm_name.replace("(64-bit)", "").replace("(32-bit)", "").replace("(x64)", "").replace("(x86)", "").strip()
            clean_ver = raw_ver.lower()

            # Canonical Product Resolution
            canonical_key = None
            try:
                from backend.inventory.recognition.alias_system import ApplicationAliasSystem
                alias_res = ApplicationAliasSystem.resolve_application(
                    raw_name=raw_name,
                    raw_publisher=raw_pub,
                    raw_version=raw_ver,
                )
                if alias_res.canonical_product and alias_res.canonical_product != "UNRESOLVED":
                    canonical_key = (alias_res.canonical_vendor.lower(), alias_res.canonical_product.lower())
                    entry["canonical_product"] = alias_res.canonical_product
                    entry["canonical_vendor"] = alias_res.canonical_vendor
            except Exception:
                pass

            matched_record: Optional[Dict[str, Any]] = None

            # 1. Match by Canonical Product + Vendor (only if versions match or one is missing)
            if canonical_key and canonical_key in app_by_canonical:
                cand_match = app_by_canonical[canonical_key]
                cand_ver = cand_match.get("raw_version")
                cand_loc = cand_match.get("raw_install_location")
                if (not cand_ver or not raw_ver or cand_ver == raw_ver) and (not cand_loc or not raw_loc or cand_loc == raw_loc):
                    matched_record = cand_match

            # 2. Match by Package Family Name
            elif pkg_family and pkg_family in app_by_pkg_family:
                matched_record = app_by_pkg_family[pkg_family]

            # 3. Match by Registry Key
            elif reg_key and reg_key.startswith("{") and reg_key in app_by_reg_key:
                matched_record = app_by_reg_key[reg_key]

            # 4. Match by Winget Package ID
            elif winget_id and winget_id in app_by_winget_id:
                matched_record = app_by_winget_id[winget_id]

            # 5. Match by Normalized Name + Version
            elif (clean_name, clean_ver) in app_by_name_ver:
                matched_record = app_by_name_ver[(clean_name, clean_ver)]

            # 6. Match by Clean Name (when version is missing in one source)
            elif (clean_name, "") in app_by_name_ver and not raw_ver:
                matched_record = app_by_name_ver[(clean_name, "")]

            if matched_record:
                # Merge metadata across detection sources
                if not matched_record.get("raw_version") and raw_ver:
                    matched_record["raw_version"] = raw_ver
                if not matched_record.get("raw_publisher") and raw_pub:
                    matched_record["raw_publisher"] = raw_pub
                if not matched_record.get("raw_install_location") and raw_loc:
                    matched_record["raw_install_location"] = raw_loc
                
                # Prefer friendly display name over raw package strings
                if ("." in matched_record.get("raw_name", "") or "_" in matched_record.get("raw_name", "")) and (" " in raw_name or not ("." in raw_name or "_" in raw_name)):
                    matched_record["raw_display_name"] = raw_name
                    matched_record["raw_name"] = raw_name

                # Combine detection methods
                curr_methods = set(matched_record.get("detection_sources", [matched_record.get("detection_method", "WINDOWS_REGISTRY")]))
                curr_methods.add(entry.get("detection_method", "WINDOWS_REGISTRY"))
                matched_record["detection_sources"] = list(curr_methods)
                if any("64" in m for m in curr_methods):
                    matched_record["detection_method"] = "WINDOWS_REGISTRY_64" if all("REGISTRY" in m for m in curr_methods) else "MULTIPLE"
                elif len(curr_methods) > 1:
                    matched_record["detection_method"] = "MULTIPLE"

                # Update index maps for subsequent lookups
                if canonical_key and canonical_key not in app_by_canonical:
                    app_by_canonical[canonical_key] = matched_record
                if pkg_family and pkg_family not in app_by_pkg_family:
                    app_by_pkg_family[pkg_family] = matched_record
                if winget_id and winget_id not in app_by_winget_id:
                    app_by_winget_id[winget_id] = matched_record
                app_by_name_ver[(clean_name, clean_ver)] = matched_record
                if clean_ver:
                    app_by_name_ver[(clean_name, "")] = matched_record
            else:
                # New unique application record
                record = dict(entry)
                record["detection_sources"] = [entry.get("detection_method", "WINDOWS_REGISTRY")]
                output.append(record)

                if canonical_key:
                    app_by_canonical[canonical_key] = record
                if pkg_family:
                    app_by_pkg_family[pkg_family] = record
                if reg_key:
                    app_by_reg_key[reg_key] = record
                if winget_id:
                    app_by_winget_id[winget_id] = record
                app_by_name_ver[(clean_name, clean_ver)] = record
                if clean_ver:
                    app_by_name_ver[(clean_name, "")] = record

        return output

    def build_payload(self, raw_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Builds standard ingestion payload for backend API."""
        device_meta = self.gather_device_metadata()
        deduped = self.deduplicate_applications(raw_entries) if self.config.deduplicate else raw_entries

        app_payloads = []
        for it in deduped:
            app_payloads.append({
                "name": it.get("raw_name"),
                "publisher": it.get("raw_publisher"),
                "version": it.get("raw_version"),
                "install_location": it.get("raw_install_location"),
                "install_source": it.get("detection_method"),
                "architecture": it.get("architecture"),
                "detection_method": it.get("detection_method", "WINDOWS_REGISTRY")
            })

        return {
            "device": device_meta,
            "applications": app_payloads,
            "inventory_source": "ENDPOINT_AGENT"
        }
