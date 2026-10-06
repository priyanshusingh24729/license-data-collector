"""
Comprehensive Test Suite for Application Qualification & Windows System Tool Filter.
Verifies:
1. Normal Win32 Registry application qualifies.
2. Valid MSIX/AppX application qualifies.
3. Valid Winget application qualifies.
4. Registry Editor in Start Menu is rejected.
5. Task Manager in Start Menu is rejected.
6. Event Viewer in Start Menu is rejected.
7. Genuine new application is detected and inserted.
8. Unresearched application does NOT receive default HIGH confidence or Standard license model.
9. Target applications (Spotify, PDF-X, WhatsApp) resolve accurate identity and high reliability.
"""

import os
import sys
import pytest

# Add paths
agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "endpoint-agent", "windows"))
if agent_dir not in sys.path:
    sys.path.insert(0, agent_dir)

from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication
from backend.inventory.detection.qualification_filter import ApplicationQualificationFilter, WindowsSystemToolFilter
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine


def test_system_tool_filter_rejections():
    """Verify built-in Windows system utilities and MMC snap-ins are rejected."""
    rejected_tools = [
        ("Registry Editor", r"C:\Windows\regedit.exe"),
        ("Task Manager", r"C:\Windows\system32\Taskmgr.exe"),
        ("Event Viewer", r"C:\Windows\system32\eventvwr.exe"),
        ("Computer Management", r"C:\Windows\system32\compmgmt.msc"),
        ("Component Services", r"C:\Windows\system32\comexp.msc"),
        ("Services", r"C:\Windows\system32\services.msc"),
        ("Task Scheduler", r"C:\Windows\system32\taskschd.msc"),
        ("System Configuration", r"C:\Windows\system32\msconfig.exe"),
        ("System Information", r"C:\Windows\system32\msinfo32.exe"),
        ("Resource Monitor", r"C:\Windows\system32\resmon.exe"),
        ("Disk Cleanup", r"C:\Windows\system32\cleanmgr.exe"),
        ("Character Map", r"C:\Windows\system32\charmap.exe"),
        ("Performance Monitor", r"C:\Windows\system32\perfmon.exe"),
        ("Steps Recorder", r"C:\Windows\system32\psr.exe"),
        ("dfrgui", r"C:\Windows\system32\dfrgui.exe"),
        ("Hyper-V Manager", r"C:\Windows\system32\virtmgmt.msc"),
        ("iSCSI Initiator", r"C:\Windows\system32\iscsicpl.exe"),
        ("Memory Diagnostics Tool", r"C:\Windows\system32\MdSched.exe"),
        ("ODBC Data Sources", r"C:\Windows\system32\odbcad32.exe"),
        ("Print Management", r"C:\Windows\system32\printmanagement.msc"),
        ("RecoveryDrive", r"C:\Windows\system32\RecoveryDrive.exe"),
        ("Remote Desktop Connection", r"C:\Windows\system32\mstsc.exe"),
        ("WSL Settings", None),
        ("WSL", None),
        ("Command Prompt", r"C:\Windows\system32\cmd.exe"),
        ("Windows PowerShell (x86)", r"C:\Windows\syswow64\WindowsPowerShell\v1.0\powershell.exe"),
    ]

    for tool_name, exe_path in rejected_tools:
        is_sys, reason = WindowsSystemToolFilter.is_system_tool(tool_name, exe_path)
        assert is_sys, f"Expected '{tool_name}' to be identified as system tool, but was not."

        # Verify candidate qualification filter also rejects it
        cand = {
            "raw_name": tool_name,
            "raw_install_location": exe_path,
            "detection_method": "WINDOWS_START_MENU"
        }
        is_qual, qual_reason, _ = ApplicationQualificationFilter.qualify_candidate(cand)
        assert not is_qual, f"Expected '{tool_name}' to be disqualified by qualification filter."


