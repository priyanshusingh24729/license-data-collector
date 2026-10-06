"""
Comprehensive Unit & Pipeline Accuracy Tests for License Intelligence.
Validates:
1. Complete removal of LicenseType across exports and final schemas.
2. Improved LicenseModel combining legal license type + commercial/use model.
3. Corrected bad patterns:
   - Python -> PSF License — Free/Open Source (never BSD)
   - MongoDB Compass -> SSPL-1.0 — Free to Use (preserves SSPL)
   - Office Home & Student 2021 -> Commercial — Perpetual (never Subscription)
   - MySQL Server 8.0 -> GPL-2.0 — Free/Open Source (never hijacked to Microsoft SQL Server / Per Core)
   - OpenJDK / Temurin -> GPL-2.0 with Classpath Exception — Free/Open Source
   - Steam -> Freeware (never Per Seat Subscription from consumer Subscriber Agreement)
   - Google Chrome / Update -> Freeware (never Chromium BSD)
   - Microsoft Store / Windows inbox packages -> Freeware / OS Bundled (never BSD)
4. LicenseMetric kept separate.
5. LicenseRequirement kept independent (YES, NO, CONTEXT_DEPENDENT).
6. Evidence drives results; unknown when unreliable.
7. Final schema exact 10 columns, standardized exact 17 columns.
"""

import pytest
from typing import Dict, Any

from backend.validation.license_validation_layer import LicenseValidationLayer
from backend.inventory.recognition.catalog import RecognitionCatalog
from backend.inventory.recognition.microsoft_identity_resolver import (
    MicrosoftProductIdentityResolver,
    ResolvedMicrosoftIdentity,
)
from backend.inventory.export.standardized_inventory_exporter import (
    StandardizedInventoryExporter,
    FINAL_OUTPUT_COLUMNS,
    STANDARDIZED_COLUMNS,
)
from backend.extraction.evidence_extractor import EvidenceExtractor
from backend.extraction.relevant_content_detector import RelevantContextBlock


