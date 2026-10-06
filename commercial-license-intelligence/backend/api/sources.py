"""FastAPI endpoints for License Source Registry."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.models.enums import (
    SourceType,
    AuthorityLevel,
    ScopeType,
    SourceStatus,
)
from backend.schemas.source import (
    LicenseSourceCreate,
    LicenseSourceUpdate,
    LicenseSourceResponse,
    SourceResolutionResponse,
)
from backend.services.source_registry_service import (
    create_source,
    get_source_by_id,
    list_sources,
    update_source,
    deactivate_source,
    get_applicable_sources,
)
from backend.sources.registry import seed_initial_sources

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sources", tags=["Source Registry"])


@router.get("", response_model=List[LicenseSourceResponse])
def get_sources(
    vendor: Optional[str] = Query(None, description="Filter by vendor name"),
    product: Optional[str] = Query(None, description="Filter by product name"),
    source_type: Optional[SourceType] = Query(None, description="Filter by source type"),
    authority_level: Optional[AuthorityLevel] = Query(None, description="Filter by authority level"),
    status: Optional[SourceStatus] = Query(None, description="Filter by source status"),
    scope_type: Optional[ScopeType] = Query(None, description="Filter by scope type"),
    active_only: bool = Query(False, description="Filter only active sources"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Retrieve registered license sources with optional filtering."""
    return list_sources(
        db=db,
        vendor=vendor,
        product=product,
        source_type=source_type,
        authority_level=authority_level,
        status=status,
        scope_type=scope_type,
        active_only=active_only,
        skip=skip,
        limit=limit
    )


@router.get("/resolve", response_model=SourceResolutionResponse)
def resolve_sources(
    vendor: str = Query(..., description="Target vendor name"),
    product: Optional[str] = Query(None, description="Target product name"),
    edition: Optional[str] = Query(None, description="Target product edition"),
    version: Optional[str] = Query(None, description="Target product version"),
    active_only: bool = Query(True, description="Only resolve active sources"),
    db: Session = Depends(get_db)
):
    """
    Resolve and rank all applicable licensing sources for a software target.
    Applies deterministic priority ordering:
    VERSION -> EDITION -> PRODUCT -> VENDOR
    """
    resolved = get_applicable_sources(
        db=db,
        vendor_name=vendor,
        product_name=product,
        edition=edition,
        version=version,
        active_only=active_only
    )
    return SourceResolutionResponse(
        vendor=vendor,
        product=product,
        edition=edition,
        version=version,
        total_sources=len(resolved),
        sources=resolved
    )


@router.get("/{source_id}", response_model=LicenseSourceResponse)
def get_source(source_id: int, db: Session = Depends(get_db)):
    """Retrieve details for a single license source."""
    src = get_source_by_id(db, source_id)
    if not src:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with ID {source_id} not found."
        )
    return src


@router.post("", response_model=LicenseSourceResponse, status_code=status.HTTP_201_CREATED)
def register_source(source_in: LicenseSourceCreate, db: Session = Depends(get_db)):
    """Register a new license source."""
    try:
        return create_source(db, source_in)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(err)
        )


@router.patch("/{source_id}", response_model=LicenseSourceResponse)
def patch_source(
    source_id: int,
    source_update: LicenseSourceUpdate,
    db: Session = Depends(get_db)
):
    """Update metadata for an existing license source."""
    updated = update_source(db, source_id, source_update)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with ID {source_id} not found."
        )
    return updated


@router.delete("/{source_id}", response_model=LicenseSourceResponse)
def delete_source(source_id: int, db: Session = Depends(get_db)):
    """
    Soft-delete a license source (marks as INACTIVE to preserve historical evidence integrity).
    """
    deactivated = deactivate_source(db, source_id)
    if not deactivated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with ID {source_id} not found."
        )
    return deactivated


@router.post("/seed/initial", status_code=status.HTTP_200_OK)
def trigger_initial_seed(db: Session = Depends(get_db)):
    """Seed verified official sources for Adobe, Microsoft, and Autodesk."""
    seeded = seed_initial_sources(db)
    return {
        "status": "ok",
        "message": f"Successfully seeded {seeded} new official sources.",
        "seeded_count": seeded
    }
