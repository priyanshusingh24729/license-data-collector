"""
Source Registry Initialization & Seed Manager.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.source import LicenseSource
from backend.schemas.source import LicenseSourceCreate
from backend.services.source_registry_service import create_source, normalize_url
from backend.sources.seed_data import SEED_SOURCES

logger = logging.getLogger(__name__)


def seed_initial_sources(db: Session) -> int:
    """
    Seeds verified commercial license sources into the database.
    Skips any sources that already exist to avoid duplicates.
    Returns the count of new sources seeded.
    """
    seeded_count = 0

    for source_dict in SEED_SOURCES:
        normalized = normalize_url(source_dict["source_url"])
        existing = db.query(LicenseSource).filter(
            func.lower(LicenseSource.vendor_name) == source_dict["vendor_name"].strip().lower(),
            LicenseSource.normalized_url == normalized,
            LicenseSource.scope_type == source_dict["scope_type"],
            func.lower(LicenseSource.scope_identifier) == source_dict["scope_identifier"].strip().lower(),
        ).first()

        if not existing:
            source_in = LicenseSourceCreate(**source_dict)
            create_source(db, source_in)
            seeded_count += 1
            logger.info(f"Seeded source: {source_dict['vendor_name']} - {source_dict['source_name']}")

    return seeded_count
