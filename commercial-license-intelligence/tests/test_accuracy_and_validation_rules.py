"""
Unit and Integration Tests for Commercial License Intelligence Accuracy & Validation Rules.
Verifies all 12 core requirements:
1. License Required strictly YES or NO
2. Metric controlled vocabulary & quantity independence
3. License Model agreement with Metric
4. Classification taxonomy preservation & no UNKNOWN
5. Version-aware EOL / EOS evaluation
6. Authoritative Evidence URLs and search URL rejection
7. Cross-field validation layer rules
8. Zero data destruction / 100% record preservation
9. Clean blanks instead of UNKNOWN
10. Final 10-column output schema transformation & export
11. LLM licensing prompt service and validation
"""

import pytest
import pandas as pd
import io

from backend.validation.license_validation_layer import (
    LicenseValidationLayer,
    ALLOWED_METRICS,
    ALLOWED_LICENSE_MODELS,
    ALLOWED_CLASSIFICATIONS,
    ALLOWED_LICENSE_TYPES,
)
from backend.inventory.recognition.lifecycle_service import LifecycleService
from backend.inventory.export.standardized_inventory_exporter import (
    StandardizedInventoryExporter,
    STANDARDIZED_COLUMNS,
    FINAL_OUTPUT_COLUMNS,
)
from backend.services.llm_licensing_prompt import LLMLicensingPromptService


class TestLicenseRequiredRules:
    """Requirement 1: Final License Required must contain ONLY 'YES' or 'NO'."""

    def test_license_required_strictly_yes_or_no(self):
        # Must never return UNKNOWN, CONTEXT_DEPENDENT, N/A, or blank
        test_inputs = [
            ("UNKNOWN", "YES"),
            ("CONTEXT_DEPENDENT", "YES"),
            ("N/A", "YES"),
            ("", "YES"),
            (None, "YES"),
            ("YES", "YES"),
            ("NO", "NO"),
            ("no", "NO"),
            ("yes", "YES"),
            ("NOT_APPLICABLE", "NO"),
            ("FREE", "NO"),
        ]
        for input_val, expected in test_inputs:
            rec = {"Application Name": "TestApp", "License Required": input_val}
            val = LicenseValidationLayer.validate_and_sanitize(rec)
            assert val["License Required"] in ("YES", "NO")
            assert val["License Required"] == expected

    def test_license_required_not_inferred_from_quantity(self):
        # Quantity = 0 must NOT mean NO or Users
        rec = {
            "Application Name": "Oracle Database Enterprise",
            "License Required": "YES",
            "quantity": 0,
            "Metric": "Processor Cores",
            "License Model": "Per Core",
        }
        val = LicenseValidationLayer.validate_and_sanitize(rec)
        assert val["License Required"] == "YES"
        assert val["Metric"] == "Processor Cores"


class TestMetricControlledVocabulary:
    """Requirement 2: Controlled vocabulary, quantity independence, free software rule."""

    def test_metric_controlled_vocabulary_normalization(self):
        test_cases = [
            ("User", "Users"),
            ("users", "Users"),
            ("Core", "Processor Cores"),
            ("Number of processor cores", "Processor Cores"),
            ("Processor Cores", "Processor Cores"),
            ("Number of processors", "Processors"),
            ("CAL (Client Access License)", "CAL"),
            ("Installations", "Installations"),
            ("Concurrent users", "Concurrent Users"),
            ("Concurrent devices", "Concurrent Devices"),
            ("PVU", "PVU"),
            ("No license required", "No License Required"),
        ]
        for raw, expected in test_cases:
            norm = LicenseValidationLayer.normalize_metric(raw)
            assert norm == expected
            assert norm in ALLOWED_METRICS

    def test_metric_left_blank_when_unestablished(self):
        # If metric cannot be reliably established, leave it None/blank rather than inventing
        assert LicenseValidationLayer.normalize_metric("random string") is None
        assert LicenseValidationLayer.normalize_metric("UNKNOWN") is None
        assert LicenseValidationLayer.normalize_metric("") is None
        assert LicenseValidationLayer.normalize_metric(None) is None

    def test_free_software_metric_is_no_license_required(self):
        # If License Required = NO -> Metric = No License Required
        rec = {
            "Application Name": "7-Zip",
            "License Required": "NO",
            "Metric": "Installations",  # Conflicting candidate
            "Classification": "OPEN_SOURCE",
        }
        val = LicenseValidationLayer.validate_and_sanitize(rec)
        assert val["License Required"] == "NO"
        assert val["Metric"] == "No License Required"
        assert val["License Model"] in ("No License Required", "LGPL — Free/Open Source")


