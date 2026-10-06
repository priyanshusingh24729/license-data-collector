"""
Source Registry Service.
Provides core business logic for registering, normalizing, querying, and resolving
licensing sources according to the deterministic hierarchy.
"""

import re
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from backend.models.source import LicenseSource
from backend.models.enums import (
    SourceType,
    AuthorityLevel,
    ScopeType,
    CollectionMethod,
    SourceStatus,
    AccessType,
)
from backend.schemas.source import LicenseSourceCreate, LicenseSourceUpdate

logger = logging.getLogger(__name__)

# Tracking query parameters to strip during normalization
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "msclkid", "_hsenc", "_hsmi", "mc_cid", "mc_eid"
}

# Authority rank mapping (lower number = higher precedence)
AUTHORITY_RANK = {
    AuthorityLevel.OFFICIAL_VENDOR: 1,
    AuthorityLevel.OFFICIAL_DISTRIBUTOR: 2,
    AuthorityLevel.TRUSTED_SECONDARY: 3,
    AuthorityLevel.UNKNOWN: 4,
}

# Scope specificity rank mapping (lower number = more specific)
SCOPE_SPECIFICITY_RANK = {
    ScopeType.VERSION: 1,
    ScopeType.EDITION: 2,
    ScopeType.PRODUCT: 3,
    ScopeType.VENDOR: 4,
}


def normalize_url(url: str) -> str:
    """
    Deterministically normalizes a URL:
    - Lowercases scheme and netloc
    - Strips default ports
    - Removes known marketing/tracking query parameters
    - Alphabetically sorts remaining functional query parameters
    - Normalizes trailing slashes (preserves single root slash)
    """
    if not url:
        return ""

    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()

    # Remove default port
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    # Normalize path
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    if not path:
        path = "/"

    # Filter and sort query params
    filtered_query_pairs = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
    ]
    filtered_query_pairs.sort(key=lambda x: x[0])
    clean_query = urlencode(filtered_query_pairs)

    # Reconstruct clean URL (fragment removed for canonical source URL)
    clean_url = urlunparse((scheme, netloc, path, parsed.params, clean_query, ""))
    return clean_url


def extract_base_domain(url: str) -> str:
    """Extracts base domain from a URL."""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower().split(":")[0]
        # Strip www.
        if netloc.startswith("www."):
            return netloc[4:]
        return netloc
    except Exception:
        return ""


def create_source(db: Session, source_in: LicenseSourceCreate) -> LicenseSource:
    """
    Registers a new license source with deduplication verification.
    """
    normalized_url = normalize_url(source_in.source_url)
    base_domain = source_in.base_domain or extract_base_domain(source_in.source_url)
    official_domain = source_in.official_domain or base_domain

    # Check for existing duplicate source
    existing = db.query(LicenseSource).filter(
        func.lower(LicenseSource.vendor_name) == source_in.vendor_name.strip().lower(),
        LicenseSource.normalized_url == normalized_url,
        LicenseSource.scope_type == source_in.scope_type,
        func.lower(LicenseSource.scope_identifier) == source_in.scope_identifier.strip().lower(),
        LicenseSource.is_active == True,
    ).first()

    if existing:
        raise ValueError(
            f"Active source already exists for vendor '{source_in.vendor_name}', "
            f"scope '{source_in.scope_type}:{source_in.scope_identifier}' and URL '{normalized_url}'."
        )

    db_source = LicenseSource(
        vendor_name=source_in.vendor_name.strip(),
        product_name=source_in.product_name.strip() if source_in.product_name else None,
        scope_type=source_in.scope_type,
        scope_identifier=source_in.scope_identifier.strip(),
        source_name=source_in.source_name.strip(),
        source_type=source_in.source_type,
        authority_level=source_in.authority_level,
        official_domain=official_domain,
        base_domain=base_domain,
        source_url=source_in.source_url.strip(),
        normalized_url=normalized_url,
        description=source_in.description,
        is_active=source_in.is_active,
        is_public=source_in.is_public,
        status=source_in.status,
        access_type=source_in.access_type,
        collection_method=source_in.collection_method,
        priority=source_in.priority,
    )

    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source


def get_source_by_id(db: Session, source_id: int) -> Optional[LicenseSource]:
    """Retrieves a license source by its primary key ID."""
    return db.query(LicenseSource).filter(LicenseSource.id == source_id).first()


def list_sources(
    db: Session,
    vendor: Optional[str] = None,
    product: Optional[str] = None,
    source_type: Optional[SourceType] = None,
    authority_level: Optional[AuthorityLevel] = None,
    status: Optional[SourceStatus] = None,
    scope_type: Optional[ScopeType] = None,
    active_only: bool = False,
    skip: int = 0,
    limit: int = 100
) -> List[LicenseSource]:
    """Retrieves a filtered list of license sources."""
    query = db.query(LicenseSource)

    if vendor:
        query = query.filter(func.lower(LicenseSource.vendor_name) == vendor.strip().lower())
    if product:
        query = query.filter(func.lower(LicenseSource.product_name) == product.strip().lower())
    if source_type:
        query = query.filter(LicenseSource.source_type == source_type)
    if authority_level:
        query = query.filter(LicenseSource.authority_level == authority_level)
    if status:
        query = query.filter(LicenseSource.status == status)
    if scope_type:
        query = query.filter(LicenseSource.scope_type == scope_type)
    if active_only:
        query = query.filter(LicenseSource.is_active == True, LicenseSource.status == SourceStatus.ACTIVE)

    return query.order_by(LicenseSource.priority.asc(), LicenseSource.id.asc()).offset(skip).limit(limit).all()


