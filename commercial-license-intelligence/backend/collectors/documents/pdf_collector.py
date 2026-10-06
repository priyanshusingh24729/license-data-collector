"""
PDF Document Collector.
Specializes in downloading, magic-byte validation, and page-level extraction of PDF files.
"""

import logging
from typing import Optional
from backend.models.enums import DocumentCollectionStatus
from backend.collectors.documents.document_downloader import DocumentDownloader, DownloadedDocumentPayload
from backend.collectors.documents.pdf_parser import PdfParser
from backend.collectors.documents.document_classifier import DocumentClassifier
from backend.collectors.documents.document_result import DocumentCollectionResult

logger = logging.getLogger(__name__)


class PdfCollector:
    """
    Downloads and parses PDF documents into page-level structured text.
    """

    def __init__(
        self,
        downloader: Optional[DocumentDownloader] = None,
        parser: Optional[PdfParser] = None,
        classifier: Optional[DocumentClassifier] = None,
    ):
        self.downloader = downloader or DocumentDownloader()
        self.parser = parser or PdfParser()
        self.classifier = classifier or DocumentClassifier()

    def collect_pdf(
        self,
        url: str,
        vendor: str,
        expected_official_domain: Optional[str] = None,
        source_id: Optional[int] = None,
    ) -> DocumentCollectionResult:
        """
        Downloads, verifies, and parses a PDF URL into page-level text.
        """
        # 1. Download document safely
        payload: DownloadedDocumentPayload = self.downloader.download_document(
            url=url,
            vendor=vendor,
            expected_official_domain=expected_official_domain,
            source_id=source_id
        )

        if payload.status != DocumentCollectionStatus.COLLECTED:
            return DocumentCollectionResult(
                source_id=source_id,
                vendor_name=vendor,
                requested_url=url,
                final_url=payload.final_url or url,
                status=payload.status,
                error_message=payload.error_message
            )

        # 2. Parse PDF and extract page-level text
        try:
            (
                meta_obj,
                pages,
                clean_text,
                text_extractable,
                ocr_required
            ) = self.parser.parse_pdf(
                raw_bytes=payload.raw_bytes,
                sha256_hash=payload.sha256_hash,
                file_path=payload.saved_file_path
            )
        except Exception as parse_err:
            logger.warning(f"Failed to parse PDF from {url}: {parse_err}")
            return DocumentCollectionResult(
                source_id=source_id,
                vendor_name=vendor,
                requested_url=url,
                final_url=payload.final_url,
                status=DocumentCollectionStatus.FAILED,
                error_message=f"PDF parsing failure: {parse_err}"
            )

        # 3. Classify document nature
        classification = self.classifier.classify(
            url=payload.final_url,
            title=meta_obj.title,
            sample_text=clean_text[:1500] if clean_text else None
        )

        final_status = DocumentCollectionStatus.OCR_REQUIRED if ocr_required else DocumentCollectionStatus.PARSED

        return DocumentCollectionResult(
            source_id=source_id,
            vendor_name=vendor,
            requested_url=url,
            final_url=payload.final_url,
            status=final_status,
            classification=classification,
            text_extractable=text_extractable,
            ocr_required=ocr_required,
            metadata=meta_obj,
            pages=pages,
            clean_text=clean_text,
            raw_file_path=payload.saved_file_path,
            error_message=None
        )
