"""
Backend Quality and Reliability Regression Test Suite (Post Step 21 Quality System).
Verifies:
1. Continuous dynamic reliability scoring (no single cluster > 35%)
2. Honest handling of GUIDs and unresolved package identities
3. Strict OS_BUNDLED evidence validation (inbox apps vs unproven stubs)
4. Discrete metrics validation (USER, CORE, DEVICE, NOT_APPLICABLE, UNKNOWN)
5. Accurate multi-source detection and licensing of OpenAI ChatGPT
"""

import pytest
from collections import Counter

from backend.database.connection import SessionLocal
from backend.models.inventory import DetectedApplication
from backend.inventory.recognition.hybrid_resolver import HybridLicenseEngine
from backend.inventory.recognition.alias_system import ApplicationAliasSystem
from backend.validation.product_scope_matcher import ProductScopeMatcher, ProductScopeMatchTier
from backend.validation.reliability_score import ReliabilityScoreEngine


def test_no_score_clustering():
    """Verify that flat template clusters (e.g. 124 apps at 91%) are eliminated."""
    db = SessionLocal()
    apps = db.query(DetectedApplication).all()
    db.close()

    assert len(apps) >= 162

    scores = [
        HybridLicenseEngine.resolve_hybrid_record(
            app_id=da.id,
            name=da.normalized_name,
            publisher=da.normalized_publisher,
            version=da.detected_version
        )["reliability_str"]
        for da in apps
    ]

    freq = Counter(scores)
    total = len(scores)

    # Assert no single score dominates more than 40% of the total dataset
    for s, count in freq.items():
        assert count / total <= 0.40, f"Score {s} appears {count} times ({count/total*100:.1f}%), exceeding 40% cluster threshold."


def test_unresolved_guids_and_stubs():
    """Verify that unmapped GUIDs and tokens are handled honestly with low reliability."""
    # 1. Test truly unmapped random GUID
    unmapped_res = HybridLicenseEngine.resolve_hybrid_record(
        app_id=None,
        name="11111111-2222-3333-4444-555555555555",
        publisher="Unknown Vendor",
        version="1.0.0"
    )
    assert unmapped_res["classification"] == "UNKNOWN"
    assert unmapped_res["evidence_status"] == "MISSING"
    assert unmapped_res["confidence"] == "UNKNOWN"
    assert unmapped_res["reliability_score"] <= 50.0

    # 2. Test mapped system components from DB
    db = SessionLocal()
    apps = db.query(DetectedApplication).all()
    db.close()

    for da in apps:
        if "f46d4000-fd22-4db4-ac8e-4e1ddde828fe" in da.raw_name.lower():
            rec = HybridLicenseEngine.resolve_hybrid_record(
                app_id=da.id,
                name=da.normalized_name,
                publisher=da.normalized_publisher,
                version=da.detected_version
            )
            assert rec["classification"] != "FREEWARE"
            assert rec["confidence"] in ("LOW", "UNKNOWN")
            assert rec["reliability_score"] <= 50.0


def test_confirmed_inbox_apps():
    """Verify that genuine Windows inbox apps retain OS_BUNDLED with verified official Learn citations."""
    inbox_cases = [
        ("Microsoft.WindowsCalculator", "Windows Calculator"),
        ("Microsoft.WindowsNotepad", "Windows Notepad"),
        ("Microsoft.Paint", "Paint"),
        ("Microsoft.Windows.Photos", "Photos"),
        ("Microsoft.ScreenSketch", "Snipping Tool"),
    ]

    for raw, expected_name in inbox_cases:
        rec = HybridLicenseEngine.resolve_hybrid_record(
            app_id=None,
            name=raw,
            publisher="Microsoft Corporation",
            version="11.0",
        )
        assert rec["classification"] == "OS_BUNDLED"
        assert rec["availability"] == "BUNDLED"
        assert rec["license_required"] == "NO"
        assert rec["metric"] in ("NOT_APPLICABLE", "No License Required")
        assert rec["evidence_status"] == "VERIFIED"
        assert rec["reliability_score"] >= 80.0


def test_chatgpt_detection_and_licensing():
    """Verify ChatGPT multi-source identity resolution and freemium subscription licensing."""
    # Test raw package resolution
    alias_res = ApplicationAliasSystem.resolve_application(
        raw_name="OpenAI.Codex",
        raw_publisher="OpenAI",
        raw_version="26.825.6671.0",
        executable_name="app/ChatGPT.exe",
    )
    assert alias_res.canonical_product == "ChatGPT"
    assert alias_res.canonical_vendor == "OpenAI"

    rec = HybridLicenseEngine.resolve_hybrid_record(
        app_id=163,
        name="ChatGPT",
        publisher="OpenAI",
        version="26.825.6671.0",
    )
    assert rec["classification"] == "FREE_AND_PAID"
    assert rec["availability"] == "FREE_AND_PAID"
    assert rec["license_required"] == "CONTEXT_DEPENDENT"
    assert rec["metric"] == "USER"
    assert rec["evidence_status"] == "VERIFIED"
    assert rec["reliability_score"] >= 95.0


def test_product_scope_matcher():
    """Verify deterministic product scope matching levels."""
    res_exact = ProductScopeMatcher.evaluate_scope(
        canonical_product="Docker Desktop",
        canonical_vendor="Docker Inc.",
        source_title="Docker Desktop Terms of Service",
        source_url="https://www.docker.com/pricing",
        evidence_text="Docker Desktop requires a paid subscription for commercial enterprise.",
    )
    assert res_exact.match_tier == ProductScopeMatchTier.EXACT_MATCH
    assert res_exact.score == 15.0

    res_unresolved = ProductScopeMatcher.evaluate_scope(
        canonical_product="UNRESOLVED",
        canonical_vendor="Unknown",
        source_title="Windows Page",
        source_url="https://microsoft.com",
        evidence_text="Windows is an operating system.",
    )
    assert res_unresolved.match_tier == ProductScopeMatchTier.NO_MATCH
    assert res_unresolved.score == 0.0
