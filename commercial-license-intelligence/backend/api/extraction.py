"""FastAPI endpoints for the License Fact Extraction Engine."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.connection import get_db
from backend.models.enums import FactType, FactStatus, ExtractionConfidence
from backend.models.fact import LicenseFact, LicenseEvidence
from backend.schemas.extraction import (
    ApplicationExtractionRequest,
    DocumentExtractionRequest,
    FactSummaryResponse,
    FactDetailResponse,
    FactEvidenceResponse,
    ApplicationLicenseIntelligenceResponse,
)
from backend.extraction.license_extractor import LicenseExtractor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["License Fact Extraction"])


@router.post("/extraction/documents/{document_id}", response_model=List[FactSummaryResponse], status_code=status.HTTP_200_OK)
def extract_facts_from_document(
    document_id: int,
    request: Optional[DocumentExtractionRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Extracts structured licensing facts with traceable evidence from a collected document.
    """
    target_product = request.target_product if request else None
    target_edition = request.target_edition if request else None
    target_version = request.target_version if request else None

    extractor = LicenseExtractor()
    facts = extractor.extract_from_document(
        db=db,
        document_id=document_id,
        target_product=target_product,
        target_edition=target_edition,
        target_version=target_version
    )
    return [
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
        ) for f in facts
    ]


@router.post("/extraction/application", response_model=ApplicationLicenseIntelligenceResponse, status_code=status.HTTP_200_OK)
def extract_application_license_intelligence(
    request: ApplicationExtractionRequest,
    db: Session = Depends(get_db)
):
    """
    Synthesizes overall licensing intelligence for a software product across all already-collected evidence.
    Does not initiate external web scraping or discovery.
    """
    extractor = LicenseExtractor()
    return extractor.extract_for_application(
        db=db,
        vendor=request.vendor,
        product=request.product,
        edition=request.edition,
        version=request.version
    )


@router.get("/license-facts", response_model=List[FactSummaryResponse])
def list_license_facts(
    vendor: Optional[str] = Query(None, description="Filter by vendor"),
    product: Optional[str] = Query(None, description="Filter by product"),
    edition: Optional[str] = Query(None, description="Filter by edition"),
    version: Optional[str] = Query(None, description="Filter by version"),
    fact_type: Optional[FactType] = Query(None, description="Filter by fact type"),
    status_filter: Optional[FactStatus] = Query(None, alias="status", description="Filter by status"),
    confidence: Optional[ExtractionConfidence] = Query(None, description="Filter by confidence tier"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Retrieve filtered list of verified licensing facts."""
    query = db.query(LicenseFact)

    if vendor:
        query = query.filter(func.lower(LicenseFact.vendor_name) == vendor.strip().lower())
    if product:
        query = query.filter(func.lower(LicenseFact.product_name) == product.strip().lower())
    if edition:
        query = query.filter(func.lower(LicenseFact.edition) == edition.strip().lower())
    if version:
        query = query.filter(func.lower(LicenseFact.version) == version.strip().lower())
    if fact_type:
        query = query.filter(LicenseFact.fact_type == fact_type)
    if status_filter:
        query = query.filter(LicenseFact.status == status_filter)
    if confidence:
        query = query.filter(LicenseFact.confidence == confidence)

    facts = query.order_by(LicenseFact.id.desc()).offset(skip).limit(limit).all()
    return [
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
        ) for f in facts
    ]


@router.get("/license-facts/{fact_id}", response_model=FactDetailResponse)
def get_license_fact_detail(fact_id: int, db: Session = Depends(get_db)):
    """Retrieve detailed licensing fact with all linked evidence records."""
    fact = db.query(LicenseFact).filter(LicenseFact.id == fact_id).first()
    if not fact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"License fact with ID {fact_id} not found."
        )

    evidence_records = db.query(LicenseEvidence).filter(LicenseEvidence.license_fact_id == fact.id).all()

    return FactDetailResponse(
        id=fact.id,
        vendor_name=fact.vendor_name,
        product_name=fact.product_name,
        edition=fact.edition,
        version=fact.version,
        fact_type=fact.fact_type,
        fact_value=fact.fact_value,
        normalized_value=fact.normalized_value,
        scope_type=fact.scope_type,
        scope_value=fact.scope_value,
        confidence=fact.confidence,
        confidence_score=fact.confidence_score,
        status=fact.status,
        evidence_text=fact.evidence_text,
        page_number=fact.page_number,
        section_name=fact.section_name,
        source_id=fact.source_id,
        document_id=fact.document_id,
        extracted_at=fact.extracted_at,
        evidence_records=[FactEvidenceResponse(
            id=e.id,
            source_id=e.source_id,
            document_id=e.document_id,
            page_number=e.page_number,
            section=e.section,
            evidence_text=e.evidence_text,
            evidence_hash=e.evidence_hash,
            evidence_type=e.evidence_type
        ) for e in evidence_records]
    )
