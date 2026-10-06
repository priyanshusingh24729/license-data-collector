"""
Vendor API Collection Coordinator.
Orchestrates API calls for registered sources, enforces credential security,
handles optional/paid fallbacks cleanly, and stores raw JSON/XML evidence.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from backend.models.enums import (
    SourceType,
    CollectionMethod,
    AccessType,
    AuthenticationType,
    ApiCollectionStatus,
)
from backend.models.source import LicenseSource
from backend.models.api_document import ApiDocument
from backend.collectors.api.adapters.generic_adapter import GenericVendorApiAdapter
from backend.collectors.api.api_client import ApiClient
from backend.collectors.api.api_result import ApiCollectionResult, ApiFetchResult

logger = logging.getLogger(__name__)


class ApiCollector:
    """
    Main coordinator for optional vendor API collection.
    Strictly operates against registered API sources in the database.
    """

    def __init__(
        self,
        api_client: Optional[ApiClient] = None,
        adapter: Optional[GenericVendorApiAdapter] = None,
    ):
        self.client = api_client or ApiClient()
        self.adapter = adapter or GenericVendorApiAdapter()

    def collect(
        self,
        db: Session,
        source_id: int,
        force_refresh: bool = False
    ) -> ApiCollectionResult:
        """
        Executes API collection for a registered LicenseSource.
        """
        # 1. Load source
        source = db.query(LicenseSource).filter(LicenseSource.id == source_id).first()
        if not source:
            return ApiCollectionResult(
                source_id=source_id,
                vendor_name="Unknown",
                request_url="",
                status=ApiCollectionStatus.NOT_FOUND,
                error_message=f"Registered source ID {source_id} not found."
            )

        if not source.is_active:
            return ApiCollectionResult(
                source_id=source_id,
                vendor_name=source.vendor_name,
                request_url=source.source_url,
                status=ApiCollectionStatus.FAILED,
                error_message="API source is inactive."
            )

        # 2. Check if source is configured as an API source
        is_api_source = (
            source.source_type == SourceType.OFFICIAL_API or
            source.collection_method == CollectionMethod.API
        )
        if not is_api_source:
            return ApiCollectionResult(
                source_id=source_id,
                vendor_name=source.vendor_name,
                request_url=source.source_url,
                status=ApiCollectionStatus.FAILED,
                error_message="Source is not configured with collection_method=API or source_type=OFFICIAL_API."
            )

        # 3. Check Credentials & Access Type Requirements
        has_creds = self.adapter.has_credentials(source)

        if source.access_type == AccessType.PAID and not has_creds:
            logger.info(f"Paid API source {source_id} ({source.vendor_name}) skipped: subscription credentials unavailable.")
            return ApiCollectionResult(
                source_id=source.id,
                vendor_name=source.vendor_name,
                request_url=source.source_url,
                status=ApiCollectionStatus.PAID_SOURCE_UNAVAILABLE,
                error_message="Vendor API requires a paid subscription/credentials which are not configured. Falling back to public web/PDF sources."
            )

        if source.access_type == AccessType.AUTHENTICATED and not has_creds:
            logger.info(f"Authenticated API source {source_id} ({source.vendor_name}) skipped: authentication credentials missing.")
            return ApiCollectionResult(
                source_id=source.id,
                vendor_name=source.vendor_name,
                request_url=source.source_url,
                status=ApiCollectionStatus.AUTHENTICATION_REQUIRED,
                error_message="Authentication credentials required for this vendor API are not configured in environment."
            )

        # 4. Build Request
        url, method, headers, payload = self.adapter.build_request(source)

        # 5. Execute HTTP Request
        fetch_res: ApiFetchResult = self.client.fetch_api(
            url=url,
            method=method,
            headers=headers,
            payload=payload,
            vendor=source.vendor_name,
            expected_official_domain=source.official_domain or source.base_domain
        )

        # Update source verification timestamp
        source.last_checked_at = datetime.now(timezone.utc)

        # 6. Check Historical Responses & Deduplication
        existing_doc = db.query(ApiDocument).filter(
            ApiDocument.source_id == source.id
        ).order_by(ApiDocument.id.desc()).first()

        is_unchanged = bool(
            existing_doc and
            fetch_res.response_hash and
            existing_doc.response_hash == fetch_res.response_hash
        )

        # 7. Persist API Document Evidence (Never storing credentials)
        if fetch_res.status == ApiCollectionStatus.COLLECTED:
            doc_record = ApiDocument(
                source_id=source.id,
                vendor_name=source.vendor_name,
                request_url=url,
                http_method=method,
                response_status=fetch_res.status_code,
                content_type=fetch_res.content_type,
                response_size=fetch_res.response_size_bytes,
                response_hash=fetch_res.response_hash,
                response_body=fetch_res.response_text,
                parsed_json=fetch_res.parsed_json,
                collection_status=fetch_res.status,
                error_message=fetch_res.error_message,
                retrieved_at=datetime.now(timezone.utc)
            )
            db.add(doc_record)
            db.commit()
            db.refresh(doc_record)

        return ApiCollectionResult(
            source_id=source.id,
            vendor_name=source.vendor_name,
            request_url=url,
            http_method=method,
            status=fetch_res.status,
            http_status=fetch_res.status_code,
            content_type=fetch_res.content_type,
            response_size=fetch_res.response_size_bytes,
            response_hash=fetch_res.response_hash,
            raw_response_text=fetch_res.response_text,
            parsed_json=fetch_res.parsed_json,
            is_cached_or_unchanged=is_unchanged,
            error_message=fetch_res.error_message
        )
