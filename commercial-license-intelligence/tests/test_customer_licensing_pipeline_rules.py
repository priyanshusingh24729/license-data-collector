"""
Comprehensive Test Suite for Customer-Grade Backend Licensing-Classification Pipeline.

Validates the 7 Representative Business Cases:
1. Completely free software -> NO
2. Free + paid version (FREE_AND_PAID) -> YES
3. Free personal + paid commercial (FREE_AND_PAID) -> YES (e.g. Outlook for Windows)
4. Free trial + paid subscription (TRIAL / COMMERCIAL) -> YES
5. Open-source software -> NO (unless commercial paid entitlement required)
6. Paid-only software (COMMERCIAL / PAID) -> YES
7. Insufficient evidence -> Uncertainty/fallback behavior, NOT an invented NO

Also validates:
- Strict binary License Required in ('YES', 'NO')
- Proper SPDX ID isolation (spdx_id is None for proprietary, valid string for open-source)
- Official vendor source attribution (never 'SEARXNG' or search engines as primary source)
- Evidence quote verification
"""

import pytest
from unittest.mock import MagicMock, patch
from backend.validation.license_validation_layer import LicenseValidationLayer
from backend.validation.consensus_engine import ConsensusVerificationEngine
from backend.validation.searxng_evidence_validator import SearxngEvidenceValidator
from backend.validation.spdx_taxonomy import SPDXTaxonomyService
from backend.inventory.export.standardized_inventory_exporter import StandardizedInventoryExporter
from backend.sources.discovery.search_provider import SearchResult
from backend.collectors.web.collection_result import WebCollectionResult


# =========================================================================
# Case 1: Completely Free Software -> NO
# =========================================================================
def test_case_1_completely_free_software():
    """Completely free software with no applicable paid license requirement MUST be NO."""
    # Test via LicenseValidationLayer
    val = LicenseValidationLayer.validate_and_sanitize({
        "Application Name": "7-Zip (Free Archive Utility)",
        "Classification": "FREEWARE",
        "License Required": "NO",
        "License Model": "Freeware",
        "Metric": "No License Required",
    })
    assert val["License Required"] == "NO"
    assert val["Classification"] == "FREEWARE"
    assert val["Metric"] == "No License Required"

    # Test via StandardizedInventoryExporter
    exp_req = StandardizedInventoryExporter.evaluate_license_required(
        record={"Name": "7-Zip", "Classification": "FREEWARE"},
        classification="FREEWARE",
        no_license_required_val=1,
    )
    assert exp_req == "NO"


# =========================================================================
# Case 2: Free + Paid Version (Freemium / FREE_AND_PAID) -> YES
# =========================================================================
def test_case_2_free_plus_paid_version():
    """
    Applications offering both free tier and paid commercial tier (FREE_AND_PAID)
    MUST be classified as License Required = YES.
    """
    # Test via LicenseValidationLayer
    val = LicenseValidationLayer.validate_and_sanitize({
        "Application Name": "ChatGPT",
        "Classification": "FREE_AND_PAID",
        "License Required": "CONTEXT_DEPENDENT",  # Raw input before validation
        "License Model": "Freemium / Named User Subscription",
        "Metric": "Users",
    })
    assert val["License Required"] == "YES"
    assert val["Classification"] == "FREE_AND_PAID"

    # Test via ConsensusEngine
    res = ConsensusVerificationEngine.verify_and_synthesize(
        raw_name="ChatGPT",
        raw_vendor="OpenAI",
        raw_version="1.0.0",
        catalog_record={
            "canonical_product": "ChatGPT",
            "classification": "FREE_AND_PAID",
            "license_model": "Freemium / Named User Subscription",
            "metric": "Users",
        },
    )
    assert res.license_required == "YES"
    assert res.classification == "FREE_AND_PAID"

    # Test via Exporter
    exp_req = StandardizedInventoryExporter.evaluate_license_required(
        record={"Name": "ChatGPT", "Classification": "FREE_AND_PAID"},
        classification="FREE_AND_PAID",
    )
    assert exp_req == "YES"