class TestLicenseModelRules:
    """Requirement 3: License Model controlled vocabulary and logical agreement with Metric."""

    def test_license_model_logically_agrees_with_metric(self):
        # Users -> Per User or Subscription
        rec_user = {
            "Application Name": "Microsoft 365",
            "License Required": "YES",
            "Metric": "Users",
            "License Model": None,
        }
        val_user = LicenseValidationLayer.validate_and_sanitize(rec_user)
        assert val_user["License Model"] in ("Per User", "Subscription", "Commercial — Per Seat Subscription")

        # Processor Cores -> Per Core
        rec_core = {
            "Application Name": "SQL Server Enterprise",
            "License Required": "YES",
            "Metric": "Processor Cores",
            "License Model": None,
        }
        val_core = LicenseValidationLayer.validate_and_sanitize(rec_core)
        assert val_core["License Model"] in ("Per Core", "Per Core / Server + CAL", "Commercial — Per Core")

        # Devices -> Per Device
        rec_dev = {
            "Application Name": "Antivirus Client",
            "License Required": "YES",
            "Metric": "Devices",
            "License Model": None,
        }
        val_dev = LicenseValidationLayer.validate_and_sanitize(rec_dev)
        assert val_dev["License Model"] in ("Per Device", "Commercial — Per Device")

        # No License Required -> No License Required
        rec_nlr = {
            "Application Name": "Notepad++",
            "License Required": "NO",
            "Metric": "No License Required",
            "License Model": "Per User",  # Contradictory model
        }
        val_nlr = LicenseValidationLayer.validate_and_sanitize(rec_nlr)
        assert val_nlr["License Model"] in ("No License Required", "GPL-3.0 — Free/Open Source")


class TestClassificationRules:
    """Requirement 4 & 10: Never UNKNOWN, preserve taxonomy, blank when unestablished."""

    def test_classification_normalization_and_no_unknown(self):
        assert LicenseValidationLayer.normalize_classification("commercial") == "COMMERCIAL"
        assert LicenseValidationLayer.normalize_classification("OPEN_SOURCE") == "OPEN_SOURCE"
        assert LicenseValidationLayer.normalize_classification("freeware") == "FREEWARE"
        assert LicenseValidationLayer.normalize_classification("free") == "FREE"
        assert LicenseValidationLayer.normalize_classification("UNKNOWN") is None
        assert LicenseValidationLayer.normalize_classification("N/A") is None
        assert LicenseValidationLayer.normalize_classification("") is None
        assert LicenseValidationLayer.normalize_classification(None) is None


class TestLifecycleRules:
    """Requirement 5: Version-aware EOL/EOS, never default to 0."""

    def test_version_aware_eol_eos_known_versions(self):
        # Windows Server 2008 is EOL (2020) -> 1
        ws2008 = LifecycleService.evaluate_lifecycle("Windows Server", "2008")
        assert ws2008.is_eol == 1
        assert ws2008.is_eos == 1

        # Windows Server 2022 is currently supported -> 0
        ws2022 = LifecycleService.evaluate_lifecycle("Windows Server", "2022")
        assert ws2022.is_eol == 0
        assert ws2022.is_eos == 0

        # Python 2.7 is EOL -> 1
        py27 = LifecycleService.evaluate_lifecycle("Python", "2.7")
        assert py27.is_eol == 1
        assert py27.is_eos == 1

        # Python 3.12 is supported -> 0
        py312 = LifecycleService.evaluate_lifecycle("Python", "3.12")
        assert py312.is_eol == 0

    def test_unknown_software_does_not_falsely_return_zero(self):
        # For software without lifecycle data, do NOT default to 0; return None
        unknown_app = LifecycleService.evaluate_lifecycle("Random Proprietary Internal Tool", "1.0")
        assert unknown_app.is_eol is None
        assert unknown_app.is_eos is None


class TestEvidenceURLRules:
    """Requirement 6: Authoritative URLs, reject search engines & fake URLs."""

    def test_search_engine_urls_rejected(self):
        bad_urls = [
            "https://www.google.com/search?q=microsoft+office+license",
            "https://www.bing.com/search?q=sql+server",
            "https://duckduckgo.com/?q=python+license",
            "http://searx.local/search?q=7zip",
            "https://search.yahoo.com/search?p=test",
            "fake_url_without_http",
            "https://example.com/search?q=test",
        ]
        for url in bad_urls:
            assert LicenseValidationLayer.validate_evidence_url(url) is None

    def test_authoritative_vendor_urls_accepted(self):
        valid_urls = [
            "https://learn.microsoft.com/en-us/lifecycle/products/windows-server-2022",
            "https://www.microsoft.com/licensing/docs/view/Licensing-Guides",
            "https://www.oracle.com/corporate/pricing/specialty-topics.html",
            "https://docs.docker.com/subscription/details/",
            "https://ubuntu.com/about/release-cycle",
        ]
        for url in valid_urls:
            assert LicenseValidationLayer.validate_evidence_url(url) == url


