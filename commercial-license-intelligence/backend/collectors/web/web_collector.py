"""
Generic Official Web Content Collector.
Coordinates safe HTTP retrieval, HTML cleaning, structural section & table parsing,
content hashing, raw storage, and evidence persistence.
"""

import os
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session

from backend.config.settings import get_settings
from backend.models.enums import CollectionStatus
from backend.models.source import LicenseSource
from backend.models.collection import CollectedDocument
from backend.collectors.web.url_policy import UrlPolicy
from backend.collectors.web.http_client import WebHttpClient, HttpFetchResult
from backend.collectors.web.content_cleaner import ContentCleaner
from backend.collectors.web.content_parser import ContentParser
from backend.collectors.web.collection_result import WebCollectionResult, TableData
from backend.collectors.web.headless_renderer import HeadlessBrowserRenderer, is_spa_page
from backend.collectors.web.trafilatura_extractor import TrafilaturaExtractor
from backend.collectors.web.sitemap_collector import SitemapCollector
from backend.collectors.web.llms_txt_collector import LlmsTxtCollector, LlmsTxtResult
from backend.collectors.web.pdf_harvester import PdfHarvester

logger = logging.getLogger(__name__)


def compute_content_hash(text: str) -> str:
    """Computes a deterministic SHA-256 hash of normalized text."""
    normalized = " ".join(text.split()).strip().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


