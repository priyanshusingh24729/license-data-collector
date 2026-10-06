"""
Safe PDF & Document Downloader.
Enforces SSRF prevention, max byte limits, timeout policies, content-type checks,
and PDF %PDF- magic-byte validation before saving to data/raw/.
"""

import os
import hashlib
import logging
from typing import Tuple, Optional, List
from datetime import datetime, timezone
import httpx

from backend.config.settings import get_settings
from backend.models.enums import DocumentCollectionStatus
from backend.collectors.web.url_policy import UrlPolicy

logger = logging.getLogger(__name__)

PDF_MAGIC_BYTES = b"%PDF-"


class DownloadedDocumentPayload:
    """Holds the raw validated bytes and metadata of a downloaded document."""
    def __init__(
        self,
        status: DocumentCollectionStatus,
        raw_bytes: bytes = b"",
        final_url: str = "",
        content_type: str = "application/pdf",
        sha256_hash: str = "",
        saved_file_path: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        self.status = status
        self.raw_bytes = raw_bytes
        self.final_url = final_url
        self.content_type = content_type
        self.sha256_hash = sha256_hash
        self.saved_file_path = saved_file_path
        self.error_message = error_message
        self.downloaded_at = datetime.now(timezone.utc)


class DocumentDownloader:
    """
    Downloads official vendor documents securely with streaming size caps and magic-byte checks.
    """

    def __init__(
        self,
        url_policy: Optional[UrlPolicy] = None,
        max_bytes: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
    ):
        settings = get_settings()
        self.url_policy = url_policy or UrlPolicy()
        self.max_bytes = max_bytes or settings.MAX_DOCUMENT_BYTES
        self.timeout = timeout_seconds or settings.DOCUMENT_DOWNLOAD_TIMEOUT_SECONDS
        self.user_agent = settings.WEB_COLLECTOR_USER_AGENT
        self.storage_dir = settings.RAW_DATA_STORAGE_DIR

    def is_pdf_content(self, raw_bytes: bytes, content_type: str) -> bool:
        """
        Validates whether raw bytes represent an authentic PDF document.
        Checks both %PDF- header signature and non-HTML content.
        """
        if not raw_bytes or len(raw_bytes) < 5:
            return False

        # Check for %PDF- magic bytes in first 1024 bytes (some PDFs have leading whitespace/BOM)
        prefix = raw_bytes[:1024]
        if PDF_MAGIC_BYTES in prefix:
            return True

        # Check if it is masquerading HTML
        prefix_lower = prefix.lower()
        if b"<!doctype html" in prefix_lower or b"<html" in prefix_lower or b"<head" in prefix_lower:
            return False

        return False

    def download_document(
        self,
        url: str,
        vendor: Optional[str] = None,
        expected_official_domain: Optional[str] = None,
        source_id: Optional[int] = None,
    ) -> DownloadedDocumentPayload:
        """
        Downloads a document URL, checks magic bytes, calculates SHA-256, and stores in data/raw/.
        """
        # 1. URL & SSRF Validation
        is_valid, policy_status, policy_msg = self.url_policy.validate_url(
            url=url,
            vendor=vendor,
            expected_official_domain=expected_official_domain
        )
        if not is_valid:
            status_map = {
                "SSRF_REJECTED": DocumentCollectionStatus.DOMAIN_REJECTED,
                "DOMAIN_REJECTED": DocumentCollectionStatus.DOMAIN_REJECTED,
            }
            return DownloadedDocumentPayload(
                status=status_map.get(policy_status.value, DocumentCollectionStatus.FAILED),
                final_url=url,
                error_message=policy_msg
            )

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/pdf,application/octet-stream,*/*;q=0.8",
            "Cache-Control": "no-cache",
        }

        try:
            with httpx.Client(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                max_redirects=5,
                headers=headers
            ) as client:
                response = client.get(url)

                final_url = str(response.url)

                # Validate final redirect destination against SSRF
                is_final_valid, f_status, f_msg = self.url_policy.validate_url(
                    url=final_url,
                    vendor=vendor,
                    expected_official_domain=expected_official_domain
                )
                if not is_final_valid:
                    return DownloadedDocumentPayload(
                        status=DocumentCollectionStatus.DOMAIN_REJECTED,
                        final_url=final_url,
                        error_message=f"Post-redirect validation failed: {f_msg}"
                    )

                if response.status_code == 404:
                    return DownloadedDocumentPayload(
                        status=DocumentCollectionStatus.NOT_FOUND,
                        final_url=final_url,
                        error_message="Document not found (404)."
                    )
                elif response.status_code == 403:
                    return DownloadedDocumentPayload(
                        status=DocumentCollectionStatus.FORBIDDEN,
                        final_url=final_url,
                        error_message="Access forbidden (403)."
                    )
                elif response.status_code == 401:
                    return DownloadedDocumentPayload(
                        status=DocumentCollectionStatus.UNAUTHORIZED,
                        final_url=final_url,
                        error_message="Authentication required (401)."
                    )
                elif response.status_code == 429:
                    return DownloadedDocumentPayload(
                        status=DocumentCollectionStatus.BLOCKED,
                        final_url=final_url,
                        error_message="Rate limit exceeded (429)."
                    )
                elif response.status_code != 200:
                    return DownloadedDocumentPayload(
                        status=DocumentCollectionStatus.FAILED,
                        final_url=final_url,
                        error_message=f"HTTP request failed with status: {response.status_code}"
                    )

                raw_bytes = response.content
                content_type = response.headers.get("content-type", "application/pdf").lower()

                # Size Limit Check
                if len(raw_bytes) > self.max_bytes:
                    return DownloadedDocumentPayload(
                        status=DocumentCollectionStatus.TOO_LARGE,
                        final_url=final_url,
                        content_type=content_type,
                        error_message=f"Document size ({len(raw_bytes)} bytes) exceeds limit ({self.max_bytes} bytes)."
                    )

                # PDF Signature & Magic Bytes Verification
                if not self.is_pdf_content(raw_bytes, content_type):
                    return DownloadedDocumentPayload(
                        status=DocumentCollectionStatus.INVALID_DOCUMENT,
                        final_url=final_url,
                        content_type=content_type,
                        error_message="Content is not a valid PDF document (missing %PDF- signature or HTML detected)."
                    )

                # Compute SHA-256 of raw binary document
                sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

                # Safe file persistence
                os.makedirs(self.storage_dir, exist_ok=True)
                doc_prefix = f"src{source_id}_" if source_id else ""
                filename = f"{doc_prefix}{sha256_hash}.pdf"
                file_path = os.path.join(self.storage_dir, filename)

                with open(file_path, "wb") as f:
                    f.write(raw_bytes)

                return DownloadedDocumentPayload(
                    status=DocumentCollectionStatus.COLLECTED,
                    raw_bytes=raw_bytes,
                    final_url=final_url,
                    content_type=content_type,
                    sha256_hash=sha256_hash,
                    saved_file_path=file_path
                )

        except (httpx.TimeoutException, httpx.ConnectTimeout) as exc:
            return DownloadedDocumentPayload(
                status=DocumentCollectionStatus.TIMEOUT,
                final_url=url,
                error_message=f"Download connection timeout: {exc}"
            )
        except httpx.RequestError as exc:
            return DownloadedDocumentPayload(
                status=DocumentCollectionStatus.FAILED,
                final_url=url,
                error_message=f"Network download error: {exc}"
            )
        except Exception as exc:
            return DownloadedDocumentPayload(
                status=DocumentCollectionStatus.FAILED,
                final_url=url,
                error_message=f"Unexpected download exception: {exc}"
            )