class TestCrossFieldValidationLayer:
    """Requirement 8: Backend validation consistency rules."""

    def test_metric_users_forces_license_required_yes(self):
        rec = {
            "Application Name": "Enterprise App",
            "License Required": "NO",
            "Metric": "Users",
        }
        val = LicenseValidationLayer.validate_and_sanitize(rec)
        assert val["License Required"] == "YES"
        assert val["Metric"] == "Users"

    def test_metric_cores_forces_license_required_yes(self):
        rec = {
            "Application Name": "Database Server",
            "License Required": "NO",
            "Metric": "Processor Cores",
        }
        val = LicenseValidationLayer.validate_and_sanitize(rec)
        assert val["License Required"] == "YES"
        assert val["Metric"] == "Processor Cores"

    def test_metric_no_license_required_forces_license_required_no(self):
        rec = {
            "Application Name": "Open Source Tool",
            "License Required": "YES",
            "Metric": "No License Required",
        }
        val = LicenseValidationLayer.validate_and_sanitize(rec)
        assert val["License Required"] == "NO"
        assert val["Metric"] == "No License Required"


class TestStandardizedInventoryExporterFinalSchema:
    """Requirement 9, 10, 12: 10-column Final Output Schema & inventory preservation."""

    def test_preserve_100_percent_of_inventory_records(self):
        sample_records = [
            {"Name": "Microsoft 365 Apps", "raw_application": "Microsoft 365 Apps", "raw_vendor": "Microsoft", "raw_version": "16.0", "Operating_System": "Windows"},
            {"Name": "Google Chrome", "raw_application": "Google Chrome", "raw_vendor": "Google", "raw_version": "120.0", "Operating_System": "Windows"},
            {"Name": "Custom Tool Without Info", "raw_application": "Custom Tool Without Info", "raw_vendor": "Internal", "raw_version": "0.1", "Operating_System": "Windows"},
        ]
        df_final = StandardizedInventoryExporter.transform_to_final_schema(sample_records)
        assert len(df_final) == 3
        assert list(df_final.columns) == FINAL_OUTPUT_COLUMNS

        # Check export bytes
        csv_bytes = StandardizedInventoryExporter.to_final_csv_bytes(df_final)
        assert isinstance(csv_bytes, bytes)
        assert len(csv_bytes) > 0

        # Read back CSV and confirm 10 columns
        df_read = pd.read_csv(io.BytesIO(csv_bytes))
        assert list(df_read.columns) == FINAL_OUTPUT_COLUMNS
        assert len(df_read) == 3

    def test_excel_export_bytes_generated(self):
        sample_records = [
            {"Name": "PostgreSQL", "raw_application": "PostgreSQL", "raw_vendor": "PostgreSQL Global Development Group", "raw_version": "16.1", "Operating_System": "Windows"},
        ]
        df_final = StandardizedInventoryExporter.transform_to_final_schema(sample_records)
        xlsx_bytes = StandardizedInventoryExporter.to_final_excel_bytes(df_final)
        assert isinstance(xlsx_bytes, bytes)
        assert len(xlsx_bytes) > 1000


class TestLLMLicensingPromptService:
    """Requirement 11: LLM prompt generation and validation."""

    def test_build_user_prompt_contains_warning_against_quantity_inference(self):
        prompt = LLMLicensingPromptService.build_user_prompt(
            application_name="Microsoft Word",
            version="2021",
            operating_system="Windows",
            publisher="Microsoft",
            inventory_quantity=0,
        )
        assert "Microsoft Word" in prompt
        assert "2021" in prompt
        assert "WARNING: Do NOT use this count to infer licensing metric" in prompt

    def test_parse_and_validate_llm_response_enforces_rules(self):
        mock_llm_json = """
        {
            "application_name": "Visual Studio Code",
            "version": "1.85.0",
            "os": "Windows",
            "license_required": "NO",
            "metric": "Installations",
            "license_model": "Freeware",
            "classification": "FREE",
            "is_end_of_support": null,
            "is_end_of_life": null,
            "evidence_url": "https://code.visualstudio.com/License"
        }
        """
        validated = LLMLicensingPromptService.parse_and_validate_response(mock_llm_json)
        assert validated["Application Name"] == "Visual Studio Code"
        assert validated["License Required"] == "NO"
        # Since License Required = NO, Metric must be No License Required
        assert validated["Metric"] == "No License Required"
        assert validated["License Model"] in ("No License Required", "Freeware", "MIT — Free/Open Source")
        assert validated["Classification"] == "FREE"


