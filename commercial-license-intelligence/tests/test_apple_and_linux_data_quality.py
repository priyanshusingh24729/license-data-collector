"""
Tests for Apple Product Resolution, Linux System Package Classification,
and Anti-Contamination Guardrails (Step 23 Quality Hardening).
"""

import pytest
from backend.inventory.recognition.apple_identity_resolver import AppleProductIdentityResolver
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
from backend.inventory.detection.qualification_filter import (
    ApplicationQualificationFilter,
    QualificationCategory,
    LinuxSystemPackageFilter,
    MacOSSystemComponentFilter,
)
from backend.validation.searxng_evidence_validator import (
    SearxngEvidenceValidator,
    is_valid_vendor_domain,
)
from backend.sources.discovery.domain_registry import DomainRegistryService


class TestAppleProductResolution:
    """Verifies deterministic identification and classification of Apple applications."""

    def test_apple_builtin_desktop_utilities(self):
        apps = ["About This Mac", "Time Machine", "Safari", "Preview", "Activity Monitor", "Calculator", "Finder"]
        for app in apps:
            res = AppleProductIdentityResolver.resolve_apple_product(name=app, vendor="apple")
            assert res is not None, f"Failed to resolve {app}"
            assert res.is_apple is True
            assert res.canonical_vendor == "Apple Inc."
            assert res.classification == "OS_BUNDLED"
            assert res.license_required == "NO"
            assert res.evidence_status == "VERIFIED"
            assert "apple.com" in res.evidence_url
            assert "docker.com" not in res.evidence_url
            assert "microsoft.com" not in res.evidence_url
            assert "git-scm.com" not in res.evidence_url

    def test_apple_free_productivity_apps(self):
        apps = ["Keynote", "Pages", "Numbers", "iMovie", "GarageBand"]
        for app in apps:
            res = AppleProductIdentityResolver.resolve_apple_product(name=app, vendor="Apple Inc.")
            assert res is not None, f"Failed to resolve {app}"
            assert res.classification == "FREEWARE"
            assert res.license_required == "NO"
            assert res.evidence_status == "VERIFIED"
            assert "apple.com" in res.evidence_url

    def test_apple_paid_professional_software(self):
        pro_apps = ["Final Cut Pro", "Logic Pro", "Motion", "Compressor", "MainStage"]
        for app in pro_apps:
            res = AppleProductIdentityResolver.resolve_apple_product(name=app, vendor="Apple Inc.")
            assert res is not None, f"Failed to resolve {app}"
            assert res.classification == "COMMERCIAL"
            assert res.license_required == "YES"
            assert res.availability == "PAID_ONLY"
            assert res.evidence_status == "VERIFIED"
            assert "apple.com" in res.evidence_url

    def test_apple_developer_tools(self):
        dev_tools = ["Xcode", "Instruments", "Simulator", "FileMerge", "Reality Composer Pro", "Create ML"]
        for tool in dev_tools:
            res = AppleProductIdentityResolver.resolve_apple_product(name=tool, vendor="Apple")
            assert res is not None, f"Failed to resolve {tool}"
            assert res.classification == "FREEWARE"
            assert res.license_required == "NO"
            assert res.evidence_status == "VERIFIED"

    def test_apple_internal_daemons_and_helpers(self):
        daemons = [
            "50onPaletteServer", "identityservicesd", "imagent", "rcd",
            "ABAssistantService", "AirScanScanner", "AppleMobileDeviceHelper",
            "AOSAlertManager", "loginwindow", "ControlStrip", "DFRHUD"
        ]
        for daemon in daemons:
            res = AppleProductIdentityResolver.resolve_apple_product(name=daemon, vendor="apple")
            assert res is not None, f"Failed to resolve daemon {daemon}"
            assert res.classification == "OS_BUNDLED"
            assert res.license_required == "NO"
            assert res.license_model == "Operating System Internal Component"
            assert "apple.com" in res.evidence_url

    def test_hybrid_resolver_apple_integration(self):
        h = HybridLicenseEngine.resolve_hybrid_record(app_id=None, name="Time Machine", publisher="apple")
        assert h["vendor"] == "Apple Inc."
        assert h["classification"] == "OS_BUNDLED"
        assert h["license_required"] == "NO"
        assert "apple.com" in h["evidence_url"]
        assert "sql-server" not in h["evidence_url"].lower()


