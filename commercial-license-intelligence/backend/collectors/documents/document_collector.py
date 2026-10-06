"""
Official Document Collection Coordinator.
Orchestrates collection of registered official PDF documents, handles document versioning,
page-level evidence persistence, and duplicate deduplication.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from backend.models.enums import DocumentCollectionStatus, CollectionStatus
from backend.models.source import LicenseSource
from backend.models.collection import CollectedDocument, DocumentPage
from backend.collectors.documents.pdf_collector import PdfCollector
from backend.collectors.documents.document_result import DocumentCollectionResult

logger = logging.getLogger(__name__)


class DocumentCollector:
    """
    Main coordinator for collecting and persisting official vendor PDF documents.
    Strictly operates against registered, validated sources in the database.
    """

    def __init__(self, pdf_collector: Optional[PdfCollector] = None):
        self.pdf_collector = pdf_collector or PdfCollector()

    def collect(
        self,
        db: Session,
        source_id: int,
        force_refresh: bool = False
    ) -> DocumentCollectionResult:
        """
        Collects an official document for a registered LicenseSource ID.
        """
        # 1. Verify registered source exists and is active
        source = db.query(LicenseSource).filter(LicenseSource.id == source_id).first()
        if not source:
            return DocumentCollectionResult(
                source_id=source_id,
                vendor_name="Unknown",
                requested_url="",
                final_url="",
                status=DocumentCollectionStatus.NOT_FOUND,
                error_message=f"Registered source ID {source_id} not found."
            )

        if not source.is_active:
            return DocumentCollectionResult(
                source_id=source_id,
                vendor_name=source.vendor_name,
                requested_url=source.source_url,
                final_url=source.source_url,
                status=DocumentCollectionStatus.FAILED,
                error_message="Source is inactive. Deactivated sources cannot be collected."
            )

        # 2. Check previous collection version for deduplication
        existing_doc = db.query(CollectedDocument).filter(
            CollectedDocument.source_id == source.id
        ).order_by(CollectedDocument.id.desc()).first()

        # 3. Perform PDF Collection
        result = self.pdf_collector.collect_pdf(
            url=source.source_url,
            vendor=source.vendor_name,
            expected_official_domain=source.official_domain or source.base_domain,
            source_id=source.id
        )

        # Update source verification timestamp
        source.last_checked_at = datetime.now(timezone.utc)

        if result.status in [DocumentCollectionStatus.COLLECTED, DocumentCollectionStatus.PARSED, DocumentCollectionStatus.OCR_REQUIRED]:
            # 4. Check Versioning & Duplicate SHA-256
            is_unchanged = bool(
                existing_doc and
                result.metadata and
                existing_doc.content_hash == result.metadata.sha256_hash
            )
            result.is_cached_or_unchanged = is_unchanged

            # 5. Persist Document Record
            doc_record = CollectedDocument(
                source_id=source.id,
                vendor_name=source.vendor_name,
                requested_url=result.requested_url,
                final_url=result.final_url,
                status=CollectionStatus.COLLECTED,
                document_collection_status=result.status,
                document_classification=result.classification,
                http_status=200,
                content_type="application/pdf",
                content_length=result.metadata.file_size_bytes if result.metadata else None,
                content_hash=result.metadata.sha256_hash if result.metadata else None,
                title=result.metadata.title if (result.metadata and result.metadata.title) else source.source_name,
                document_author=result.metadata.author if result.metadata else None,
                document_subject=result.metadata.subject if result.metadata else None,
                page_count=result.metadata.page_count if result.metadata else len(result.pages),
                text_extractable=result.text_extractable,
                ocr_required=result.ocr_required,
                clean_text=result.clean_text,
                raw_storage_path=result.raw_file_path,
                published_at=result.metadata.creation_date if result.metadata else None,
                modified_at=result.metadata.modification_date if result.metadata else None,
                retrieved_at=datetime.now(timezone.utc),
            )
            db.add(doc_record)
            db.commit()
            db.refresh(doc_record)

            # 6. Persist Page-Level Evidence Records
            for page in result.pages:
                page_record = DocumentPage(
                    document_id=doc_record.id,
                    page_number=page.page_number,
                    text=page.text,
                    character_count=page.character_count,
                    created_at=datetime.now(timezone.utc)
                )
                db.add(page_record)

            db.commit()

        return result
