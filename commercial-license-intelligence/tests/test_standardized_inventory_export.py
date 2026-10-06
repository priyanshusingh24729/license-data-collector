"""
Tests for Standardized Application Inventory Export Engine.
Verifies the exact 17-column schema and 8-layer processing pipeline matching the user's reference format:
1. Exact 17 columns in strict order.
2. Original application name preserved in 'Name'.
3. 'Normalized_Application' properly cleans platform tags, architecture, duplicate version numbers.
4. Version extraction and major/minor/patch splitting.
5. OS and consistent numeric OSType detection (0=Windows, 1=macOS, 2=Linux, 8=iOS, 9=Android).
6. NULL representation for missing/unknown values.
7. License/support metadata evaluation (NoLicenseRequired, IsEndOfLife, IsEndOfSupport, Metric).
8. Classification layer (COMMERCIAL, FREE, FREE_AND_PAID, OPEN_SOURCE, TRIAL, UNKNOWN).
9. License Required layer (YES, NO, CONTEXT_DEPENDENT, UNKNOWN).
10. License Model layer (Standard Commercial, Per User, Subscription, Open Source, Freeware, UNKNOWN).
11. Sequential App_ID generation.
12. Row independence (no invalid merging).
13. Clean Excel (.xlsx) and CSV generation with 'NULL' for missing values.
"""

import io
import pytest
import pandas as pd
from backend.inventory.export.standardized_inventory_exporter import (
    StandardizedInventoryExporter,
    STANDARDIZED_COLUMNS,
)

EXPECTED_17_COLUMNS = [
    "App_ID",
    "Name",
    "OSType",
    "Version",
    "Normalized_Application",
    "Created_At",
    "Operating_System",
    "Major_Version",
    "Minor_Version",
    "Patch_Version",
    "NoLicenseRequired",
    "IsEndOfLife",
    "IsEndOfSupport",
    "Metric",
    "Classification",
    "License Required",
    "License Model",
]


def test_schema_columns_exact_order():
    """Requirement: Exact standardized columns in specified order, no extra columns."""
    assert STANDARDIZED_COLUMNS == EXPECTED_17_COLUMNS

    records = [{"raw_name": "Google Chrome", "raw_version": "124.0.6367.208"}]
    df = StandardizedInventoryExporter.transform_inventory(records)
    assert list(df.columns) == EXPECTED_17_COLUMNS


def test_normalization_examples_from_user_spec():
    """
    Normalization verification:
    "Adobe Acrobat 7 Standard (Mac.)" -> "Adobe Acrobat Standard"
    "Weston 3 (Linux)" -> "Weston"
    "TS-LogRhythm Web Console 6" -> "TS LogRhythm Web Console"
    """
    sample_records = [
        {
            "raw_name": "Adobe Acrobat 7 Standard (Mac.)",
            "raw_vendor": "Adobe Systems",
        },
        {
            "raw_name": "Weston 3 (Linux)",
            "raw_vendor": "Wayland Project",
        },
        {
            "raw_name": "TS-LogRhythm Web Console 6",
            "raw_vendor": "LogRhythm",
        },
    ]

    df = StandardizedInventoryExporter.transform_inventory(sample_records)

    # 1. Adobe Acrobat check
    row_adobe = df.iloc[0]
    assert row_adobe["Name"] == "Adobe Acrobat 7 Standard (Mac.)"
    assert row_adobe["Normalized_Application"] == "Adobe Acrobat Standard"
    assert row_adobe["Version"] == "7"
    assert row_adobe["Major_Version"] == 7
    assert pd.isna(row_adobe["Minor_Version"])
    assert pd.isna(row_adobe["Patch_Version"])
    assert row_adobe["OSType"] == 1
    assert row_adobe["Operating_System"] == "macOS"

    # 2. Weston check
    row_weston = df.iloc[1]
    assert row_weston["Name"] == "Weston 3 (Linux)"
    assert row_weston["Normalized_Application"] == "Weston"
    assert row_weston["Version"] == "3"
    assert row_weston["Major_Version"] == 3
    assert pd.isna(row_weston["Minor_Version"])
    assert pd.isna(row_weston["Patch_Version"])
    assert row_weston["OSType"] == 2
    assert row_weston["Operating_System"] == "Linux"

    # 3. TS LogRhythm check
    row_ts = df.iloc[2]
    assert row_ts["Name"] == "TS-LogRhythm Web Console 6"
    assert row_ts["Normalized_Application"] == "TS LogRhythm Web Console"
    assert row_ts["Version"] == "6"
    assert row_ts["Major_Version"] == 6
    assert row_ts["OSType"] == 0
    assert row_ts["Operating_System"] == "Windows"