class TestLinuxSystemPackageResolution:
    """Verifies identification and classification of Linux/Debian system packages."""

    def test_linux_core_utilities(self):
        core_pkgs = ["bash", "sed", "grep", "coreutils", "tar", "systemd", "dpkg", "apt", "cron", "cups"]
        for pkg in core_pkgs:
            is_lnx, reason, cat = LinuxSystemPackageFilter.is_linux_system_package(
                name=pkg, vendor="Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>"
            )
            assert is_lnx is True, f"Failed to recognize {pkg}"

    def test_ubuntu_maintainer_packages(self):
        maintainer_pkgs = ["accountsservice", "acl", "acpid", "adduser", "adwaita-icon-theme", "alsa", "anacron"]
        for pkg in maintainer_pkgs:
            is_lnx, reason, cat = LinuxSystemPackageFilter.is_linux_system_package(
                name=pkg, vendor="Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>"
            )
            assert is_lnx is True, f"Failed to recognize maintainer package {pkg}"

    def test_linux_shared_libraries_and_kernels(self):
        sys_pkgs = ["libc6", "libssl3", "libasound2", "libgtk-3-0", "linux-image-6.14.0-35-generic", "fonts-dejavu-core"]
        for pkg in sys_pkgs:
            is_lnx, reason, cat = LinuxSystemPackageFilter.is_linux_system_package(name=pkg)
            assert is_lnx is True, f"Failed to recognize {pkg}"

    def test_hybrid_resolver_linux_packages_no_microsoft_urls(self):
        h = HybridLicenseEngine.resolve_hybrid_record(
            app_id=None,
            name="bash",
            publisher="Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>"
        )
        assert h["classification"] == "LINUX_SYSTEM_PACKAGE"
        assert h["license_required"] == "NO"
        assert "visualstudio.microsoft.com" not in h["evidence_url"]
        assert "docker.com" not in h["evidence_url"]
        assert "ubuntu.com" in h["evidence_url"]


class TestAntiContaminationGuardrails:
    """Verifies that no cross-contamination of major vendor URLs can occur."""

    def test_docker_url_guardrail(self):
        docker_url = "https://www.docker.com/legal/docker-software-end-user-license-agreement/"
        # Valid for Docker
        assert is_valid_vendor_domain(docker_url, "Docker Inc.", app_name="Docker Desktop") is True
        # Blocked for unrelated software
        assert is_valid_vendor_domain(docker_url, "Advanced Micro Devices Inc.", app_name="AMD Radeon Software") is False
        assert is_valid_vendor_domain(docker_url, "AnyDesk Software GmbH", app_name="AnyDesk") is False
        assert is_valid_vendor_domain(docker_url, "apple", app_name="Install in Progress") is False
        assert is_valid_vendor_domain(docker_url, "Canonical", app_name="Ubuntu Pro Client") is False

    def test_microsoft_url_guardrail(self):
        ms_url = "https://visualstudio.microsoft.com/license-terms/"
        # Valid for Microsoft
        assert is_valid_vendor_domain(ms_url, "Microsoft", app_name="Visual Studio") is True
        # Blocked for non-Microsoft software
        assert is_valid_vendor_domain(ms_url, "Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>", app_name="bash") is False
        assert is_valid_vendor_domain(ms_url, "ALCPU", app_name="Core Temp") is False
        assert is_valid_vendor_domain(ms_url, "Amazon", app_name="Send to Kindle") is False

    def test_git_and_python_url_guardrails(self):
        git_url = "https://git-scm.com/about/free-and-open-source"
        # Valid for Git
        assert is_valid_vendor_domain(git_url, "The Git Development Community", app_name="Git") is True
        # Blocked for Apple utilities
        assert is_valid_vendor_domain(git_url, "apple", app_name="About This Mac") is False
        assert is_valid_vendor_domain(git_url, "apple", app_name="Mission Control") is False

        python_url = "https://docs.python.org/3/license.html"
        # Valid for Python
        assert is_valid_vendor_domain(python_url, "Python Software Foundation", app_name="Python") is True
        # Blocked for OpenOffice / LibreOffice
        assert is_valid_vendor_domain(python_url, "Apache Software Foundation", app_name="OpenOffice 4.0.0") is False
        assert is_valid_vendor_domain(python_url, "The Document Foundation", app_name="LibreOffice") is False
