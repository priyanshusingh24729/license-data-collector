"""
Unit Tests for the 6 Core Licensing Intelligence Pipeline Enhancements:
1. Edition Disambiguation Engine
2. Version-Inflection Engine
3. Authoritative Vendor Legal Sources
4. SPDX License Taxonomy Service
5. Exact Licensing Metrics
6. Multi-Source Consensus Verification Engine
"""

import pytest
from backend.inventory.recognition.edition_disambiguator import EditionDisambiguator
from backend.inventory.recognition.version_inflection_service import VersionInflectionService
from backend.sources.legal.legal_portal_registry import LegalPortalRegistry
from backend.validation.spdx_taxonomy import SPDXTaxonomyService
from backend.validation.consensus_engine import ConsensusVerificationEngine
from backend.validation.license_validation_layer import LicenseValidationLayer


# =========================================================================
# 1. Edition Disambiguation Tests
# =========================================================================
def test_edition_disambiguation_community():
    res = EditionDisambiguator.disambiguate("Microsoft Visual Studio Community 2022")
    assert res.edition == "Community"
    assert not res.is_ambiguous
    assert res.license_required == "NO"
    assert res.metric == "No License Required"
    assert res.classification == "FREEWARE"


def test_edition_disambiguation_professional_enterprise():
    pro = EditionDisambiguator.disambiguate("Microsoft Visual Studio 2022 Professional")
    assert pro.edition == "Professional"
    assert not pro.is_ambiguous
    assert pro.license_required == "YES"
    assert pro.metric == "Named User"
    assert pro.classification == "COMMERCIAL"

    ent = EditionDisambiguator.disambiguate("Microsoft Visual Studio 2022 Enterprise")
    assert ent.edition == "Enterprise"
    assert not ent.is_ambiguous
    assert ent.license_required == "YES"
    assert ent.metric == "Named User"
    assert ent.classification == "COMMERCIAL"


def test_edition_disambiguation_ambiguous_fallback():
    amb = EditionDisambiguator.disambiguate("Microsoft Visual Studio 2022")
    assert amb.edition == "EDITION_AMBIGUOUS"
    assert amb.is_ambiguous
    assert amb.classification == "UNKNOWN"

    sql_amb = EditionDisambiguator.disambiguate("Microsoft SQL Server 2019")
    assert sql_amb.edition == "EDITION_AMBIGUOUS"
    assert sql_amb.is_ambiguous


def test_edition_disambiguation_sql_express_vs_standard():
    exp = EditionDisambiguator.disambiguate("Microsoft SQL Server 2022 Express Edition")
    assert exp.edition == "Express"
    assert not exp.is_ambiguous
    assert exp.license_required == "NO"
    assert exp.metric == "No License Required"

    std = EditionDisambiguator.disambiguate("Microsoft SQL Server 2022 Standard")
    assert std.edition == "Standard"
    assert not std.is_ambiguous
    assert std.license_required == "YES"
    assert std.metric == "Processor Cores"


# =========================================================================
# 2. Version-Inflection Engine Tests
# =========================================================================
def test_version_inflection_docker_desktop():
    # Docker Desktop >= 4.0 requires commercial subscription
    v4 = VersionInflectionService.evaluate_version("Docker Desktop", "4.28.0")
    assert v4 is not None
    assert v4.is_inflected
    assert v4.license_required == "YES"
    assert v4.classification == "COMMERCIAL"
    assert v4.metric == "Users"
    assert ">= 4.0.0" in v4.rule_applied

    # Docker Desktop < 4.0 legacy was free
    v3 = VersionInflectionService.evaluate_version("Docker Desktop", "3.6.0")
    assert v3 is not None
    assert v3.is_inflected
    assert v3.license_required == "NO"
    assert v3.metric == "No License Required"


def test_version_inflection_terraform():
    # Terraform >= 1.5.6 is BSL-1.1
    t_new = VersionInflectionService.evaluate_version("Terraform", "1.6.0")
    assert t_new is not None
    assert t_new.is_inflected
    assert t_new.spdx_id == "BSL-1.1"
    assert t_new.license_required == "YES"

    # Terraform < 1.5.6 was MPL-2.0 open source
    t_old = VersionInflectionService.evaluate_version("Terraform", "1.5.5")
    assert t_old is not None
    assert t_old.is_inflected
    assert t_old.spdx_id == "MPL-2.0"
    assert t_old.license_required == "NO"


def test_version_inflection_redis():
    # Redis >= 7.4.0 is RSALv2 / SSPL
    r_new = VersionInflectionService.evaluate_version("Redis", "7.4.1")
    assert r_new is not None
    assert r_new.is_inflected
    assert r_new.spdx_id == "SSPL-1.0"
    assert r_new.license_required == "YES"

    # Redis < 7.4.0 was BSD-3-Clause
    r_old = VersionInflectionService.evaluate_version("Redis", "7.2.4")
    assert r_old is not None
    assert r_old.is_inflected
    assert r_old.spdx_id == "BSD-3-Clause"
    assert r_old.license_required == "NO"


