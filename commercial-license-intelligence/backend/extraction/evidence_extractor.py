"""
Rule-Based & Pattern-Driven Evidence Fact Extractor.
Parses relevant context blocks to extract discrete candidate facts with strict evidence traceability.
Enforces product match verification and anti-hallucination guardrails.
"""

import re
import hashlib
from typing import List, Optional, Tuple, Dict, Any

from backend.models.enums import (
    FactType,
    FactStatus,
    EvidenceType,
    ExtractionConfidence,
    AuthorityLevel,
    ScopeType,
)
from backend.schemas.extraction import ExtractedFactCandidate
from backend.extraction.relevant_content_detector import RelevantContextBlock
from backend.extraction.fact_normalizer import FactNormalizer
from backend.extraction.confidence_engine import ConfidenceEngine


def compute_text_hash(text: str) -> str:
    """Deterministic SHA-256 hash of normalized text snippet."""
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


class EvidenceExtractor:
    """
    Extracts structured licensing fact candidates directly from relevant source text snippets.
    """

    def __init__(
        self,
        normalizer: Optional[FactNormalizer] = None,
        confidence_engine: Optional[ConfidenceEngine] = None,
    ):
        self.normalizer = normalizer or FactNormalizer()
        self.confidence_engine = confidence_engine or ConfidenceEngine()

    def _validate_product_match(
        self,
        text: str,
        target_product: Optional[str] = None
    ) -> bool:
        """
        Confirms the evidence text is referring to the target product rather than an unrelated product.
        """
        if not target_product:
            return True
        prod_clean = target_product.strip().lower()
        text_lower = text.lower()
        if prod_clean in text_lower:
            return True
        return False

    def extract_candidates_from_block(
        self,
        block: RelevantContextBlock,
        target_vendor: str,
        target_product: Optional[str] = None,
        target_edition: Optional[str] = None,
        target_version: Optional[str] = None,
        authority: AuthorityLevel = AuthorityLevel.OFFICIAL_VENDOR
    ) -> List[ExtractedFactCandidate]:
        """
        Evaluates a context block and extracts discrete candidate facts with direct evidence.
        """
        text = block.text
        text_lower = text.lower()
        candidates: List[ExtractedFactCandidate] = []

        # Product matching evaluation
        prod_matched = self._validate_product_match(text, target_product)
        edition_matched = bool(target_edition and target_edition.lower() in text_lower)
        version_matched = bool(target_version and target_version.lower() in text_lower)

        # Helper to append fact
        def add_candidate(fact_type: FactType, raw_val: str, ev_type: EvidenceType = EvidenceType.DIRECT_STATEMENT):
            norm_val = self.normalizer.normalize(fact_type, raw_val)
            if norm_val == "UNKNOWN":
                return

            score, conf_tier = self.confidence_engine.calculate_confidence(
                authority=authority,
                product_matched=prod_matched,
                edition_matched=edition_matched,
                version_matched=version_matched,
                evidence_type=ev_type,
                is_scope_universal=(not target_product or prod_matched)
            )

            scope_type = ScopeType.PRODUCT if prod_matched else ScopeType.VENDOR
            scope_val = target_product if prod_matched else target_vendor

            candidates.append(ExtractedFactCandidate(
                fact_type=fact_type,
                fact_value=raw_val,
                normalized_value=norm_val,
                scope_type=scope_type,
                scope_value=scope_val or target_vendor,
                confidence=conf_tier,
                confidence_score=score,
                status=FactStatus.EXTRACTED,
                evidence_text=text,
                evidence_type=ev_type,
                page_number=block.page_number,
                section_name=block.section_name,
                document_id=block.document_id,
                source_id=block.source_id,
            ))

        # -------------------------------------------------------------
        # 1. LICENSE_CLASSIFICATION Extraction
        # -------------------------------------------------------------
        if re.search(r"\bcommercial\b", text_lower) and "non-commercial" not in text_lower:
            add_candidate(FactType.LICENSE_CLASSIFICATION, "COMMERCIAL")
        elif re.search(r"\bproprietary\b", text_lower):
            add_candidate(FactType.LICENSE_CLASSIFICATION, "PROPRIETARY")
        elif re.search(r"\bfreeware\b", text_lower) or "free for personal use" in text_lower:
            add_candidate(FactType.LICENSE_CLASSIFICATION, "FREEWARE")
        elif (
            re.search(r"\b(?:open\s+source|foss|floss)\b", text_lower)
            or re.search(r"\b(?:gpl|lgpl|mit|apache|bsd|sspl|psf)\b", text_lower)
            or "classpath exception" in text_lower
        ):
            add_candidate(FactType.LICENSE_CLASSIFICATION, "OPEN_SOURCE")
        elif "public domain" in text_lower or re.search(r"\bcc0\b", text_lower):
            add_candidate(FactType.LICENSE_CLASSIFICATION, "PUBLIC_DOMAIN")

        # -------------------------------------------------------------
        # 2. LICENSE_MODEL Extraction (Combined Legal + Commercial)
        # -------------------------------------------------------------
        legal_candidate = None
        if re.search(r"\b(?:psf|python\s+software\s+foundation)\b", text_lower):
            legal_candidate = "PSF License"
        elif re.search(r"\b(?:sspl|server\s+side\s+public\s+license)\b", text_lower):
            legal_candidate = "SSPL-1.0"
        elif "classpath exception" in text_lower:
            legal_candidate = "GPL-2.0 with Classpath Exception"
        elif re.search(r"\bapache(?:-2(?:\.0)?)?\b", text_lower):
            legal_candidate = "Apache-2.0"
        elif re.search(r"\b(?:gpl-3(?:\.0)?|gplv3|gpl\s+3)\b", text_lower):
            legal_candidate = "GPL-3.0"
        elif re.search(r"\b(?:gpl-2(?:\.0)?|gplv2|gpl\s+2)\b", text_lower):
            legal_candidate = "GPL-2.0"
        elif re.search(r"\blgpl\b", text_lower):
            legal_candidate = "LGPL"
        elif re.search(r"\bgpl\b", text_lower):
            legal_candidate = "GPL-3.0"
        elif re.search(r"\bmit\b", text_lower):
            legal_candidate = "MIT"
        elif re.search(r"\bbsd-?3-?clause\b", text_lower):
            legal_candidate = "BSD-3-Clause"
        elif re.search(r"\bbsd-?2-?clause\b", text_lower):
            legal_candidate = "BSD-2-Clause"
        elif re.search(r"\bbsd\b", text_lower):
            legal_candidate = "BSD"
        elif re.search(r"\b(?:mpl|mozilla\s+public\s+license)\b", text_lower):
            legal_candidate = "MPL"
        elif "public domain" in text_lower or re.search(r"\bcc0\b", text_lower):
            legal_candidate = "Public Domain"
        elif re.search(r"\bproprietary\b", text_lower):
            legal_candidate = "Proprietary"
        elif re.search(r"\bcommercial\b", text_lower) and "non-commercial" not in text_lower:
            legal_candidate = "Commercial"
        elif re.search(r"\bfreeware\b", text_lower):
            legal_candidate = "Freeware"

        comm_candidate = None
        is_steam = "steam" in (target_product or "").lower() or "steam" in text_lower
        is_subscriber_agreement = "subscriber agreement" in text_lower
        
        if is_steam or (is_subscriber_agreement and not any(k in text_lower for k in ("enterprise", "commercial", "per seat", "per core"))):
            legal_candidate = "Freeware"
            comm_candidate = None
        elif any(term in (target_product or "").lower() or term in text_lower for term in ("home & student", "home and student", "ltsc", "2016", "2019", "2021", "2024", "one-time")):
            comm_candidate = "Perpetual"
        elif "subscription" in text_lower or "saas" in text_lower:
            if "per seat" in text_lower or "per user" in text_lower or "named user" in text_lower:
                comm_candidate = "Per Seat Subscription"
            else:
                comm_candidate = "Subscription"
        elif "perpetual with maintenance" in text_lower or "active maintenance" in text_lower:
            comm_candidate = "Perpetual with Maintenance"
        elif "perpetual" in text_lower or "one-time purchase" in text_lower:
            comm_candidate = "Perpetual"
        elif "per core" in text_lower or "core-based" in text_lower:
            comm_candidate = "Per Core"
        elif "per device" in text_lower or "device-based" in text_lower:
            comm_candidate = "Per Device"
        elif "per user" in text_lower or "user-based" in text_lower:
            comm_candidate = "Per User"
        elif "concurrent" in text_lower or "floating" in text_lower:
            comm_candidate = "Concurrent User"

        if legal_candidate in ("MIT", "Apache-2.0", "GPL-2.0", "GPL-3.0", "LGPL", "BSD", "BSD-3-Clause", "BSD-2-Clause", "MPL", "GPL-2.0 with Classpath Exception"):
            add_candidate(FactType.LICENSE_MODEL, f"{legal_candidate} — Free/Open Source")
        elif legal_candidate == "PSF License":
            add_candidate(FactType.LICENSE_MODEL, "PSF License — Free/Open Source")
        elif legal_candidate == "SSPL-1.0":
            add_candidate(FactType.LICENSE_MODEL, "SSPL-1.0 — Free to Use")
        elif legal_candidate == "Public Domain":
            add_candidate(FactType.LICENSE_MODEL, "Public Domain — Free")
        elif legal_candidate == "Freeware":
            add_candidate(FactType.LICENSE_MODEL, "Freeware")
        elif comm_candidate:
            add_candidate(FactType.LICENSE_MODEL, comm_candidate)

        # -------------------------------------------------------------
        # 3. LICENSE_METRIC Extraction
        # -------------------------------------------------------------
        if "named user" in text_lower or "per user" in text_lower or "named-user" in text_lower:
            add_candidate(FactType.LICENSE_METRIC, "NAMED_USER")
        elif "concurrent user" in text_lower or "floating user" in text_lower:
            add_candidate(FactType.LICENSE_METRIC, "CONCURRENT_USER")
        elif "per core" in text_lower or "core-based" in text_lower:
            add_candidate(FactType.LICENSE_METRIC, "CORE")
        elif "per socket" in text_lower or "socket-based" in text_lower:
            add_candidate(FactType.LICENSE_METRIC, "SOCKET")
        elif "per device" in text_lower or "node-locked" in text_lower:
            add_candidate(FactType.LICENSE_METRIC, "DEVICE")

        # -------------------------------------------------------------
        # 4. LICENSE_REQUIRED Extraction
        # -------------------------------------------------------------
        if re.search(r"(?:requires|must\s+acquire|must\s+purchase)\s+(?:a\s+)?(?:separate\s+)?license", text_lower) or \
           re.search(r"license\s+is\s+required", text_lower) or \
           re.search(r"licensed\s+under", text_lower) or \
           "each named user requires a separate license" in text_lower:
            add_candidate(FactType.LICENSE_REQUIRED, "TRUE")
        elif "no license required" in text_lower or "free of charge" in text_lower:
            add_candidate(FactType.LICENSE_REQUIRED, "FALSE")

        # -------------------------------------------------------------
        # 5. TRIAL_AVAILABLE Extraction
        # -------------------------------------------------------------
        if re.search(r"\b(?:trial|evaluation)\b", text_lower) and "available" in text_lower or "evaluation version" in text_lower:
            add_candidate(FactType.TRIAL_AVAILABLE, "TRUE")

        # -------------------------------------------------------------
        # 6. SECONDARY_DEVICE_RIGHTS & VIRTUALIZATION
        # -------------------------------------------------------------
        if "secondary device" in text_lower or "portable device" in text_lower or "2 devices" in text_lower:
            if "permitted" in text_lower or "allowed" in text_lower or "up to 2" in text_lower:
                add_candidate(FactType.SECONDARY_DEVICE_RIGHTS, "ALLOWED")
            elif "prohibited" in text_lower:
                add_candidate(FactType.SECONDARY_DEVICE_RIGHTS, "NOT_ALLOWED")

        if "virtualization" in text_lower or "multiplexing" in text_lower or "vdi" in text_lower:
            if "requires" in text_lower or "cal" in text_lower:
                add_candidate(FactType.VIRTUALIZATION_RIGHTS, "RESTRICTED")
            elif "permitted" in text_lower:
                add_candidate(FactType.VIRTUALIZATION_RIGHTS, "ALLOWED")

        return candidates
