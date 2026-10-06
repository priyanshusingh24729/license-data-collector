"""End-to-end tests for the Tier 4 feedback loop, immediate db updates, code generation, and promotion."""

import unittest
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import sessionmaker

from backend.database.connection import engine, Base
from backend.models.tier4_feedback import PendingCatalogRule, CatalogAuditLog
from backend.models.inventory_upload import UploadLicenseResult, InventoryUpload
from backend.inventory.feedback.tier4_loop_service import Tier4LoopService, Tier4Resolution
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
from remediate_inventory_accuracy import get_tier


class TestTier4FeedbackLoop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.Session = sessionmaker(bind=engine)

    def setUp(self):
        self.db = self.Session()
        self._fixture_backup = Tier4LoopService.FIXTURES_PATH.read_text(encoding="utf-8") if Tier4LoopService.FIXTURES_PATH.exists() else None
        self._catalog_backup = Tier4LoopService.CATALOG_FILE_PATH.read_text(encoding="utf-8") if Tier4LoopService.CATALOG_FILE_PATH.exists() else None

    def tearDown(self):
        if self._fixture_backup and Tier4LoopService.FIXTURES_PATH.exists():
            Tier4LoopService.FIXTURES_PATH.write_text(self._fixture_backup, encoding="utf-8")
        if self._catalog_backup and Tier4LoopService.CATALOG_FILE_PATH.exists():
            Tier4LoopService.CATALOG_FILE_PATH.write_text(self._catalog_backup, encoding="utf-8")
        self.db.close()

    def test_structured_resolution_and_immediate_db_update(self):
        """Verify that submitting a resolution immediately updates existing database rows."""
        test_sig = f"CustomInhouseTool_{uuid.uuid4().hex[:6]}"
        upload_id = f"test_up_{uuid.uuid4().hex[:6]}"

        # Insert a fake upload header
        upload_record = InventoryUpload(
            upload_id=upload_id,
            file_name="test_inventory.csv",
            file_type="CSV",
            status="COMPLETED",
        )
        self.db.add(upload_record)

        # Seed 3 unresolved Tier 4 rows with this signature
        for i in range(3):
            row = UploadLicenseResult(
                upload_id=upload_id,
                raw_application=test_sig,
                raw_vendor="Unknown Vendor",
                raw_version="1.0.0",
                classification="UNKNOWN",
                license_required="UNKNOWN",
                evidence_status="MISSING",
                hostname=f"host-{i}.corp.local",
            )
            self.db.add(row)
        self.db.commit()

        # Submit structured resolution
        resolution = Tier4Resolution(
            signature_id=test_sig,
            matched_pattern=test_sig,
            canonical_name="Enterprise Internal Tool Suite",
            vendor="Acme Corporation",
            license_type="FREEWARE",
            license_required="NO",
            metric="NOT_APPLICABLE",
            tier=2,
            evidence_url="https://intranet.acme.corp/tools",
            evidence_quote="Internal utility approved for corporate workstation use.",
            resolved_by="auditor_jane",
            confidence="auditor_confirmed",
            scope="exact_match",
            auto_promote=False
        )

        result = Tier4LoopService.submit_resolution(resolution, db=self.db)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["existing_rows_updated"], 3)

        # Verify existing rows were updated IMMEDIATELY
        updated_rows = self.db.query(UploadLicenseResult).filter(
            UploadLicenseResult.raw_application == test_sig
        ).all()
        self.assertEqual(len(updated_rows), 3)
        for r in updated_rows:
            self.assertEqual(r.canonical_product, "Enterprise Internal Tool Suite")
            self.assertEqual(r.canonical_vendor, "Acme Corporation")
            self.assertEqual(r.classification, "FREEWARE")
            self.assertEqual(r.license_required, "NO")
            self.assertEqual(r.evidence_status, "VERIFIED")
            self.assertEqual(r.confidence, "VERY_HIGH")

        # Verify staged in pending_catalog_rules
        rule_id = result["rule_id"]
        pending = self.db.query(PendingCatalogRule).filter(PendingCatalogRule.rule_id == rule_id).first()
        self.assertIsNotNone(pending)
        self.assertEqual(pending.status, "pending_review")
        self.assertEqual(pending.occurrence_count, 3)
        self.assertIn("CatalogRecognitionEntry", pending.diff_preview)

        # Verify audit log entry
        audit = self.db.query(CatalogAuditLog).filter(CatalogAuditLog.rule_id == rule_id).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.action, "rule_staged")
        self.assertEqual(audit.performed_by, "auditor_jane")

    def test_promotion_workflow_and_dynamic_recognition(self):
        """Verify that promoting a rule adds it to dynamic memory recognition and regression fixtures."""
        unique_name = f"TestDynamicProduct_{uuid.uuid4().hex[:6]}"
        
        resolution = Tier4Resolution(
            signature_id=unique_name,
            matched_pattern=unique_name.lower(),
            canonical_name=unique_name,
            vendor="Dynamic Vendor LLC",
            license_type="COMMERCIAL",
            license_required="YES",
            metric="USER",
            tier=1,
            evidence_url="https://vendor.com/pricing",
            evidence_quote="Standard commercial licensing applies.",
            resolved_by="lead_auditor",
            confidence="auditor_confirmed",
            scope="exact_match",
            auto_promote=False
        )

        res = Tier4LoopService.submit_resolution(resolution, db=self.db)
        rule_id = res["rule_id"]

        # Promote to catalog
        promote_res = Tier4LoopService.promote_to_catalog(rule_id, approved_by="sr_compliance_officer", db=self.db)
        self.assertEqual(promote_res["status"], "MERGED")
        self.assertEqual(promote_res["approved_by"], "sr_compliance_officer")

        # Verify rule status updated to merged
        rule = self.db.query(PendingCatalogRule).filter(PendingCatalogRule.rule_id == rule_id).first()
        self.assertEqual(rule.status, "merged")
        self.assertEqual(rule.approved_by, "sr_compliance_officer")

        # Test dynamic in-memory recognition immediately recognizes it!
        resolved = HybridLicenseEngine.resolve_hybrid_record(
            app_id=None,
            name=unique_name,
            publisher="Dynamic Vendor LLC"
        )
        self.assertEqual(resolved["application"], unique_name)
        self.assertEqual(resolved["vendor"], "Dynamic Vendor LLC")
        self.assertEqual(resolved["classification"], "COMMERCIAL")
        self.assertEqual(resolved["license_required"], "YES")
        tier = get_tier(resolved["classification"], resolved["license_required"])
        self.assertEqual(tier, "Tier 1: Commercial & Billable")


if __name__ == "__main__":
    unittest.main()