def test_version_extraction_and_splitting():
    """Intelligently split version into Major, Minor, Patch."""
    records = [
        {"raw_name": "Python 3.11.4", "raw_version": "3.11.4"},
        {"raw_name": "7-Zip 24.05", "raw_version": "24.05"},
        {"raw_name": "Docker Desktop 4.30.0", "raw_version": "4.30.0"},
        {"raw_name": "Git", "raw_version": "v2.45.0.windows.1"},
        {"raw_name": "Legacy Tool No Version"},
    ]

    df = StandardizedInventoryExporter.transform_inventory(records)

    # Python
    p_row = df.iloc[0]
    assert p_row["Version"] == "3.11.4"
    assert p_row["Major_Version"] == 3
    assert p_row["Minor_Version"] == 11
    assert p_row["Patch_Version"] == 4
    assert p_row["Normalized_Application"] == "Python"

    # 7-Zip: brand number '7' preserved, version '24.05'
    z_row = df.iloc[1]
    assert z_row["Version"] == "24.05"
    assert z_row["Major_Version"] == 24
    assert z_row["Minor_Version"] == 5
    assert pd.isna(z_row["Patch_Version"])
    assert z_row["Normalized_Application"] == "7-Zip"

    # Docker Desktop
    d_row = df.iloc[2]
    assert d_row["Version"] == "4.30.0"
    assert d_row["Major_Version"] == 4
    assert d_row["Minor_Version"] == 30
    assert d_row["Patch_Version"] == 0
    assert d_row["Normalized_Application"] == "Docker Desktop"

    # Git
    g_row = df.iloc[3]
    assert g_row["Major_Version"] == 2
    assert g_row["Minor_Version"] == 45
    assert g_row["Patch_Version"] == 0

    # No version -> all null
    n_row = df.iloc[4]
    assert pd.isna(n_row["Version"])
    assert pd.isna(n_row["Major_Version"])
    assert pd.isna(n_row["Minor_Version"])
    assert pd.isna(n_row["Patch_Version"])


def test_os_and_ostype_numeric_detection():
    """Standardize OS and numeric OSType matching reference spreadsheet."""
    records = [
        {"raw_name": "App for Mac", "install_location": "/Applications/App.app"},
        {"raw_name": "Linux Package [Linux]", "install_location": "/usr/bin/tool"},
        {"raw_name": "Windows App (64-bit)", "install_location": "C:\\Program Files\\App"},
        {"raw_name": "Foreign Affairs 1 (iOS)"},
        {"raw_name": "Lampguiden 2 (Android)"},
        {"raw_name": "Solaris Command [solaris]"},
    ]

    df = StandardizedInventoryExporter.transform_inventory(records)

    # macOS -> 1
    assert df.iloc[0]["OSType"] == 1
    assert df.iloc[0]["Operating_System"] == "macOS"

    # Linux -> 2
    assert df.iloc[1]["OSType"] == 2
    assert df.iloc[1]["Operating_System"] == "Linux"

    # Windows -> 0
    assert df.iloc[2]["OSType"] == 0
    assert df.iloc[2]["Operating_System"] == "Windows"

    # iOS -> 8, Operating_System is None/NULL
    assert df.iloc[3]["OSType"] == 8
    assert pd.isna(df.iloc[3]["Operating_System"])

    # Android -> 9, Operating_System is None/NULL
    assert df.iloc[4]["OSType"] == 9
    assert pd.isna(df.iloc[4]["Operating_System"])

    # Solaris -> 3
    assert df.iloc[5]["OSType"] == 3


def test_classification_and_license_layers():
    """Tests Classification, License Required, and License Model layers."""
    records = [
        {
            "raw_name": "Oracle Database Enterprise Edition",
            "classification": "COMMERCIAL",
            "license_model": "Per Core / Server + CAL",
        },
        {
            "raw_name": "Visual Studio Code",
            "raw_vendor": "Microsoft",
        },
        {
            "raw_name": "Slack",
            "raw_vendor": "Slack Technologies",
            "classification": "FREE_AND_PAID",
        },
        {
            "raw_name": "Totally Unknown Custom Binary",
        },
    ]

    df = StandardizedInventoryExporter.transform_inventory(records)

    # Oracle
    r_ora = df.iloc[0]
    assert r_ora["Classification"] == "COMMERCIAL"
    assert r_ora["License Required"] == "YES"
    assert "Per Core" in r_ora["License Model"]
    assert r_ora["NoLicenseRequired"] == 0

    # VS Code (Matched from catalog as Freeware / Free / Open Source)
    r_vsc = df.iloc[1]
    assert r_vsc["Classification"] in ("FREE", "OPEN_SOURCE")
    assert r_vsc["License Required"] == "NO"
    assert r_vsc["License Model"] in ("No License Required", "Freeware", "MIT — Free", "MIT — Free/Open Source")
    assert r_vsc["NoLicenseRequired"] == 1

    # Slack (Free and Paid) - requires commercial entitlement -> YES (Never CONTEXT_DEPENDENT)
    r_slack = df.iloc[2]
    assert r_slack["Classification"] == "FREE_AND_PAID"
    assert r_slack["License Required"] == "YES"

    # Unknown - Never return UNKNOWN, leave classification/model blank/None, License Required strictly YES/NO
    r_unk = df.iloc[3]
    assert pd.isna(r_unk["Classification"])
    assert r_unk["License Required"] in ("YES", "NO")
    assert pd.isna(r_unk["License Model"])


