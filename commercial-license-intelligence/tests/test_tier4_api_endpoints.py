"""Tests for the Tier 4 feedback loop REST API endpoints."""

import unittest
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.connection import SessionLocal
from backend.models.tier4_feedback import PendingCatalogRule, CatalogAuditLog
from backend.inventory.feedback.tier4_loop_service import Tier4LoopService


class TestTier4APIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self._fixture_backup = Tier4LoopService.FIXTURES_PATH.read_text(encoding="utf-8") if Tier4LoopService.FIXTURES_PATH.exists() else None
        self._catalog_backup = Tier4LoopService.CATALOG_FILE_PATH.read_text(encoding="utf-8") if Tier4LoopService.CATALOG_FILE_PATH.exists() else None

    def tearDown(self):
        if self._fixture_backup and Tier4LoopService.FIXTURES_PATH.exists():
            Tier4LoopService.FIXTURES_PATH.write_text(self._fixture_backup, encoding="utf-8")
        if self._catalog_backup and Tier4LoopService.CATALOG_FILE_PATH.exists():
            Tier4LoopService.CATALOG_FILE_PATH.write_text(self._catalog_backup, encoding="utf-8")

    def test_tier4_api_lifecycle(self):
        # 1. Test queue retrieval
        res = self.client.get("/api/tier4/queue?limit=10")
        self.assertEqual(res.status_code, 200)
        queue_data = res.json()
        self.assertIsInstance(queue_data, list)

        # 2. Test structured resolution submission
        res_payload = {
            "signature_id": "APISampleUnresolvedTool",
            "matched_pattern": "apisampleunresolvedtool",
            "canonical_name": "API Sample Tool",
            "vendor": "API Sample Vendor Inc.",
            "license_type": "FREEWARE",
            "license_required": "NO",
            "metric": "NOT_APPLICABLE",
            "tier": 2,
            "evidence_url": "https://example.com/tool-terms",
            "evidence_quote": "Freeware utility for enterprise endpoints.",
            "resolved_by": "qa_auditor",
            "confidence": "auditor_confirmed",
            "scope": "exact_match",
            "auto_promote": False,
        }

        resolve_res = self.client.post("/api/tier4/resolve", json=res_payload)
        self.assertEqual(resolve_res.status_code, 200)
        data = resolve_res.json()
        self.assertEqual(data["status"], "SUCCESS")
        rule_id = data["rule_id"]
        self.assertTrue(rule_id.startswith("rule_"))

        # 3. Test pending rules retrieval
        pending_res = self.client.get("/api/tier4/pending?status=pending_review")
        self.assertEqual(pending_res.status_code, 200)
        pending_list = pending_res.json()
        matching_rules = [r for r in pending_list if r["rule_id"] == rule_id]
        self.assertTrue(len(matching_rules) > 0)

        # 4. Test diff preview
        diff_res = self.client.get(f"/api/tier4/diff/{rule_id}")
        self.assertEqual(diff_res.status_code, 200)
        diff_data = diff_res.json()
        self.assertIn("CatalogRecognitionEntry", diff_data["diff_preview"])
        self.assertIn("API Sample Tool", diff_data["diff_preview"])

        # 5. Test promotion
        promote_res = self.client.post(
            f"/api/tier4/promote/{rule_id}",
            json={"approved_by": "lead_compliance_lead"}
        )
        self.assertEqual(promote_res.status_code, 200)
        promoted_data = promote_res.json()
        self.assertEqual(promoted_data["status"], "MERGED")

        # 6. Test audit log
        audit_res = self.client.get("/api/tier4/audit-log?limit=5")
        self.assertEqual(audit_res.status_code, 200)
        audit_entries = audit_res.json()
        self.assertTrue(len(audit_entries) > 0)


if __name__ == "__main__":
    unittest.main()
