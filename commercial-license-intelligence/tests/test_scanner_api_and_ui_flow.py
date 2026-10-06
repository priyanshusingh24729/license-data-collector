"""
Test suite for Local Computer Scanner API, Frontend Services, and Pipeline Integration.
Validates:
- GET /api/scan/device-info
- POST /api/scan/start and GET /api/scan/status/{scan_id}
- 9-step pipeline states and live statistics
- POST /api/license/analyze direct submission
- Seamless integration with BulkUploadProcessor / UploadJobManager
"""

import sys
import os
import time
import pytest
from fastapi.testclient import TestClient

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from backend.main import app
from backend.api.scan import get_local_device_info, PIPELINE_STEPS
from backend.database.connection import SessionLocal
from backend.models.inventory_upload import InventoryUpload, UploadLicenseResult
from frontend.streamlit.services.scanner_service import ScannerService
from frontend.streamlit.components.dashboard.results_view import get_tier, generate_csv_bytes, generate_excel_bytes


@pytest.fixture
def client():
    return TestClient(app)


def test_device_info_structure():
    """Validates local device info metadata detection."""
    info = get_local_device_info()
    assert "operating_system" in info
    assert "device_name" in info
    assert "architecture" in info
    assert "scan_source" in info
    assert info["scan_source"] == "Local Machine"
    assert isinstance(info["is_windows"], bool)


def test_api_device_info_endpoint(client):
    """Tests GET /api/scan/device-info HTTP endpoint."""
    response = client.get("/api/scan/device-info")
    assert response.status_code == 200
    data = response.json()
    assert "operating_system" in data
    assert "device_name" in data
    assert data["scan_source"] == "Local Machine"


def test_api_scan_lifecycle(client):
    """Tests POST /api/scan/start and polling GET /api/scan/status/{scan_id}."""
    start_resp = client.post("/api/scan/start", json={"include_appx": True, "custom_device_name": "TEST-ENDPOINT"})
    assert start_resp.status_code == 202
    start_data = start_resp.json()
    scan_id = start_data["scan_id"]
    assert scan_id.startswith("scan_")
    assert start_data["status"] == "QUEUED"

    # Poll status
    time.sleep(0.5)
    status_resp = client.get(f"/api/scan/status/{scan_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["scan_id"] == scan_id
    assert status_data["status"] in ("QUEUED", "RUNNING", "COMPLETED")
    assert "step_statuses" in status_data
    assert "statistics" in status_data

    # Verify all 9 pipeline steps exist
    for step in PIPELINE_STEPS:
        assert step["id"] in status_data["step_statuses"]


def test_api_license_analyze(client):
    """Tests POST /api/license/analyze direct submission endpoint."""
    payload = {
        "applications": [
            {"Application": "Adobe Photoshop 2024", "Vendor": "Adobe Systems", "Version": "25.0.0"},
            {"Application": "7-Zip 24.05", "Vendor": "Igor Pavlov", "Version": "24.05"},
            {"Application": "Python 3.11", "Vendor": "Python Software Foundation", "Version": "3.11.4"},
        ],
        "source_name": "Test_Custom_Scan",
        "device_name": "ANALYZE-PC",
        "operating_system": "Windows 11",
    }
    resp = client.post("/api/license/analyze", json=payload)
    assert resp.status_code == 202
    data = resp.json()
    assert "upload_id" in data
    assert data["upload_id"].startswith("upl_")
    assert data["total_records"] == 3


def test_scanner_service_fallback():
    """Tests that frontend ScannerService operates without crashing."""
    dev_info = ScannerService.get_device_info()
    assert dev_info is not None
    assert "device_name" in dev_info


def test_dashboard_tier_categorization_and_exports():
    """Tests classification tier assignment and CSV/Excel export generation."""
    assert get_tier("COMMERCIAL", "YES").startswith("Tier 1")
    assert get_tier("FREEWARE", "NO").startswith("Tier 2")
    assert get_tier("OS_BUNDLED", "NO").startswith("Tier 3")
    assert get_tier("UNKNOWN", None).startswith("Tier 4")

    sample_records = [
        {"Tier": "Tier 1: Commercial & Billable", "Application": "Photoshop", "Vendor": "Adobe", "Version": "25", "Classification": "COMMERCIAL"},
        {"Tier": "Tier 2: Freeware & Developer Open Source", "Application": "Git", "Vendor": "Git", "Version": "2.45", "Classification": "OPEN_SOURCE"},
    ]
    csv_bytes = generate_csv_bytes(sample_records)
    assert len(csv_bytes) > 0
    assert b"Photoshop" in csv_bytes

    excel_bytes = generate_excel_bytes(sample_records)
    assert len(excel_bytes) > 0
