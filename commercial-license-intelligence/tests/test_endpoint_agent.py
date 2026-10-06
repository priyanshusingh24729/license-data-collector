"""
Test suite for Step 16: Windows Endpoint Application Discovery Agent.
Covers registry parsing, uninstall metadata extraction, AppX scanning, deduplication,
security constraints (no command execution), device identity, system component filtering, and dry-run execution.
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

# Ensure agent package in path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
agent_dir = os.path.join(root_dir, "endpoint-agent")
for p in [root_dir, agent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from windows.config import AgentConfig
from windows.uninstall_scanner import UninstallEntryParser
from windows.inventory_builder import InventoryBuilder
from windows.version_parser import VersionParser
from windows.publisher_normalizer import PublisherNormalizer
from windows.collector import WindowsEndpointCollector


# -------------------------------------------------------------
# 1. Critical Security Test: UninstallString Metadata Only (Never Executed)
# -------------------------------------------------------------

def test_uninstall_string_treated_strictly_as_data():
    """
    Critical Security Test:
    Provide an uninstall registry entry with a malicious/dangerous UninstallString.
    Verify: It is parsed purely as string metadata, and no subprocess or execution occurs.
    """
    malicious_cmd = 'cmd.exe /c del /f /q C:\\Windows\\System32\\calc.exe'
    raw_values = {
        "DisplayName": "Risky Software 2026",
        "DisplayVersion": "1.0.0",
        "Publisher": "Unknown Corp",
        "UninstallString": malicious_cmd,
        "InstallLocation": "C:\\Program Files\\RiskyApp"
    }

    with patch("subprocess.run") as mock_subproc, patch("os.system") as mock_os_sys:
        parsed = UninstallEntryParser.parse_entry(
            key_name="{MALICIOUS-KEY-001}",
            values=raw_values,
            detection_method="WINDOWS_REGISTRY_64"
        )

        assert parsed is not None
        assert parsed["raw_name"] == "Risky Software 2026"
        assert parsed["raw_uninstall_string"] == malicious_cmd
        assert parsed["is_probable_application"] is True

        # Verify NO execution took place
        mock_subproc.assert_not_called()
        mock_os_sys.assert_not_called()


# -------------------------------------------------------------
# 2. Critical Inventory Test: Deduplication
# -------------------------------------------------------------

def test_deduplication_of_registry_and_package_entries(tmp_path):
    """
    Critical Inventory Test:
    Provide duplicate records:
    - Adobe Acrobat Pro
    - Adobe Acrobat Pro (64-bit)
    with identical publisher, version, and location.
    Expected: Exactly one normalized application installation candidate.
    """
    config = AgentConfig(device_key_file=str(tmp_path / ".test_key"))
    builder = InventoryBuilder(config)

    raw_entries = [
        {
            "raw_name": "Adobe Acrobat Pro",
            "raw_publisher": "Adobe Systems Inc.",
            "raw_version": "25.001.20456",
            "raw_install_location": "C:\\Program Files\\Adobe\\Acrobat",
            "detection_method": "WINDOWS_REGISTRY_32",
            "is_probable_application": True
        },
        {
            "raw_name": "Adobe Acrobat Pro (64-bit)",
            "raw_publisher": "Adobe Inc.",
            "raw_version": "25.001.20456",
            "raw_install_location": "C:\\Program Files\\Adobe\\Acrobat",
            "detection_method": "WINDOWS_REGISTRY_64",
            "is_probable_application": True
        },
    ]

    deduped = builder.deduplicate_applications(raw_entries)
    assert len(deduped) == 1
    # 64-bit provenance is prioritized
    assert "64" in deduped[0]["detection_method"]


# -------------------------------------------------------------
# 3. Multiple Installations with Different Locations Preserved
# -------------------------------------------------------------

def test_multiple_installations_different_locations_preserved(tmp_path):
    """Verify separate installations (e.g. Python 3.11 vs Python 3.12 or different dirs) are preserved."""
    config = AgentConfig(device_key_file=str(tmp_path / ".test_key"))
    builder = InventoryBuilder(config)

    raw_entries = [
        {
            "raw_name": "Python 3.11",
            "raw_publisher": "Python Software Foundation",
            "raw_version": "3.11.8",
            "raw_install_location": "C:\\Python311",
            "detection_method": "WINDOWS_REGISTRY_64",
            "is_probable_application": True
        },
        {
            "raw_name": "Python 3.12",
            "raw_publisher": "Python Software Foundation",
            "raw_version": "3.12.2",
            "raw_install_location": "C:\\Python312",
            "detection_method": "WINDOWS_REGISTRY_64",
            "is_probable_application": True
        },
    ]

    deduped = builder.deduplicate_applications(raw_entries)
    assert len(deduped) == 2


# -------------------------------------------------------------
# 4. System Component and Hotfix Filtering
# -------------------------------------------------------------

def test_system_component_and_hotfix_filtering():
    """Verify Windows updates and KB hotfixes are flagged is_probable_application: False."""
    kb_update = {
        "DisplayName": "Security Update for Windows (KB5034441)",
        "DisplayVersion": "1.0",
        "Publisher": "Microsoft Corporation"
    }
    parsed = UninstallEntryParser.parse_entry("KB5034441", kb_update, "WINDOWS_REGISTRY_64")
    assert parsed is not None
    assert parsed["is_probable_application"] is False
    assert parsed["filter_reason"] == "WINDOWS_HOTFIX_OR_RUNTIME"

    # Missing DisplayName
    no_name = {"DisplayVersion": "1.0", "Publisher": "Test"}
    assert UninstallEntryParser.parse_entry("NoNameKey", no_name, "WINDOWS_REGISTRY_64") is None


# -------------------------------------------------------------
# 5. Device Identity & Persistence
# -------------------------------------------------------------

def test_device_identity_persistence(tmp_path):
    """Verify stable device key generation and file persistence."""
    key_file = str(tmp_path / ".device_key")
    config = AgentConfig(device_key_file=key_file)
    builder = InventoryBuilder(config)

    key1 = builder.get_or_create_device_key()
    assert key1.startswith("WIN-")
    assert os.path.exists(key_file)

    # Second call reads from file and returns identical key
    key2 = builder.get_or_create_device_key()
    assert key1 == key2

    dev_meta = builder.gather_device_metadata()
    assert dev_meta["device_key"] == key1
    assert dev_meta["agent_version"] == "1.0.0"
    assert len(dev_meta["hostname"]) > 0


# -------------------------------------------------------------
# 6. Dry-Run Discovery Execution & Local Report Generation
# -------------------------------------------------------------

def test_dry_run_discovery_flow(tmp_path):
    """Verify collector runs dry-run, creates JSON report without network calls."""
    out_file = str(tmp_path / "test_inventory.json")
    config = AgentConfig(
        dry_run=True,
        output_file=out_file,
        device_key_file=str(tmp_path / ".device_key"),
        quiet=True
    )

    collector = WindowsEndpointCollector(config)

    # Mock registry and package scanners for consistent test environment
    mock_reg = [
        {
            "registry_key": "Google Chrome",
            "raw_name": "Google Chrome",
            "raw_version": "131.0.6778.86",
            "raw_publisher": "Google LLC",
            "raw_install_location": "C:\\Program Files\\Google\\Chrome\\Application",
            "detection_method": "WINDOWS_REGISTRY_64",
            "is_probable_application": True
        }
    ]
    collector.registry_scanner.scan_all_hives = MagicMock(return_value=(mock_reg, {"registry_machine_64": 1}))
    collector.package_scanner.scan_packages = MagicMock(return_value=[])
    collector.winget_scanner.scan_packages = MagicMock(return_value=[])
    collector.start_menu_scanner.scan_shortcuts = MagicMock(return_value=[])

    res = collector.run_discovery()

    assert res["status"] == "SUCCESS"
    assert res["application_count"] == 1
    assert res["upload_status"] == "SKIPPED_DRY_RUN"
    assert os.path.exists(out_file)

    with open(out_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
        assert saved_data["device"]["device_key"].startswith("WIN-")
        assert len(saved_data["applications"]) == 1
        assert saved_data["applications"][0]["name"] == "Google Chrome"