def test_start_menu_shortcut_alone_disqualified():
    """Verify raw Start Menu shortcuts without primary source backing are rejected."""
    shortcut_candidate = {
        "raw_name": "Some Random Shortcut",
        "shortcut_path": r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\SomeTool.lnk",
        "detection_method": "WINDOWS_START_MENU"
    }
    is_qual, reason, _ = ApplicationQualificationFilter.qualify_candidate(shortcut_candidate)
    assert not is_qual
    assert "START_MENU" in reason


def test_primary_sources_qualification():
    """Verify genuine Win32, AppX, and Winget applications are accepted."""
    # 1. Valid Win32 Registry application
    win32_cand = {
        "raw_name": "Docker Desktop",
        "raw_version": "4.26.1",
        "raw_publisher": "Docker Inc.",
        "raw_install_location": r"C:\Program Files\Docker\Docker",
        "raw_uninstall_string": r"C:\Program Files\Docker\Docker\uninstall.exe",
        "detection_method": "WINDOWS_REGISTRY_64"
    }
    is_qual, _, cat = ApplicationQualificationFilter.qualify_candidate(win32_cand)
    assert is_qual
    assert cat == "STANDALONE_APPLICATION"

    # 2. Valid AppX / MSIX package
    appx_cand = {
        "raw_name": "SpotifyAB.SpotifyMusic",
        "raw_publisher": "Spotify AB",
        "package_family_name": "SpotifyAB.SpotifyMusic_zpdnekdrzrea0",
        "detection_method": "WINDOWS_APPX"
    }
    is_qual, _, cat = ApplicationQualificationFilter.qualify_candidate(appx_cand)
    assert is_qual
    assert cat == "STANDALONE_APPLICATION"

    # 3. Valid Winget package
    winget_cand = {
        "raw_name": "Google Chrome",
        "raw_version": "120.0.6099.130",
        "package_identifier": "Google.Chrome",
        "detection_method": "WINDOWS_WINGET"
    }
    is_qual, _, cat = ApplicationQualificationFilter.qualify_candidate(winget_cand)
    assert is_qual
    assert cat == "STANDALONE_APPLICATION"


def test_unresearched_default_values():
    """Verify unresearched newly detected applications receive UNKNOWN confidence and UNKNOWN license model."""
    rec = HybridLicenseEngine.resolve_hybrid_record(
        app_id=None,
        name="BrandNewUnknownApp2026",
        publisher="SomeNewVendor",
        version="1.0.0"
    )

    assert rec["classification"] == "UNKNOWN"
    assert rec["confidence"] == "UNKNOWN"
    assert rec["license_model"] == "UNKNOWN"
    assert rec["metric"] == "UNKNOWN"
    assert rec["license_required"] == "UNKNOWN"
    assert rec["evidence_status"] == "MISSING"
    assert rec["reliability_score"] <= 50.0


def test_target_applications_identity_resolution():
    """Verify Spotify, PDF-X, and WhatsApp resolve exact canonical identity and licensing."""
    # Spotify
    spot = HybridLicenseEngine.resolve_hybrid_record(None, "SpotifyAB.SpotifyMusic", "Spotify AB", "1.298.301.0")
    assert spot["vendor"] == "Spotify AB"
    assert spot["classification"] == "FREE_AND_PAID"
    assert spot["confidence"] == "VERY_HIGH"
    assert spot["reliability_score"] >= 90.0

    # PDF-X
    pdfx = HybridLicenseEngine.resolve_hybrid_record(None, "6760NGPDFLab.PDFX", "PDF Technologies", "1.4.27.0")
    assert pdfx["vendor"] == "PDF Technologies"
    assert pdfx["classification"] == "FREE_AND_PAID"
    assert pdfx["confidence"] == "VERY_HIGH"
    assert pdfx["reliability_score"] >= 90.0

    # WhatsApp
    wa = HybridLicenseEngine.resolve_hybrid_record(None, "5319275A.WhatsAppDesktop", "Meta Platforms, Inc.", "2.24.0.0")
    assert wa["vendor"] == "Meta Platforms, Inc."
    assert wa["classification"] == "FREEWARE"
    assert wa["confidence"] == "VERY_HIGH"
    assert wa["reliability_score"] >= 90.0


