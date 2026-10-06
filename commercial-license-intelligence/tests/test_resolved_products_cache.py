"""
Comprehensive Unit Tests for:
1. Persistent Cross-Upload Product Resolution Cache & Zero-Search Guarantee
2. Decoupled Deduplication Keys (Edition Bucketing vs Point Release Noise)
3. Non-Blocking Staleness Detection & Background Revalidation
4. Staleness Drift Detection & Routing to Tier 4 Human Review (No Silent Overwrite)
5. YaCy Search Fallback & SearXNG + YaCy Cross-Validation Agreement Boosting
6. Observability Telemetry (Hit Rates, Stale Counts, Tier Distributions)
"""

import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.database.connection import SessionLocal
from backend.models.resolved_product_cache import ResolvedProductCache
from backend.models.inventory_upload import InventoryUpload, UploadLicenseResult
from backend.models.tier4_feedback import PendingCatalogRule, CatalogAuditLog
from backend.inventory.recognition.resolved_product_service import ResolvedProductService
from backend.inventory.upload.bulk_upload_processor import BulkUploadProcessor, extract_version_bucket
from backend.validation.searxng_evidence_validator import SearxngEvidenceValidator, SearxngValidationEvidence
from backend.sources.discovery.search_provider import SearchResult
from backend.main import app