class TestLicenseModelAccuracyAndPatterns:
    """Test factual accuracy across the 8 critical patterns."""

    def test_python_classified_as_psf_license_not_bsd(self):
        """Pattern 1: Python must be PSF License — Free/Open Source, not BSD."""
        rule = RecognitionCatalog.find_rule_by_name("Python 3.12")
        assert rule is not None, "Python 3 rule must exist in catalog"
        combined = RecognitionCatalog.derive_combined_license_model(rule)
        assert combined == "PSF License — Free/Open Source"
        assert "BSD" not in combined

        # Test exporter fallback
        rec = {"Application Name": "Python 3.11.4", "Vendor": "Python Software Foundation"}
        model = StandardizedInventoryExporter.evaluate_license_model(
            rec, classification="OPEN_SOURCE", license_required="NO", catalog_rule=rule
        )
        assert model == "PSF License — Free/Open Source"
        assert "BSD" not in model

    def test_mongodb_compass_preserves_sspl(self):
        """Pattern 2: MongoDB Compass must preserve SSPL-1.0 — Free to Use."""
        rule = RecognitionCatalog.find_rule_by_name("MongoDB Compass")
        assert rule is not None, "MongoDB Compass rule must exist in catalog"
        combined = RecognitionCatalog.derive_combined_license_model(rule)
        assert combined == "SSPL-1.0 — Free to Use"
        assert "SSPL" in combined

        # Test via exporter
        rec = {"Application Name": "MongoDB Compass", "Vendor": "MongoDB, Inc."}
        model = StandardizedInventoryExporter.evaluate_license_model(
            rec, classification="OPEN_SOURCE", license_required="NO", catalog_rule=rule
        )
        assert model == "SSPL-1.0 — Free to Use"

    def test_office_home_and_student_2021_perpetual_not_subscription(self):
        """Pattern 3: Office Home & Student 2021 must be Commercial — Perpetual, never Subscription."""
        rule = RecognitionCatalog.find_rule_by_name("Microsoft Office Home & Student 2021")
        assert rule is not None, "Office 2021 Perpetual rule must exist in catalog"
        combined = RecognitionCatalog.derive_combined_license_model(rule)
        assert combined == "Commercial — Perpetual"
        assert "Subscription" not in combined

        # Test via Validation Layer
        val_model = LicenseValidationLayer.build_combined_license_model(
            raw_model="Perpetual",
            metric="Devices",
            classification="COMMERCIAL",
            app_name="Microsoft Office Home & Student 2021",
        )
        assert val_model == "Commercial — Perpetual"

    def test_mysql_server_not_hijacked_as_microsoft_sql_server(self):
        """Pattern 4: MySQL Server 8.0 must NOT be hijacked as Microsoft SQL Server or Per Core."""
        resolved = MicrosoftProductIdentityResolver.resolve_identity(
            raw_name="MySQL Server 8.0",
            raw_package_name="MySQL Server 8.0",
            raw_publisher="Oracle Corporation",
            raw_version="8.0.34",
        )
        # MySQL must NOT resolve to Microsoft SQL Server
        if resolved:
            assert resolved.canonical_name != "Microsoft SQL Server"
            assert resolved.canonical_vendor != "Microsoft"

        # Catalog entry test
        rule = RecognitionCatalog.find_rule_by_name("MySQL Server 8.0")
        assert rule is not None, "MySQL Server rule must exist in catalog"
        assert rule.canonical_name == "MySQL Community Server"
        assert rule.canonical_vendor == "Oracle"
        combined = RecognitionCatalog.derive_combined_license_model(rule)
        assert combined == "GPL-2.0 — Free/Open Source"
        assert "Core" not in combined
        assert "NO" in rule.license_required.value

    def test_java_distinguishes_openjdk_from_oracle_subscription(self):
        """Pattern 5: OpenJDK / Temurin must be GPL-2.0 with Classpath Exception, not Commercial Subscription."""
        rule = RecognitionCatalog.find_rule_by_name("Eclipse Temurin JDK with Hotspot")
        if not rule:
            rule = RecognitionCatalog.find_rule_by_name("openjdk")
        assert rule is not None, "OpenJDK rule must exist in catalog"
        combined = RecognitionCatalog.derive_combined_license_model(rule)
        assert combined == "GPL-2.0 with Classpath Exception — Free/Open Source"
        assert "NO" in rule.license_required.value

    def test_steam_freeware_not_subscription(self):
        """Pattern 6: Steam client must be Freeware, not Per Seat Subscription."""
        rule = RecognitionCatalog.find_rule_by_name("Steam")
        assert rule is not None, "Steam rule must exist in catalog"
        combined = RecognitionCatalog.derive_combined_license_model(rule)
        assert combined == "Freeware"
        assert "Subscription" not in combined

        # Evidence extractor test: Steam Subscriber Agreement must NOT extract as Subscription
        extractor = EvidenceExtractor()
        block = RelevantContextBlock(
            text="The Steam client is distributed by Valve Corporation free of charge under the Steam Subscriber Agreement.",
            page_number=1,
            section_name="Terms",
            document_id=1,
            source_id=1,
            matched_keywords=["steam", "terms"],
        )
        facts = extractor.extract_candidates_from_block(
            block, target_vendor="Valve", target_product="Steam"
        )
        for f in facts:
            if f.fact_type.value == "LICENSE_MODEL":
                assert "Subscription" not in f.normalized_value
                assert f.normalized_value in ("Freeware", "Free")

    def test_google_chrome_freeware_not_bsd(self):
        """Pattern 7: Google Chrome binary is Freeware, not open-source BSD."""
        rule = RecognitionCatalog.find_rule_by_name("Google Chrome")
        assert rule is not None, "Google Chrome rule must exist in catalog"
        combined = RecognitionCatalog.derive_combined_license_model(rule)
        assert "Freeware" in combined or combined == "Freeware"
        assert "BSD" not in combined

    def test_microsoft_store_and_inbox_components_not_bsd(self):
        """Pattern 8: Microsoft Windows OS and inbox components are OS_BUNDLED/Freeware, not BSD."""
        assert RecognitionCatalog.is_windows_os_component("Microsoft.WindowsTerminal", "Microsoft Corporation")
        assert RecognitionCatalog.is_windows_os_component("Microsoft.GamingApp", "Microsoft Corporation")
        assert RecognitionCatalog.is_windows_os_component("Microsoft.HEIFImageExtension", "Microsoft Corporation")

        model = StandardizedInventoryExporter.evaluate_license_model(
            {"Application Name": "Microsoft.WindowsTerminal", "Vendor": "Microsoft Corporation"},
            classification="OS_BUNDLED",
            license_required="NO",
        )
        assert "BSD" not in model