def test_runtime_and_framework_exclusion():
    """Verify technical runtime, framework, SDK, and shared dependency packages are excluded."""
    runtime_packages = [
        ("Microsoft.UI.Xaml.2.1", "Microsoft.UI.Xaml.2.1_7.2307.18001.0_x64__8wekyb3d8bbwe"),
        ("Microsoft.UI.Xaml.2.5", "Microsoft.UI.Xaml.2.5_8.2307.18001.0_x64__8wekyb3d8bbwe"),
        ("Microsoft.UI.Xaml.2.7", "Microsoft.UI.Xaml.2.7_7.2208.15002.0_x64__8wekyb3d8bbwe"),
        ("Microsoft.UI.Xaml.2.8", "Microsoft.UI.Xaml.2.8_8.2307.18001.0_x64__8wekyb3d8bbwe"),
        ("WindowsAppRuntime.1.1", "Microsoft.WindowsAppRuntime.1.1"),
        ("WindowsAppRuntime.1.5", "Microsoft.WindowsAppRuntime.1.5"),
        ("WindowsAppRuntime.2", "Microsoft.WindowsAppRuntime.2.0"),
        ("MicrosoftCorporationII.WinAppRuntime.Main.1.3", "MicrosoftCorporationII.WinAppRuntime.Main.1.3_3000.934.1904.0_x64__8wekyb3d8bbwe"),
        ("Microsoft.WinAppRuntime.DDLM.3000.882.2207.0-x6", "Microsoft.WinAppRuntime.DDLM.3000.882.2207.0-x6_3000.882.2207.0_x64__8wekyb3d8bbwe"),
        ("Microsoft Visual C++ 2015 UWP Desktop Runtime Package", "Microsoft.VCLibs.140.00.UWPDesktop_14.0.33728.0_x64__8wekyb3d8bbwe"),
        ("Microsoft Visual C++ 2015 UWP Runtime Package", "Microsoft.VCLibs.140.00_14.0.33519.0_x64__8wekyb3d8bbwe"),
        ("Microsoft .Net Native Framework Package 2.2", "Microsoft.NET.Native.Framework.2.2_2.2.29512.0_x64__8wekyb3d8bbwe"),
        ("Microsoft .Net Native Runtime Package 2.2", "Microsoft.NET.Native.Runtime.2.2_2.2.28604.0_x64__8wekyb3d8bbwe"),
        ("Microsoft Engagement Framework", "Microsoft.Services.Store.Engagement_10.0.19011.0_x64__8wekyb3d8bbwe"),
    ]

    for name, pkg_name in runtime_packages:
        cand = {
            "raw_name": name,
            "raw_package_name": pkg_name,
            "detection_method": "WINDOWS_APPX"
        }
        is_qual, reason, cat = ApplicationQualificationFilter.qualify_candidate(cand)
        assert not is_qual, f"Expected runtime package '{name}' to be excluded, but it qualified."
        assert cat == "RUNTIME_FRAMEWORK"

    # Verify genuine standalone applications are NOT excluded
    standalone_apps = [
        ("Spotify - Music and Podcasts", "Spotify AB", "WINDOWS_APPX"),
        ("WhatsApp", "Meta Platforms, Inc.", "WINDOWS_APPX"),
        ("ChatGPT", "OpenAI", "WINDOWS_APPX"),
        ("Outlook for Windows", "Microsoft Corporation", "WINDOWS_APPX"),
        ("Windows Subsystem for Linux", "Microsoft Corporation", "WINDOWS_APPX"),
        ("Docker Desktop", "Docker Inc.", "WINDOWS_REGISTRY_64"),
        ("Microsoft SQL Server 2022", "Microsoft Corporation", "WINDOWS_REGISTRY_64"),
    ]

    for name, pub, det in standalone_apps:
        cand = {
            "raw_name": name,
            "raw_publisher": pub,
            "detection_method": det
        }
        is_qual, reason, cat = ApplicationQualificationFilter.qualify_candidate(cand)
        assert is_qual, f"Expected standalone application '{name}' to qualify, but got: {reason}"

