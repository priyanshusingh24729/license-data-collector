"""
OCR Architecture Interface & Future Expansion Adapter.
Defines contracts for optical character recognition for scanned/image-only PDFs.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from backend.collectors.documents.document_result import PageContent


class OcrEngineInterface(ABC):
    """Abstract interface for optional OCR engines."""

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the underlying OCR engine (e.g. Tesseract/EasyOCR) is installed and operational."""
        pass

    @abstractmethod
    def extract_text_from_pdf_bytes(self, pdf_bytes: bytes) -> List[PageContent]:
        """Extracts text from scanned/image-only PDF pages using OCR."""
        pass


class NullOcrEngine(OcrEngineInterface):
    """Default lightweight null engine when no external OCR binary is installed."""

    def is_available(self) -> bool:
        return False

    def extract_text_from_pdf_bytes(self, pdf_bytes: bytes) -> List[PageContent]:
        return []
