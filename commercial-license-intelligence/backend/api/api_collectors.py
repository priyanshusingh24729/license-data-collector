"""FastAPI endpoints for the Optional Vendor API Collector."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.connection import get_db
from backend.models.enums import ApiCollectionStatus, SourceType, CollectionMethod, AccessType, AuthenticationType
from backend.models.source import LicenseSource
from backend.models.api_document import ApiDocument
from backend.collectors.api.api_result import (
    ApiCollectionRequest,
    ApiCollectionResult,
    ApiSourceStatusResponse,
    ApiDocumentSummaryResponse,
    ApiDocumentDetailResponse,
)
from backend.collectors.api.adapters.generic_adapter import GenericVendorApiAdapter
from backend.collectors.api.api_collector import ApiCollector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/collector/api", tags=["API Collector"])


@router.post("", response_model=ApiCollectionResult, status_code=status.HTTP_200_OK)
def trigger_api_collection(
    request: ApiCollectionRequest,
    db: Session = Depends(get_db)
):
    """
    Executes collection from an official vendor API for a registered source.
    Enforces security, rate limits, credential decoupling, and handles paid/missing creds gracefully.
    """
    collector = ApiCollector()
    result = collector.collect(
        db=db,
        source_id=request.source_id,
        force_refresh=request.force_refresh
    )
    if result.status == ApiCollectionStatus.NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error_message or "API source not found."
        )
    return result


@router.get("/{source_id}/status", response_model=ApiSourceStatusResponse)
def get_api_source_status(
    source_id: int,
    db: Session = Depends(get_db)
):
    """
    Retrieves operational status of an API source and whether required environment credentials exist.
    NEVER exposes secrets, tokens, or headers.
    """
    source = db.query(LicenseSource).filter(LicenseSource.id == source_id).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source ID {source_id} not found."
        )

    adapter = GenericVendorApiAdapter()
    has_creds = adapter.has_credentials(source)

    last_doc = db.query(ApiDocument).filter(
        ApiDocument.source_id == source.id
    ).order_by(ApiDocument.id.desc()).first()

    return ApiSourceStatusResponse(
        source_id=source.id,
        vendor_name=source.vendor_name,
        source_name=source.source_name,
        api_url=source.source_url,
        access_type=source.access_type or AccessType.PUBLIC,
        authentication_type=source.authentication_type or AuthenticationType.NONE,
        credentials_configured=has_creds,
        last_collection_status=last_doc.collection_status.value if last_doc else None,
        last_collection_time=last_doc.retrieved_at if last_doc else None
    )


@router.get("/documents", response_model=List[ApiDocumentSummaryResponse])
def list_api_documents(
    source_id: Optional[int] = Query(None, description="Filter by source ID"),
    vendor: Optional[str] = Query(None, description="Filter by vendor"),
    status_filter: Optional[ApiCollectionStatus] = Query(None, alias="status", description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """List collected API document evidence records."""
    query = db.query(ApiDocument)

    if source_id:
        query = query.filter(ApiDocument.source_id == source_id)
    if vendor:
        query = query.filter(func.lower(ApiDocument.vendor_name) == vendor.strip().lower())
    if status_filter:
        query = query.filter(ApiDocument.collection_status == status_filter)

    return query.order_by(ApiDocument.id.desc()).offset(skip).limit(limit).all()


@router.get("/documents/{document_id}", response_model=ApiDocumentDetailResponse)
def get_api_document_detail(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Retrieve raw payload and structured data for a specific API collection record."""
    doc = db.query(ApiDocument).filter(ApiDocument.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API document with ID {document_id} not found."
        )
    return doc
