"""
Research Cache (Post Step 21 Quality System - Sections 25 & 26).
Deterministic cache for discovered official licensing sources, passage extractions,
and validated canonical identities to prevent redundant research overhead.
"""

import hashlib
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class CachedEvidenceEntry:
    """Cached research evidence unit."""
    canonical_product: str
    canonical_vendor: str
    source_url: str
    source_title: str
    source_authority: str
    evidence_type: str
    evidence_text: str
    license_model: str
    license_metric: str
    license_required: str
    classification: str
    availability: str
    scope_match_tier: str
    evidence_hash: str
    cached_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_valid: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["cached_at"] = self.cached_at.isoformat()
        return d


from backend.sources.discovery.domain_registry import DomainRegistryService


class ResearchCache:
    """
    In-memory and persistent research cache keyed by (canonical_product, canonical_vendor).
    Enforces domain-to-vendor integrity on cache storage and retrieval.
    """

    _CACHE: Dict[str, CachedEvidenceEntry] = {}

    @classmethod
    def _compute_key(cls, canonical_product: str, canonical_vendor: Optional[str] = None) -> str:
        p_clean = (canonical_product or "").strip().lower()
        v_clean = (canonical_vendor or "").strip().lower()
        return f"{v_clean}::{p_clean}"

    @classmethod
    def _compute_evidence_hash(cls, source_url: str, evidence_text: str) -> str:
        raw = f"{source_url}|{evidence_text}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    @classmethod
    def get(cls, canonical_product: str, canonical_vendor: Optional[str] = None) -> Optional[CachedEvidenceEntry]:
        """Retrieves cached evidence entry if present and valid."""
        k = cls._compute_key(canonical_product, canonical_vendor)
        entry = cls._CACHE.get(k)

        # Fallback 1: Try normalized vendor variant if canonical_vendor provided
        if (not entry or not entry.is_valid) and canonical_vendor:
            from backend.inventory.detection.detection_normalizer import DetectionNormalizer
            norm_v = DetectionNormalizer.normalize_publisher(canonical_vendor, canonical_product)
            if norm_v and norm_v.lower() != (canonical_vendor or "").strip().lower():
                k_norm = cls._compute_key(canonical_product, norm_v)
                candidate = cls._CACHE.get(k_norm)
                if candidate and candidate.is_valid:
                    entry = candidate

        # Fallback 2: Product match across cache if vendor was omitted or unknown
        if not entry or not entry.is_valid:
            p_clean = (canonical_product or "").strip().lower()
            if p_clean:
                for ck, cand in list(cls._CACHE.items()):
                    if cand and cand.is_valid and ck.endswith(f"::{p_clean}"):
                        entry = cand
                        break

        if entry and entry.is_valid:
            # Re-validate domain check on retrieval
            v_clean = (entry.canonical_vendor or canonical_vendor or "").strip().lower()
            if entry.source_url and v_clean not in ("unknown", "various", "n/a", "none", ""):
                if not DomainRegistryService.is_official_domain(None, entry.source_url, v_clean):
                    entry.is_valid = False
                    cls._CACHE.pop(k, None)
                    return None
            return entry
        return None

    @classmethod
    def put(
        cls,
        canonical_product: str,
        canonical_vendor: str,
        source_url: str,
        source_title: str,
        source_authority: str,
        evidence_type: str,
        evidence_text: str,
        license_model: str,
        license_metric: str,
        license_required: str,
        classification: str,
        availability: str,
        scope_match_tier: str,
    ) -> CachedEvidenceEntry:
        """Stores a validated research evidence result in the cache."""
        v_clean = (canonical_vendor or "").strip().lower()
        if source_url and v_clean not in ("unknown", "various", "n/a", "none", ""):
            if not DomainRegistryService.is_official_domain(None, source_url, v_clean):
                raise ValueError(f"Cannot cache evidence URL '{source_url}' for unrelated vendor '{canonical_vendor}'")

        k = cls._compute_key(canonical_product, canonical_vendor)
        ev_hash = cls._compute_evidence_hash(source_url, evidence_text)
        entry = CachedEvidenceEntry(
            canonical_product=canonical_product,
            canonical_vendor=canonical_vendor,
            source_url=source_url,
            source_title=source_title,
            source_authority=source_authority,
            evidence_type=evidence_type,
            evidence_text=evidence_text,
            license_model=license_model,
            license_metric=license_metric,
            license_required=license_required,
            classification=classification,
            availability=availability,
            scope_match_tier=scope_match_tier,
            evidence_hash=ev_hash,
        )
        cls._CACHE[k] = entry
        return entry

    @classmethod
    def clear(cls) -> None:
        """Clears cache entries."""
        cls._CACHE.clear()

    @classmethod
    def size(cls) -> int:
        """Returns total cached items."""
        return len(cls._CACHE)
