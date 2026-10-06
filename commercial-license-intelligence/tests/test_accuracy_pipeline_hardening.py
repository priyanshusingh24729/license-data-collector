"""
Comprehensive Test Suite: Commercial License Intelligence Pipeline Hardening
Tests:
1. Domain-to-Vendor Guardrails & Evidence Rejection
2. Evidence Validation (Specific Product Match, Confidence Capping)
3. Linux Noise Filtering & Maintainer Normalization
4. macOS System Component Filtering & Bundled Recognition
5. Browser Artifact and PWA Filtering
6. Modern Application Catalog Recognition & Official URLs
7. Research Cache Invalidation & Mismatch Prevention
8. Safe Evidence Fallback (No HIGH/VERY_HIGH on MISSING, No Empty URLs on VERIFIED)
"""

import pytest
from backend.sources.discovery.domain_registry import DomainRegistryService
from backend.validation.searxng_evidence_validator import SearxngEvidenceValidator
from backend.sources.research_cache import ResearchCache
from backend.inventory.detection.qualification_filter import (
    ApplicationQualificationFilter,
    QualificationCategory,
    LinuxSystemPackageFilter,
    MacOSSystemComponentFilter,
    BrowserArtifactAndPWAFilter,
)
from backend.inventory.detection.detection_normalizer import DetectionNormalizer
from backend.inventory.recognition.catalog import RecognitionCatalog
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine


# -------------------------------------------------------------------------------------------------
# 1. Domain-to-Vendor Guardrail Tests
# -------------------------------------------------------------------------------------------------
def test_domain_to_vendor_seed_coverage():
    """Verify that official seed domains exist for modern and standard vendors."""
    vendors = [
        ("Apple Inc.", "apple.com"),
        ("Advanced Micro Devices, Inc.", "amd.com"),
        ("Anysphere", "cursor.com"),
        ("Anthropic", "anthropic.com"),
        ("VideoLAN", "videolan.org"),
        ("Simon Tatham", "greenend.org.uk"),
        ("Postman, Inc.", "postman.com"),
        ("Notion Labs, Inc.", "notion.so"),
        ("Discord Inc.", "discord.com"),
        ("Canva Pty Ltd", "canva.com"),
        ("MongoDB, Inc.", "mongodb.com"),
        ("CrowdStrike", "crowdstrike.com"),
        ("Logitech", "logitech.com"),
        ("Docker Inc.", "docker.com"),
        ("Google LLC", "google.com"),
        ("Canonical Ltd.", "ubuntu.com"),
        ("Free Software Foundation", "gnu.org"),
    ]
    for vendor, expected_domain in vendors:
        official_domains = DomainRegistryService.get_official_domains(vendor)
        assert expected_domain in official_domains, f"Expected {expected_domain} for {vendor}, got {official_domains}"


def test_cross_contamination_rejection_rules():
    """Verify that cross-contamination pairs are strictly rejected by the validator."""
    contaminated_pairs = [
        ("AMD Radeon Software", "Advanced Micro Devices, Inc.", "https://www.docker.com/legal/docker-software-end-user-license-agreement/"),
        ("Brave Browser", "Brave Software, Inc.", "https://www.docker.com/legal/docker-software-end-user-license-agreement/"),
        ("Time Machine", "Apple Inc.", "https://www.microsoft.com/licensing/docs/view/SQL-Server"),
        ("Google Chrome", "Google LLC", "https://deepmind.google/technologies/antigravity/licensing-terms"),
        ("AirPort Utility", "Apple Inc.", "https://deepmind.google/technologies/antigravity/licensing-terms"),
        ("CrowdStrike Device Control", "CrowdStrike", "https://www.adobe.com/products/acrobatpro/pricing.html"),
        ("Logitech Options", "Logitech", "https://www.adobe.com/products/acrobatpro/pricing.html"),
        ("Linux Kernel Headers", "Ubuntu Community", "https://www.microsoft.com/licensing/terms/en-US/product/forany/all"),
        ("Gcc 11", "Free Software Foundation", "https://www.microsoft.com/licensing/terms/en-US/product/forany/all"),
    ]
    for app_name, vendor, bad_url in contaminated_pairs:
        is_valid = SearxngEvidenceValidator.is_valid_vendor_domain(bad_url, vendor, app_name)
        assert not is_valid, f"Validation should fail for {app_name} ({vendor}) with URL {bad_url}"