# =========================================================================
# Case 3: Free Personal + Paid Commercial Usage -> YES (The Outlook Example)
# =========================================================================
def test_case_3_free_personal_plus_paid_commercial():
    """
    If official Microsoft evidence states:
    'The new Outlook for Windows is available free of charge for personal email accounts...
     Adding commercial work or school accounts requires an eligible Microsoft 365 subscription license.'
    The backend MUST classify:
    Classification = FREE_AND_PAID
    License Required = YES
    Source = Official Microsoft Documentation (not search engine)
    """
    mock_search = [
        SearchResult(
            url="https://support.microsoft.com/en-us/office/outlook-for-windows-overview",
            title="Outlook for Windows Licensing and Account Support",
            snippet=(
                "The new Outlook for Windows is available free of charge for personal email accounts. "
                "Adding commercial work or school accounts requires an eligible Microsoft 365 subscription license containing Exchange Online."
            ),
            engine="google",
            rank=1,
        )
    ]
    mock_coll = WebCollectionResult(
        requested_url="https://support.microsoft.com/en-us/office/outlook-for-windows-overview",
        final_url="https://support.microsoft.com/en-us/office/outlook-for-windows-overview",
        vendor="Microsoft",
        status="COLLECTED",
        title="Outlook for Windows Licensing and Account Support",
        clean_text=(
            "The new Outlook for Windows is available free of charge for personal email accounts. "
            "Adding commercial work or school accounts requires an eligible Microsoft 365 subscription license containing Exchange Online."
        ),
        markdown_content="The new Outlook for Windows is available free of charge for personal email accounts. Adding commercial work or school accounts requires an eligible Microsoft 365 subscription license containing Exchange Online.",
        tables=[],
    )

    with patch("backend.validation.searxng_evidence_validator.get_search_provider") as mock_gp, \
         patch("backend.collectors.web.web_collector.WebCollector.collect", return_value=mock_coll):

        mock_provider = MagicMock()
        mock_provider.search.return_value = mock_search
        mock_gp.return_value = mock_provider

        ev = SearxngEvidenceValidator.validate_application(
            app_name="Outlook for Windows",
            vendor="Microsoft Corporation",
            version="1.2024.0.0",
            scrape_page=True,
        )

        assert ev.classification == "FREE_AND_PAID"
        assert ev.license_required == "YES"
        assert "Official Microsoft" in ev.evidence_source or "microsoft.com" in ev.evidence_source
        assert "SEARXNG" not in ev.evidence_source
        assert "commercial work or school accounts requires an eligible Microsoft 365 subscription" in ev.evidence_quote

        # Test validation layer preserves YES
        val = LicenseValidationLayer.validate_and_sanitize({
            "Application Name": "Outlook for Windows",
            "Classification": ev.classification,
            "License Required": ev.license_required,
            "License Model": "Subscription / Free Client",
            "Metric": "Users",
        })
        assert val["License Required"] == "YES"
        assert val["Classification"] == "FREE_AND_PAID"


# =========================================================================
# Case 4: Free Trial + Paid Subscription -> YES
# =========================================================================
def test_case_4_free_trial_plus_paid_subscription():
    """Software operating under a trial model that expires into a paid subscription MUST be YES."""
    val = LicenseValidationLayer.validate_and_sanitize({
        "Application Name": "Adobe Acrobat Pro 2024",
        "Classification": "TRIAL",
        "License Required": "YES",
        "License Model": "30-Day Free Trial / Annual Subscription",
        "Metric": "Users",
    })
    assert val["License Required"] == "YES"
    assert val["Classification"] == "TRIAL"

    # Also test via Exporter
    exp_req = StandardizedInventoryExporter.evaluate_license_required(
        record={"Name": "Adobe Acrobat Pro 2024", "Classification": "TRIAL"},
        classification="TRIAL",
    )
    assert exp_req == "YES"


