"""
HTTP Fetcher Client with Safety Guards, Retry Policies, and Content-Type Verification.
"""

import time
import logging
from typing import Tuple, Optional, List, Dict, Any
from datetime import datetime, timezone
import httpx

from backend.config.settings import get_settings
from backend.models.enums import CollectionStatus
from backend.collectors.web.url_policy import UrlPolicy
from backend.collectors.web.collection_result import HttpResponseMetadata

logger = logging.getLogger(__name__)


class HttpFetchResult:
    """Raw result container for HTTP fetch operations."""
    def __init__(
        self,
        status: CollectionStatus,
        status_code: Optional[int] = None,
        content_bytes: bytes = b"",
        text_content: str = "",
        content_type: str = "",
        final_url: str = "",
        redirect_chain: Optional[List[str]] = None,
        error_message: Optional[str] = None,
    ):
        self.status = status
        self.status_code = status_code
        self.content_bytes = content_bytes
        self.text_content = text_content
        self.content_type = content_type
        self.final_url = final_url
        self.redirect_chain = redirect_chain or []
        self.error_message = error_message
        self.retrieved_at = datetime.now(timezone.utc)

    @property
    def metadata(self) -> HttpResponseMetadata:
        return HttpResponseMetadata(
            status_code=self.status_code or 0,
            content_type=self.content_type,
            content_length=len(self.content_bytes),
            final_url=self.final_url,
            redirect_chain=self.redirect_chain,
            retrieved_at=self.retrieved_at,
        )