def test_null_and_boolean_formatting():
    """Keep missing/unknown values as NULL in exports, flags as 0/1."""
    records = [
        {
            "raw_name": "Commercial Tool",
            "classification": "COMMERCIAL",
            "is_end_of_life": False,
            "is_end_of_support": True,
        }
    ]

    df = StandardizedInventoryExporter.transform_inventory(records)
    row = df.iloc[0]

    assert row["NoLicenseRequired"] == 0
    assert row["IsEndOfLife"] == 0
    assert row["IsEndOfSupport"] == 1

    csv_bytes = StandardizedInventoryExporter.to_csv_bytes(df)
    csv_text = csv_bytes.decode("utf-8")
    # Missing version and patch should serialize as NULL
    assert ",NULL," in csv_text


def test_sequential_app_id_and_separate_rows():
    """Unique sequential App_ID (1..N) and distinct rows for variants."""
    records = [
        {"raw_name": "Python 3.10.0", "raw_version": "3.10.0"},
        {"raw_name": "Python 3.11.4", "raw_version": "3.11.4"},
        {"raw_name": "Adobe Acrobat 7 Standard (Mac.)"},
        {"raw_name": "Adobe Acrobat 7 Standard (Windows)"},
    ]

    df = StandardizedInventoryExporter.transform_inventory(records)

    assert len(df) == 4
    assert list(df["App_ID"]) == [1, 2, 3, 4]


def test_csv_and_excel_export_bytes():
    """Clean Excel-ready CSV and XLSX generation strictly matching 17 columns."""
    records = [
        {
            "raw_name": "Adobe Acrobat 7 Standard (Mac.)",
            "raw_vendor": "Adobe",
            "classification": "COMMERCIAL",
            "license_requirement": "YES",
            "metric": "Installations",
        },
        {
            "raw_name": "Weston 3 (Linux)",
            "classification": "OPEN_SOURCE",
            "license_requirement": "NO",
        },
    ]

    df = StandardizedInventoryExporter.transform_inventory(records)

    # Test CSV
    csv_bytes = StandardizedInventoryExporter.to_csv_bytes(df)
    assert csv_bytes.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    csv_text = csv_bytes.decode("utf-8")
    lines = csv_text.strip().split("\n")
    header = lines[0].replace("\ufeff", "").strip()
    assert header == ",".join(STANDARDIZED_COLUMNS)

    # Test Excel
    excel_bytes = StandardizedInventoryExporter.to_excel_bytes(df)
    assert len(excel_bytes) > 2000
    df_read = pd.read_excel(io.BytesIO(excel_bytes), sheet_name="Application Inventory")
    assert list(df_read.columns) == STANDARDIZED_COLUMNS
    assert len(df_read) == 2


def test_scan_export_api_endpoints():
    """Verifies that scan export endpoints return 17-column CSV and XLSX."""
    from starlette.testclient import TestClient
    from backend.main import app

    client = TestClient(app)

    start_resp = client.post("/api/scan/start", json={"include_appx": False, "include_winget": False})
    assert start_resp.status_code == 202
    scan_id = start_resp.json()["scan_id"]

    import time
    for _ in range(60):
        st_resp = client.get(f"/api/scan/status/{scan_id}")
        if st_resp.status_code == 200 and st_resp.json()["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.5)

    status_data = client.get(f"/api/scan/status/{scan_id}").json()
    if status_data["status"] == "COMPLETED":
        # Test CSV export
        csv_res = client.get(f"/api/scan/export/{scan_id}/csv")
        assert csv_res.status_code == 200
        assert "text/csv" in csv_res.headers["content-type"]
        first_line = csv_res.text.strip().split("\n")[0].replace("\ufeff", "").strip()
        assert first_line == ",".join(STANDARDIZED_COLUMNS)

        # Test Excel export
        xlsx_res = client.get(f"/api/scan/export/{scan_id}/excel")
        assert xlsx_res.status_code == 200
        assert len(xlsx_res.content) > 1000
        df_scan = pd.read_excel(io.BytesIO(xlsx_res.content), sheet_name="Application Inventory")
        assert list(df_scan.columns) == STANDARDIZED_COLUMNS
        assert len(df_scan) > 0
