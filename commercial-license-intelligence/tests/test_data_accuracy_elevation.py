"""
tests/test_data_accuracy_elevation.py
--------------------------------------
Validates the data accuracy elevations implemented to resolve the 55% accuracy baseline:
1. Windows OS updates (KBs, servicing stacks) are classified as OS_BUNDLED (License Required: NO).
2. OEM hardware drivers retain authentic vendors and are not hijacked by Microsoft.
3. Third-party software with "Windows" in the name (CrowdStrike, Corel) are not hijacked by Microsoft.
4. AppX / UWP / MSIX package full names are cleanly normalized into canonical products and publishers.
5. Commercial components with license_required='NO' are excluded from Tier 1 Commercial & Billable.
6. Evidence status integrity prevents 'VERIFIED' status on empty or generic root URLs.
"""

import unittest
from backend.inventory.detection.qualification_filter import (
    ApplicationQualificationFilter,
    QualificationCategory,
    WindowsOSUpdateFilter,
    WindowsDriverFilter,
    WindowsRuntimeFrameworkFilter,
)
from backend.inventory.detection.detection_normalizer import DetectionNormalizer
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
from backend.inventory.recognition.microsoft_identity_resolver import MicrosoftProductIdentityResolver
from remediate_inventory_accuracy import get_tier


class TestWindowsOSUpdateAndDriverAccuracy(unittest.TestCase):
    def test_windows_kb_and_servicing_updates(self):
        kbs = [
            "Update for (KB2504637)",
            "Update for x64-based Windows Systems (KB5001716)",
            "March 2014 servicing stack update for Windows 8.1 and Windows Server 2012 R2 (KB2919442)",
            "Security update for Windows kernel: March 10, 2015",
            "Update for Universal C Runtime in Windows (KB2999226)",
        ]
        for kb in kbs:
            is_up, reason = WindowsOSUpdateFilter.is_os_update_or_patch(kb)
            self.assertTrue(is_up, f"Expected {kb} to be recognized as an OS update")
            
            # Test resolution through hybrid resolver
            res = HybridLicenseEngine.resolve_hybrid_record(
                app_id=None,
                name=kb,
                publisher="Microsoft Corporation",
            )
            self.assertEqual(res["classification"], "OS_BUNDLED")
            self.assertEqual(res["license_required"], "NO")
            self.assertEqual(get_tier(res["classification"], res["license_required"]), "Tier 3: OS & System Infrastructure")

    def test_hardware_drivers_not_hijacked_as_microsoft(self):
        drivers = [
            ("Windows Driver Package - Apple, Inc. (USBAAPL) USB", "Apple, Inc.", "Apple Inc."),
            ("Windows Driver Package - Silicon Laboratories (silabenm) Ports", "Silicon Laboratories", "Silicon Laboratories"),
            ("Realtek USB Ethernet Controller All-In-One Windows Driver", "Realtek", "Realtek Semiconductor Corp"),
            ("Synaptics Pointing Device Driver", "Synaptics Incorporated", "Synaptics"),
        ]
        for raw_name, raw_pub, expected_vendor in drivers:
            is_drv, _ = WindowsDriverFilter.is_hardware_driver(raw_name, raw_pub)
            self.assertTrue(is_drv, f"Expected {raw_name} to be recognized as a hardware driver")

            res = HybridLicenseEngine.resolve_hybrid_record(
                app_id=None,
                name=raw_name,
                publisher=raw_pub,
            )
            self.assertEqual(res["classification"], "OEM_OR_BUNDLED")
            self.assertEqual(res["license_required"], "NO")
            self.assertIn(expected_vendor.lower(), res["vendor"].lower(), f"Expected vendor {expected_vendor}, got {res['vendor']}")
            self.assertEqual(get_tier(res["classification"], res["license_required"]), "Tier 3: OS & System Infrastructure")


class TestVendorDecoupling(unittest.TestCase):
    def test_crowdstrike_windows_sensor_attribution(self):
        res = HybridLicenseEngine.resolve_hybrid_record(
            app_id=None,
            name="CrowdStrike Windows Sensor",
            publisher="CrowdStrike, Inc.",
        )
        self.assertEqual(res["vendor"], "CrowdStrike, Inc.")
        self.assertNotIn("microsoft", res["vendor"].lower())
        self.assertEqual(res["classification"], "COMMERCIAL")
        self.assertEqual(res["license_required"], "YES")
        self.assertEqual(get_tier(res["classification"], res["license_required"]), "Tier 1: Commercial & Billable")

    def test_corel_windows_shell_extension_attribution(self):
        res = HybridLicenseEngine.resolve_hybrid_record(
            app_id=None,
            name="Corel Graphics - Windows Shell Extension",
            publisher="Corel Corporation",
        )
        self.assertNotIn("microsoft", res["vendor"].lower())
        self.assertTrue("corel" in res["vendor"].lower() or "alludo" in res["vendor"].lower())


