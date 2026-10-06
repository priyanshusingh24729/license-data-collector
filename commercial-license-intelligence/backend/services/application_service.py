"""
Application Catalog Management Service.
Handles application registration, canonical identity resolution, duplicate prevention,
CSV import preview/execution, and catalog export.
"""

import io
import csv
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.enums import ApplicationStatus, ApplicationResearchStatus
from backend.models.application import Application, compute_canonical_application_key
from backend.models.profile import LicenseProfile
from backend.schemas.application import (
    ApplicationCreateRequest,
    CsvImportPreviewResponse,
)

logger = logging.getLogger(__name__)


class ApplicationService:
    """
    Service for managing the Application Catalog and CSV import/export workflows.
    """

    def create_or_get_application(
        self,
        db: Session,
        req: ApplicationCreateRequest
    ) -> Application:
        """
        Registers an application or returns existing entity if canonical key matches.
        """
        clean_v = req.vendor.strip()
        clean_p = req.product.strip()
        clean_ed = req.edition.strip() if req.edition else None
        clean_ver = req.version.strip() if req.version else None
        clean_os = req.operating_system.strip() if req.operating_system else None

        app_key = compute_canonical_application_key(clean_v, clean_p, clean_ed, clean_ver, clean_os)

        # 1. Check duplicate by application_key
        existing = db.query(Application).filter(Application.application_key == app_key).first()
        if existing:
            return existing

        # 2. Insert new application
        disp_name = req.display_name or f"{clean_v} {clean_p}" + (f" {clean_ver}" if clean_ver else "")
        app_obj = Application(
            vendor_name=clean_v,
            product_name=clean_p,
            display_name=disp_name,
            edition=clean_ed,
            version=clean_ver,
            operating_system=clean_os,
            architecture=req.architecture,
            publisher=req.publisher or clean_v,
            product_identifier=req.product_identifier,
            application_key=app_key,
            status=ApplicationStatus.ACTIVE,
            research_status=ApplicationResearchStatus.NOT_RESEARCHED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(app_obj)
        db.commit()
        db.refresh(app_obj)
        return app_obj

    def preview_csv_import(
        self,
        db: Session,
        csv_text: str
    ) -> CsvImportPreviewResponse:
        """
        Validates uploaded CSV content without inserting records into the database.
        """
        reader = csv.DictReader(io.StringIO(csv_text))
        valid_records: List[Dict[str, Any]] = []
        invalid_records: List[Dict[str, Any]] = []
        seen_keys = set()
        duplicate_count = 0

        # Load existing keys from DB
        existing_keys = set(r[0] for r in db.query(Application.application_key).all())

        for idx, row in enumerate(reader, start=1):
            # Normalize column names (case-insensitive)
            row_norm = {k.strip().lower(): v.strip() for k, v in row.items() if k and v}

            vendor = row_norm.get("vendor") or row_norm.get("vendor_name") or row_norm.get("publisher")
            product = row_norm.get("product") or row_norm.get("product_name") or row_norm.get("application") or row_norm.get("app_name")

            if not vendor or not product:
                invalid_records.append({
                    "row_number": idx,
                    "data": row,
                    "reason": "Missing mandatory 'vendor' or 'product' field."
                })
                continue

            edition = row_norm.get("edition")
            version = row_norm.get("version")
            os_name = row_norm.get("operating_system") or row_norm.get("os")
            disp_name = row_norm.get("display_name")
            arch = row_norm.get("architecture")

            app_key = compute_canonical_application_key(vendor, product, edition, version, os_name)

            if app_key in seen_keys or app_key in existing_keys:
                duplicate_count += 1

            seen_keys.add(app_key)

            valid_records.append({
                "vendor": vendor,
                "product": product,
                "edition": edition,
                "version": version,
                "operating_system": os_name,
                "display_name": disp_name,
                "architecture": arch,
                "application_key": app_key,
                "is_duplicate": app_key in existing_keys
            })

        return CsvImportPreviewResponse(
            total_rows=len(valid_records) + len(invalid_records),
            valid_rows=len(valid_records),
            invalid_rows=len(invalid_records),
            duplicate_rows=duplicate_count,
            preview_records=valid_records[:50],
            invalid_records=invalid_records[:50]
        )

    def execute_csv_import(
        self,
        db: Session,
        records: List[Dict[str, Any]]
    ) -> List[Application]:
        """Imports validated CSV records into the application catalog."""
        created_apps: List[Application] = []
        for r in records:
            req = ApplicationCreateRequest(
                vendor=r["vendor"],
                product=r["product"],
                edition=r.get("edition"),
                version=r.get("version"),
                operating_system=r.get("operating_system"),
                architecture=r.get("architecture"),
                display_name=r.get("display_name")
            )
            app_obj = self.create_or_get_application(db, req)
            created_apps.append(app_obj)
        return created_apps

    def export_catalog_csv(self, db: Session) -> str:
        """
        Generates CSV export of cataloged applications with consolidated license profiles.
        """
        apps = db.query(Application).order_by(Application.id.asc()).all()

        output = io.StringIO()
        fieldnames = [
            "id", "application_key", "display_name", "vendor", "product", "edition", "version", "operating_system",
            "research_status", "license_classification", "license_required", "license_model",
            "license_metric", "license_duration", "overall_confidence", "profile_status"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for a in apps:
            profile = db.query(LicenseProfile).filter(LicenseProfile.id == a.current_profile_id).first() if a.current_profile_id else None

            writer.writerow({
                "id": a.id,
                "application_key": a.application_key,
                "display_name": a.display_name or f"{a.vendor_name} {a.product_name}",
                "vendor": a.vendor_name,
                "product": a.product_name,
                "edition": a.edition or "",
                "version": a.version or "",
                "operating_system": a.operating_system or "",
                "research_status": a.research_status.value,
                "license_classification": profile.license_classification if profile else "UNKNOWN",
                "license_required": profile.license_required if profile else "UNKNOWN",
                "license_model": profile.license_model if profile else "UNKNOWN",
                "license_metric": profile.license_metric if profile else "UNKNOWN",
                "license_duration": profile.license_duration if profile else "UNKNOWN",
                "overall_confidence": profile.overall_confidence.value if profile else "UNKNOWN",
                "profile_status": profile.profile_status.value if profile else "NOT_RESEARCHED"
            })

        return output.getvalue()