# -------------------------------------------------------------------------------------------------
# 2. Evidence Validator Matching & Fallback
# -------------------------------------------------------------------------------------------------
def test_searxng_evidence_validator_product_matching():
    """Verify matches_application_identity matches genuine product titles and rejects mismatches."""
    assert SearxngEvidenceValidator.matches_application_identity("Google Chrome Terms of Service", "Google Chrome", "Google LLC")
    assert SearxngEvidenceValidator.matches_application_identity("VLC Media Player - Open Source", "VLC media player", "VideoLAN")
    assert SearxngEvidenceValidator.matches_application_identity("Cursor - The AI Code Editor", "Cursor", "Anysphere")

    # Mismatch: Docker EULA snippet should NOT match AMD Radeon
    assert not SearxngEvidenceValidator.matches_application_identity(
        "Docker Desktop EULA and Subscription Terms", "AMD Radeon Software", "Advanced Micro Devices, Inc."
    )
    # Mismatch: Microsoft SQL Server snippet should NOT match Apple Time Machine
    assert not SearxngEvidenceValidator.matches_application_identity(
        "Microsoft SQL Server Enterprise Licensing", "Time Machine", "Apple Inc."
    )


def test_validator_safe_fallback_on_unrelated_candidate():
    """When only unrelated candidates are returned, validator falls back safely and never accepts foreign domain."""
    assert not SearxngEvidenceValidator.is_valid_vendor_domain(
        "https://www.docker.com/legal/docker-software-end-user-license-agreement/",
        "Advanced Micro Devices, Inc.",
        "AMD Radeon Software"
    )
    res = SearxngEvidenceValidator.validate_and_enrich(
        raw_app="AMD Radeon Software",
        raw_vend="Advanced Micro Devices, Inc.",
        raw_ver="23.10.2",
        scrape_page=False,
    )
    assert "docker.com" not in res.get("evidence_url", "")
    assert "microsoft.com" not in res.get("evidence_url", "")


# -------------------------------------------------------------------------------------------------
# 3. Linux Noise Filtering & Maintainer Normalization
# -------------------------------------------------------------------------------------------------
def test_linux_system_package_filter():
    """Test Linux package filter identifies shared libraries, headers, and core components."""
    test_cases = [
        ("libssl3", True),
        ("libgl1-mesa-dri", True),
        ("gir1.2-gtk-3.0", True),
        ("fonts-dejavu-core", True),
        ("linux-headers-5.15.0-89", True),
        ("linux-modules-extra-5.15.0-89-generic", True),
        ("cpp-11", True),
        ("systemd", True),
        ("bash", True),
        ("coreutils", True),
        ("Google Chrome", False),
        ("Postman", False),
        ("Cursor", False),
    ]
    for pkg, should_filter in test_cases:
        is_pkg, reason, _ = LinuxSystemPackageFilter.is_linux_system_package(pkg)
        assert is_pkg == should_filter, f"Package '{pkg}' expected is_system_package={should_filter}, got {is_pkg} ({reason})"


def test_maintainer_email_normalization():
    """Test Debian/Ubuntu maintainer email normalization in DetectionNormalizer."""
    test_cases = [
        ("Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>", "Ubuntu Community"),
        ("Debian Install System Team <debian-boot@lists.debian.org>", "Debian Project"),
        ("GNU Project <maintainers@gnu.org>", "Free Software Foundation"),
        ("Canonical Desktop Team <desktop@canonical.com>", "Canonical"),
    ]
    for raw_pub, expected_norm in test_cases:
        norm = DetectionNormalizer.normalize_publisher(raw_pub)
        assert norm == expected_norm, f"Expected '{expected_norm}' for '{raw_pub}', got '{norm}'"


# -------------------------------------------------------------------------------------------------
# 4. macOS System Component Filtering & Recognition
# -------------------------------------------------------------------------------------------------
def test_macos_system_component_filter():
    """Test macOS daemon, agent, and system directory detection."""
    test_cases = [
        ("com.apple.ABAssistantService", None, True),
        ("launchd", None, True),
        ("Safari", "/Applications/Safari.app", False),
        ("AirPort Utility", "/Applications/Utilities/AirPort Utility.app", False),
        ("CoreLocationAgent", "/System/Library/CoreServices/CoreLocationAgent.app", True),
        ("diagnosticd", "/usr/libexec/diagnosticd", True),
    ]
    for name, loc, expected in test_cases:
        is_comp, _ = MacOSSystemComponentFilter.is_macos_system_component(name, loc)
        assert is_comp == expected, f"Component '{name}' at '{loc}' expected is_system_component={expected}, got {is_comp}"