class TestResolvedProductCacheAndDecoupling(unittest.TestCase):

    def setUp(self):
        self.db = SessionLocal()
        self._cleanup_test_records()
        SearxngEvidenceValidator._CACHE.clear()
        ResolvedProductService._mem_cache.clear()

    def tearDown(self):
        self._cleanup_test_records()
        self.db.close()
        SearxngEvidenceValidator._CACHE.clear()
        ResolvedProductService._mem_cache.clear()

    def _cleanup_test_records(self):
        try:
            self.db.query(ResolvedProductCache).filter(
                ResolvedProductCache.normalized_name.in_([
                    "testapp pro", "staletool legacy", "staticverifiedapp", "dockerstyleshiftapp", "slack", "autonomoustool", "yacyspecialtool", "consensusapp"
                ])
            ).delete(synchronize_session=False)
            self.db.query(PendingCatalogRule).filter(
                PendingCatalogRule.canonical_name.in_(["DockerStyleShiftApp", "StaticVerifiedApp", "AutonomousTool", "YaCySpecialTool", "ConsensusApp"])
            ).delete(synchronize_session=False)
            self.db.commit()
        except Exception:
            self.db.rollback()

    def test_version_bucketing(self):
        """Verify edition-sensitive products get bucketed, while point releases map to ANY."""
        # SQL Server editions should bucket
        self.assertEqual(extract_version_bucket("Microsoft SQL Server 2022 Express", "16.0.1"), "EXPRESS")
        self.assertEqual(extract_version_bucket("Microsoft SQL Server Enterprise", "15.0"), "ENTERPRISE")
        self.assertEqual(extract_version_bucket("Visual Studio Community 2022", "17.9.0"), "COMMUNITY")
        
        # Standard software point releases should map to ANY
        self.assertEqual(extract_version_bucket("Google Chrome", "124.0.6367.208"), "ANY")
        self.assertEqual(extract_version_bucket("Google Chrome", "125.0.6422.60"), "ANY")
        self.assertEqual(extract_version_bucket("Slack", "4.38.125"), "ANY")
        self.assertEqual(extract_version_bucket("7-Zip", "24.05"), "ANY")

    def test_cache_service_upsert_and_retrieve(self):
        """Verify upserting and retrieving from ResolvedProductCache."""
        mock_record = {
            "application": "TestApp Pro",
            "vendor": "Acme Corp",
            "classification": "COMMERCIAL",
            "availability": "PAID_ONLY",
            "license_required": "YES",
            "license_model": "Named User Subscription",
            "metric": "USER",
            "confidence": "VERY_HIGH",
            "reliability_score": 96.0,
            "reliability_str": "96%",
            "evidence_status": "VERIFIED",
            "evidence_url": "https://acme.example.com/terms",
            "evidence_quote": "Acme TestApp requires an annual commercial license.",
            "override_reason": "Verified enterprise pricing",
        }

        # Upsert
        ResolvedProductService.upsert_resolution(
            record=mock_record,
            evidence_source="SEARXNG",
            raw_name="TestApp Pro",
            raw_vendor="Acme Corp",
            version_bucket="PRO",
            db=self.db,
        )

        # Retrieve
        cached = ResolvedProductService.get_cached_resolution(
            name="TestApp Pro",
            publisher="Acme Corp",
            version_bucket="PRO",
            db=self.db,
        )

        self.assertIsNotNone(cached)
        self.assertEqual(cached["application"], "TestApp Pro")
        self.assertEqual(cached["classification"], "COMMERCIAL")
        self.assertEqual(cached["license_required"], "YES")
        self.assertTrue(cached.get("is_cached"))

    def test_bulk_upload_uses_cache_and_decouples_versions(self):
        """
        Verify that multiple point-releases of the same product collapse into 1 group,
        and subsequent uploads hit the global cache with zero new searches.
        """
        upload_id_1 = f"upl_test_decouple_1_{int(datetime.now(timezone.utc).timestamp())}"
        
        # 5 installations of Slack with 5 different versions across 5 machines
        df_1 = pd.DataFrame([
            {"App": "Slack", "Vendor": "Slack Technologies", "Ver": "4.35.0", "Host": "PC-1"},
            {"App": "Slack", "Vendor": "Slack Technologies", "Ver": "4.36.0", "Host": "PC-2"},
            {"App": "Slack", "Vendor": "Slack Technologies", "Ver": "4.37.0", "Host": "PC-3"},
            {"App": "Slack", "Vendor": "Slack Technologies", "Ver": "4.38.0", "Host": "PC-4"},
            {"App": "Slack", "Vendor": "Slack Technologies", "Ver": "4.38.1", "Host": "PC-5"},
        ])

        col_mapping = {
            "application": "App",
            "vendor": "Vendor",
            "version": "Ver",
            "hostname": "Host",
        }

        res_1 = BulkUploadProcessor.process_upload_dataframe(
            upload_id=upload_id_1,
            file_name="slack_multi_version.csv",
            file_type="CSV",
            df=df_1,
            column_mapping=col_mapping,
        )

        # 5 rows should have collapsed to 1 unique product group!
        self.assertEqual(res_1["total_rows"], 5)
        self.assertEqual(res_1["unique_applications"], 1)

        # Verify results were written with engine version
        db_results = self.db.query(UploadLicenseResult).filter(
            UploadLicenseResult.upload_id == upload_id_1
        ).all()
        self.assertEqual(len(db_results), 5)
        for r in db_results:
            self.assertEqual(r.resolution_engine_version, "v1.2.0")
            self.assertEqual(r.canonical_product, "Slack")

        # Second upload from a completely different file/company with Slack
        upload_id_2 = f"upl_test_decouple_2_{int(datetime.now(timezone.utc).timestamp())}"
        df_2 = pd.DataFrame([
            {"App": "Slack", "Vendor": "Slack Technologies", "Ver": "4.39.0", "Host": "PC-99"},
        ])

        res_2 = BulkUploadProcessor.process_upload_dataframe(
            upload_id=upload_id_2,
            file_name="slack_company_b.csv",
            file_type="CSV",
            df=df_2,
            column_mapping=col_mapping,
        )

        # Should be an immediate cache hit, 0 new researched
        self.assertEqual(res_2["cache_hits"], 1)
        self.assertEqual(res_2["new_researched"], 0)

    def test_staleness_detection_and_non_blocking_return(self):
        """
        Verify that a stale cache entry (>90 days old) returns cached data immediately
        with is_stale=True, ensuring user scans are never blocked.
        """
        stale_app = "StaleTool Legacy"
        stale_vendor = "Legacy Software Ltd"

        # Manually seed a stale entry 120 days old
        old_date = datetime.now(timezone.utc) - timedelta(days=120)
        cache_row = ResolvedProductCache(
            normalized_name=stale_app.lower(),
            normalized_vendor=stale_vendor.lower(),
            version_bucket="ANY",
            canonical_product=stale_app,
            canonical_vendor=stale_vendor,
            classification="COMMERCIAL",
            license_required="YES",
            license_model="Annual Subscription",
            reliability_score=90.0,
            reliability_str="90%",
            evidence_source="SEARXNG",
            evidence_status="VERIFIED",
            resolution_engine_version="v1.2.0",
            first_resolved_at=old_date,
            last_validated_at=old_date,
            validation_count=1,
        )
        self.db.add(cache_row)
        self.db.commit()

        # Retrieve with mocked background scheduler to avoid spawning unmocked revalidation network calls
        with patch.object(ResolvedProductService, "schedule_background_revalidation") as mock_sched:
            cached = ResolvedProductService.get_cached_resolution(
                name=stale_app,
                publisher=stale_vendor,
                version_bucket="ANY",
                max_age_days=90,
                db=self.db,
            )
            mock_sched.assert_called_once_with(cache_row.id)

        self.assertIsNotNone(cached)
        self.assertTrue(cached.get("is_cached"))
        self.assertTrue(cached.get("is_stale"), "Entry older than 90 days must be flagged as stale")
        self.assertEqual(cached["classification"], "COMMERCIAL")

    def test_staleness_revalidation_confirmed_unchanged(self):
        """
        Verify that background revalidation confirms unchanged licensing,
        increments validation_count, and refreshes last_validated_at.
        """
        app_name = "StaticVerifiedApp"
        vendor_name = "Verified Vendor Inc"
        old_date = datetime.now(timezone.utc) - timedelta(days=100)

        cache_row = ResolvedProductCache(
            normalized_name=app_name.lower(),
            normalized_vendor=vendor_name.lower(),
            version_bucket="ANY",
            canonical_product=app_name,
            canonical_vendor=vendor_name,
            classification="FREEWARE",
            license_required="NO",
            license_model="Freeware",
            reliability_score=95.0,
            reliability_str="95%",
            evidence_source="CATALOG",
            evidence_status="VERIFIED",
            resolution_engine_version="v1.2.0",
            first_resolved_at=old_date,
            last_validated_at=old_date,
            validation_count=1,
        )
        self.db.add(cache_row)
        self.db.commit()
        rec_id = cache_row.id

        # Mock revalidation returning the same classification
        mock_ev = SearxngValidationEvidence(
            application=app_name,
            vendor=vendor_name,
            version="1.0",
            classification="FREEWARE",
            availability="FREE",
            license_required="NO",
            license_model="Freeware",
            confidence="VERY_HIGH",
            evidence_status="VERIFIED",
            evidence_url="https://verified.example.com/license",
            evidence_quote="Freeware application for personal and commercial use.",
            reliability_score=95.0,
        )

        with patch.object(SearxngEvidenceValidator, "validate_application", return_value=mock_ev):
            reval_res = ResolvedProductService.revalidate_product_entry(rec_id, db=self.db)

        self.assertEqual(reval_res["status"], "confirmed_unchanged")
        self.assertEqual(reval_res["validation_count"], 2)

        # Confirm DB record updated
        updated_rec = self.db.query(ResolvedProductCache).filter(ResolvedProductCache.id == rec_id).first()
        self.assertEqual(updated_rec.validation_count, 2)
        val_date = updated_rec.last_validated_at.replace(tzinfo=timezone.utc) if updated_rec.last_validated_at.tzinfo is None else updated_rec.last_validated_at
        self.assertGreater(val_date, old_date)

    def test_staleness_drift_routed_to_tier4_review(self):
        """
        CRITICAL COMPLIANCE TEST:
        When revalidation detects that licensing terms changed (e.g. FREEWARE flipped to COMMERCIAL),
        it MUST NOT silently overwrite! It must route to Tier 4 review and write a CatalogAuditLog.
        """
        app_name = "DockerStyleShiftApp"
        vendor_name = "Shift Corp"
        old_date = datetime.now(timezone.utc) - timedelta(days=110)

        # Initially cached as FREEWARE
        cache_row = ResolvedProductCache(
            normalized_name=app_name.lower(),
            normalized_vendor=vendor_name.lower(),
            version_bucket="ANY",
            canonical_product=app_name,
            canonical_vendor=vendor_name,
            classification="FREEWARE",
            license_required="NO",
            license_model="Freeware",
            reliability_score=90.0,
            reliability_str="90%",
            evidence_source="SEARXNG",
            evidence_status="VERIFIED",
            resolution_engine_version="v1.2.0",
            first_resolved_at=old_date,
            last_validated_at=old_date,
            validation_count=1,
        )
        self.db.add(cache_row)
        self.db.commit()
        rec_id = cache_row.id

        # Revalidation now discovers commercial subscription required!
        mock_changed_ev = SearxngValidationEvidence(
            application=app_name,
            vendor=vendor_name,
            version="2.0",
            classification="COMMERCIAL",
            availability="PAID_ONLY",
            license_required="YES",
            license_model="Named User Subscription",
            confidence="VERY_HIGH",
            evidence_status="VERIFIED",
            evidence_url="https://shift.example.com/pricing",
            evidence_quote="ShiftApp now requires a paid commercial subscription for business use.",
            reliability_score=95.0,
        )

        with patch.object(SearxngEvidenceValidator, "validate_application", return_value=mock_changed_ev):
            reval_res = ResolvedProductService.revalidate_product_entry(rec_id, db=self.db)

        self.assertEqual(reval_res["status"], "drift_flagged_to_tier4")

        # Verify PendingCatalogRule was staged for human auditor review
        pending_rule = self.db.query(PendingCatalogRule).filter(
            PendingCatalogRule.canonical_name == app_name
        ).first()
        self.assertIsNotNone(pending_rule, "Drift must create a PendingCatalogRule for human review")
        self.assertEqual(pending_rule.license_type, "COMMERCIAL")
        self.assertEqual(pending_rule.license_required, "YES")
        self.assertIn("Cached: FREEWARE", pending_rule.diff_preview)

        # Verify CatalogAuditLog was written
        audit_entry = self.db.query(CatalogAuditLog).filter(
            CatalogAuditLog.action == "staleness_drift_flagged"
        ).order_by(CatalogAuditLog.id.desc()).first()
        self.assertIsNotNone(audit_entry, "Audit log must be created on license drift")

        # Verify cached record was NOT silently overwritten to avoid unauthorized compliance shifts
        cached_rec = self.db.query(ResolvedProductCache).filter(ResolvedProductCache.id == rec_id).first()
        self.assertEqual(cached_rec.classification, "FREEWARE", "Original record must not be silently overwritten")
        self.assertIn("Pending Tier 4 Review", cached_rec.override_reason)

    def test_yacy_search_fallback_and_evidence_tagging(self):
        """
        Verify that when SearXNG returns zero results / fails, YaCy successfully
        provides authoritative results, tagging evidence_source as YACY.
        """
        app_name = "AutonomousTool"
        vendor_name = "Autonomous Systems"

        # Mock SearchResult coming from YaCy
        yacy_result = SearchResult(
            url="https://github.com/autonomous-systems/license",
            title="AutonomousTool Official Terms",
            snippet="AutonomousTool is distributed under the Apache 2.0 open source license.",
            engine="yacy",
            rank=1,
            cross_validated=False,
        )

        # Mock provider returning the YaCy result
        mock_provider = MagicMock()
        mock_provider.search.return_value = [yacy_result]

        ev = SearxngEvidenceValidator.validate_application(
            app_name=app_name,
            vendor=vendor_name,
            search_provider=mock_provider,
        )

        self.assertEqual(ev.source_engine, "yacy")
        self.assertEqual(ev.classification, "OPEN_SOURCE")
        self.assertEqual(ev.license_required, "NO")

        # Enriched record should carry YACY evidence_source
        target_rec = {"application": app_name, "vendor": vendor_name, "classification": "UNKNOWN"}
        enriched = SearxngEvidenceValidator.validate_and_enrich(
            record=target_rec,
            app_name=app_name,
            vendor=vendor_name,
            search_provider=mock_provider,
        )
        self.assertEqual(enriched["evidence_source"], "YACY")

    def test_searxng_and_yacy_cross_validation_boost(self):
        """
        Verify that when both SearXNG and YaCy return results confirming the same official vendor domain,
        cross_validated is True, boosting reliability score by +5% and elevating confidence.
        """
        app_name = "ConsensusApp"
        vendor_name = "Dual Engine Corp"

        # Mock SearchResult with cross_validated = True
        cross_val_result = SearchResult(
            url="https://github.com/dual-engine/terms",
            title="ConsensusApp Official Terms",
            snippet="ConsensusApp requires a commercial subscription for enterprise deployments.",
            engine="searxng",
            rank=1,
            cross_validated=True,
        )

        mock_provider = MagicMock()
        mock_provider.search.return_value = [cross_val_result]

        ev = SearxngEvidenceValidator.validate_application(
            app_name=app_name,
            vendor=vendor_name,
            search_provider=mock_provider,
        )

        # Should be boosted
        self.assertEqual(ev.confidence, "VERY_HIGH")
        self.assertGreaterEqual(ev.reliability_score, 100.0)
        self.assertEqual(ev.source_engine, "searxng+yacy")

    def test_observability_endpoint_telemetry(self):
        """
        Verify /api/inventory/resolution-stats exposes hit rates, stale counts,
        engine telemetry, and tier distributions.
        """
        client = TestClient(app)
        resp = client.get("/api/inventory/resolution-stats")
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["engine_version"], "v1.2.0")

        # Cache health signals
        cache = data["cache"]
        self.assertIn("total_cached_products", cache)
        self.assertIn("hit_rate_pct", cache)
        self.assertIn("stale_entries_count", cache)
        self.assertIn("drift_flagged_count", cache)
        self.assertIn("sources_breakdown", cache)

        # Search chain telemetry
        search_telemetry = data["search_chain_telemetry"]
        self.assertIn("total_queries", search_telemetry)
        self.assertIn("circuit_breaker_states", search_telemetry)

        # Tier distribution
        tier_dist = data["tier_distribution"]
        self.assertIn("tier4_rate_pct", tier_dist)


if __name__ == "__main__":
    unittest.main()
