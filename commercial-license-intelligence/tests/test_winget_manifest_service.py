"""
Tests for WinGet Package Manifest Integration Service.
Validates manifest parsing, caching, matching, ground-truth preservation, and provenance logging.
"""

import os
import tempfile
import pytest
from backend.sources.winget.winget_manifest_service import (
    WinGetManifest,
    WinGetManifestService,
)


SAMPLE_WINGET_SHOW_OUTPUT = """Found Git [Git.Git]
Version: 2.44.0
Publisher: The Git Development Community
Publisher Url: https://git-scm.com/
Author: The Git Development Community
Description: Git is a free and open source distributed version control system designed to handle everything from small to very large projects with speed and efficiency.
Homepage: https://git-scm.com/
License: GPL-2.0
License Url: https://git-scm.com/about/free-and-open-source
Installer:
  Installer Type: inno
  Installer Url: https://github.com/git-for-windows/git/releases/download/v2.44.0.windows.1/Git-2.44.0-64-bit.exe
  Installer SHA256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
"""


SAMPLE_COMMERCIAL_SHOW_OUTPUT = """Found Tableau Desktop [Tableau.TableauDesktop]
Version: 2024.1.0
Publisher: Salesforce, Inc.
Homepage: https://www.tableau.com
License: Proprietary
License Url: https://www.tableau.com/legal/eula
Installer:
  Installer Type: exe
  Installer Url: https://downloads.tableau.com/tssoftware/TableauDesktop-64bit-2024-1-0.exe
  Installer SHA256: 112233445566778899aabbccddeeff00112233445566778899aabbccddeeff00
"""


@pytest.fixture
def temp_winget_service():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = os.path.join(tmpdir, "test_license.db")
        cache_dir = os.path.join(tmpdir, "winget_cache")
        service = WinGetManifestService(db_path=db_path, cache_dir=cache_dir)
        yield service


def test_parse_winget_show_output(temp_winget_service):
    """Test parsing YAML-like stdout from `winget show`."""
    manifest = temp_winget_service.parse_winget_show_output(SAMPLE_WINGET_SHOW_OUTPUT)
    assert manifest is not None
    assert manifest.package_id == "Git.Git"
    assert manifest.package_name == "Git"
    assert manifest.publisher == "The Git Development Community"
    assert manifest.version == "2.44.0"
    assert manifest.license == "GPL-2.0"
    assert manifest.license_url == "https://git-scm.com/about/free-and-open-source"
    assert "Git-2.44.0-64-bit.exe" in manifest.installer_url
    assert manifest.installer_sha256 == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_cache_saving_and_retrieval(temp_winget_service):
    """Test SQLite persistence and microsecond cache retrieval."""
    manifest = temp_winget_service.parse_winget_show_output(SAMPLE_WINGET_SHOW_OUTPUT)
    temp_winget_service.save_to_cache(manifest)

    # 1. Retrieve by exact Package ID
    cached = temp_winget_service.get_cached_manifest("Git.Git")
    assert cached is not None
    assert cached.package_id == "Git.Git"
    assert cached.license == "GPL-2.0"
    assert cached.is_cached is True
    assert "winget_cache:Git.Git" in cached.provenance

    # 2. Retrieve by normalized application name
    cached_by_name = temp_winget_service.get_cached_manifest_by_name("Git")
    assert cached_by_name is not None
    assert cached_by_name.package_id == "Git.Git"


def test_ground_truth_preservation_and_conflict_handling():
    """Verify WinGet data does NOT overwrite human-verified catalog ground truth."""
    manifest = WinGetManifest(
        package_id="MongoDB.Compass.Full",
        package_name="MongoDB Compass",
        publisher="MongoDB Inc.",
        version="1.42.0",
        license="Proprietary",  # WinGet labels it generically as Proprietary
        license_url="https://www.mongodb.com/legal/terms-of-use",
        installer_url="https://downloads.mongodb.com/compass/mongodb-compass-1.42.0-win32-x64.exe",
        installer_sha256="abcdef1234567890",
    )

    catalog_record = {
        "application": "MongoDB Compass",
        "vendor": "MongoDB Inc.",
        "version": "1.42.0",
        "classification": "OPEN_SOURCE",
        "license_model": "SSPL-1.0 — Free to Use",
        "override_type": "EVIDENCE_CONFIRMED",
        "evidence_source": "MANUAL_AUDIT",
    }

    enriched, logs = WinGetManifestService.apply_winget_enrichment(
        record=catalog_record,
        manifest=manifest,
        has_catalog_ground_truth=True
    )

    # Catalog ground truth MUST be retained
    assert enriched["license_model"] == "SSPL-1.0 — Free to Use"
    assert enriched["classification"] == "OPEN_SOURCE"

    # Missing installer metadata MUST be enriched
    assert enriched["installer_url"] == manifest.installer_url
    assert enriched["installer_sha256"] == manifest.installer_sha256

    # Conflict and provenance MUST be logged
    assert any("[Conflict]" in log for log in logs)
    assert any("[Provenance] installer_url enriched" in log for log in logs)


def test_uncataloged_application_enrichment():
    """Verify uncataloged software is enriched as high-confidence ground truth from WinGet."""
    manifest = WinGetManifest(
        package_id="Tableau.TableauDesktop",
        package_name="Tableau Desktop",
        publisher="Salesforce, Inc.",
        version="2024.1.0",
        license="Proprietary",
        license_url="https://www.tableau.com/legal/eula",
        installer_url="https://downloads.tableau.com/tssoftware/TableauDesktop-64bit-2024-1-0.exe",
        installer_sha256="112233445566778899aabbccddeeff00112233445566778899aabbccddeeff00",
    )

    raw_record = {
        "application": "Tableau Desktop",
        "vendor": "UNKNOWN",
        "version": "2024.1.0",
        "classification": "UNKNOWN",
        "license_model": None,
    }

    enriched, logs = WinGetManifestService.apply_winget_enrichment(
        record=raw_record,
        manifest=manifest,
        has_catalog_ground_truth=False
    )

    assert enriched["canonical_vendor"] == "Salesforce, Inc."
    assert enriched["classification"] == "COMMERCIAL"
    assert enriched["license_model"] == "Commercial — Subscription"
    assert enriched["confidence"] == "HIGH"
    assert enriched["evidence_url"] == "https://www.tableau.com/legal/eula"
    assert enriched["installer_url"] == manifest.installer_url
    assert enriched["installer_sha256"] == manifest.installer_sha256
    assert any("[Provenance] canonical_vendor enriched" in log for log in logs)