class WebHttpClient:
    """
    Resilient, safe HTTP client for fetching public vendor web pages.
    """

    def __init__(
        self,
        url_policy: Optional[UrlPolicy] = None,
        timeout_seconds: Optional[int] = None,
        max_size_bytes: Optional[int] = None,
        max_retries: Optional[int] = None,
        user_agent: Optional[str] = None,
    ):
        settings = get_settings()
        self.url_policy = url_policy or UrlPolicy()
        self.timeout = timeout_seconds or settings.WEB_COLLECTOR_TIMEOUT_SECONDS
        self.max_size_bytes = max_size_bytes or settings.WEB_COLLECTOR_MAX_SIZE_BYTES
        self.max_retries = max_retries or settings.WEB_COLLECTOR_MAX_RETRIES
        self.user_agent = user_agent or settings.WEB_COLLECTOR_USER_AGENT

    def fetch(
        self,
        url: str,
        vendor: Optional[str] = None,
        expected_official_domain: Optional[str] = None
    ) -> HttpFetchResult:
        """
        Safely fetches the HTML content of a URL.
        """
        # 1. Initial URL validation
        is_valid, policy_status, policy_msg = self.url_policy.validate_url(
            url=url,
            vendor=vendor,
            expected_official_domain=expected_official_domain
        )
        if not is_valid:
            return HttpFetchResult(
                status=policy_status,
                final_url=url,
                error_message=policy_msg
            )

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        }

        redirect_chain: List[str] = [url]
        current_url = url
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(
                    timeout=httpx.Timeout(self.timeout),
                    follow_redirects=True,
                    max_redirects=5,
                    headers=headers
                ) as client:
                    response = client.get(current_url)

                    # Track redirect chain
                    if response.history:
                        redirect_chain = [str(r.url) for r in response.history] + [str(response.url)]
                    final_url = str(response.url)

                    # Validate final URL after redirects (prevent redirect-to-SSRF attacks)
                    is_final_valid, f_status, f_msg = self.url_policy.validate_url(
                        url=final_url,
                        vendor=vendor,
                        expected_official_domain=expected_official_domain
                    )
                    if not is_final_valid:
                        return HttpFetchResult(
                            status=f_status,
                            status_code=response.status_code,
                            final_url=final_url,
                            redirect_chain=redirect_chain,
                            error_message=f"Post-redirect check failed: {f_msg}"
                        )

                    # HTTP Status Code Evaluation
                    if response.status_code == 404:
                        return HttpFetchResult(
                            status=CollectionStatus.NOT_FOUND,
                            status_code=404,
                            final_url=final_url,
                            redirect_chain=redirect_chain,
                            error_message="Resource not found (404)."
                        )
                    elif response.status_code == 403:
                        return HttpFetchResult(
                            status=CollectionStatus.FORBIDDEN,
                            status_code=403,
                            final_url=final_url,
                            redirect_chain=redirect_chain,
                            error_message="Access forbidden (403)."
                        )
                    elif response.status_code == 401:
                        return HttpFetchResult(
                            status=CollectionStatus.UNAUTHORIZED,
                            status_code=401,
                            final_url=final_url,
                            redirect_chain=redirect_chain,
                            error_message="Authentication required (401)."
                        )
                    elif response.status_code == 429:
                        return HttpFetchResult(
                            status=CollectionStatus.BLOCKED,
                            status_code=429,
                            final_url=final_url,
                            redirect_chain=redirect_chain,
                            error_message="Rate limit exceeded (429)."
                        )
                    elif response.status_code >= 500:
                        if attempt < self.max_retries:
                            time.sleep(1.0 * (attempt + 1))
                            continue
                        return HttpFetchResult(
                            status=CollectionStatus.NETWORK_ERROR,
                            status_code=response.status_code,
                            final_url=final_url,
                            redirect_chain=redirect_chain,
                            error_message=f"Server returned 5xx error: {response.status_code}"
                        )

                    content_type = response.headers.get("content-type", "").lower()

                    # Check for PDF detection
                    if "application/pdf" in content_type or final_url.lower().endswith(".pdf"):
                        return HttpFetchResult(
                            status=CollectionStatus.DOCUMENT_REQUIRES_STEP_5,
                            status_code=response.status_code,
                            content_type=content_type,
                            final_url=final_url,
                            redirect_chain=redirect_chain,
                            error_message="Response is a PDF document. Deferred to Step 5 PDF Collector."
                        )

                    # Size check
                    raw_bytes = response.content
                    if len(raw_bytes) > self.max_size_bytes:
                        return HttpFetchResult(
                            status=CollectionStatus.TOO_LARGE,
                            status_code=response.status_code,
                            content_type=content_type,
                            final_url=final_url,
                            redirect_chain=redirect_chain,
                            error_message=f"Response size ({len(raw_bytes)} bytes) exceeds limit ({self.max_size_bytes} bytes)."
                        )

                    # Content-Type check (HTML / XHTML / XML)
                    if not any(t in content_type for t in ["text/html", "application/xhtml", "text/plain", "text/xml"]):
                        return HttpFetchResult(
                            status=CollectionStatus.INVALID_CONTENT,
                            status_code=response.status_code,
                            content_type=content_type,
                            final_url=final_url,
                            redirect_chain=redirect_chain,
                            error_message=f"Non-HTML content type: {content_type}"
                        )

                    return HttpFetchResult(
                        status=CollectionStatus.COLLECTED,
                        status_code=response.status_code,
                        content_bytes=raw_bytes,
                        text_content=response.text,
                        content_type=content_type,
                        final_url=final_url,
                        redirect_chain=redirect_chain,
                    )

            except (httpx.TimeoutException, httpx.ConnectTimeout) as exc:
                last_error = f"HTTP timeout: {exc}"
                if attempt < self.max_retries:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                return HttpFetchResult(
                    status=CollectionStatus.TIMEOUT,
                    final_url=current_url,
                    redirect_chain=redirect_chain,
                    error_message=last_error
                )
            except httpx.RequestError as exc:
                last_error = f"Network connection error: {exc}"
                if attempt < self.max_retries:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                return HttpFetchResult(
                    status=CollectionStatus.NETWORK_ERROR,
                    final_url=current_url,
                    redirect_chain=redirect_chain,
                    error_message=last_error
                )
            except Exception as exc:
                return HttpFetchResult(
                    status=CollectionStatus.NETWORK_ERROR,
                    final_url=current_url,
                    redirect_chain=redirect_chain,
                    error_message=f"Unexpected error: {str(exc)}"
                )

        return HttpFetchResult(
            status=CollectionStatus.NETWORK_ERROR,
            final_url=current_url,
            redirect_chain=redirect_chain,
            error_message=last_error or "Maximum retries exceeded."
        )
