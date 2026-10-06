"""
Unit & Integration Tests for Xbox Product Identity and Licensing Classification.

Verifies:
1. Exact Canonical Identity resolution (no generic 'Xbox' merge)
2. Xbox app for Windows (Freeware Store app, separate from Game Pass)
3. Xbox Game Bar (OS_BUNDLED Windows feature)
4. Xbox Game Pass (Paid subscription entitlement)
5. Xbox Gaming Services (Supporting background component)
6. Xbox Identity Provider (OS authentication module)
7. Xbox Speech-to-Text Overlay (OS accessibility component)
8. Entitlement separation (Xbox app installed != Game Pass subscription owned)
"""

import pytest
from backend.inventory.recognition.microsoft_identity_resolver import (
    MicrosoftProductIdentityResolver,
    WindowsProductCategory,
)
from backend.inventory.recognition.alias_system import ApplicationAliasSystem
from backend.research.windows_product_adapter import WindowsProductResearchAdapter
from backend.validation.microsoft_evidence_validator import MicrosoftEvidenceValidator
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine


class TestXboxIdentityClassification:
    """Test suite for exact Xbox product identification and licensing classification."""

    def test_xbox_app_for_windows_resolution(self):
        """1. Xbox app for Windows: Free Store companion app, separate from Game Pass."""
        # Test resolution from package name
        id_pkg = MicrosoftProductIdentityResolver.resolve_identity(
            raw_name="Microsoft.GamingApp_26.2601.1001.0_x64__8wekyb3d8bbwe",
            raw_publisher="Microsoft Corporation",
            raw_package_name="Microsoft.GamingApp",
        )
        assert id_pkg.canonical_name == "Xbox app for Windows"
        assert id_pkg.product_type == WindowsProductCategory.MICROSOFT_STORE_APP

        # Test research & validation
        research = WindowsProductResearchAdapter.research_product(id_pkg)
        assert research.classification == "FREEWARE"
        assert research.license_required == "NO"
        assert "Game Pass" in research.license_model or "Freeware" in research.license_model

        # Test full hybrid resolution
        rec = HybridLicenseEngine.resolve_hybrid_record(
            app_id=None,
            name="Xbox",
            publisher="Microsoft Corporation",
            version="26.2601.1001.0",
        )
        assert rec["application"] == "Xbox app for Windows"
        assert rec["classification"] in ("FREEWARE", "OS_BUNDLED")
        assert rec["license_required"] == "NO"
        assert rec["availability"] in ("FREE", "BUNDLED")

    def test_xbox_game_bar_resolution(self):
        """2. Xbox Game Bar: Built-in Windows gaming overlay."""
        id_pkg = MicrosoftProductIdentityResolver.resolve_identity(
            raw_name="Microsoft.XboxGamingOverlay_7.126.1102.0_x64__8wekyb3d8bbwe",
            raw_publisher="Microsoft Corporation",
            raw_package_name="Microsoft.XboxGamingOverlay",
        )
        assert id_pkg.canonical_name == "Xbox Game Bar"
        assert id_pkg.product_type == WindowsProductCategory.WINDOWS_INBOX_APP

        research = WindowsProductResearchAdapter.research_product(id_pkg)
        assert research.classification == "OS_BUNDLED"
        assert research.license_required == "NO"
        assert research.availability == "BUNDLED"

        rec = HybridLicenseEngine.resolve_hybrid_record(
            app_id=None,
            name="Xbox Game Bar",
            publisher="Microsoft",
            version="7.126.1102.0",
        )
        assert rec["application"] == "Xbox Game Bar"
        assert rec["classification"] == "OS_BUNDLED"
        assert rec["license_required"] == "NO"

    def test_xbox_gaming_services_resolution(self):
        """3. Xbox Gaming Services: Supporting background system dependency."""
        id_pkg = MicrosoftProductIdentityResolver.resolve_identity(
            raw_name="Microsoft.GamingServices",
            raw_publisher="Microsoft Corporation",
            raw_package_name="Microsoft.GamingServices",
        )
        assert id_pkg.canonical_name == "Xbox Gaming Services"
        assert id_pkg.product_type == WindowsProductCategory.SYSTEM_DEPENDENCY

        research = WindowsProductResearchAdapter.research_product(id_pkg)
        assert research.classification == "OS_BUNDLED"
        assert research.license_required == "NO"

        rec = HybridLicenseEngine.resolve_hybrid_record(
            app_id=None,
            name="Gaming Services",
            publisher="Microsoft Corporation",
        )
        assert rec["application"] == "Xbox Gaming Services"
        assert rec["classification"] == "OS_BUNDLED"
        assert rec["license_required"] == "NO"

    def test_xbox_identity_provider_resolution(self):
        """4. Xbox Identity Provider: OS authentication module."""
        id_pkg = MicrosoftProductIdentityResolver.resolve_identity(
            raw_name="Microsoft.XboxIdentityProvider",
            raw_publisher="Microsoft Corporation",
            raw_package_name="Microsoft.XboxIdentityProvider",
        )
        assert id_pkg.canonical_name == "Xbox Identity Provider"
        assert id_pkg.product_type == WindowsProductCategory.WINDOWS_OS_COMPONENT

        research = WindowsProductResearchAdapter.research_product(id_pkg)
        assert research.classification == "OS_BUNDLED"
        assert research.license_required == "NO"

    def test_xbox_speech_to_text_overlay_resolution(self):
        """5. Xbox Speech-to-Text Overlay: Accessibility component."""
        id_pkg = MicrosoftProductIdentityResolver.resolve_identity(
            raw_name="Microsoft.XboxSpeechToTextOverlay",
            raw_publisher="Microsoft Corporation",
            raw_package_name="Microsoft.XboxSpeechToTextOverlay",
        )
        assert id_pkg.canonical_name == "Game Speech Window (Xbox Speech-to-Text Overlay)"
        assert id_pkg.product_type == WindowsProductCategory.WINDOWS_OS_COMPONENT

        research = WindowsProductResearchAdapter.research_product(id_pkg)
        assert research.classification == "OS_BUNDLED"
        assert research.license_required == "NO"

    def test_xbox_game_pass_subscription_entitlement(self):
        """6. Xbox Game Pass: Paid commercial subscription entitlement."""
        id_res = MicrosoftProductIdentityResolver.resolve_identity(
            raw_name="Xbox Game Pass",
            raw_publisher="Microsoft",
        )
        assert id_res.canonical_name == "Xbox Game Pass"
        assert id_res.product_type == WindowsProductCategory.COMMERCIAL_APPLICATION

        research = WindowsProductResearchAdapter.research_product(id_res)
        assert research.classification == "COMMERCIAL"
        assert research.license_required == "YES"
        assert research.availability == "PAID_ONLY"
        assert research.license_metric == "USER"

    def test_entitlement_separation_no_false_commercial_claim(self):
        """7. Entitlement separation: Xbox app detection does NOT claim Game Pass subscription."""
        rec = HybridLicenseEngine.resolve_hybrid_record(
            app_id=None,
            name="Xbox",
            publisher="Microsoft",
            version="26.2601.1001.0",
        )
        # Must be FREEWARE or OS_BUNDLED, not COMMERCIAL
        assert rec["classification"] in ("FREEWARE", "OS_BUNDLED")
        assert rec["license_required"] == "NO"
        assert rec["application"] != "Xbox Game Pass"
        assert rec["application"] == "Xbox app for Windows"

    def test_distinct_products_not_merged_into_generic_xbox(self):
        """8. Verification that 6 distinct products resolve to distinct canonical names."""
        raw_names = [
            ("Microsoft.GamingApp", "Xbox app for Windows"),
            ("Microsoft.XboxGamingOverlay", "Xbox Game Bar"),
            ("Microsoft.GamingServices", "Xbox Gaming Services"),
            ("Microsoft.XboxIdentityProvider", "Xbox Identity Provider"),
            ("Microsoft.XboxSpeechToTextOverlay", "Game Speech Window (Xbox Speech-to-Text Overlay)"),
            ("Xbox Game Pass", "Xbox Game Pass"),
        ]

        resolved_names = set()
        for raw, expected_canonical in raw_names:
            identity = MicrosoftProductIdentityResolver.resolve_identity(
                raw_name=raw,
                raw_publisher="Microsoft Corporation",
                raw_package_name=raw,
            )
            assert identity.canonical_name == expected_canonical
            assert identity.canonical_name != "Xbox"
            resolved_names.add(identity.canonical_name)

        # All 6 must be completely unique
        assert len(resolved_names) == 6