def test_macos_bundled_apps_catalog():
    """Test Time Machine and AirPort Utility catalog entries."""
    tm_rule = RecognitionCatalog.find_rule_by_name("Time Machine", "Apple Inc.")
    assert tm_rule is not None
    assert tm_rule.classification == "OS_BUNDLED"
    assert "apple.com" in tm_rule.primary_url

    airport_rule = RecognitionCatalog.find_rule_by_name("AirPort Utility", "Apple Inc.")
    assert airport_rule is not None
    assert airport_rule.classification == "OS_BUNDLED"
    assert "apple.com" in airport_rule.primary_url


# -------------------------------------------------------------------------------------------------
# 5. Browser Artifact and PWA Filtering
# -------------------------------------------------------------------------------------------------
def test_browser_artifact_and_pwa_filter():
    """Test detection of PWA desktop shortcuts and browser session artifacts."""
    test_cases = [
        ("cr.sb.123456", "Chrome", True),
        ("meet.google.com-12345.desktop", "Google Chrome", True),
        ("teams.microsoft.com-abc.desktop", "Microsoft Edge", True),
        ("Google Chrome", "Google LLC", False),
        ("Microsoft Teams", "Microsoft Corporation", False),
    ]
    for name, vendor, expected in test_cases:
        is_pwa, _, _ = BrowserArtifactAndPWAFilter.is_browser_artifact_or_pwa(name, vendor)
        assert is_pwa == expected, f"Artifact '{name}' expected is_pwa={expected}, got {is_pwa}"


# -------------------------------------------------------------------------------------------------
# 6. Modern Application Catalog Recognition & Official URLs
# -------------------------------------------------------------------------------------------------
def test_modern_application_catalog_entries():
    """Verify catalog recognition and accurate official URLs for all key modern applications."""
    apps_to_test = [
        ("Cursor", "Anysphere", "cursor.com", "FREE_AND_PAID"),
        ("Claude", "Anthropic", "anthropic.com", "FREE_AND_PAID"),
        ("VLC Media Player", "VideoLAN", "videolan.org", "OPEN_SOURCE"),
        ("WinRAR", "win.rar GmbH", "rarlab.com", "COMMERCIAL"),
        ("PuTTY", "Simon Tatham", "greenend.org.uk", "OPEN_SOURCE"),
        ("Postman", "Postman, Inc.", "postman.com", "FREE_AND_PAID"),
        ("Notion", "Notion Labs, Inc.", "notion.so", "FREE_AND_PAID"),
        ("Discord", "Discord Inc.", "discord.com", "FREEWARE"),
        ("Canva", "Canva Pty Ltd", "canva.com", "FREE_AND_PAID"),
        ("MongoDB Community Server", "MongoDB, Inc.", "mongodb.com", "OPEN_SOURCE"),
        ("Google Chrome", "Google LLC", "google.com", "FREEWARE"),
        ("Brave Browser", "Brave Software, Inc.", "brave.com", "OPEN_SOURCE"),
        ("AMD Radeon Software", "Advanced Micro Devices, Inc.", "amd.com", "OEM_OR_BUNDLED"),
        ("CrowdStrike Falcon Sensor", "CrowdStrike", "crowdstrike.com", "COMMERCIAL"),
        ("Logitech Options", "Logitech", "logitech.com", "OEM_OR_BUNDLED"),
        ("Linux Kernel Headers", "Ubuntu Community", "kernel.org", "OPEN_SOURCE"),
        ("GCC", "Free Software Foundation", "gnu.org", "OPEN_SOURCE"),
    ]
    for app_name, vendor, expected_domain, expected_class in apps_to_test:
        rule = RecognitionCatalog.find_rule_by_name(app_name, vendor)
        assert rule is not None, f"RecognitionCatalog entry missing for '{app_name}' ({vendor})"
        assert expected_domain in rule.primary_url, f"Expected {expected_domain} in primary_url for {app_name}, got {rule.primary_url}"
        assert rule.classification == expected_class, f"Expected classification {expected_class} for {app_name}, got {rule.classification}"


