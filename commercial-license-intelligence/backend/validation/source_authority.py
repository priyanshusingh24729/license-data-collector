"""
Source Authority & Domain Validator for Evidence Validation (Step 18).
Evaluates Tier 1 to Tier 5 source authority hierarchy, validates domain authenticity against
OfficialDomainRegistry, and strictly prevents search snippets from creating final high-confidence license facts.
"""

from typing import Tuple, Optional
from sqlalchemy.orm import Session

from backend.models.source import LicenseSource
from backend.models.fact import LicenseFact, LicenseEvidence
from backend.models.enums import AuthorityLevel, SourceAuthorityTier, SourceType
from backend.sources.discovery.domain_registry import DomainRegistryService


class SourceAuthorityValidator:
    """
    Evaluates the authority standing and domain validity of the evidence source according to Step 18 hierarchy.
    """

    def validate_authority(
        self,
        db: Session,
        fact: LicenseFact
    ) -> Tuple[bool, SourceAuthorityTier, Optional[str]]:
        """
        Validates source authority and returns (is_official, SourceAuthorityTier, reason).
        
        Hierarchy (Section 9):
        TIER_1: Official vendor licensing terms, Official EULA, Official product terms, Official licensing guide
        TIER_2: Official vendor documentation, Official product/pricing pages
        TIER_3: Authorized reseller/distributor
        TIER_4: Third-party technical/documentation source
        TIER_5: Blogs/forums/search-only evidence
        """
        # 1. Check if direct evidence record is attached
        if fact.evidence_records:
            ev: LicenseEvidence = fact.evidence_records[0]
            if ev.authority_level:
                is_official = ev.authority_level in [SourceAuthorityTier.TIER_1, SourceAuthorityTier.TIER_2]
                if ev.authority_level == SourceAuthorityTier.TIER_5:
                    return False, SourceAuthorityTier.TIER_5, "SEARCH_SNIPPET_REJECTED: Search snippets alone cannot establish authoritative license facts."
                return is_official, ev.authority_level, None

            if ev.source_url:
                is_auth = DomainRegistryService.is_official_domain(db, ev.source_url, fact.vendor_name)
                if is_auth:
                    # Check URL indicators
                    u_lower = ev.source_url.lower()
                    if any(kw in u_lower for kw in ["eula", "license", "terms", "legal", "licensing"]):
                        return True, SourceAuthorityTier.TIER_1, None
                    return True, SourceAuthorityTier.TIER_2, None
                else:
                    return False, SourceAuthorityTier.TIER_4, "NON_OFFICIAL_DOMAIN: Evidence URL does not belong to vendor's registered domains."

        # 2. Check source_id if present
        if fact.source_id:
            source = db.query(LicenseSource).filter(LicenseSource.id == fact.source_id).first()
            if not source:
                return False, SourceAuthorityTier.TIER_5, "SOURCE_RECORD_MISSING: Source ID is not registered."

            # Verify domain authenticity
            is_official_dom = DomainRegistryService.is_official_domain(db, source.source_url, fact.vendor_name)
            if not is_official_dom:
                return False, SourceAuthorityTier.TIER_4, f"DOMAIN_MISMATCH: Source URL {source.source_url} is not an official domain for {fact.vendor_name}."

            if source.source_type in [SourceType.OFFICIAL_TERMS, SourceType.OFFICIAL_EULA, SourceType.OFFICIAL_LICENSING_GUIDE]:
                return True, SourceAuthorityTier.TIER_1, None
            elif source.source_type in [SourceType.OFFICIAL_WEB, SourceType.OFFICIAL_DOCUMENT, SourceType.OFFICIAL_PRODUCT_DOCUMENTATION]:
                return True, SourceAuthorityTier.TIER_2, None
            else:
                return False, SourceAuthorityTier.TIER_4, f"SECONDARY_SOURCE_TYPE: Source type is {source.source_type}."

        # 3. Default fallback if fact has verified document without explicit source record
        if fact.document_id:
            return True, SourceAuthorityTier.TIER_2, None

        return False, SourceAuthorityTier.TIER_5, "NO_SOURCE_OR_EVIDENCE: Fact lacks verified source or document link."