class TestCombinedLicenseModelAndNoLicenseTypeColumn:
    """Test improved combined LicenseModel (legal + commercial) and total removal of License Type column."""

    def test_combined_license_model_output(self):
        # 1. MIT — Free / MIT — Free/Open Source
        assert LicenseValidationLayer.build_combined_license_model("MIT — Free") == "MIT — Free"
        assert LicenseValidationLayer.build_combined_license_model("MIT", app_name="Visual Studio Code") == "MIT — Free/Open Source"
        
        # 2. Apache-2.0 — Free/Open Source
        assert LicenseValidationLayer.build_combined_license_model("Apache-2.0") == "Apache-2.0 — Free/Open Source"
        
        # 3. GPL-2.0 / GPL-3.0 — Free/Open Source
        assert LicenseValidationLayer.build_combined_license_model("GPL-2.0", app_name="Git") == "GPL-2.0 — Free/Open Source"
        assert LicenseValidationLayer.build_combined_license_model("GPL-3.0", app_name="Notepad++") == "GPL-3.0 — Free/Open Source"
        
        # 4. Proprietary — Subscription & Perpetual
        assert LicenseValidationLayer.build_combined_license_model("Subscription", classification="PROPRIETARY") == "Proprietary — Subscription"
        assert LicenseValidationLayer.build_combined_license_model("Perpetual", classification="PROPRIETARY") == "Proprietary — Perpetual"
        
        # 5. Commercial — Per Seat Subscription & Per Core
        assert LicenseValidationLayer.build_combined_license_model("Subscription", classification="COMMERCIAL", metric="Users") == "Commercial — Per Seat Subscription"
        assert LicenseValidationLayer.build_combined_license_model("Per Core", classification="COMMERCIAL", metric="Processor Cores") == "Commercial — Per Core"

    def test_three_way_separation_preserved_in_pipeline(self):
        # LicenseModel = complete description (legal license + commercial model)
        # LicenseMetric = consumption metric
        # LicenseRequired = obligation (YES/NO)
        rec = {
            "Application Name": "Docker Desktop",
            "raw_application": "Docker Desktop",
            "raw_vendor": "Docker",
            "raw_version": "4.26.1",
            "Operating_System": "Windows",
            "Classification": "COMMERCIAL",
            "License Required": "YES",
            "License Model": "Subscription",
            "Metric": "Users",
        }
        val = LicenseValidationLayer.validate_and_sanitize(rec)
        assert val["License Required"] == "YES"
        assert val["License Model"] == "Commercial — Per Seat Subscription"
        assert val["Metric"] == "Users"
        # Must NOT contain License Type
        assert "License Type" not in val
        assert "LicenseType" not in val
        assert "license_type" not in val

    def test_final_schema_contains_no_license_type_column(self):
        sample_records = [
            {"Name": "7-Zip", "raw_application": "7-Zip", "raw_vendor": "Igor Pavlov", "raw_version": "23.01", "Operating_System": "Windows"},
            {"Name": "Microsoft 365 Apps", "raw_application": "Microsoft 365 Apps", "raw_vendor": "Microsoft", "raw_version": "16.0", "Operating_System": "Windows"},
        ]
        df_final = StandardizedInventoryExporter.transform_to_final_schema(sample_records)
        assert "License Type" not in df_final.columns
        assert "LicenseType" not in df_final.columns
        assert list(df_final.columns) == FINAL_OUTPUT_COLUMNS
        assert len(FINAL_OUTPUT_COLUMNS) == 10
        
        row_7zip = df_final[df_final["Application Name"].str.contains("7-Zip")].iloc[0]
        assert "LGPL" in row_7zip["License Model"] or "Free/Open Source" in row_7zip["License Model"]
        
        row_m365 = df_final[df_final["Application Name"].str.contains("Microsoft 365")].iloc[0]
        assert "Commercial" in row_m365["License Model"] or "Subscription" in row_m365["License Model"]

    def test_standardized_17_column_schema_has_no_license_type(self):
        assert len(STANDARDIZED_COLUMNS) == 17
        assert "License Type" not in STANDARDIZED_COLUMNS
        assert "LicenseType" not in STANDARDIZED_COLUMNS
        assert STANDARDIZED_COLUMNS[-1] == "License Model"