class WebCollector:
    """
    Retrieves and prepares public vendor webpage content as structured evidence.
    Supports clean Markdown extraction via Trafilatura, headless browser rendering
    for client-side JavaScript SPAs, sitemap & robots.txt discovery, llms.txt probing,
    and automatic PDF licensing whitepaper harvesting.
    """

    def __init__(
        self,
        url_policy: Optional[UrlPolicy] = None,
        http_client: Optional[WebHttpClient] = None,
        content_cleaner: Optional[ContentCleaner] = None,
        content_parser: Optional[ContentParser] = None,
        headless_renderer: Optional[HeadlessBrowserRenderer] = None,
        sitemap_collector: Optional[SitemapCollector] = None,
        llms_txt_collector: Optional[LlmsTxtCollector] = None,
        pdf_harvester: Optional[PdfHarvester] = None,
    ):
        self.url_policy = url_policy or UrlPolicy()
        self.http_client = http_client or WebHttpClient(url_policy=self.url_policy)
        self.cleaner = content_cleaner or ContentCleaner()
        self.parser = content_parser or ContentParser()
        self.headless_renderer = headless_renderer or HeadlessBrowserRenderer()
        self.sitemap_collector = sitemap_collector or SitemapCollector()
        self.llms_txt_collector = llms_txt_collector or LlmsTxtCollector()
        self.pdf_harvester = pdf_harvester or PdfHarvester()
        self.settings = get_settings()

    def _save_raw_html(self, content_hash: str, raw_bytes: bytes) -> Optional[str]:
        """Saves raw HTML payload to data/raw/ storage directory."""
        try:
            storage_dir = self.settings.RAW_DATA_STORAGE_DIR
            os.makedirs(storage_dir, exist_ok=True)
            filename = f"{content_hash}.html"
            filepath = os.path.join(storage_dir, filename)
            with open(filepath, "wb") as f:
                f.write(raw_bytes)
            return filepath
        except Exception as exc:
            logger.warning(f"Could not persist raw HTML file: {exc}")
            return None

    def collect(
        self,
        url: str,
        vendor: Optional[str] = None,
        expected_domain: Optional[str] = None
    ) -> WebCollectionResult:
        """
        Fetches, cleans, structures, and hashes a webpage.
        """
        vendor_name = vendor.strip() if vendor else "Generic"

        # 1. Safe HTTP Fetch
        fetch_result: HttpFetchResult = self.http_client.fetch(
            url=url,
            vendor=vendor,
            expected_official_domain=expected_domain
        )

        if fetch_result.status != CollectionStatus.COLLECTED:
            return WebCollectionResult(
                requested_url=url,
                final_url=fetch_result.final_url or url,
                vendor=vendor_name,
                status=fetch_result.status,
                http_metadata=fetch_result.metadata,
                error_message=fetch_result.error_message
            )

        # 2. Check for SPA / JavaScript-rendered page (Headless Browser Fallback)
        html_to_process = fetch_result.text_content
        raw_bytes_to_save = fetch_result.content_bytes
        is_rendered_spa = False

        if getattr(self.settings, "ENABLE_HEADLESS_BROWSER_FALLBACK", True) and is_spa_page(html_to_process):
            logger.info(f"[WebCollector] Detected dynamic SPA shell at {url}. Triggering headless browser fallback...")
            rendered_dom = self.headless_renderer.render(fetch_result.final_url or url)
            if rendered_dom and len(rendered_dom) > len(html_to_process):
                html_to_process = rendered_dom
                raw_bytes_to_save = rendered_dom.encode("utf-8")
                is_rendered_spa = True

        # 3. Clean & Parse via Trafilatura (Modern Ingestion Layer)
        markdown_content: Optional[str] = None
        use_trafilatura = getattr(self.settings, "USE_TRAFILATURA_EXTRACTION", True)

        if use_trafilatura:
            traf_res = TrafilaturaExtractor.extract(html_to_process, base_url=fetch_result.final_url or url)
            if traf_res.is_success and traf_res.char_count >= 50:
                markdown_content = traf_res.markdown_content

        # 4. Standard DOM cleaning & structural parsing
        soup = self.cleaner.clean_html(html_to_process)
        title, sections, tables, clean_text = self.parser.parse_document(soup)

        # If Trafilatura extracted markdown and clean text, prioritize clean text if longer/cleaner
        if markdown_content and len(markdown_content) > len(clean_text):
            clean_text = markdown_content

        # 5. Compute Content Hash
        content_hash = compute_content_hash(clean_text)

        # 6. Persist Raw HTML Snapshot
        raw_storage_path = self._save_raw_html(content_hash, raw_bytes_to_save)

        # 7. Harvest Licensing PDFs if enabled
        discovered_pdfs: List[str] = []
        if getattr(self.settings, "ENABLE_PDF_HARVESTING", True):
            try:
                pdf_matches = self.pdf_harvester.find_licensing_pdf_links(
                    html_or_text=html_to_process,
                    base_url=fetch_result.final_url or url
                )
                discovered_pdfs = [p[0] for p in pdf_matches]
                if discovered_pdfs:
                    logger.info(f"[WebCollector] Discovered {len(discovered_pdfs)} licensing PDF(s) at {url}: {discovered_pdfs}")
            except Exception as e:
                logger.debug(f"[WebCollector] PDF harvesting discovery notice: {e}")

        # 8. Calculate Metrics
        words = len(clean_text.split())
        chars = len(clean_text)

        return WebCollectionResult(
            requested_url=url,
            final_url=fetch_result.final_url or url,
            vendor=vendor_name,
            status=CollectionStatus.COLLECTED,
            http_metadata=fetch_result.metadata,
            title=title,
            clean_text=clean_text,
            markdown_content=markdown_content,
            is_rendered_spa=is_rendered_spa,
            structured_sections=sections,
            tables=tables,
            content_hash=content_hash,
            raw_storage_path=raw_storage_path,
            word_count=words,
            character_count=chars,
            harvested_pdfs=discovered_pdfs,
            error_message=None
        )

    def discover_vendor_sitemaps(self, base_url_or_domain: str) -> List[str]:
        """
        Discovers licensing-related URLs from the vendor's robots.txt and sitemap.
        """
        if not getattr(self.settings, "ENABLE_SITEMAP_DISCOVERY", True):
            return []
        try:
            return self.sitemap_collector.discover_licensing_sitemap_urls(base_url_or_domain)
        except Exception as e:
            logger.warning(f"[WebCollector] Sitemap discovery error for {base_url_or_domain}: {e}")
            return []

    def check_vendor_llms_txt(self, base_url_or_domain: str) -> Optional[LlmsTxtResult]:
        """
        Checks vendor domain for /llms.txt or /llms-full.txt and extracts clean markdown licensing links.
        """
        if not getattr(self.settings, "ENABLE_LLMS_TXT_DISCOVERY", True):
            return None
        try:
            return self.llms_txt_collector.discover(base_url_or_domain)
        except Exception as e:
            logger.warning(f"[WebCollector] llms.txt discovery error for {base_url_or_domain}: {e}")
            return None

    def harvest_pdf(
        self,
        pdf_url: str,
        vendor: str,
        expected_official_domain: Optional[str] = None,
        source_id: Optional[int] = None,
    ):
        """
        Directly downloads and extracts text from an authoritative licensing PDF.
        """
        return self.pdf_harvester.harvest_pdf(
            pdf_url=pdf_url,
            vendor=vendor,
            expected_official_domain=expected_official_domain,
            source_id=source_id,
        )

    def collect_source(
        self,
        db: Session,
        source_id: int,
        force_refresh: bool = False
    ) -> WebCollectionResult:
        """
        Collects content for a registered LicenseSource and persists the evidence in database.
        """
        source = db.query(LicenseSource).filter(LicenseSource.id == source_id).first()
        if not source:
            return WebCollectionResult(
                requested_url="",
                final_url="",
                vendor="",
                status=CollectionStatus.NOT_FOUND,
                error_message=f"License source with ID {source_id} does not exist."
            )

        # Check existing collection record if not forcing refresh
        existing_doc = db.query(CollectedDocument).filter(
            CollectedDocument.source_id == source.id,
            CollectedDocument.status == CollectionStatus.COLLECTED
        ).order_by(CollectedDocument.id.desc()).first()

        result = self.collect(
            url=source.source_url,
            vendor=source.vendor_name,
            expected_domain=source.official_domain or source.base_domain
        )

        # Update source last_checked_at
        source.last_checked_at = datetime.now(timezone.utc)

        # Check if content has changed
        is_unchanged = bool(existing_doc and existing_doc.content_hash == result.content_hash)
        result.is_cached_or_unchanged = is_unchanged

        # Persist CollectedDocument evidence record
        doc_record = CollectedDocument(
            source_id=source.id,
            vendor_name=source.vendor_name,
            requested_url=result.requested_url,
            final_url=result.final_url,
            status=result.status,
            http_status=result.http_metadata.status_code if result.http_metadata else None,
            content_type=result.http_metadata.content_type if result.http_metadata else None,
            content_length=result.http_metadata.content_length if result.http_metadata else None,
            content_hash=result.content_hash,
            title=result.title,
            clean_text=result.clean_text,
            structured_sections=[s.model_dump() for s in result.structured_sections],
            tables_data=[t.model_dump() for t in result.tables],
            redirect_chain=result.http_metadata.redirect_chain if result.http_metadata else [],
            raw_storage_path=result.raw_storage_path,
            retrieved_at=datetime.now(timezone.utc)
        )
        db.add(doc_record)
        db.commit()
        db.refresh(doc_record)

        return result
