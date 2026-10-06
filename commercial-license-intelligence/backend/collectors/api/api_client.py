"""
Secure, Rate-Limited Vendor API HTTP Client.
Enforces SSRF prevention, domain validation, size limits, transient retry policy,
and status-to-collection mapping.
"""

import time
import hashlib
import logging
from typing import Dict, Any, Optional, Tuple
import httpx

from backend.config.settings import get_settings
from backend.models.enums import ApiCollectionStatus
from backend.collectors.web.url_policy import UrlPolicy
from backend.collectors.api.adapters.generic_adapter import GenericVendorApiAdapter
from backend.collectors.api.api_result import ApiFetchResult

logger = logging.getLogger(__name__)

# Transient status codes that warrant retry
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class ApiClient:
    """
    Executes HTTP calls to official vendor API endpoints.
    """

    def __init__(
        self,
        url_policy: Optional[UrlPolicy] = None,
        max_bytes: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        max_retries: Optional[int] = None,
        rate_delay: Optional[float] = None,
    ):
        settings = get_settings()
        self.url_policy = url_policy or UrlPolicy()
        self.max_bytes = max_bytes or settings.MAX_API_RESPONSE_BYTES
        self.timeout = timeout_seconds or settings.API_COLLECTOR_TIMEOUT_SECONDS
        self.max_retries = max_retries or settings.API_COLLECTOR_MAX_RETRIES
        self.rate_delay = rate_delay if rate_delay is not None else settings.API_REQUEST_DELAY_SECONDS
        self.user_agent = settings.WEB_COLLECTOR_USER_AGENT
        self.adapter = GenericVendorApiAdapter()

    def fetch_api(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        payload: Optional[Dict[str, Any]] = None,
        vendor: Optional[str] = None,
        expected_official_domain: Optional[str] = None,
    ) -> ApiFetchResult:
        """
        Executes a rate-limited, validated HTTP request to an official vendor API.
        """
        # 1. URL & SSRF Validation
        is_valid, policy_status, policy_msg = self.url_policy.validate_url(
            url=url,
            vendor=vendor,
            expected_official_domain=expected_official_domain
        )
        if not is_valid:
            return ApiFetchResult(
                status=ApiCollectionStatus.DOMAIN_REJECTED,
                error_message=policy_msg
            )

        req_headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, application/xml, text/xml;q=0.9, */*;q=0.8"
        }
        if headers:
            req_headers.update(headers)

        # Rate Limiting Delay
        if self.rate_delay > 0:
            time.sleep(self.rate_delay)

        attempt = 0
        last_error: Optional[str] = None

        while attempt <= self.max_retries:
            attempt += 1
            try:
                with httpx.Client(
                    timeout=httpx.Timeout(self.timeout),
                    follow_redirects=True,
                    max_redirects=3,
                    headers=req_headers
                ) as client:
                    if method.upper() == "POST":
                        response = client.post(url, json=payload)
                    else:
                        response = client.get(url)

                    final_url = str(response.url)

                    # Post-redirect SSRF check
                    is_final_valid, f_status, f_msg = self.url_policy.validate_url(
                        url=final_url,
                        vendor=vendor,
                        expected_official_domain=expected_official_domain
                    )
                    if not is_final_valid:
                        return ApiFetchResult(
                            status=ApiCollectionStatus.DOMAIN_REJECTED,
                            status_code=response.status_code,
                            error_message=f"Post-redirect SSRF validation failed: {f_msg}"
                        )

                    status_code = response.status_code

                    # Map HTTP status codes
                    if status_code == 401:
                        return ApiFetchResult(
                            status=ApiCollectionStatus.AUTHENTICATION_REQUIRED,
                            status_code=401,
                            error_message="Vendor API authentication failed or missing (401)."
                        )
                    elif status_code == 403:
                        return ApiFetchResult(
                            status=ApiCollectionStatus.ACCESS_DENIED,
                            status_code=403,
                            error_message="Vendor API access forbidden or unauthorized (403)."
                        )
                    elif status_code == 404:
                        return ApiFetchResult(
                            status=ApiCollectionStatus.NOT_FOUND,
                            status_code=404,
                            error_message="Vendor API endpoint not found (404)."
                        )
                    elif status_code == 429:
                        if attempt <= self.max_retries:
                            time.sleep(1.0 * attempt)
                            continue
                        return ApiFetchResult(
                            status=ApiCollectionStatus.RATE_LIMITED,
                            status_code=429,
                            error_message="Vendor API rate limit exceeded (429)."
                        )
                    elif status_code in [500, 502, 503, 504]:
                        if attempt <= self.max_retries:
                            time.sleep(0.5 * attempt)
                            continue
                        return ApiFetchResult(
                            status=ApiCollectionStatus.VENDOR_SERVER_ERROR,
                            status_code=status_code,
                            error_message=f"Vendor API server error ({status_code})."
                        )
                    elif status_code not in [200, 201, 204]:
                        return ApiFetchResult(
                            status=ApiCollectionStatus.FAILED,
                            status_code=status_code,
                            error_message=f"Vendor API returned unexpected HTTP status: {status_code}"
                        )

                    raw_bytes = response.content
                    raw_text = response.text
                    content_type = response.headers.get("content-type", "application/json")

                    # Size check
                    if len(raw_bytes) > self.max_bytes:
                        return ApiFetchResult(
                            status=ApiCollectionStatus.TOO_LARGE,
                            status_code=status_code,
                            content_type=content_type,
                            response_size_bytes=len(raw_bytes),
                            error_message=f"API response size ({len(raw_bytes)} bytes) exceeds limit."
                        )

                    # Compute SHA-256 hash of payload
                    response_hash = hashlib.sha256(raw_bytes).hexdigest()

                    # Parse JSON/XML structure
                    parsed_json, parse_err = self.adapter.parse_payload(content_type, raw_text)

                    return ApiFetchResult(
                        status=ApiCollectionStatus.COLLECTED,
                        status_code=status_code,
                        content_type=content_type,
                        response_bytes=raw_bytes,
                        response_text=raw_text,
                        parsed_json=parsed_json,
                        response_hash=response_hash,
                        response_size_bytes=len(raw_bytes),
                        error_message=parse_err
                    )

            except (httpx.TimeoutException, httpx.ConnectTimeout) as exc:
                if attempt <= self.max_retries:
                    time.sleep(0.5 * attempt)
                    continue
                return ApiFetchResult(
                    status=ApiCollectionStatus.TIMEOUT,
                    error_message=f"API request timed out: {exc}"
                )
            except httpx.RequestError as exc:
                if attempt <= self.max_retries:
                    time.sleep(0.5 * attempt)
                    continue
                return ApiFetchResult(
                    status=ApiCollectionStatus.NETWORK_ERROR,
                    error_message=f"Network error during API fetch: {exc}"
                )
            except Exception as exc:
                return ApiFetchResult(
                    status=ApiCollectionStatus.FAILED,
                    error_message=f"Unexpected API client exception: {exc}"
                )

        return ApiFetchResult(
            status=ApiCollectionStatus.FAILED,
            error_message=last_error or "Max retries exceeded."
        )
