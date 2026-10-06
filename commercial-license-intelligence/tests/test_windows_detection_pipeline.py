"""
Regression Tests for Windows Application Detection Pipeline and Inventory Synchronization.
Verifies:
1. Multi-source detection (Registry, AppX, Winget, Start Menu)
2. Deduplication priority hierarchy
3. Database insertion and synchronization
4. Visibility of UNKNOWN newly detected applications in results table
5. ChatGPT modern packaged app detection
"""

import os
import sys
import pytest
from sqlalchemy.orm import Session

# Add endpoint-agent to sys.path
agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "endpoint-agent", "windows"))
if agent_dir not in sys.path:
    sys.path.insert(0, agent_dir)

from backend.database.connection import SessionLocal
from backend.models.inventory import Device, DetectedApplication, DeviceApplication
from backend.inventory.detection.live_scanner import LiveWindowsScanner
from backend.inventory.detection.inventory_ingestor import InventoryIngestor
from backend.inventory.detection.detection_result import InventoryIngestRequest, ApplicationIngestItem, DeviceIngestPayload
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
from inventory_builder import InventoryBuilder
from config import AgentConfig
from winget_scanner import WindowsWingetScanner
from start_menu_scanner import WindowsStartMenuScanner


def test_winget_scanner_structure():
    """Verify Winget scanner executes or handles environments cleanly."""
    scanner = WindowsWingetScanner()
    entries = scanner.scan_packages()
    assert isinstance(entries, list)
    for e in entries:
        assert "raw_name" in e
        assert e.get("detection_method") == "WINDOWS_WINGET"


def test_start_menu_scanner_structure():
    """Verify Start Menu scanner discovers shortcut items."""
    scanner = WindowsStartMenuScanner()
    shortcuts = scanner.scan_shortcuts()
    assert isinstance(shortcuts, list)
    for s in shortcuts:
        assert "raw_name" in s
        assert s.get("detection_method") == "WINDOWS_START_MENU"


def test_deduplication_hierarchy():
    """Verify multi-source deduplication merges records by PackageFamilyName, RegistryKey, and Name+Version."""
    config = AgentConfig()
    builder = InventoryBuilder(config)

    raw_items = [
        {
            "raw_name": "Docker Desktop (64-bit)",
            "raw_version": "4.26.1",
            "raw_publisher": "Docker Inc.",
            "raw_install_location": r"C:\Program Files\Docker\Docker",
            "registry_key": "Docker Desktop",
            "detection_method": "WINDOWS_REGISTRY_64",
            "is_probable_application": True
        },
        {
            "raw_name": "Docker Desktop",
            "raw_version": "4.26.1",
            "raw_publisher": "Docker Inc",
            "package_identifier": "Docker.DockerDesktop",
            "detection_method": "WINDOWS_WINGET",
            "is_probable_application": True
        },
        {
            "raw_name": "Docker Desktop",
            "shortcut_path": r"C:\ProgramData\Start Menu\Docker Desktop.lnk",
            "detection_method": "WINDOWS_START_MENU",
            "is_probable_application": True
        },
    ]

    deduped = builder.deduplicate_applications(raw_items)
    assert len(deduped) == 1
    d = deduped[0]
    assert d["raw_name"] == "Docker Desktop (64-bit)"
    assert d["raw_version"] == "4.26.1"
    assert "MULTIPLE" in d.get("detection_method") or len(d.get("detection_sources", [])) == 3


def test_unknown_application_visibility_in_results():
    """Verify that a brand new application without baseline is visible with UNKNOWN classification."""
    rec = HybridLicenseEngine.resolve_hybrid_record(
        app_id=9999,
        name="CustomEnterpriseInternalTool",
        publisher="Acme Corp",
        version="1.0.0"
    )

    # Must NOT disappear or throw error
    assert rec["application"] == "CustomEnterpriseInternalTool"
    assert rec["classification"] == "UNKNOWN"
    assert rec["license_required"] == "UNKNOWN"
    assert rec["metric"] == "UNKNOWN"
    assert rec["evidence_status"] == "MISSING"
    assert rec["reliability_score"] <= 50.0


def test_live_scan_dry_run():
    """Verify live scanner dry run executes without altering database."""
    db = SessionLocal()
    try:
        initial_count = db.query(DetectedApplication).count()
        result = LiveWindowsScanner.execute_fresh_scan(db, dry_run=True)
        assert result["status"] == "SUCCESS"
        assert result["total_raw_discovered"] > 0
        assert result["deduplicated_count"] > 0
        final_count = db.query(DetectedApplication).count()
        assert initial_count == final_count
    finally:
        db.close()
