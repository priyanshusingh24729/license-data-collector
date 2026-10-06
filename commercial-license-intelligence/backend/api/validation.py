"""FastAPI endpoints for Evidence Validation & Quality Engine."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.connection import get_db
from backend.models.fact import LicenseFact
from backend.models.source import LicenseSource
from backend.models.validation import FactValidationRun
from backend.schemas.extraction import ApplicationExtractionRequest
from backend.validation.validation_result import (
    FactValidationResult,
    FactValidationDetailResponse,
    ApplicationValidationSummaryResponse,
    ValidationChecks,
)
from backend.validation.fact_validator import FactValidator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/validation", tags=["Evidence Validation & Quality Engine"])


@router.post("/facts/{fact_id}", response_model=FactValidationResult, status_code=status.HTTP_200_OK)
def validate_single_fact(
    fact_id: int,
    target_edition: Optional[str] = Query(None),
    target_version: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Validates an individual license fact against primary evidence, product scope, and semantic rules.
    """
    fact = db.query(LicenseFact).filter(LicenseFact.id == fact_id).first()
    if not fact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"License fact ID {fact_id} not found."
        )

    validator = FactValidator()
    return validator.validate_fact(
        db=db,
        fact=fact,
        target_edition=target_edition,
        target_version=target_version
    )


@router.post("/documents/{document_id}", response_model=List[FactValidationResult], status_code=status.HTTP_200_OK)
def validate_document_facts(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Validates all extracted licensing facts referencing a specific collected document.
    """
    validator = FactValidator()
    return validator.validate_document_facts(db=db, document_id=document_id)


@router.post("/application", response_model=ApplicationValidationSummaryResponse, status_code=status.HTTP_200_OK)
def validate_application_intelligence(
    request: ApplicationExtractionRequest,
    db: Session = Depends(get_db)
):
    """
    Validates all applicable licensing facts for an application target.
    """
    validator = FactValidator()
    return validator.validate_application_target(
        db=db,
        vendor=request.vendor,
        product=request.product,
        edition=request.edition,
        version=request.version
    )


@router.get("/facts/{fact_id}", response_model=FactValidationDetailResponse)
def get_fact_validation_detail(fact_id: int, db: Session = Depends(get_db)):
    """
    Retrieves full validation audit trail, checks breakdown, and quality metrics for a fact.
    """
    fact = db.query(LicenseFact).filter(LicenseFact.id == fact_id).first()
    if not fact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"License fact ID {fact_id} not found."
        )

    last_run = db.query(FactValidationRun).filter(
        FactValidationRun.license_fact_id == fact.id
    ).order_by(FactValidationRun.id.desc()).first()

    src_name = None
    src_url = None
    if fact.source_id:
        src = db.query(LicenseSource).filter(LicenseSource.id == fact.source_id).first()
        if src:
            src_name = src.source_name
            src_url = src.source_url

    checks = ValidationChecks(**(last_run.checks_summary if last_run and last_run.checks_summary else {}))
    reasons = [last_run.validation_reason] if (last_run and last_run.validation_reason) else []

    return FactValidationDetailResponse(
        fact_id=fact.id,
        vendor_name=fact.vendor_name,
        product_name=fact.product_name,
        edition=fact.edition,
        version=fact.version,
        fact_type=fact.fact_type,
        normalized_value=fact.normalized_value,
        status=fact.status,
        quality=fact.confidence,
        quality_score=fact.confidence_score,
        checks=checks,
        reasons=reasons,
        source_name=src_name,
        source_url=src_url,
        document_id=fact.document_id,
        page_number=fact.page_number,
        evidence_text=fact.evidence_text,
        validator_version=last_run.validator_version if last_run else "1.0.0",
        validated_at=last_run.validated_at if last_run else fact.created_at
    )


@router.get("/application", response_model=ApplicationValidationSummaryResponse)
def get_application_quality_summary(
    vendor: str = Query(..., description="Software publisher"),
    product: str = Query(..., description="Software product"),
    edition: Optional[str] = Query(None),
    version: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Returns high-level quality metrics and review queues for an application target.
    """
    validator = FactValidator()
    return validator.validate_application_target(
        db=db,
        vendor=vendor,
        product=product,
        edition=edition,
        version=version
    )
