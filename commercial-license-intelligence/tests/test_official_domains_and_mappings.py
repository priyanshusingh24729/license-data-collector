"""
Comprehensive Verification Tests for Official Domains Whitelist & Application Mapping across All 11 Categories.
"""

import pytest
from backend.search_engines.base import load_official_domains, SearchEngine
from backend.sources.discovery.domain_registry import DomainRegistryService
from backend.inventory.detection.detection_normalizer import DetectionNormalizer
from backend.inventory.recognition.alias_system import ApplicationAliasSystem
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
from backend.validation.searxng_evidence_validator import (
    SearxngEvidenceValidator,
    is_valid_vendor_domain,
    matches_application_identity,
)
from backend.sources.discovery.search_provider import SearchResult


def test_official_domains_yaml_loading():
    """Verify that all categorized domains in official_domains.yaml load properly."""
    domains = load_official_domains()
    assert len(domains) >= 80, f"Expected at least 80 official domains, got {len(domains)}"

    expected_samples = [
        # Original 40
        "microsoft.com", "adobe.com", "docker.com", "python.org", "postman.com",
        "anydesk.com", "notion.so", "canva.com", "figma.com", "videolan.org",
        # Apple / OS
        "apple.com", "support.apple.com",
        # Browsers
        "google.com", "chromium.org", "mozilla.org", "opera.com", "operasoftware.com",
        "brave.com", "vivaldi.com", "coccoc.com", "frontmotion.com",
        # Cloud storage
        "dropbox.com", "box.com", "onedrive.live.com",
        # Consumer / social
        "facebook.com", "messenger.com", "instagram.com", "strava.com", "whatsapp.com",
        "spotify.com", "linkedin.com", "netflix.com", "discord.com",
        # Dev / data tools
        "postgresql.org", "eclipse.org", "java.com", "redhat.com", "splunk.com",
        "filezilla-project.org", "gams.com", "mendix.com", "mongodb.com", "nodejs.org",
        "dotnet.microsoft.com", "git-scm.com", "openssl.org", "apache.org", "nmap.org",
        "ngrok.com", "ollama.com", "cursor.com", "perplexity.ai",
        # Creative / media
        "foundry.com", "descript.com", "mkvtoolnix.download", "steelseries.com",
        "dolby.com", "obsproject.com", "krita.org",
        # Office / productivity
        "libreoffice.org", "documentfoundation.org",
        # Security / endpoint
        "cisco.com", "broadcom.com", "fortinet.com", "mcafee.com", "sophos.com",
        "tenable.com", "pulsesecure.net",
        # Hardware / OEM
        "nvidia.com", "lenovo.com", "dell.com", "hp.com", "intel.com", "amd.com",
        "realtek.com", "logitech.com", "gigabyte.com", "wacom.com",
        # Misc utilities
        "corel.com", "bittorrent.com", "zoho.com", "epicgames.com", "teamviewer.com",
        "ccleaner.com", "qbittorrent.org", "win-rar.com", "servicenow.com",
    ]

    for d in expected_samples:
        assert d in domains, f"Missing domain {d} in official_domains.yaml"


def test_domain_registry_service_whitelist_validation():
    """Verify that DomainRegistryService recognizes all whitelist domains as trusted."""
    domains = load_official_domains()
    for d in domains:
        test_url = f"https://www.{d}/terms"
        assert DomainRegistryService.is_trusted_official_domain(test_url), (
            f"Expected {test_url} to be trusted by DomainRegistryService"
        )


def test_mozilla_firefox_end_to_end_normalization():
    """
    Test user requirement:
    Ensure application names are correctly normalized and mapped to the appropriate vendor/domain:
    Mozilla.Firefox -> Mozilla Firefox -> mozilla.org
    """
    raw_name = "Mozilla.Firefox"
    raw_publisher = None

    # 1. Normalize application name
    norm_name = DetectionNormalizer.normalize_name(raw_name)
    assert norm_name == "Mozilla Firefox", f"Expected 'Mozilla Firefox', got '{norm_name}'"

    # 2. Normalize publisher from raw name
    norm_vendor = DetectionNormalizer.normalize_publisher(raw_publisher, raw_name=raw_name)
    assert norm_vendor == "Mozilla", f"Expected 'Mozilla', got '{norm_vendor}'"

    # 3. Domain registry lookup
    official_domains = DomainRegistryService.get_official_domains(norm_vendor)
    assert "mozilla.org" in official_domains, f"Expected 'mozilla.org' in {official_domains}"

    # 4. Evidence domain guardrail check
    candidate_url = "https://www.mozilla.org/en-US/privacy/firefox/"
    assert is_valid_vendor_domain(candidate_url, norm_vendor, norm_name) is True

    # 5. Application identity match
    res = SearchResult(url=candidate_url, title="Mozilla Firefox Privacy and License Notice", snippet="Firefox browser open source terms", engine="duckduckgo")
    assert matches_application_identity(norm_name, res, norm_vendor) is True


