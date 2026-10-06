"""
Collectors Package.
Contains multi-modal content collection engines:
- Web Collector (Step 4)
- PDF / Document Collector (Step 5)
- Optional API Collector (Step 6)
"""

from backend.collectors.web import WebCollector, WebCollectionResult
from backend.collectors.documents import DocumentCollector, PdfCollector, DocumentCollectionResult
from backend.collectors.api import ApiCollector, ApiClient, ApiCollectionResult

__all__ = [
    "WebCollector",
    "WebCollectionResult",
    "DocumentCollector",
    "PdfCollector",
    "DocumentCollectionResult",
    "ApiCollector",
    "ApiClient",
    "ApiCollectionResult",
]
