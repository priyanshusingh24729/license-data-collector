"""
PDF Licensing Whitepaper Harvester.
Detects, filters, and downloads authoritative licensing PDFs linked on vendor webpages,
reusing the existing PdfCollector for page-level structured text extraction.
"""

import re
import logging
from urllib.parse import urljoin, urlparse
from typing import List, Optional, Dict, Any, Tuple
from bs4 import BeautifulSoup

from backend.config.settings import get_settings
from backend.collectors.documents.pdf_collector import PdfCollector
from backend.collectors.documents.document_result import DocumentCollectionResult

logger = logging.getLogger(__name__)

# Keywords indicating a PDF is specifically a licensing or legal document
RELEVANT_PDF_KEYWORDS = [
    "licensing",
    "license",
    "eula",
    "terms",
    "brief",
    "product terms",
    "licensing guide",
    "licensing brief",
    "commercial terms",
    "pricing guide",
    "subscription terms",
    "end user license",
    "volume licensing",
]

# Keywords indicating an irrelevant PDF (to prevent wasted downloads)
IRRELEVANT_PDF_KEYWORDS = [
    "brochure",
    "datasheet",
    "data-sheet",
    "flyer",
    "case-study",
    "case study",
    "infographic",
    "whitepaper/overview",
    "annual-report",
    "press-release",
    "privacy-policy",
]


class PdfHarvester:
    """
    Finds and harvests relevant licensing PDFs from HTML and Markdown content.
    """

    def __init__(self, pdf_collector: Optional[PdfCollector] = None):
        settings = get_settings()
        self.pdf_collector = pdf_collector or PdfCollector()
        self.max_harvest = getattr(settings, "MAX_PDF_HARVEST_PER_PAGE", 3)

    def find_licensing_pdf_links(self, html_or_text: str, base_url: str) -> List[Tuple[str, str]]:
        """
        Scans HTML/text for links pointing to .pdf files.
        Returns a list of (pdf_url, anchor_context) that match licensing keywords.
        """
        candidates: List[Tuple[str, str]] = []
        if not html_or_text:
            return []

        # 1. Check HTML <a> tags via BeautifulSoup
        try:
            soup = BeautifulSoup(html_or_text, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if ".pdf" in href.lower():
                    full_url = urljoin(base_url, href)
                    anchor_text = a_tag.get_text(strip=True)
                    combined = f"{full_url} {anchor_text}".lower()

                    # Avoid irrelevant
                    if any(irr in combined for irr in IRRELEVANT_PDF_KEYWORDS):
                        continue
                    # Match licensing
                    if any(rel in combined for rel in RELEVANT_PDF_KEYWORDS):
                        candidates.append((full_url, anchor_text or "Licensing PDF Document"))
        except Exception as e:
            logger.debug(f"[PdfHarvester] BS4 link parsing notice: {e}")

        # 2. Check Markdown links: [Title](URL.pdf)
        md_matches = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+\.pdf[^\)]*)\)', html_or_text, re.IGNORECASE)
        for title, link in md_matches:
            full_url = urljoin(base_url, link.strip())
            combined = f"{full_url} {title}".lower()
            if not any(irr in combined for irr in IRRELEVANT_PDF_KEYWORDS):
                if any(rel in combined for rel in RELEVANT_PDF_KEYWORDS):
                    if not any(c[0] == full_url for c in candidates):
                        candidates.append((full_url, title))

        return candidates[:self.max_harvest]

    def harvest_pdf(
        self,
        pdf_url: str,
        vendor: str,
        expected_official_domain: Optional[str] = None,
        source_id: Optional[int] = None,
    ) -> Optional[DocumentCollectionResult]:
        """
        Downloads, validates magic bytes, and extracts structured page-level text from the PDF.
        """
        try:
            logger.info(f"[PdfHarvester] Harvesting licensing PDF: {pdf_url} (vendor: {vendor})")
            result = self.pdf_collector.collect_pdf(
                url=pdf_url,
                vendor=vendor,
                expected_official_domain=expected_official_domain,
                source_id=source_id,
            )
            return result
        except Exception as e:
            logger.warning(f"[PdfHarvester] Error harvesting PDF from {pdf_url}: {e}")
            return None
