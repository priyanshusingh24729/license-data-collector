"""FastAPI endpoints for the Official PDF & Document Collector."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.connection import get_db
from backend.models.collection import CollectedDocument, DocumentPage
from backend.models.enums import DocumentClassification, DocumentCollectionStatus
from backend.collectors.documents.document_result import (
    DocumentCollectionRequest,
    DocumentCollectionResult,
    DocumentSummaryResponse,
    DocumentDetailResponse,
    DocumentPageResponse,
)
from backend.collectors.documents.document_collector import DocumentCollector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Document Collector"])


@router.post("/collector/document", response_model=DocumentCollectionResult, status_code=status.HTTP_200_OK)
def trigger_document_collection(
    request: DocumentCollectionRequest,
    db: Session = Depends(get_db)
):
    """
    Executes automated collection for a registered official PDF/document source.
    Downloads PDF, validates magic-bytes, extracts page-by-page text, and preserves evidence.
    """
    collector = DocumentCollector()
    result = collector.collect(
        db=db,
        source_id=request.source_id,
        force_refresh=request.force_refresh
    )
    if result.status == DocumentCollectionStatus.NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error_message or "Document source not found."
        )
    return result


@router.get("/documents", response_model=List[DocumentSummaryResponse])
def list_collected_documents(
    source_id: Optional[int] = Query(None, description="Filter by source ID"),
    document_classification: Optional[DocumentClassification] = Query(None, description="Filter by document classification"),
    status_filter: Optional[DocumentCollectionStatus] = Query(None, alias="status", description="Filter by status"),
    vendor: Optional[str] = Query(None, description="Filter by vendor"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Retrieve list of collected document records."""
    query = db.query(CollectedDocument).filter(
        CollectedDocument.content_type.like("%pdf%")
    )

    if source_id:
        query = query.filter(CollectedDocument.source_id == source_id)
    if document_classification:
        query = query.filter(CollectedDocument.document_classification == document_classification)
    if status_filter:
        query = query.filter(CollectedDocument.document_collection_status == status_filter)
    if vendor:
        query = query.filter(func.lower(CollectedDocument.vendor_name) == vendor.strip().lower())

    docs = query.order_by(CollectedDocument.id.desc()).offset(skip).limit(limit).all()

    # Map status safely
    return [
        DocumentSummaryResponse(
            id=d.id,
            source_id=d.source_id,
            vendor_name=d.vendor_name,
            requested_url=d.requested_url,
            final_url=d.final_url,
            status=d.document_collection_status.value if d.document_collection_status else d.status.value,
            document_classification=d.document_classification or DocumentClassification.UNKNOWN,
            title=d.title,
            page_count=d.page_count,
            file_size=d.content_length,
            content_hash=d.content_hash,
            text_extractable=d.text_extractable,
            ocr_required=d.ocr_required,
            retrieved_at=d.retrieved_at,
            created_at=d.created_at
        ) for d in docs
    ]


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
def get_document_detail(document_id: int, db: Session = Depends(get_db)):
    """Retrieve complete metadata and extracted text for an official document."""
    doc = db.query(CollectedDocument).filter(CollectedDocument.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found."
        )

    pages = db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).order_by(DocumentPage.page_number.asc()).all()

    return DocumentDetailResponse(
        id=doc.id,
        source_id=doc.source_id,
        vendor_name=doc.vendor_name,
        requested_url=doc.requested_url,
        final_url=doc.final_url,
        status=doc.document_collection_status.value if doc.document_collection_status else doc.status.value,
        document_classification=doc.document_classification or DocumentClassification.UNKNOWN,
        title=doc.title,
        document_author=doc.document_author,
        document_subject=doc.document_subject,
        page_count=doc.page_count,
        file_size=doc.content_length,
        content_hash=doc.content_hash,
        text_extractable=doc.text_extractable,
        ocr_required=doc.ocr_required,
        clean_text=doc.clean_text,
        raw_storage_path=doc.raw_storage_path,
        retrieved_at=doc.retrieved_at,
        created_at=doc.created_at,
        pages=[DocumentPageResponse(
            page_number=p.page_number,
            text=p.text,
            character_count=p.character_count
        ) for p in pages]
    )


@router.get("/documents/{document_id}/pages", response_model=List[DocumentPageResponse])
def get_document_pages(document_id: int, db: Session = Depends(get_db)):
    """Retrieve all page-level text evidence records for a specific document."""
    doc = db.query(CollectedDocument).filter(CollectedDocument.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found."
        )

    pages = db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).order_by(DocumentPage.page_number.asc()).all()
    return [
        DocumentPageResponse(
            page_number=p.page_number,
            text=p.text,
            character_count=p.character_count
        ) for p in pages
    ]


@router.get("/documents/{document_id}/pages/{page_number}", response_model=DocumentPageResponse)
def get_document_page_by_number(document_id: int, page_number: int, db: Session = Depends(get_db)):
    """Retrieve text evidence for an exact page number within a document."""
    page = db.query(DocumentPage).filter(
        DocumentPage.document_id == document_id,
        DocumentPage.page_number == page_number
    ).first()
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_number} not found for document {document_id}."
        )
    return DocumentPageResponse(
        page_number=page.page_number,
        text=page.text,
        character_count=page.character_count
    )
