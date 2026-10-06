"""
test_csv_vendor_remediation.py
-------------------------------
Unit tests verifying that problematic/unknown vendor signatures from the
user-provided vendor mapping CSV are correctly resolved to their canonical vendors,
appropriate license requirements, and classifications.
"""

import pytest
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine


TEST_CASES = [
    # Gaming / Client Utilities
    ("Riot Vanguard", "", "Riot Games, Inc.", "FREEWARE", "NO"),
    ("VALORANT", "Riot Games", "Riot Games, Inc.", "FREEWARE", "NO"),
    ("Riot Client", "Riot Games, Inc.", "Riot Games, Inc.", "FREEWARE", "NO"),
    ("TLauncher", "UNKNOWN", "TLauncher", "FREEWARE", "NO"),
    ("Launcher Prerequisites", "Epic Games", "Epic Games, Inc.", "FREEWARE", "NO"),

    # Developer Tools & Build Systems
    ("CMake 3.30.2", "Kitware, Inc.", "Kitware, Inc.", "OPEN_SOURCE", "NO"),
    ("AWS Command Line Interface v2", "Amazon Web Services, Inc.", "Amazon Web Services, Inc.", "OPEN_SOURCE", "NO"),
    ("Warp", "Warp", "Warp, Inc.", "FREE_AND_PAID", "CONTEXT_DEPENDENT"),
    ("Create React App Sample", "UNKNOWN", "Meta Platforms, Inc. / Open Source Community", "OPEN_SOURCE", "NO"),

    # MySQL Suite
    ("MySQL Workbench 8.0 CE", "Oracle", "Oracle Corporation", "OPEN_SOURCE", "NO"),
    ("MySQL Shell 8.0", "Oracle", "Oracle Corporation", "OPEN_SOURCE", "NO"),
    ("MySQL Router 8.0", "Oracle", "Oracle Corporation", "OPEN_SOURCE", "NO"),

    # Hardware Drivers & OEM Utilities
    ("NVIDIA Graphics Driver 560.94", "NVIDIA Corporation", "NVIDIA Corporation", "OEM_OR_BUNDLED", "NO"),
    ("NVIDIA HD Audio Driver 1.4.1.3", "NVIDIA Corporation", "NVIDIA Corporation", "OEM_OR_BUNDLED", "NO"),
    ("NVIDIA PhysX System Software 9.23.1019", "NVIDIA Corporation", "NVIDIA Corporation", "OEM_OR_BUNDLED", "NO"),
    ("AMD Chipset Software", "Advanced Micro Devices, Inc.", "Advanced Micro Devices, Inc. (AMD)", "OEM_OR_BUNDLED", "NO"),
    ("AMD PSP Driver", "Advanced Micro Devices, Inc.", "Advanced Micro Devices, Inc. (AMD)", "OEM_OR_BUNDLED", "NO"),
    ("RyzenMasterSDK", "Advanced Micro Devices, Inc.", "Advanced Micro Devices, Inc. (AMD)", "OEM_OR_BUNDLED", "NO"),
    ("Legion Arena", "Lenovo", "Lenovo", "OEM_OR_BUNDLED", "NO"),

    # Security & Background Services
    ("WebAdvisor by McAfee", "McAfee, LLC", "McAfee, LLC", "FREEWARE", "NO"),
    ("Avast Update Helper", "Avast", "Gen Digital Inc. / Avast", "FREEWARE", "NO"),
    ("Wondershare Helper Compact 2.6.0", "Wondershare", "Wondershare Technology Co., Ltd.", "COMMERCIAL_COMPONENT", "NO"),

    # AppX / Store Packages & Networking
    ("57495kankaria.luminous", "UNKNOWN", "Kankaria", "FREEWARE", "NO"),
    ("Telegram Desktop", "Telegram Messenger LLP", "Telegram Messenger LLP", "OPEN_SOURCE", "NO"),
    ("Adobe Creative Cloud Express", "Adobe Systems Incorporated", "Adobe Inc.", "FREE_AND_PAID", "CONTEXT_DEPENDENT"),
    ("Bonjour", "Apple Inc.", "Apple Inc.", "OS_BUNDLED", "NO"),
]


@pytest.mark.parametrize("name,publisher,expected_vendor,expected_class,expected_req", TEST_CASES)
def test_csv_signatures_resolution(name, publisher, expected_vendor, expected_class, expected_req):
    res = HybridLicenseEngine.resolve_hybrid_record(
        app_id=None,
        name=name,
        publisher=publisher,
        version="1.0.0",
    )
    assert res.get("vendor") == expected_vendor, f"Expected vendor '{expected_vendor}', got '{res.get('vendor')}' for {name}"
    assert res.get("classification") == expected_class, f"Expected classification '{expected_class}', got '{res.get('classification')}' for {name}"
    assert res.get("license_required") == expected_req, f"Expected license_required '{expected_req}', got '{res.get('license_required')}' for {name}"