def test_version_inflection_oracle_java():
    # Java 8 update >= 211 requires commercial license
    j_paid = VersionInflectionService.evaluate_version("Oracle Java SE Development Kit", "8u291")
    assert j_paid is not None
    assert j_paid.is_inflected
    assert j_paid.license_required == "YES"
    assert j_paid.classification == "COMMERCIAL"

    # Java 8 update <= 202 is legacy BCL free
    j_free = VersionInflectionService.evaluate_version("Oracle Java SE Development Kit", "8u202")
    assert j_free is not None
    assert j_free.is_inflected
    assert j_free.license_required == "NO"


# =========================================================================
# 3. Authoritative Vendor Legal Sources Tests
# =========================================================================
def test_authoritative_legal_sources_lookup():
    ms_src = LegalPortalRegistry.find_legal_source("Visual Studio 2022", "Microsoft Corporation")
    assert ms_src is not None
    assert "visualstudio.microsoft.com" in ms_src.legal_portal_url

    docker_src = LegalPortalRegistry.find_legal_source("Docker Desktop", "Docker Inc.")
    assert docker_src is not None
    assert "docker.com/legal" in docker_src.legal_portal_url

    assert LegalPortalRegistry.is_authoritative_legal_url("https://www.microsoft.com/licensing/terms/")
    assert LegalPortalRegistry.is_authoritative_legal_url("https://www.docker.com/legal/terms")
    assert not LegalPortalRegistry.is_authoritative_legal_url("https://random-tech-blog.com/licensing")


# =========================================================================
# 4. SPDX License Taxonomy Tests
# =========================================================================
def test_spdx_taxonomy_normalization():
    assert SPDXTaxonomyService.normalize_spdx("Apache License 2.0") == "Apache-2.0"
    assert SPDXTaxonomyService.normalize_spdx("MIT License") == "MIT"
    assert SPDXTaxonomyService.normalize_spdx("GPL v3") == "GPL-3.0-only"
    assert SPDXTaxonomyService.normalize_spdx("GPL 2.0") == "GPL-2.0-only"
    assert SPDXTaxonomyService.normalize_spdx("BSD 3-Clause") == "BSD-3-Clause"
    assert SPDXTaxonomyService.normalize_spdx("Server Side Public License") == "SSPL-1.0"
    assert SPDXTaxonomyService.normalize_spdx("Business Source License 1.1") == "BSL-1.1"
    assert SPDXTaxonomyService.normalize_spdx("Commercial EULA") == "Proprietary"
    assert SPDXTaxonomyService.normalize_spdx(None) == "UNKNOWN"

    mit_info = SPDXTaxonomyService.get_spdx_info("MIT")
    assert mit_info.is_open_source
    assert mit_info.category == "PERMISSIVE"

    bsl_info = SPDXTaxonomyService.get_spdx_info("BSL-1.1")
    assert bsl_info.is_source_available
    assert bsl_info.category == "SOURCE_AVAILABLE"


# =========================================================================
# 5. Multi-Source Consensus Verification Engine Tests
# =========================================================================
def test_consensus_engine_docker_desktop_inflected():
    res = ConsensusVerificationEngine.verify_and_synthesize(
        raw_name="Docker Desktop",
        raw_vendor="Docker Inc.",
        raw_version="4.28.0",
        catalog_record={"canonical_product": "Docker Desktop", "vendor": "Docker Inc."},
    )
    assert res.classification == "COMMERCIAL"
    assert res.license_required == "YES"
    assert res.metric == "Users"
    # Valid SPDX identifier check: Proprietary software must NOT use fake 'Proprietary' SPDX ID
    assert res.spdx_id is None
    assert res.version_rule_applied is not None
    assert ">= 4.0.0" in res.version_rule_applied
    assert res.consensus_status in ("HIGH_CONSENSUS", "VERIFIED")
    assert res.reliability_score >= 95.0


def test_consensus_engine_ambiguous_edition():
    res = ConsensusVerificationEngine.verify_and_synthesize(
        raw_name="Microsoft Visual Studio 2022",
        raw_vendor="Microsoft Corporation",
        raw_version="17.0.0",
        catalog_record={},
    )
    assert res.canonical_edition == "EDITION_AMBIGUOUS"
    assert res.consensus_status == "EDITION_AMBIGUOUS"
    assert res.conflict_status == "EDITION_AMBIGUOUS"
    assert res.classification == "UNKNOWN"
    assert res.metric == "UNKNOWN"


def test_consensus_engine_open_source_conflict_preservation():
    # WinGet labels MongoDB generic proprietary, catalog has SSPL-1.0
    class MockWinGetManifest:
        license = "Proprietary"
        installer_url = "https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-7.0.0-signed.msi"
        installer_sha256 = "abcd1234"

    res = ConsensusVerificationEngine.verify_and_synthesize(
        raw_name="MongoDB 7.0 Community",
        raw_vendor="MongoDB Inc.",
        raw_version="7.0.0",
        catalog_record={
            "canonical_product": "MongoDB Community Server",
            "classification": "OPEN_SOURCE",
            "license_required": "NO",
            "license_model": "SSPL-1.0 — Free to Use",
            "metric": "No License Required",
        },
        winget_manifest=MockWinGetManifest(),
    )
    assert res.conflict_status == "CONFLICT_PRESERVED"
    assert res.classification == "OPEN_SOURCE"
    assert res.spdx_id == "SSPL-1.0"
    assert res.license_required == "NO"
