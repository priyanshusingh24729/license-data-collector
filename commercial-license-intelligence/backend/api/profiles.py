"""FastAPI endpoints for License Knowledge Profile Consolidation."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.connection import get_db
from backend.models.enums import ProfileStatus
from backend.models.profile import LicenseProfile, LicenseProfileFact
from backend.models.fact import LicenseFact
from backend.models.source import LicenseSource
from backend.consolidation.profile_schemas import (
    ApplicationProfileRequest,
    LicenseProfileResponse,
    ProfileVersionResponse,
    FieldExplanation,
    ProfileSummaryBlock,
)
from backend.consolidation.profile_consolidator import LicenseProfileConsolidator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profiles", tags=["License Knowledge Profile Consolidation"])


@router.post("/application", response_model=LicenseProfileResponse, status_code=status.HTTP_200_OK)
def consolidate_application_profile(
    request: ApplicationProfileRequest,
    db: Session = Depends(get_db)
):
    """
    Consolidates already-validated facts into a version- and edition-aware license intelligence profile.
    Does not initiate external web scraping or document discovery.
    """
    consolidator = LicenseProfileConsolidator()
    return consolidator.consolidate_profile(
        db=db,
        vendor=request.vendor,
        product=request.product,
        edition=request.edition,
        version=request.version
    )


@router.get("", response_model=List[LicenseProfileResponse])
def list_license_profiles(
    vendor: Optional[str] = Query(None, description="Filter by vendor"),
    product: Optional[str] = Query(None, description="Filter by product"),
    edition: Optional[str] = Query(None, description="Filter by edition"),
    version: Optional[str] = Query(None, description="Filter by version"),
    status_filter: Optional[ProfileStatus] = Query(None, alias="status", description="Filter by profile status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Retrieve filtered list of consolidated license profiles."""
    query = db.query(LicenseProfile)

    if vendor:
        query = query.filter(func.lower(LicenseProfile.vendor_name) == vendor.strip().lower())
    if product:
        query = query.filter(func.lower(LicenseProfile.product_name) == product.strip().lower())
    if edition:
        query = query.filter(func.lower(LicenseProfile.edition) == edition.strip().lower())
    if version:
        query = query.filter(func.lower(LicenseProfile.version) == version.strip().lower())
    if status_filter:
        query = query.filter(LicenseProfile.profile_status == status_filter)

    profiles = query.order_by(LicenseProfile.id.desc()).offset(skip).limit(limit).all()

    results = []
    for p in profiles:
        exp_dict = {}
        if p.explanation_json:
            for k, v in p.explanation_json.items():
                exp_dict[k] = FieldExplanation(**v)

        summary_block = ProfileSummaryBlock(
            required=p.license_required,
            classification=p.license_classification,
            model=p.license_model,
            metric=p.license_metric,
            duration=p.license_duration
        )

        results.append(LicenseProfileResponse(
            id=p.id,
            vendor=p.vendor_name,
            product=p.product_name,
            edition=p.edition,
            version=p.version,
            license_classification=p.license_classification,
            license_required=p.license_required,
            license_model=p.license_model,
            license_metric=p.license_metric,
            license_duration=p.license_duration,
            commercial_use=p.commercial_use,
            educational_use=p.educational_use,
            trial_available=p.trial_available,
            overall_confidence=p.overall_confidence,
            profile_status=p.profile_status,
            validated_fact_count=p.validated_fact_count,
            review_fact_count=p.review_fact_count,
            conflict_fact_count=p.conflict_fact_count,
            unknown_fact_count=p.unknown_fact_count,
            profile_hash=p.profile_hash,
            explanations=exp_dict,
            license_summary=summary_block,
            generated_at=p.generated_at
        ))

    return results


@router.get("/{profile_id}", response_model=LicenseProfileResponse)
def get_license_profile_detail(profile_id: int, db: Session = Depends(get_db)):
    """Retrieve detailed license profile with underlying supporting facts and evidence citations."""
    p = db.query(LicenseProfile).filter(LicenseProfile.id == profile_id).first()
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"License profile ID {profile_id} not found."
        )

    # Fetch supporting facts
    assoc_facts = db.query(LicenseProfileFact).filter(
        LicenseProfileFact.profile_id == p.id
    ).all()

    supporting_facts_payload = []
    for af in assoc_facts:
        fact_obj = db.query(LicenseFact).filter(LicenseFact.id == af.license_fact_id).first()
        if fact_obj:
            src_name = None
            src_url = None
            if fact_obj.source_id:
                src = db.query(LicenseSource).filter(LicenseSource.id == fact_obj.source_id).first()
                if src:
                    src_name = src.source_name
                    src_url = src.source_url

            supporting_facts_payload.append({
                "id": fact_obj.id,
                "fact_type": fact_obj.fact_type.value,
                "value": fact_obj.normalized_value,
                "confidence": fact_obj.confidence.value,
                "status": fact_obj.status.value,
                "source_name": src_name,
                "source_url": src_url,
                "document_id": fact_obj.document_id,
                "page_number": fact_obj.page_number,
                "evidence_text": fact_obj.evidence_text
            })

    exp_dict = {}
    if p.explanation_json:
        for k, v in p.explanation_json.items():
            exp_dict[k] = FieldExplanation(**v)

    summary_block = ProfileSummaryBlock(
        required=p.license_required,
        classification=p.license_classification,
        model=p.license_model,
        metric=p.license_metric,
        duration=p.license_duration
    )

    return LicenseProfileResponse(
        id=p.id,
        vendor=p.vendor_name,
        product=p.product_name,
        edition=p.edition,
        version=p.version,
        license_classification=p.license_classification,
        license_required=p.license_required,
        license_model=p.license_model,
        license_metric=p.license_metric,
        license_duration=p.license_duration,
        commercial_use=p.commercial_use,
        educational_use=p.educational_use,
        trial_available=p.trial_available,
        overall_confidence=p.overall_confidence,
        profile_status=p.profile_status,
        validated_fact_count=p.validated_fact_count,
        review_fact_count=p.review_fact_count,
        conflict_fact_count=p.conflict_fact_count,
        unknown_fact_count=p.unknown_fact_count,
        profile_hash=p.profile_hash,
        explanations=exp_dict,
        supporting_facts=supporting_facts_payload,
        license_summary=summary_block,
        generated_at=p.generated_at
    )


@router.get("/{profile_id}/history", response_model=List[ProfileVersionResponse])
def get_profile_history(profile_id: int, db: Session = Depends(get_db)):
    """Retrieve historical version snapshots for a profile."""
    consolidator = LicenseProfileConsolidator()
    return consolidator.get_profile_history(db=db, profile_id=profile_id)
