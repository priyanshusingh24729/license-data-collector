"""
PDF Extraction & Document Parser powered by PyMuPDF (fitz).
Extracts page-by-page text boundaries, document metadata, and evaluates OCR requirements.
"""

import re
import logging
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timezone
import fitz  # PyMuPDF

from backend.config.settings import get_settings
from backend.collectors.documents.document_result import PageContent, DocumentMetadata

logger = logging.getLogger(__name__)


def parse_pdf_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parses PDF date format (e.g. D:20240115120000Z or D:20240115) into datetime.
    """
    if not date_str or not isinstance(date_str, str):
        return None
    try:
        # Strip D: prefix
        clean = date_str.strip()
        if clean.startswith("D:"):
            clean = clean[2:]
        # Extract YYYYMMDDHHMMSS
        match = re.match(r"^(\d{4})(\d{2})(\d{2})(?:(\d{2})(\d{2})(\d{2}))?", clean)
        if match:
            parts = match.groups()
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2])
            hour = int(parts[3]) if parts[3] else 0
            minute = int(parts[4]) if parts[4] else 0
            second = int(parts[5]) if parts[5] else 0
            return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    except Exception as exc:
        logger.debug(f"Could not parse PDF date '{date_str}': {exc}")
    return None


class PdfParser:
    """
    Extracts structured page-level text and document metadata from PDF files.
    """

    def __init__(self, min_char_threshold: Optional[int] = None):
        settings = get_settings()
        self.min_char_threshold = min_char_threshold or settings.MIN_TEXT_EXTRACTION_CHAR_THRESHOLD

    def parse_pdf(
        self,
        raw_bytes: bytes,
        sha256_hash: str,
        file_path: Optional[str] = None
    ) -> Tuple[DocumentMetadata, List[PageContent], str, bool, bool]:
        """
        Parses a PDF document from raw bytes.
        
        Returns:
        (metadata, pages, clean_text, text_extractable, ocr_required)
        """
        try:
            doc = fitz.open(stream=raw_bytes, filetype="pdf")
        except Exception as exc:
            raise ValueError(f"PyMuPDF failed to parse PDF document: {exc}")

        page_count = len(doc)
        raw_meta = doc.metadata or {}

        # 1. Extract metadata
        title = raw_meta.get("title") or None
        if title:
            title = title.strip() or None

        author = raw_meta.get("author") or None
        if author:
            author = author.strip() or None

        subject = raw_meta.get("subject") or None
        if subject:
            subject = subject.strip() or None

        creation_dt = parse_pdf_date(raw_meta.get("creationDate"))
        mod_dt = parse_pdf_date(raw_meta.get("modDate"))

        # 2. Extract page-level text
        pages: List[PageContent] = []
        total_chars = 0
        text_lines: List[str] = []

        for page_idx in range(page_count):
            page = doc[page_idx]
            page_text = page.get_text("text").strip()
            char_count = len(page_text)
            word_count = len(page_text.split())
            total_chars += char_count

            page_obj = PageContent(
                page_number=page_idx + 1,
                text=page_text,
                character_count=char_count,
                word_count=word_count
            )
            pages.append(page_obj)

            text_lines.append(f"--- PAGE {page_idx + 1} ---")
            if page_text:
                text_lines.append(page_text)
            else:
                text_lines.append("[Empty or image-only page]")
            text_lines.append("")

        doc.close()

        clean_text = "\n".join(text_lines).strip()

        # 3. Evaluate OCR requirement
        text_extractable = total_chars >= self.min_char_threshold
        ocr_required = not text_extractable

        meta_obj = DocumentMetadata(
            title=title,
            author=author,
            subject=subject,
            page_count=page_count,
            file_size_bytes=len(raw_bytes),
            content_type="application/pdf",
            sha256_hash=sha256_hash,
            creation_date=creation_dt,
            modification_date=mod_dt
        )

        return meta_obj, pages, clean_text, text_extractable, ocr_required
