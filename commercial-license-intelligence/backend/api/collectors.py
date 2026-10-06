"""FastAPI endpoints for the Web Content Collector."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.connection import get_db
from backend.models.collection import CollectedDocument
from backend.models.enums import CollectionStatus
from backend.collectors.web.collection_result import (
    WebCollectionRequest,
    WebCollectionResult,
    CollectedDocumentSummaryResponse,
    CollectedDocumentDetailResponse,
)
from backend.collectors.web.web_collector import WebCollector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/collectors/web", tags=["Web Collector"])


@router.post("/collect", response_model=WebCollectionResult, status_code=status.HTTP_200_OK)
def trigger_web_collection(
    request: WebCollectionRequest,
    db: Session = Depends(get_db)
):
    """
    Executes web content collection for a specific URL or registered license source.
    Performs SSRF validation, safe HTTP fetch, HTML cleaning, and structured section parsing.
    """
    collector = WebCollector()

    if request.source_id:
        result = collector.collect_source(
            db=db,
            source_id=request.source_id,
            force_refresh=request.force_refresh
        )
        return result
    elif request.url:
        result = collector.collect(
            url=request.url,
            vendor=request.vendor,
            expected_domain=request.expected_domain
        )
        return result
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'url' or 'source_id' must be provided."
        )


@router.get("/documents", response_model=List[CollectedDocumentSummaryResponse])
def list_collected_documents(
    vendor: Optional[str] = Query(None, description="Filter by vendor"),
    status_filter: Optional[CollectionStatus] = Query(None, alias="status", description="Filter by collection status"),
    source_id: Optional[int] = Query(None, description="Filter by source ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Retrieve summarized metadata of collected webpage documents."""
    query = db.query(CollectedDocument)

    if vendor:
        query = query.filter(func.lower(CollectedDocument.vendor_name) == vendor.strip().lower())
    if status_filter:
        query = query.filter(CollectedDocument.status == status_filter)
    if source_id:
        query = query.filter(CollectedDocument.source_id == source_id)

    return query.order_by(CollectedDocument.id.desc()).offset(skip).limit(limit).all()


@router.get("/documents/{document_id}", response_model=CollectedDocumentDetailResponse)
def get_collected_document(document_id: int, db: Session = Depends(get_db)):
    """Retrieve full structured content and evidence for a specific collected document."""
    doc = db.query(CollectedDocument).filter(CollectedDocument.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collected document with ID {document_id} not found."
        )
    return doc


@router.get("/documents/by-hash/{content_hash}", response_model=CollectedDocumentDetailResponse)
def get_collected_document_by_hash(content_hash: str, db: Session = Depends(get_db)):
    """Retrieve collected document by its unique SHA-256 content hash."""
    doc = db.query(CollectedDocument).filter(CollectedDocument.content_hash == content_hash).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with content hash '{content_hash}' not found."
        )
    return doc
