"""
Source Ranking & Classification Engine.
Evaluates discovered search candidates against target application identity,
assigns authority hierarchy, classifies document type, and computes relevance scores.
"""

from typing import List, Tuple, Optional
from urllib.parse import urlparse
from backend.models.enums import (
    SourceType,
    AuthorityLevel,
    ScopeType,
    DomainValidationStatus,
    RelevanceTier,
    CollectionMethod,
)


class SourceRanker:
    """
    Ranks discovered URL candidates using deterministic signal weighting.
    """

    LICENSING_KEYWORDS = [
        "licensing", "license", "terms", "eula", "product terms",
        "subscription", "named user", "per core", "cal", "entitlement"
    ]

    def classify_source_type(self, url: str, title: str) -> SourceType:
        """
        Determines the source type based on URL patterns, file extensions, and titles.
        """
        url_lower = url.lower()
        title_lower = title.lower()

        if url_lower.endswith(".pdf") or ".pdf?" in url_lower or "/pdf/" in url_lower or "filetype:pdf" in title_lower:
            return SourceType.OFFICIAL_PDF

        if "eula" in url_lower or "eula" in title_lower:
            return SourceType.OFFICIAL_EULA

        if "terms" in url_lower or "licenses-terms" in url_lower or "terms of use" in title_lower:
            return SourceType.OFFICIAL_TERMS

        if "licensing" in url_lower or "licensing-faq" in url_lower or "licensing guide" in title_lower:
            return SourceType.OFFICIAL_LICENSING_GUIDE

        if "docs." in url_lower or "learn." in url_lower or "documentation" in title_lower or "support." in url_lower:
            return SourceType.OFFICIAL_PRODUCT_DOCUMENTATION

        return SourceType.OFFICIAL_WEB

    def infer_scope(
        self,
        vendor: str,
        product: Optional[str],
        edition: Optional[str],
        version: Optional[str],
        url: str,
        title: str
    ) -> Tuple[ScopeType, str]:
        """
        Infers the most specific scope applicable to this source.
        """
        text = f"{url} {title}".lower()
        clean_vendor = vendor.strip()
        clean_product = product.strip() if product else ""
        clean_edition = edition.strip() if edition else ""
        clean_version = version.strip() if version else ""

        # Version match
        if clean_version and clean_version.lower() in text:
            scope_id = f"{clean_product} {clean_edition} {clean_version}".strip() if clean_product else clean_version
            return ScopeType.VERSION, scope_id

        # Edition match
        if clean_edition and clean_edition.lower() in text:
            scope_id = f"{clean_product} {clean_edition}".strip() if clean_product else clean_edition
            return ScopeType.EDITION, scope_id

        # Product match
        if clean_product and clean_product.lower() in text:
            return ScopeType.PRODUCT, clean_product

        # Default to vendor scope
        return ScopeType.VENDOR, clean_vendor

    def rank_candidate(
        self,
        url: str,
        title: str,
        snippet: Optional[str],
        vendor: str,
        product: Optional[str],
        edition: Optional[str],
        version: Optional[str],
        domain_status: DomainValidationStatus
    ) -> Tuple[int, RelevanceTier, AuthorityLevel, SourceType, List[str], bool, bool, bool, bool]:
        """
        Computes score, tier, authority, and breakdown reasons.
        """
        text = f"{url} {title} {snippet or ''}".lower()
        reasons: List[str] = []
        score = 0

        clean_vendor = vendor.strip().lower()
        clean_product = product.strip().lower() if product else None
        clean_edition = edition.strip().lower() if edition else None
        clean_version = version.strip().lower() if version else None

        matched_vendor = clean_vendor in text
        matched_product = bool(clean_product and clean_product in text)
        matched_edition = bool(clean_edition and clean_edition in text)
        matched_version = bool(clean_version and clean_version in text)

        # 1. Domain Authority Signal (Up to +35 pts)
        if domain_status == DomainValidationStatus.OFFICIAL:
            score += 35
            reasons.append("Official authoritative vendor domain verified (+35)")
            authority_level = AuthorityLevel.OFFICIAL_VENDOR
        elif domain_status == DomainValidationStatus.RELATED_OFFICIAL:
            score += 25
            reasons.append("Verified related official subsidiary / documentation host (+25)")
            authority_level = AuthorityLevel.OFFICIAL_DISTRIBUTOR
        else:
            score -= 20
            reasons.append("Non-official or unverified domain (-20)")
            authority_level = AuthorityLevel.TRUSTED_SECONDARY if "licensing" in text else AuthorityLevel.UNKNOWN

        # 2. Vendor Identity Signal (+20 pts)
        if matched_vendor:
            score += 20
            reasons.append(f"Vendor '{vendor}' identified (+20)")

        # 3. Product Match Signal (+20 pts)
        if matched_product:
            score += 20
            reasons.append(f"Product '{product}' matched in source (+20)")

        # 4. Edition Match Signal (+10 pts)
        if matched_edition:
            score += 10
            reasons.append(f"Edition '{edition}' matched in source (+10)")

        # 5. Version Match Signal (+10 pts)
        if matched_version:
            score += 10
            reasons.append(f"Version '{version}' matched in source (+10)")

        # 6. Licensing Terminology Signal (+15 pts)
        keyword_hits = [kw for kw in self.LICENSING_KEYWORDS if kw in text]
        if keyword_hits:
            score += 15
            reasons.append(f"Licensing terminology matched: {', '.join(keyword_hits[:3])} (+15)")

        # Source Type classification
        source_type = self.classify_source_type(url, title)
        if source_type in [SourceType.OFFICIAL_TERMS, SourceType.OFFICIAL_LICENSING_GUIDE, SourceType.OFFICIAL_PDF]:
            score += 5
            reasons.append(f"Authoritative document type ({source_type.value}) (+5)")

        # Bound score between 0 and 100
        final_score = max(0, min(100, score))

        # Assign Tier
        if final_score >= 85:
            tier = RelevanceTier.VERY_HIGH
        elif final_score >= 70:
            tier = RelevanceTier.HIGH
        elif final_score >= 50:
            tier = RelevanceTier.MEDIUM
        elif final_score >= 30:
            tier = RelevanceTier.LOW
        else:
            tier = RelevanceTier.IRRELEVANT

        return (
            final_score,
            tier,
            authority_level,
            source_type,
            reasons,
            matched_vendor,
            matched_product,
            matched_edition,
            matched_version
        )