# =========================================================================
# Case 5: Open-Source Software -> NO (Unless commercial entitlement required)
# =========================================================================
def test_case_5_open_source_software():
    """
    Pure open-source software (MIT, Apache-2.0, GPL) MUST be License Required = NO.
    Source-available software with commercial license requirements (e.g. SSPL, BSL) MUST be YES.
    """
    # 5A: Pure Open Source (MIT) -> NO
    val_oss = LicenseValidationLayer.validate_and_sanitize({
        "Application Name": "Visual Studio Code",
        "Classification": "OPEN_SOURCE",
        "License Required": "NO",
        "License Model": "MIT License — Free/Open Source",
        "Metric": "No License Required",
    })
    assert val_oss["License Required"] == "NO"
    assert val_oss["Classification"] == "OPEN_SOURCE"

    # 5B: Commercial / source-available server requirement -> YES
    val_comm = LicenseValidationLayer.validate_and_sanitize({
        "Application Name": "MongoDB Enterprise Server",
        "Classification": "COMMERCIAL",
        "License Required": "YES",
        "License Model": "Commercial — Subscription",
        "Metric": "Servers",
    })
    assert val_comm["License Required"] == "YES"


# =========================================================================
# Case 6: Paid-Only Software -> YES
# =========================================================================
def test_case_6_paid_only_software():
    """Commercial / proprietary paid-only enterprise applications MUST be License Required = YES."""
    val = LicenseValidationLayer.validate_and_sanitize({
        "Application Name": "Microsoft SQL Server Enterprise",
        "Classification": "COMMERCIAL",
        "License Required": "YES",
        "License Model": "Commercial — Core License",
        "Metric": "Processor Cores",
    })
    assert val["License Required"] == "YES"
    assert val["Classification"] == "COMMERCIAL"
    assert val["Metric"] in ("Processor Cores", "Cores")


# =========================================================================
# Case 7: Insufficient Evidence -> Uncertainty / Fallback, NOT Invented NO
# =========================================================================
def test_case_7_insufficient_evidence_preserves_uncertainty():
    """
    When evidence is completely missing or ambiguous, the pipeline MUST NOT
    falsely invent 'NO'. It must return UNKNOWN / low confidence fallback.
    """
    res = ConsensusVerificationEngine.verify_and_synthesize(
        raw_name="SomeObscureInternalAppWithoutAnyCatalogMatch12345",
        raw_vendor="UnknownVendorLLC",
        raw_version="0.0.1",
        catalog_record={},
        winget_manifest=None,
    )
    assert res.consensus_status == "INSUFFICIENT_EVIDENCE"
    assert res.confidence == "LOW"
    assert res.classification == "UNKNOWN"
    # Crucially: it must NOT be falsely declared as License Required = NO
    assert res.license_required != "NO"


# =========================================================================
# SPDX ID Rule: Proprietary software must NOT use 'Proprietary' as SPDX ID
# =========================================================================
def test_spdx_id_proper_separation():
    """
    Do not blindly use SPDX ID = Proprietary.
    Only valid official SPDX 3.0 identifiers populate spdx_id.
    """
    # 1. Proprietary check
    assert SPDXTaxonomyService.is_valid_spdx_id("Proprietary") is False
    assert SPDXTaxonomyService.is_valid_spdx_id("Commercial") is False
    assert SPDXTaxonomyService.is_valid_spdx_id("UNKNOWN") is False
    assert SPDXTaxonomyService.get_valid_spdx_id("Commercial — Subscription") is None
    assert SPDXTaxonomyService.get_valid_spdx_id("Proprietary") is None

    # 2. Valid SPDX identifiers check
    assert SPDXTaxonomyService.is_valid_spdx_id("MIT") is True
    assert SPDXTaxonomyService.is_valid_spdx_id("Apache-2.0") is True
    assert SPDXTaxonomyService.is_valid_spdx_id("GPL-3.0-only") is True
    assert SPDXTaxonomyService.is_valid_spdx_id("SSPL-1.0") is True
    assert SPDXTaxonomyService.is_valid_spdx_id("BSL-1.1") is True

    # 3. get_valid_spdx_id extraction
    assert SPDXTaxonomyService.get_valid_spdx_id("MIT License") == "MIT"
    assert SPDXTaxonomyService.get_valid_spdx_id("Apache 2.0") == "Apache-2.0"

    # 4. License Type legal family
    assert SPDXTaxonomyService.get_license_type("Commercial", "COMMERCIAL") == "Proprietary"
    assert SPDXTaxonomyService.get_license_type("MIT", "OPEN_SOURCE") == "Open Source (MIT)"
