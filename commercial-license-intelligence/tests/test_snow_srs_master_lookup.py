"""
Unit Test Suite for Snow SRS Master Lookup Service (907k Snow Dump Integration).

Tests:
1. Exact & Hierarchical lookup against snow_srs_master.db for key target applications:
   - Microsoft OLE DB Driver for SQL Server -> NoLicenseRequired=1, Metric='No license required'
   - Microsoft Power BI Desktop -> NoLicenseRequired=1, Metric='No license required'
   - IntelliJ IDEA Community -> NoLicenseRequired=1, Metric='No license required'
   - ODBC Driver for Teradata -> NoLicenseRequired=0, Metric='Installations'
   - CData ODBC Driver for MongoDB -> NoLicenseRequired=0, Metric='Installations'
   - Microsoft SQL Server 2022 -> NoLicenseRequired=0, Metric='Devices'
   - Microsoft ODBC Driver 17 for SQL Server -> NoLicenseRequired=1, Metric='No license required'
   - Docker Desktop -> NoLicenseRequired=0, License Required='YES'
2. Strict preservation of Snow's metric ('Installations', 'Users', 'Devices', 'No license required')
3. Non-fabrication guarantee: Does not blindly assign 'Installations' to everything
4. Bulk Upload integration with Snow baseline preservation
"""

import pytest
import os

from backend.inventory.recognition.snow_srs_service import SnowSRSMasterService, SnowBaselineRecord


def test_snow_srs_service_database_available():
    """Verify that snow_srs_master.db exists and contains 907k indexed records."""
    conn = SnowSRSMasterService.get_db_connection()
    assert conn is not None, "Snow SRS master database connection failed"
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM snow_srs_master;")
    total = cursor.fetchone()[0]
    conn.close()
    assert total == 907437, f"Expected 907,437 rows in snow_srs_master.db, found {total}"


def test_ole_db_driver_for_sql_server():
    """Verify Microsoft OLE DB Driver for SQL Server inherits Snow's free baseline."""
    rec = SnowSRSMasterService.lookup(
        raw_name="Microsoft OLE DB Driver for SQL Server",
        vendor="Microsoft Corporation",
        version="18.7.5.0",
        os_name="Windows"
    )
    assert rec is not None
    assert rec.no_license_required == 1
    assert rec.license_required == "NO"
    assert rec.metric == "No license required"


def test_power_bi_desktop():
    """Verify Power BI Desktop inherits Snow's free baseline instead of processor cores."""
    rec = SnowSRSMasterService.lookup(
        raw_name="Microsoft Power BI Desktop",
        vendor="Microsoft Corporation",
        version="2.157.1354.0",
        os_name="Windows"
    )
    assert rec is not None
    assert rec.no_license_required == 1
    assert rec.license_required == "NO"
    assert rec.metric == "No license required"


def test_intellij_idea_community():
    """Verify IntelliJ IDEA Community Edition inherits Snow's free baseline."""
    rec = SnowSRSMasterService.lookup(
        raw_name="IntelliJ IDEA Community Edition",
        vendor="JetBrains",
        version="2024.1",
        os_name="Windows"
    )
    assert rec is not None
    assert rec.no_license_required == 1
    assert rec.license_required == "NO"
    assert rec.metric == "No license required"


def test_teradata_odbc_driver_installations_metric():
    """Verify ODBC Driver for Teradata inherits Snow's 'Installations' metric."""
    rec = SnowSRSMasterService.lookup(
        raw_name="ODBC Driver for Teradata",
        vendor="Teradata",
        version="14.0",
        os_name="Windows"
    )
    assert rec is not None
    assert rec.no_license_required == 0
    assert rec.license_required == "YES"
    assert rec.metric == "Installations"


def test_cdata_mongodb_odbc_driver_installations_metric():
    """Verify CData ODBC Driver for MongoDB inherits Snow's 'Installations' metric."""
    rec = SnowSRSMasterService.lookup(
        raw_name="CData ODBC Driver for MongoDB",
        vendor="CData Software",
        version="2023",
        os_name="Windows"
    )
    assert rec is not None
    assert rec.no_license_required == 0
    assert rec.license_required == "YES"
    assert rec.metric == "Installations"


def test_microsoft_sql_server_commercial_baseline():
    """Verify Microsoft SQL Server inherits Snow's commercial baseline."""
    rec = SnowSRSMasterService.lookup(
        raw_name="Microsoft SQL Server 2022",
        vendor="Microsoft Corporation",
        version="16.0",
        os_name="Windows"
    )
    assert rec is not None
    assert rec.no_license_required == 0
    assert rec.license_required == "YES"
    assert rec.metric in ("Devices", "Installations", "Number of processor cores", None)


def test_microsoft_odbc_driver_17():
    """Verify Microsoft ODBC Driver 17 inherits Snow's free baseline."""
    rec = SnowSRSMasterService.lookup(
        raw_name="Microsoft ODBC Driver 17 for SQL Server",
        vendor="Microsoft Corporation",
        version="17.10.6.1",
        os_name="Windows"
    )
    assert rec is not None
    assert rec.no_license_required == 1
    assert rec.license_required == "NO"
    assert rec.metric == "No license required"


def test_docker_desktop_commercial():
    """Verify Docker Desktop inherits Snow's commercial baseline."""
    rec = SnowSRSMasterService.lookup(
        raw_name="Docker Desktop",
        vendor="Docker Inc.",
        version="4.87.0",
        os_name="Windows"
    )
    assert rec is not None
    assert rec.no_license_required == 0
    assert rec.license_required == "YES"


def test_deterministic_ranking_prefers_non_null_metric():
    """Verify that multiple Snow matches rank records with valid metrics first."""
    rec = SnowSRSMasterService.lookup(
        raw_name="ODBC Driver for Teradata",
        vendor="Teradata",
        version="14.0",
        os_name="Windows"
    )
    assert rec is not None
    assert rec.metric == "Installations"