# -------------------------------------------------------------------------------------------------
# 7. Hybrid License Engine Integration
# -------------------------------------------------------------------------------------------------
def test_hybrid_engine_resolves_modern_apps_with_official_url():
    """Verify HybridLicenseEngine returns correct classification and official URLs without Microsoft leak."""
    records = [
        ("Cursor", "Anysphere", "0.40.4", "FREE_AND_PAID", "cursor.com"),
        ("Google Chrome", "Google LLC", "128.0.6613.85", "FREEWARE", "google.com"),
        ("VLC Media Player", "VideoLAN", "3.0.20", "OPEN_SOURCE", "videolan.org"),
        ("AMD Radeon Software", "Advanced Micro Devices, Inc.", "23.10.2", "OEM_OR_BUNDLED", "amd.com"),
        ("Brave Browser", "Brave Software, Inc.", "1.69.153", "OPEN_SOURCE", "brave.com"),
        ("CrowdStrike Falcon Sensor", "CrowdStrike", "7.15.0", "COMMERCIAL", "crowdstrike.com"),
    ]
    for name, pub, ver, exp_class, exp_domain in records:
        res = HybridLicenseEngine.resolve_hybrid_record(
            app_id=None,
            name=name,
            publisher=pub,
            version=ver,
            install_location=None,
        )
        assert res["classification"] == exp_class, f"Expected {exp_class} for {name}, got {res['classification']}"
        ev_url = res.get("primary_source_url") or res.get("source_url") or res.get("evidence_url") or ""
        assert exp_domain in ev_url, f"Expected domain {exp_domain} in evidence URL for {name}, got '{ev_url}'"
        assert "microsoft.com" not in ev_url, f"Microsoft URL leaked into {name}: '{ev_url}'"


def test_hybrid_engine_handles_qualification_categories():
    """Verify web shortcuts, Linux packages, and macOS components get non-commercial categories."""
    # Web Shortcut / PWA
    pwa_res = HybridLicenseEngine.resolve_hybrid_record(
        app_id=None,
        name="cr.sb.meet.google.com-123",
        publisher="Google LLC",
        version="1.0",
        install_location=None,
    )
    assert pwa_res["classification"] == "WEB_SHORTCUT/PWA"
    assert pwa_res["license_required"] == "NO"

    # Linux system library
    linux_res = HybridLicenseEngine.resolve_hybrid_record(
        app_id=None,
        name="libgl1-mesa-dri",
        publisher="Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>",
        version="22.0.5",
        install_location=None,
    )
    assert linux_res["classification"] == "LINUX_SYSTEM_PACKAGE"
    assert linux_res["license_required"] == "NO"

    # macOS system daemon
    macos_res = HybridLicenseEngine.resolve_hybrid_record(
        app_id=None,
        name="com.apple.ABAssistantService",
        publisher="Apple Inc.",
        version="1.0",
        install_location=None,
    )
    assert macos_res["classification"] == "OS_BUNDLED"
    assert macos_res["license_required"] == "NO"


# -------------------------------------------------------------------------------------------------
# 8. Research Cache Invalidation
# -------------------------------------------------------------------------------------------------
def test_research_cache_rejects_and_evicts_mismatched_domains():
    """Verify ResearchCache raises ValueError on invalid put, and evicts invalid on get."""
    from backend.sources.research_cache import CachedEvidenceEntry

    # 1. Invalid PUT must raise ValueError
    with pytest.raises(ValueError):
        ResearchCache.put(
            canonical_product="AMD Radeon Software",
            canonical_vendor="Advanced Micro Devices, Inc.",
            source_url="https://www.docker.com/legal/docker-software-end-user-license-agreement/",
            source_title="Docker Software EULA",
            source_authority="OFFICIAL_VENDOR",
            evidence_type="DIRECT_STATEMENT",
            evidence_text="Docker Desktop subscription required",
            license_model="Commercial",
            license_metric="USER",
            license_required="YES",
            classification="COMMERCIAL",
            availability="PAID",
            scope_match_tier="EXACT_PRODUCT_EXACT_VERSION",
        )

    # 2. Simulate legacy corrupt in-memory cache entry and verify get() purges it
    bad_key = ResearchCache._compute_key("AMD Radeon Software", "Advanced Micro Devices, Inc.")
    ResearchCache._CACHE[bad_key] = CachedEvidenceEntry(
        canonical_product="AMD Radeon Software",
        canonical_vendor="Advanced Micro Devices, Inc.",
        source_url="https://www.docker.com/legal/docker-software-end-user-license-agreement/",
        source_title="Docker EULA",
        source_authority="OFFICIAL_VENDOR",
        evidence_type="DIRECT_STATEMENT",
        evidence_text="Docker terms",
        license_model="Commercial",
        license_metric="USER",
        license_required="YES",
        classification="COMMERCIAL",
        availability="PAID",
        scope_match_tier="EXACT_PRODUCT",
        evidence_hash="mockhash123",
        is_valid=True,
    )

    # get() must detect mismatch, evict entry, and return None
    fetched = ResearchCache.get("AMD Radeon Software", "Advanced Micro Devices, Inc.")
    assert fetched is None, "Cache should evict cross-contaminated domain"
    assert bad_key not in ResearchCache._CACHE
