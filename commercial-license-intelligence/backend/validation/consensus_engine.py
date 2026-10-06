"""
Multi-Source Consensus Verification Engine.
Cross-checks licensing facts across:
1. WinGet Package Manifests (cryptographic hashes, official installer URLs, license keys)
2. Authoritative Vendor Legal Portals (direct terms and conditions)
3. Official PDF EULAs and licensing whitepapers
4. Verified Internal Catalog Ground Truth
5. Version-Inflection Engine Rules
6. Edition Disambiguation Engine Results

Enforces strict source precedence, detects and preserves verified terms during conflicts,
and prevents guessing by returning UNKNOWN / EDITION_AMBIGUOUS when evidence is insufficient.
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from backend.inventory.recognition.edition_disambiguator import (
    EditionDisambiguator,
    EditionDisambiguationResult,
)
from backend.inventory.recognition.version_inflection_service import (
    VersionInflectionService,
    VersionInflectionResult,
)
from backend.sources.legal.legal_portal_registry import (
    LegalPortalRegistry,
    AuthoritativeLegalSource,
)
from backend.validation.spdx_taxonomy import SPDXTaxonomyService

logger = logging.getLogger(__name__)


@dataclass
class ConsensusVerificationResult:
    canonical_product: str
    canonical_vendor: str
    canonical_edition: Optional[str]
    version: str
    classification: str
    license_required: str
    license_model: str
    metric: str
    spdx_id: Optional[str]
    version_rule_applied: Optional[str]
    conflict_status: str  # VERIFIED, CONFLICT_PRESERVED, CONFLICT_OVERRIDDEN
    consensus_status: str  # HIGH_CONSENSUS, VERIFIED, CONFLICT_RESOLVED, EDITION_AMBIGUOUS, INSUFFICIENT_EVIDENCE
    evidence_source: str
    evidence_url: str
    evidence_quote: str
    confidence: str
    reliability_score: float
    resolution_notes: str


class ConsensusVerificationEngine:
    """
    Consolidates, verifies, and arbitrates multi-source licensing evidence.
    """

    @classmethod
    def verify_and_synthesize(
        cls,
        raw_name: str,
        raw_vendor: Optional[str],
        raw_version: Optional[str],
        catalog_record: Optional[Dict[str, Any]] = None,
        winget_manifest: Optional[Any] = None,
        web_evidence: Optional[Dict[str, Any]] = None,
        install_location: Optional[str] = None,
        snow_baseline: Optional[Dict[str, Any]] = None,
    ) -> ConsensusVerificationResult:
        """
        Synthesizes all evidence streams into a deterministic verified licensing result.
        Treats Snow baseline as authoritative customer baseline when provided.
        """
        app_name = raw_name.strip()
        vendor = (raw_vendor or "").strip() or "Unknown"
        version = (raw_version or "").strip() or "N/A"

        # -------------------------------------------------------------
        # 1. Edition Disambiguation
        # -------------------------------------------------------------
        ed_res: EditionDisambiguationResult = EditionDisambiguator.disambiguate(
            raw_name=app_name,
            vendor=vendor,
            version=version,
            install_location=install_location,
        )
        canonical_edition = ed_res.edition

        # -------------------------------------------------------------
        # 2. Version-Inflection Evaluation
        # -------------------------------------------------------------
        v_inf: Optional[VersionInflectionResult] = VersionInflectionService.evaluate_version(
            app_name=app_name,
            version=version,
            publisher=vendor,
        )

        # -------------------------------------------------------------
        # 3. Authoritative Legal Portal Lookup
        # -------------------------------------------------------------
        legal_src: Optional[AuthoritativeLegalSource] = LegalPortalRegistry.find_legal_source(
            app_name=app_name,
            publisher=vendor,
        )

        # Start synthesizing evidence
        sources_agreeing: List[str] = []
        conflicts: List[str] = []
        conflict_status = "VERIFIED"
        consensus_status = "VERIFIED"
        version_rule_applied = None

        # Base properties from catalog if available
        cat = catalog_record or {}
        has_catalog = bool(cat.get("classification") and cat.get("classification") != "UNKNOWN")

        classification = cat.get("classification") or "UNKNOWN"
        lic_req = cat.get("license_required") or ("NO" if classification in ("OPEN_SOURCE", "FREEWARE", "FREE", "OS_BUNDLED", "COMMERCIAL_COMPONENT") else "YES")
        lic_model = cat.get("license_model") or ""
        metric = cat.get("metric") or cat.get("license_metric") or ""
        ev_url = cat.get("evidence_url") or cat.get("source_url") or ""
        ev_src = cat.get("evidence_source") or "CATALOG"
        ev_quote = cat.get("evidence_quote") or ""
        confidence = cat.get("confidence") or "HIGH"
        rel_score = float(cat.get("reliability_score") or 90.0)

        if has_catalog:
            sources_agreeing.append("CATALOG_GROUND_TRUTH")

        # -------------------------------------------------------------
        # 4. Integrate Edition Disambiguation Implications
        # -------------------------------------------------------------
        if ed_res.is_ambiguous:
            consensus_status = "EDITION_AMBIGUOUS"
            conflict_status = "EDITION_AMBIGUOUS"
            classification = "UNKNOWN"
            lic_model = "Unknown"
            metric = "UNKNOWN"
            confidence = "MEDIUM"
            rel_score = min(rel_score, 60.0)
            ev_quote = ed_res.reason
        elif ed_res.is_split_product and ed_res.license_model:
            classification = ed_res.classification or classification
            lic_req = ed_res.license_required or lic_req
            lic_model = ed_res.license_model or lic_model
            metric = ed_res.metric or metric
            sources_agreeing.append("EDITION_DISAMBIGUATION")

        # -------------------------------------------------------------
        # 5. Integrate Version-Inflection Engine Implications
        # -------------------------------------------------------------
        if v_inf and v_inf.is_inflected:
            version_rule_applied = v_inf.rule_applied
            classification = v_inf.classification or classification
            lic_req = v_inf.license_required or lic_req
            lic_model = v_inf.license_model or lic_model
            metric = v_inf.metric or metric
            if v_inf.evidence_url and not ev_url:
                ev_url = v_inf.evidence_url
            if v_inf.evidence_quote:
                ev_quote = f"{ev_quote} | {v_inf.evidence_quote}" if ev_quote else v_inf.evidence_quote
            sources_agreeing.append("VERSION_INFLECTION_ENGINE")

        # -------------------------------------------------------------
        # 6. Integrate WinGet Ground Truth & Conflict Arbitrator
        # -------------------------------------------------------------
        if winget_manifest:
            wg_license = getattr(winget_manifest, "license", "") or ""
            wg_spdx = SPDXTaxonomyService.normalize_spdx(wg_license)
            sources_agreeing.append("WINGET_MANIFEST")

            # Check for conflict with open-source catalog rule
            is_catalog_oss = classification in ("OPEN_SOURCE", "FREEWARE", "FREE") or "SSPL" in lic_model or "GPL" in lic_model or "MIT" in lic_model or "Apache" in lic_model
            is_winget_generic_prop = wg_spdx == "Proprietary" or "proprietary" in wg_license.lower()

            if is_catalog_oss and is_winget_generic_prop:
                # WinGet generic proprietary tag conflict with verified open-source/source-available catalog rule
                conflict_status = "CONFLICT_PRESERVED"
                conflicts.append(f"WinGet labeled as '{wg_license}', preserved verified catalog/inflection model: '{lic_model}'")
            elif not has_catalog and wg_spdx != "UNKNOWN":
                # Uncataloged product: WinGet acts as high-confidence ground truth
                if wg_spdx == "Proprietary":
                    classification = "COMMERCIAL"
                    lic_req = "YES"
                    lic_model = "Commercial — Proprietary License"
                else:
                    info = SPDXTaxonomyService.get_spdx_info(wg_spdx)
                    classification = info.default_classification
                    lic_req = "NO" if info.is_open_source else "YES"
                    lic_model = f"{info.spdx_id} — Free/Open Source" if info.is_open_source else f"{info.spdx_id} — Commercial"
                    metric = "No License Required" if info.is_open_source else "Named User"
                ev_src = "WINGET_GROUND_TRUTH"

        # -------------------------------------------------------------
        # 7. Integrate Authoritative Vendor Legal Portal
        # -------------------------------------------------------------
        if legal_src:
            sources_agreeing.append("VENDOR_LEGAL_PORTAL")
            # Upgrade evidence URL to official legal portal if current is generic or missing
            if not ev_url or "google" in ev_url or "duckduckgo" in ev_url or not LegalPortalRegistry.is_authoritative_legal_url(ev_url):
                ev_url = legal_src.legal_portal_url
                ev_src = legal_src.evidence_type
            if legal_src.notes:
                ev_quote = f"{ev_quote} | [{legal_src.vendor_canonical} Legal Portal] {legal_src.notes}" if ev_quote else f"[{legal_src.vendor_canonical} Legal Portal] {legal_src.notes}"

        # -------------------------------------------------------------
        # 8. Standardize SPDX Identifier
        # -------------------------------------------------------------
        # Only populate an SPDX identifier when it is actually a valid SPDX identifier.
        # Never populate 'Proprietary' or 'Commercial' as an SPDX identifier.
        spdx_id = SPDXTaxonomyService.get_valid_spdx_id(lic_model)
        if not spdx_id and winget_manifest:
            spdx_id = SPDXTaxonomyService.get_valid_spdx_id(getattr(winget_manifest, "license", None))

        # -------------------------------------------------------------
        # 9. Exact Metric Harmonization & License Required Enforcement
        # -------------------------------------------------------------
        c_upper = str(classification or "").strip().upper()
        m_lower = str(lic_model or "").lower()

        # Enforce Customer-Grade Commercial Business Rule:
        # If an application has ANY applicable commercial/organizational usage scenario
        # that requires a paid license, subscription, entitlement, or eligible commercial plan,
        # the final value MUST be YES.
        if c_upper == "COMMERCIAL_COMPONENT":
            lic_req = "NO"
            metric = "No License Required"
        elif c_upper in ("COMMERCIAL", "FREE_AND_PAID", "TRIAL", "PROPRIETARY", "PAID"):
            lic_req = "YES"
        elif any(term in m_lower for term in ("subscription", "commercial", "enterprise", "per user", "per device", "per core")):
            lic_req = "YES"
        elif c_upper in ("FREE", "FREEWARE", "OPEN_SOURCE", "OS_BUNDLED", "LINUX_SYSTEM_PACKAGE"):
            if not lic_req or lic_req == "CONTEXT_DEPENDENT":
                lic_req = "NO"

        if consensus_status == "EDITION_AMBIGUOUS" or classification == "UNKNOWN":
            metric = "UNKNOWN"
            lic_req = "UNKNOWN"
        elif lic_req == "NO":
            metric = "No License Required"
        # -------------------------------------------------------------
        # 9B. Snow Authoritative Baseline Evaluation
        # -------------------------------------------------------------
        if snow_baseline:
            snow_no_lic = snow_baseline.get("NoLicenseRequired")
            if snow_no_lic is None:
                snow_no_lic = snow_baseline.get("no_license_required")

            snow_metric = snow_baseline.get("Metric") or snow_baseline.get("metric")

            if snow_no_lic is not None and str(snow_no_lic).strip() in ("0", "1"):
                snow_lic_req = "YES" if str(snow_no_lic).strip() == "0" else "NO"
                if lic_req in ("YES", "NO"):
                    if lic_req == snow_lic_req:
                        sources_agreeing.append("SNOW_AUTHORITATIVE_BASELINE")
                        conflict_status = "CONFIRMED"
                    else:
                        conflicts.append(
                            f"Snow Baseline specifies NoLicenseRequired={snow_no_lic} ({snow_lic_req}) "
                            f"while Intelligence detected {lic_req}"
                        )
                        conflict_status = "DISCREPANCY_FLAGGED"
                        consensus_status = "REVIEW_RECOMMENDED"

            if snow_metric and str(snow_metric).strip().upper() not in ("NULL", "NONE", ""):
                metric = str(snow_metric).strip()
                sources_agreeing.append(f"SNOW_METRIC({metric})")
            elif metric and metric not in ("UNKNOWN", "", "No License Required"):
                if conflict_status != "DISCREPANCY_FLAGGED":
                    conflict_status = "ENRICHED"
                sources_agreeing.append(f"ENRICHED_METRIC({metric})")

        # -------------------------------------------------------------
        # 10. Consensus Status & Reliability Scoring
        # -------------------------------------------------------------
        num_sources = len(sources_agreeing)
        if consensus_status not in ("EDITION_AMBIGUOUS", "REVIEW_RECOMMENDED"):
            if num_sources >= 3:
                consensus_status = "HIGH_CONSENSUS"
                confidence = "VERY_HIGH"
                rel_score = 100.0
            elif num_sources >= 2:
                consensus_status = "VERIFIED"
                confidence = "VERY_HIGH"
                rel_score = max(rel_score, 95.0)
            elif num_sources == 1:
                consensus_status = "SINGLE_SOURCE_VERIFIED"
                confidence = "HIGH"
                rel_score = max(rel_score, 85.0)
            else:
                consensus_status = "INSUFFICIENT_EVIDENCE"
                confidence = "LOW"
                classification = "UNKNOWN"
                lic_model = "Unknown"
                metric = "UNKNOWN"
                rel_score = 25.0

        resolution_notes = f"Sources: {', '.join(sources_agreeing)}"
        if conflicts:
            resolution_notes = f"{resolution_notes} | Conflicts: {'; '.join(conflicts)}"

        return ConsensusVerificationResult(
            canonical_product=cat.get("canonical_product") or cat.get("application") or app_name,
            canonical_vendor=cat.get("canonical_vendor") or cat.get("vendor") or vendor,
            canonical_edition=canonical_edition,
            version=version,
            classification=classification,
            license_required=lic_req,
            license_model=lic_model,
            metric=metric,
            spdx_id=spdx_id,
            version_rule_applied=version_rule_applied,
            conflict_status=conflict_status,
            consensus_status=consensus_status,
            evidence_source=ev_src,
            evidence_url=ev_url,
            evidence_quote=ev_quote,
            confidence=confidence,
            reliability_score=rel_score,
            resolution_notes=resolution_notes,
        )