def update_source(
    db: Session,
    source_id: int,
    source_update: LicenseSourceUpdate
) -> Optional[LicenseSource]:
    """Updates an existing license source."""
    db_source = get_source_by_id(db, source_id)
    if not db_source:
        return None

    update_data = source_update.model_dump(exclude_unset=True)

    if "source_url" in update_data and update_data["source_url"]:
        normalized = normalize_url(update_data["source_url"])
        update_data["normalized_url"] = normalized
        if "base_domain" not in update_data or not update_data["base_domain"]:
            update_data["base_domain"] = extract_base_domain(update_data["source_url"])

    for key, value in update_data.items():
        setattr(db_source, key, value)

    # Sync is_active with status
    if "status" in update_data:
        db_source.is_active = (db_source.status == SourceStatus.ACTIVE)

    db.commit()
    db.refresh(db_source)
    return db_source


def deactivate_source(db: Session, source_id: int) -> Optional[LicenseSource]:
    """
    Soft-deletes a license source by marking it INACTIVE to preserve evidence integrity.
    """
    db_source = get_source_by_id(db, source_id)
    if not db_source:
        return None

    db_source.is_active = False
    db_source.status = SourceStatus.INACTIVE
    db.commit()
    db.refresh(db_source)
    return db_source


def get_vendor_sources(
    db: Session,
    vendor_name: str,
    active_only: bool = True
) -> List[LicenseSource]:
    """Retrieves all sources registered at the VENDOR scope for a given vendor."""
    query = db.query(LicenseSource).filter(
        func.lower(LicenseSource.vendor_name) == vendor_name.strip().lower(),
        LicenseSource.scope_type == ScopeType.VENDOR
    )
    if active_only:
        query = query.filter(LicenseSource.is_active == True, LicenseSource.status == SourceStatus.ACTIVE)

    return query.order_by(LicenseSource.priority.asc(), LicenseSource.id.asc()).all()


def get_product_sources(
    db: Session,
    vendor_name: str,
    product_name: str,
    active_only: bool = True
) -> List[LicenseSource]:
    """Retrieves all sources registered for a specific product and its vendor."""
    return get_applicable_sources(
        db=db,
        vendor_name=vendor_name,
        product_name=product_name,
        active_only=active_only
    )


def get_applicable_sources(
    db: Session,
    vendor_name: str,
    product_name: Optional[str] = None,
    edition: Optional[str] = None,
    version: Optional[str] = None,
    active_only: bool = True
) -> List[LicenseSource]:
    """
    Resolves all applicable licensing sources for a vendor/product target.
    
    Deterministic Selection & Ordering Rule:
    1. Scope Specificity:
       VERSION (most specific) -> EDITION -> PRODUCT -> VENDOR (broadest)
    2. Authority Level:
       OFFICIAL_VENDOR -> OFFICIAL_DISTRIBUTOR -> TRUSTED_SECONDARY -> UNKNOWN
    3. Numeric Priority (Lower integer = Higher priority)
    4. ID (Deterministic tie-breaker)
    """
    clean_vendor = vendor_name.strip().lower()
    clean_product = product_name.strip().lower() if product_name else None
    clean_edition = edition.strip().lower() if edition else None
    clean_version = version.strip().lower() if version else None

    # Base query for the vendor
    query = db.query(LicenseSource).filter(
        func.lower(LicenseSource.vendor_name) == clean_vendor
    )

    if active_only:
        query = query.filter(
            LicenseSource.is_active == True,
            LicenseSource.status == SourceStatus.ACTIVE
        )

    all_candidate_sources = query.all()

    matched_sources: List[LicenseSource] = []

    for src in all_candidate_sources:
        src_scope = src.scope_type
        src_scope_id = src.scope_identifier.strip().lower()
        src_prod = src.product_name.strip().lower() if src.product_name else ""

        # Scope: VENDOR
        if src_scope == ScopeType.VENDOR:
            matched_sources.append(src)
            continue

        # If product wasn't supplied, skip more specific scopes
        if not clean_product:
            continue

        # Scope: PRODUCT
        if src_scope == ScopeType.PRODUCT:
            if src_prod == clean_product or src_scope_id == clean_product or clean_product in src_scope_id:
                matched_sources.append(src)
            continue

        # Scope: EDITION
        if src_scope == ScopeType.EDITION:
            if clean_edition and (
                src_scope_id == clean_edition
                or (clean_product and f"{clean_product} {clean_edition}" in src_scope_id)
                or (src_prod == clean_product and clean_edition in src_scope_id)
            ):
                matched_sources.append(src)
            continue

        # Scope: VERSION
        if src_scope == ScopeType.VERSION:
            if clean_version and (
                src_scope_id == clean_version
                or clean_version in src_scope_id
                or (src_prod == clean_product and clean_version in src_scope_id)
                or (clean_edition and f"{clean_edition} {clean_version}" in src_scope_id)
            ):
                matched_sources.append(src)
            continue

    # Sort deterministically
    def sort_key(s: LicenseSource):
        specificity = SCOPE_SPECIFICITY_RANK.get(s.scope_type, 99)
        authority = AUTHORITY_RANK.get(s.authority_level, 99)
        priority = s.priority if s.priority is not None else 99
        return (specificity, authority, priority, s.id)

    matched_sources.sort(key=sort_key)
    return matched_sources
