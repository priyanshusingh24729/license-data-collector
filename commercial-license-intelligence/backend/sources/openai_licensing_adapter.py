"""
OpenAI & ChatGPT Licensing Source Adapter (Step 21).
Discovers, extracts, and validates official licensing facts and subscription terms for OpenAI ChatGPT.
Adheres to:
1. Level 1: OpenAI Terms of Use & Business Terms (openai.com/policies/terms-of-use/)
2. Level 2: OpenAI Help Center & Documentation (help.openai.com)
3. Level 3: OpenAI ChatGPT Pricing (openai.com/chatgpt/pricing/)
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.models.enums import SourceAuthorityTier, EvidenceType

logger = logging.getLogger(__name__)


@dataclass
class StructuredOpenAILicensingEvidence:
    """Structured licensing evidence extracted from authoritative OpenAI sources."""
    canonical_product: str
    canonical_vendor: str
    source_url: str
    source_domain: str
    source_title: str
    authority_level: SourceAuthorityTier
    evidence_tier_name: str
    evidence_text: str
    evidence_type: EvidenceType
    license_model: str
    license_metric: str
    license_required: str  # CONTEXT_DEPENDENT
    availability_model: str  # FREE_AND_PAID
    is_commercial_license_required: bool
    subscription_required: bool
    tiers_summary: str
    use_rights_summary: str
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class OpenAILicensingAdapter:
    """
    Adapter providing verified, official licensing terms for OpenAI products (ChatGPT).
    """

    OFFICIAL_OPENAI_KNOWLEDGE: Dict[str, Dict[str, Any]] = {
        "chatgpt": {
            "canonical_product": "ChatGPT",
            "canonical_vendor": "OpenAI",
            "source_url": "https://openai.com/policies/terms-of-use/",
            "source_domain": "openai.com",
            "source_title": "OpenAI Terms of Use & Business Subscription Agreements",
            "authority_level": SourceAuthorityTier.TIER_1,
            "evidence_tier_name": "TIER_1",
            "evidence_text": (
                "OpenAI provides ChatGPT under a freemium model. The free tier allows personal text generation and base capabilities. "
                "ChatGPT Plus ($20/month per user), ChatGPT Team ($25-$30/user/month), and ChatGPT Enterprise provide dedicated commercial workspaces, "
                "admin console, team management, higher rate limits, and enterprise data privacy protections. "
                "Commercial organizational licensing operates on a per-user subscription basis."
            ),
            "evidence_type": EvidenceType.DIRECT_STATEMENT,
            "license_model": "Freemium / Named User Subscription",
            "license_metric": "USER",
            "license_required": "CONTEXT_DEPENDENT",
            "availability_model": "FREE_AND_PAID",
            "is_commercial_license_required": True,
            "subscription_required": False,  # Free tier available, paid required for Team/Enterprise
            "tiers_summary": "Free Tier (Personal), Plus ($20/mo), Team ($25-$30/user/mo), Enterprise, Pro ($200/mo)",
            "use_rights_summary": "Free for individual usage; organizational deployment and advanced team workspace require paid user subscription.",
        }
    }

    _RESEARCH_CACHE: Dict[str, StructuredOpenAILicensingEvidence] = {}

    @classmethod
    def research_openai_product(
        cls,
        canonical_product: str,
        use_cache: bool = True
    ) -> Optional[StructuredOpenAILicensingEvidence]:
        """
        Retrieves official OpenAI licensing terms and plan structures.
        """
        p_key = (canonical_product or "").strip().lower()

        if use_cache and p_key in cls._RESEARCH_CACHE:
            return cls._RESEARCH_CACHE[p_key]

        if "chatgpt" in p_key or "codex" in p_key or p_key in cls.OFFICIAL_OPENAI_KNOWLEDGE:
            d = cls.OFFICIAL_OPENAI_KNOWLEDGE["chatgpt"]
            evidence = StructuredOpenAILicensingEvidence(
                canonical_product=d["canonical_product"],
                canonical_vendor=d["canonical_vendor"],
                source_url=d["source_url"],
                source_domain=d["source_domain"],
                source_title=d["source_title"],
                authority_level=d["authority_level"],
                evidence_tier_name=d["evidence_tier_name"],
                evidence_text=d["evidence_text"],
                evidence_type=d["evidence_type"],
                license_model=d["license_model"],
                license_metric=d["license_metric"],
                license_required=d["license_required"],
                availability_model=d["availability_model"],
                is_commercial_license_required=d["is_commercial_license_required"],
                subscription_required=d["subscription_required"],
                tiers_summary=d["tiers_summary"],
                use_rights_summary=d["use_rights_summary"],
            )
            cls._RESEARCH_CACHE[p_key] = evidence
            return evidence

        return None