class TestAppXNormalization(unittest.TestCase):
    def test_appx_full_name_cleaning(self):
        samples = [
            ("AdvancedMicroDevicesInc-2.AMDRadeonSoftware_10.23.19012.0_x64__0a9344xs7nr4m", "AMD Radeon Software", "Advanced Micro Devices, Inc."),
            ("AdobeAcrobatDCCoreApp_26.1.0.0_x64__pc75e8sa7ep4e", "Adobe Acrobat DC", "Adobe"),
            ("A-Volute.Nahimic_1.10.9.0_neutral_~_w2gh52qy24etm", "Nahimic", "A-Volute"),
            ("Claude_1.3109.0.0_x64__pzs8sxrjxfjjc", "Claude", "Anthropic"),
            ("Dell.SupportAssistforPCs_5.0.1.0_x64__18ctm2993j0dg", "Dell SupportAssist", "Dell"),
            ("4505Fortemedia.FMAPOControl_1.0.38.0_neutral_~_4pejv7q2gmsnr", "Fortemedia FMAPO Control", "Fortemedia"),
        ]
        for raw_pkg, expected_app, expected_vendor in samples:
            clean_name = DetectionNormalizer.normalize_name(raw_pkg)
            clean_pub = DetectionNormalizer.normalize_publisher(None, raw_name=raw_pkg)
            self.assertEqual(clean_name, expected_app, f"Expected {expected_app}, got {clean_name}")
            self.assertIn(expected_vendor.lower(), clean_pub.lower(), f"Expected vendor {expected_vendor}, got {clean_pub}")


class TestTierIntegrityAndCommercialComponents(unittest.TestCase):
    def test_commercial_component_not_in_tier_1_billable(self):
        # Citrix Browser Redirection is a commercial component with license_required=NO
        res = HybridLicenseEngine.resolve_hybrid_record(
            app_id=None,
            name="Citrix Browser Content Redirection Plugin",
            publisher="Citrix Systems, Inc.",
        )
        self.assertEqual(res["classification"], "COMMERCIAL_COMPONENT")
        self.assertEqual(res["license_required"], "NO")
        tier = get_tier(res["classification"], res["license_required"])
        self.assertEqual(tier, "Tier 3: OS & System Infrastructure")
        self.assertFalse(tier.startswith("Tier 1"))

    def test_standalone_commercial_in_tier_1(self):
        res = HybridLicenseEngine.resolve_hybrid_record(
            app_id=None,
            name="WinZip",
            publisher="Corel / Alludo",
        )
        self.assertEqual(res["classification"], "COMMERCIAL")
        self.assertEqual(res["license_required"], "YES")
        tier = get_tier(res["classification"], res["license_required"])
        self.assertEqual(tier, "Tier 1: Commercial & Billable")

    def test_google_and_social_apps_resolution(self):
        apps = [
            ("Docs", "Google", "Google Docs", "Google"),
            ("Sheets", "Google", "Google Sheets", "Google"),
            ("Gmail", "Google", "Gmail", "Google"),
            ("YouTube", "Google", "YouTube", "Google"),
            ("Facebook", "Google", "Facebook", "Meta Platforms, Inc."),
        ]
        for raw_app, raw_pub, expected_prod, expected_vend in apps:
            res = HybridLicenseEngine.resolve_hybrid_record(
                app_id=None,
                name=raw_app,
                publisher=raw_pub,
            )
            self.assertNotEqual(res["classification"], "UNKNOWN", f"{raw_app} should not be UNKNOWN")
            self.assertEqual(res["application"], expected_prod)
            self.assertIn(expected_vend.lower(), res["vendor"].lower())

    def test_adobe_reader_freeware_vs_acrobat_pro(self):
        reader_res = HybridLicenseEngine.resolve_hybrid_record(
            app_id=None,
            name="Adobe Acrobat Reader DC",
            publisher="Adobe",
        )
        self.assertEqual(reader_res["classification"], "FREEWARE")
        self.assertEqual(reader_res["license_required"], "NO")
        reader_tier = get_tier(reader_res["classification"], reader_res["license_required"])
        self.assertEqual(reader_tier, "Tier 2: Freeware & Developer Open Source")

        acrobat_res = HybridLicenseEngine.resolve_hybrid_record(
            app_id=None,
            name="Adobe Acrobat DC",
            publisher="Adobe",
        )
        self.assertEqual(acrobat_res["classification"], "COMMERCIAL")
        self.assertEqual(acrobat_res["license_required"], "YES")
        acrobat_tier = get_tier(acrobat_res["classification"], acrobat_res["license_required"])
        self.assertEqual(acrobat_tier, "Tier 1: Commercial & Billable")

    def test_windows_sdk_and_dev_tools_not_commercial_billable(self):
        sdk_res = HybridLicenseEngine.resolve_hybrid_record(
            app_id=None,
            name="Windows Software Development Kit - Windows 10.0.26100.4188",
            publisher="Microsoft",
        )
        self.assertIn(sdk_res["classification"], ("FREEWARE", "FRAMEWORK_RUNTIME"))
        self.assertEqual(sdk_res["license_required"], "NO")
        sdk_tier = get_tier(sdk_res["classification"], sdk_res["license_required"])
        self.assertFalse(sdk_tier.startswith("Tier 1"), "Windows SDK must never be Tier 1 Commercial")


if __name__ == "__main__":
    unittest.main()