@pytest.mark.parametrize(
    "raw_package, expected_app, expected_vendor, expected_domain",
    [
        # Apple / OS
        ("Apple.Bonjour", "Apple Bonjour", "Apple Inc.", "apple.com"),
        # Browsers
        ("Mozilla.Firefox", "Mozilla Firefox", "Mozilla", "mozilla.org"),
        ("Brave.Brave", "Brave Browser", "Brave Software Inc", "brave.com"),
        ("Vivaldi.Vivaldi", "Vivaldi", "Vivaldi Technologies", "vivaldi.com"),
        ("CocCoc.CocCoc", "Coc Coc", "Coc Coc", "coccoc.com"),
        ("FrontMotion.Firefox", "FrontMotion Firefox Community Edition", "FrontMotion", "frontmotion.com"),
        # Cloud storage
        ("Dropbox.Dropbox", "Dropbox", "Dropbox", "dropbox.com"),
        ("Box.Box", "Box", "Box", "box.com"),
        # Consumer / social
        ("Spotify.Spotify", "Spotify", "Spotify", "spotify.com"),
        ("Discord.Discord", "Discord", "Discord Inc.", "discord.com"),
        ("Netflix.Netflix", "Netflix", "Netflix, Inc.", "netflix.com"),
        ("Meta.WhatsApp", "WhatsApp", "Meta Platforms, Inc.", "meta.com"),
        ("Strava.Strava", "Strava", "Strava", "strava.com"),
        # Dev / data tools
        ("Insecure.Nmap", "Nmap", "Insecure.Com LLC", "nmap.org"),
        ("Ollama.Ollama", "Ollama", "Ollama", "ollama.com"),
        ("Anysphere.Cursor", "Cursor", "Anysphere", "cursor.com"),
        ("PostgreSQL.PostgreSQL", "PostgreSQL", "PostgreSQL Global Development Group", "postgresql.org"),
        ("Eclipse.Eclipse", "Eclipse IDE", "Eclipse Foundation", "eclipse.org"),
        ("OpenJS.NodeJS", "Node.js", "OpenJS Foundation", "nodejs.org"),
        ("Git.Git", "Git", "The Git Development Community", "git-scm.com"),
        # Creative / media
        ("OBSProject.OBSStudio", "OBS Studio", "OBS Project", "obsproject.com"),
        ("Krita.Krita", "Krita", "Krita Foundation", "krita.org"),
        ("TheFoundry.Nuke", "The Foundry Nuke", "The Foundry", "foundry.com"),
        ("Descript.Descript", "Descript", "Descript", "descript.com"),
        ("MoritzBunkus.MKVToolNix", "MKVToolNix", "MKVToolNix", "mkvtoolnix.download"),
        ("SteelSeries.GG", "SteelSeries GG", "SteelSeries", "steelseries.com"),
        ("Dolby.DolbyAccess", "Dolby Access", "Dolby Laboratories", "dolby.com"),
        # Office / productivity
        ("TheDocumentFoundation.LibreOffice", "LibreOffice", "The Document Foundation", "documentfoundation.org"),
        # Security / endpoint
        ("Cisco.AnyConnect", "Cisco AnyConnect Secure Mobility Client", "Cisco Systems, Inc.", "cisco.com"),
        ("Fortinet.FortiClient", "FortiClient", "Fortinet, Inc.", "fortinet.com"),
        ("Sophos.Endpoint", "Sophos Endpoint", "Sophos", "sophos.com"),
        ("Tenable.Nessus", "Nessus Agent", "Tenable", "tenable.com"),
        # Hardware / OEM
        ("Wacom.WacomTablet", "Wacom Tablet Driver", "Wacom", "wacom.com"),
        ("Logitech.GHub", "Logitech G HUB", "Logitech", "logitech.com"),
        ("Lenovo.Vantage", "Lenovo Vantage", "Lenovo", "lenovo.com"),
        ("Dell.SupportAssist", "Dell SupportAssist", "Dell", "dell.com"),
        ("HP.SupportAssistant", "HP Support Assistant", "HP", "hp.com"),
        ("Gigabyte.ControlCenter", "Gigabyte Control Center", "Gigabyte", "gigabyte.com"),
        # Misc utilities
        ("Corel.CorelDRAW", "CorelDRAW", "Corel", "corel.com"),
        ("BitTorrent.BitTorrent", "BitTorrent", "BitTorrent", "bittorrent.com"),
        ("TeamViewer.TeamViewer", "TeamViewer", "TeamViewer", "teamviewer.com"),
        ("Piriform.CCleaner", "CCleaner", "CCleaner", "ccleaner.com"),
        ("qBittorrent.qBittorrent", "qBittorrent", "qBittorrent", "qbittorrent.org"),
        ("ServiceNow.Agent", "ServiceNow Agent", "ServiceNow", "servicenow.com"),
    ]
)
def test_all_categories_normalization_and_domain_mapping(raw_package, expected_app, expected_vendor, expected_domain):
    """
    Verifies that representative applications from all 11 categories:
    1. Normalize to canonical application names without being marked UNKNOWN.
    2. Normalize to canonical vendor without being marked UNKNOWN.
    3. Resolve the expected official domain via DomainRegistryService.
    4. Pass the evidence guardrail check with their official domain.
    """
    norm_name = DetectionNormalizer.normalize_name(raw_package)
    assert norm_name == expected_app, f"For {raw_package}, expected app '{expected_app}', got '{norm_name}'"

    norm_vendor = DetectionNormalizer.normalize_publisher(None, raw_name=raw_package)
    assert norm_vendor != "UNKNOWN", f"Vendor for '{raw_package}' was unexpectedly marked UNKNOWN"
    assert norm_vendor == expected_vendor, f"For {raw_package}, expected vendor '{expected_vendor}', got '{norm_vendor}'"

    official_domains = DomainRegistryService.get_official_domains(norm_vendor)
    assert expected_domain in official_domains, (
        f"Expected domain '{expected_domain}' for vendor '{norm_vendor}', got {official_domains}"
    )

    test_evidence_url = f"https://www.{expected_domain}/legal/terms"
    assert is_valid_vendor_domain(test_evidence_url, norm_vendor, norm_name) is True, (
        f"Evidence URL '{test_evidence_url}' rejected for app '{norm_name}' / vendor '{norm_vendor}'"
    )