class TestSchemaIntegrityAndIndependence:
    """Validates schemas, separation of Metric and Requirement, and complete absence of LicenseType."""

    def test_final_schema_exact_10_columns_no_license_type(self):
        """Final output schema must be exactly 10 columns and contain no LicenseType."""
        expected = [
            "Application Name",
            "Version",
            "OS",
            "License Required",
            "End of Support",
            "End of Life",
            "Metric",
            "Classification",
            "License Model",
            "Evidence URL",
        ]
        assert FINAL_OUTPUT_COLUMNS == expected
        assert len(FINAL_OUTPUT_COLUMNS) == 10
        assert "License Type" not in FINAL_OUTPUT_COLUMNS
        assert "license_type" not in FINAL_OUTPUT_COLUMNS
        assert "LicenseType" not in FINAL_OUTPUT_COLUMNS

    def test_standardized_17_columns_no_license_type(self):
        """Standardized schema must be exactly 17 columns and contain no LicenseType."""
        assert len(STANDARDIZED_COLUMNS) == 17
        assert "License Type" not in STANDARDIZED_COLUMNS
        assert "LicenseType" not in STANDARDIZED_COLUMNS
        assert "license_type" not in STANDARDIZED_COLUMNS
        assert "License Model" in STANDARDIZED_COLUMNS

    def test_license_metric_remains_separate(self):
        """Metric must remain distinct and not merged into LicenseModel."""
        rec = {
            "Application Name": "JetBrains IntelliJ IDEA Ultimate",
            "Vendor": "JetBrains",
            "Metric": "Users",
        }
        model = LicenseValidationLayer.build_combined_license_model(
            raw_model="Commercial — Subscription",
            metric="Users",
            classification="COMMERCIAL",
            app_name=rec["Application Name"],
        )
        assert model == "Commercial — Subscription"
        # Metric is verified separately via metadata extraction
        _, _, _, metric, _ = StandardizedInventoryExporter.evaluate_license_metadata(
            rec, classification="COMMERCIAL"
        )
        assert metric in ("Users", "USER")

    def test_license_required_remains_independent(self):
        """License Required must be independent (YES, NO, CONTEXT_DEPENDENT)."""
        # Free & open source is NO
        req_oss = StandardizedInventoryExporter.evaluate_license_required(
            {"Application Name": "Git", "Classification": "OPEN_SOURCE"},
            classification="OPEN_SOURCE"
        )
        assert req_oss == "NO"

        # Commercial paid is YES
        req_comm = StandardizedInventoryExporter.evaluate_license_required(
            {"Application Name": "Microsoft Visio", "Classification": "COMMERCIAL"},
            classification="COMMERCIAL"
        )
        assert req_comm == "YES"

    def test_unreliable_evidence_yields_unknown_not_hallucinated(self):
        """When evidence cannot reliably determine the license, fallback to Unknown."""
        model = LicenseValidationLayer.build_combined_license_model(
            raw_model=None,
            metric=None,
            classification=None,
            app_name="CustomInternalScriptXYZ",
        )
        assert model == "Unknown"
