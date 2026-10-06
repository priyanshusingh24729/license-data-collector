"""Regression tests to verify confirmed human resolutions remain stable and never regress."""

import unittest
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
from backend.inventory.feedback.tier4_loop_service import Tier4LoopService
from remediate_inventory_accuracy import get_tier


class TestCatalogRegressions(unittest.TestCase):
    def test_no_regression_on_confirmed_resolutions(self):
        """Ensures all confirmed auditor resolutions resolve to their expected tier without regression."""
        confirmed_cases = Tier4LoopService.load_confirmed_resolutions()
        self.assertTrue(len(confirmed_cases) > 0, "Confirmed resolutions fixture set should not be empty")

        for case in confirmed_cases:
            sig = case["signature_id"]
            expected_tier = case["expected_tier"]
            vendor = case.get("vendor")

            res = HybridLicenseEngine.resolve_hybrid_record(
                app_id=None,
                name=sig,
                publisher=vendor,
            )

            actual_tier = get_tier(res["classification"], res["license_required"])
            self.assertEqual(
                actual_tier,
                expected_tier,
                f"Regression on '{sig}'! Expected '{expected_tier}', got '{actual_tier}' (class: {res['classification']}, req: {res['license_required']})"
            )
            self.assertEqual(
                res["application"],
                case["canonical_name"],
                f"Canonical name mismatch on '{sig}'! Expected '{case['canonical_name']}', got '{res['application']}'"
            )


if __name__ == "__main__":
    unittest.main()
