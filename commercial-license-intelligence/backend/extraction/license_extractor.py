"""
License Fact Extraction Coordinator.
Coordinates relevant text detection, pattern extraction, evidence anchoring,
confidence scoring, conflict detection, and historical fact persistence.
Operates exclusively on already-collected evidence without initiating network requests.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.enums import (
    FactType,
    FactStatus,
    EvidenceType,
    ExtractionConfidence,
    ExtractionRunStatus,
    AuthorityLevel,
    ScopeType,
)
from backend.models.collection import CollectedDocument, DocumentPage
from backend.models.source import LicenseSource
from backend.models.api_document import ApiDocument
from backend.models.fact import LicenseFact, LicenseEvidence, ExtractionRun
from backend.schemas.extraction import (
    ExtractedFactCandidate,
    ApplicationLicenseIntelligenceResponse,
    FactSummaryResponse,
    FactConflictItem,
)
from backend.extraction.relevant_content_detector import RelevantContentDetector, RelevantContextBlock
from backend.extraction.fact_normalizer import FactNormalizer
from backend.extraction.confidence_engine import ConfidenceEngine
from backend.extraction.conflict_detector import ConflictDetector
from backend.extraction.evidence_extractor import EvidenceExtractor, compute_text_hash

logger = logging.getLogger(__name__)


class LicenseExtractor:
    """
    Main extraction engine converting collected HTML, PDF, and API evidence into structured licensing facts.
    """

    def __init__(
        self,
        detector: Optional[RelevantContentDetector] = None,
        extractor: Optional[EvidenceExtractor] = None,
        conflict_detector: Optional[ConflictDetector] = None,
    ):
        self.detector = detector or RelevantContentDetector()
        self.extractor = extractor or EvidenceExtractor()
        self.conflict_detector = conflict_detector or ConflictDetector()

    def extract_from_document(
        self,
        db: Session,
        document_id: int,
        target_product: Optional[str] = None,
        target_edition: Optional[str] = None,
        target_version: Optional[str] = None,
    ) -> List[LicenseFact]:
        """
        Extracts verified licensing facts from a single CollectedDocument record.
        """
        doc = db.query(CollectedDocument).filter(CollectedDocument.id == document_id).first()
        if not doc:
            logger.warning(f"Document ID {document_id} not found for extraction.")
            return []

        # Lookup source authority level if source_id is attached
        authority = AuthorityLevel.OFFICIAL_VENDOR
        if doc.source_id:
            src = db.query(LicenseSource).filter(LicenseSource.id == doc.source_id).first()
            if src and src.authority_level:
                authority = src.authority_level

        # 1. Harvest relevant context blocks
        blocks: List[RelevantContextBlock] = []
        pages = db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).order_by(DocumentPage.page_number.asc()).all()

        if pages:
            blocks = self.detector.scan_pages(pages, document_id=doc.id, source_id=doc.source_id)
        elif doc.clean_text:
            blocks = self.detector.scan_text(doc.clean_text, document_id=doc.id, source_id=doc.source_id)

        # 2. Extract candidate facts from each block
        candidates: List[ExtractedFactCandidate] = []
        for b in blocks:
            cands = self.extractor.extract_candidates_from_block(
                block=b,
                target_vendor=doc.vendor_name,
                target_product=target_product,
                target_edition=target_edition,
                target_version=target_version,
                authority=authority
            )
            candidates.extend(cands)

        # 3. Detect and mark conflicts
        processed_candidates, conflict_items = self.conflict_detector.detect_conflicts(candidates)

        # 4. Create Extraction Run Record
        run_record = ExtractionRun(
            source_document_id=doc.id,
            vendor_name=doc.vendor_name,
            product_name=target_product,
            edition=target_edition,
            version=target_version,
            status=ExtractionRunStatus.COMPLETED,
            facts_found=len(candidates),
            facts_validated=len([c for c in processed_candidates if c.status == FactStatus.EXTRACTED]),
            conflicts_found=len(conflict_items),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
        db.add(run_record)
        db.commit()

        # 5. Persist License Facts and Evidence Records
        persisted_facts: List[LicenseFact] = []
        seen_fact_signatures = set()

        for cand in processed_candidates:
            sig = (cand.fact_type, cand.normalized_value, cand.page_number, cand.evidence_text)
            if sig in seen_fact_signatures:
                continue
            seen_fact_signatures.add(sig)

            ev_hash = compute_text_hash(cand.evidence_text)

            # Check if this exact fact and evidence already exists (prevent duplicate rows)
            existing_fact = db.query(LicenseFact).filter(
                LicenseFact.vendor_name == doc.vendor_name,
                LicenseFact.fact_type == cand.fact_type,
                LicenseFact.normalized_value == cand.normalized_value,
                LicenseFact.evidence_hash == ev_hash
            ).first()

            if existing_fact:
                persisted_facts.append(existing_fact)
                continue

            fact_obj = LicenseFact(
                vendor_name=doc.vendor_name,
                product_name=target_product or doc.vendor_name,
                edition=target_edition,
                version=target_version,
                fact_type=cand.fact_type,
                fact_value=cand.fact_value,
                normalized_value=cand.normalized_value,
                scope_type=cand.scope_type,
                scope_value=cand.scope_value,
                confidence=cand.confidence,
                confidence_score=cand.confidence_score,
                status=FactStatus.VALIDATED if cand.confidence_score >= 0.7 else cand.status,
                source_id=doc.source_id,
                document_id=doc.id,
                page_number=cand.page_number,
                section_name=cand.section_name,
                evidence_text=cand.evidence_text,
                evidence_hash=ev_hash,
                evidence_type=cand.evidence_type,
                extracted_at=datetime.now(timezone.utc),
                verified_at=datetime.now(timezone.utc) if cand.confidence_score >= 0.7 else None
            )
            db.add(fact_obj)
            db.commit()
            db.refresh(fact_obj)

            # Add Evidence Record
            ev_record = LicenseEvidence(
                license_fact_id=fact_obj.id,
                source_id=doc.source_id,
                document_id=doc.id,
                page_number=cand.page_number,
                section=cand.section_name,
                evidence_text=cand.evidence_text,
                evidence_hash=ev_hash,
                evidence_type=cand.evidence_type,
                created_at=datetime.now(timezone.utc)
            )
            db.add(ev_record)
            persisted_facts.append(fact_obj)

        db.commit()
        return persisted_facts

    def extract_for_application(
        self,
        db: Session,
        vendor: str,
        product: str,
        edition: Optional[str] = None,
        version: Optional[str] = None
    ) -> ApplicationLicenseIntelligenceResponse:
        """
        Extracts consolidated licensing intelligence for an application target across all already-collected evidence.
        """
        clean_v = vendor.strip()
        clean_p = product.strip()

        # 1. Lookup all relevant collected documents for this vendor
        docs = db.query(CollectedDocument).filter(
            func.lower(CollectedDocument.vendor_name) == clean_v.lower()
        ).all()

        if not docs:
            return ApplicationLicenseIntelligenceResponse(
                vendor=clean_v,
                product=clean_p,
                edition=edition,
                version=version,
                status="NO_EVIDENCE_AVAILABLE",
                message=f"No collected documents found for {clean_v}. Collect official sources first using Steps 3–6."
            )

        all_facts: List[LicenseFact] = []
        for doc in docs:
            doc_facts = self.extract_from_document(
                db=db,
                document_id=doc.id,
                target_product=clean_p,
                target_edition=edition,
                target_version=version
            )
            all_facts.extend(doc_facts)

        # 2. Consolidate Highest Confidence Fact Values per FactType
        by_type: Dict[FactType, List[LicenseFact]] = {}
        for f in all_facts:
            by_type.setdefault(f.fact_type, []).append(f)

        def get_best_value(ft: FactType) -> Optional[str]:
            items = by_type.get(ft, [])
            if not items:
                return "UNKNOWN"
            # Sort by confidence score descending
            items_sorted = sorted(items, key=lambda x: x.confidence_score, reverse=True)
            return items_sorted[0].normalized_value

        # Build responses
        classification = get_best_value(FactType.LICENSE_CLASSIFICATION)
        license_req = get_best_value(FactType.LICENSE_REQUIRED)
        license_model = get_best_value(FactType.LICENSE_MODEL)
        license_metric = get_best_value(FactType.LICENSE_METRIC)
        duration = get_best_value(FactType.LICENSE_DURATION)
        comm_use = get_best_value(FactType.COMMERCIAL_USE)
        edu_use = get_best_value(FactType.EDUCATIONAL_USE)
        trial_avail = get_best_value(FactType.TRIAL_AVAILABLE)

        # Compute overall confidence
        scores = [f.confidence_score for f in all_facts]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        if avg_score >= 0.8:
            overall_tier = ExtractionConfidence.VERY_HIGH
        elif avg_score >= 0.65:
            overall_tier = ExtractionConfidence.HIGH
        elif avg_score >= 0.45:
            overall_tier = ExtractionConfidence.MEDIUM
        elif avg_score > 0.0:
            overall_tier = ExtractionConfidence.LOW
        else:
            overall_tier = ExtractionConfidence.UNKNOWN

        # Conflict items
        conflicts: List[FactConflictItem] = []
        for ft, facts_list in by_type.items():
            distinct_vals = list(set([f.normalized_value for f in facts_list if f.normalized_value != "UNKNOWN"]))
            if len(distinct_vals) > 1:
                conflicts.append(FactConflictItem(
                    fact_type=ft,
                    values=distinct_vals,
                    conflicting_fact_ids=[f.id for f in facts_list],
                    reasons=[f"Multiple conflicting values detected: {', '.join(distinct_vals)}"]
                ))

        fact_summaries = [
            FactSummaryResponse(
                id=f.id,
                vendor_name=f.vendor_name,
                product_name=f.product_name,
                edition=f.edition,
                version=f.version,
                fact_type=f.fact_type,
                fact_value=f.fact_value,
                normalized_value=f.normalized_value,
                scope_type=f.scope_type,
                scope_value=f.scope_value,
                confidence=f.confidence,
                confidence_score=f.confidence_score,
                status=f.status,
                evidence_text=f.evidence_text,
                page_number=f.page_number,
                section_name=f.section_name,
                source_id=f.source_id,
                document_id=f.document_id,
                extracted_at=f.extracted_at
            ) for f in all_facts
        ]

        return ApplicationLicenseIntelligenceResponse(
            vendor=clean_v,
            product=clean_p,
            edition=edition,
            version=version,
            classification=classification,
            license_required=license_req,
            license_model=license_model,
            license_metric=license_metric,
            license_duration=duration,
            commercial_use=comm_use,
            educational_use=edu_use,
            trial_available=trial_avail,
            overall_confidence=overall_tier,
            facts=fact_summaries,
            conflicts=conflicts,
            status="COMPLETED"
        )
