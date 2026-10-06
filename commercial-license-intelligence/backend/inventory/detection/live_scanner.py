"""
Live Windows Application Discovery and Inventory Synchronization Engine.
Executes fresh, multi-source scans (Registry, AppX/MSIX, Winget, Start Menu) and synchronizes directly with the database.
"""

import sys
import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

# Import endpoint agent scanning modules
endpoint_agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "endpoint-agent", "windows"))
if endpoint_agent_dir not in sys.path:
    sys.path.insert(0, endpoint_agent_dir)

from registry_scanner import WindowsRegistryScanner
from package_scanner import WindowsPackageScanner
from winget_scanner import WindowsWingetScanner
from start_menu_scanner import WindowsStartMenuScanner
from inventory_builder import InventoryBuilder
from config import AgentConfig

from backend.models.enums import DetectedAppStatus, DetectionMethod, DeviceStatus
from backend.models.inventory import Device, DetectedApplication, DeviceApplication
from backend.inventory.detection.detection_normalizer import DetectionNormalizer
from backend.inventory.detection.identity_resolver import IdentityResolver

logger = logging.getLogger("live-scanner")


class LiveWindowsScanner:
    """
    Coordinates fresh in-process Windows scanning across all discovery sources
    and synchronizes new and existing applications with PostgreSQL/SQLite.
    """

    @classmethod
    def execute_fresh_scan(cls, db: Session, dry_run: bool = False) -> Dict[str, Any]:
        """
        Executes live multi-source Windows application discovery:
        1. Registry (HKLM 64, HKLM 32, HKCU)
        2. AppX / MSIX Modern Packages
        3. Winget Packages
        4. Start Menu Shortcuts
        5. Deduplicates and syncs with database
        """
        start_time = datetime.now(timezone.utc)
        logger.info("[SCAN STARTED] Initiating fresh live Windows application discovery...")

        config = AgentConfig(dry_run=dry_run)
        builder = InventoryBuilder(config)
        device_meta = builder.gather_device_metadata()

        # 1. Scan Registry Hives
        reg_scanner = WindowsRegistryScanner()
        reg_entries, reg_counts = reg_scanner.scan_all_hives()
        logger.info(f"[REGISTRY SCAN COMPLETE: {len(reg_entries)} applications]")

        # 2. Scan Modern AppX / MSIX Packages
        pkg_scanner = WindowsPackageScanner()
        pkg_entries = pkg_scanner.scan_packages()
        logger.info(f"[APPX SCAN COMPLETE: {len(pkg_entries)} packages]")

        # 3. Scan Winget Packages
        winget_scanner = WindowsWingetScanner()
        winget_entries = winget_scanner.scan_packages()
        logger.info(f"[WINGET SCAN COMPLETE: {len(winget_entries)} applications]")

        # 4. Scan Start Menu Shortcuts (For Identity Enrichment Only)
        sm_scanner = WindowsStartMenuScanner()
        sm_enrichment = sm_scanner.get_enrichment_map()
        logger.info(f"[START MENU ENRICHMENT LOADED: {len(sm_enrichment)} shortcuts]")

        all_raw = reg_entries + pkg_entries + winget_entries
        logger.info(f"[DISCOVERY COMPLETE: {len(all_raw)} total raw detections from primary sources]")

        # 5. Deduplicate
        deduped = builder.deduplicate_applications(all_raw)
        logger.info(f"[NORMALIZATION COMPLETE] [DUPLICATES MERGED: {len(all_raw) - len(deduped)}]")

        # 6. Synchronize with Database (Applying ApplicationQualificationFilter)
        from backend.inventory.detection.qualification_filter import ApplicationQualificationFilter, WindowsSystemToolFilter
        normalizer = DetectionNormalizer
        resolver = IdentityResolver()
        now = datetime.now(timezone.utc)

        new_count = 0
        updated_count = 0
        disqualified_count = 0
        persisted_apps = []

        if not dry_run:
            # Ensure Device Record Exists
            dev_key = device_meta.get("device_key", "WIN-LOCAL")
            device = db.query(Device).filter(Device.device_key == dev_key).first()
            if not device:
                device = Device(
                    device_key=dev_key,
                    hostname=device_meta.get("hostname"),
                    operating_system=device_meta.get("operating_system", "Windows"),
                    os_version=device_meta.get("os_version"),
                    architecture=device_meta.get("architecture", "x64"),
                    agent_version=device_meta.get("agent_version", "1.0.0"),
                    status=DeviceStatus.ACTIVE,
                    first_seen_at=now,
                    last_seen_at=now,
                    created_at=now,
                    updated_at=now
                )
                db.add(device)
                db.commit()
                db.refresh(device)
            else:
                device.last_seen_at = now
                device.status = DeviceStatus.ACTIVE
                db.commit()

            # Process each deduplicated application
            for app_data in deduped:
                raw_name = (app_data.get("raw_name") or "").strip()
                if not raw_name:
                    continue

                # Enrich with Start Menu metadata if available
                s_meta = sm_enrichment.get(raw_name.lower())
                if s_meta and not app_data.get("raw_install_location"):
                    app_data["raw_install_location"] = s_meta.get("folder")
                    app_data["shortcut_path"] = s_meta.get("shortcut_path")

                # Run Qualification Filter
                is_qual, qual_reason, qual_cat = ApplicationQualificationFilter.qualify_candidate(app_data)
                if not is_qual:
                    logger.debug(f"Candidate '{raw_name}' disqualified: {qual_reason}")
                    disqualified_count += 1
                    continue

                raw_pub = app_data.get("raw_publisher")
                raw_ver = app_data.get("raw_version")
                raw_loc = app_data.get("raw_install_location")
                det_method = app_data.get("detection_method", "WINDOWS_REGISTRY")
                arch = app_data.get("architecture", "x64")
                pkg_fam = app_data.get("package_family_name") or app_data.get("raw_package_name")

                norm_name = normalizer.normalize_name(raw_name)
                norm_pub = normalizer.normalize_publisher(raw_pub)
                raw_v, maj_v, min_v, pat_v = normalizer.normalize_version(raw_ver)

                # Pre-Resolution: Canonical Product & Vendor Identification
                from backend.inventory.recognition.alias_system import ApplicationAliasSystem
                import sqlalchemy
                alias_res = ApplicationAliasSystem.resolve_application(
                    raw_name=raw_name,
                    raw_publisher=raw_pub,
                    raw_version=raw_ver,
                )
                canonical_prod = alias_res.canonical_product if alias_res.canonical_product != "UNRESOLVED" else None
                canonical_vend = alias_res.canonical_vendor if alias_res.canonical_vendor != "UNKNOWN" else None

                # Find existing record in DB (by canonical product, package family, normalized name or raw name)
                match_clauses = [
                    (DetectedApplication.normalized_name == norm_name),
                    (DetectedApplication.raw_name == raw_name),
                ]
                if canonical_prod:
                    match_clauses.append(DetectedApplication.canonical_product == canonical_prod)
                    match_clauses.append(DetectedApplication.raw_name.ilike(f"%{canonical_prod}%"))
                if pkg_fam:
                    pkg_base = pkg_fam.split("_")[0] if "_" in pkg_fam else pkg_fam
                    match_clauses.append(DetectedApplication.raw_package_name == pkg_fam)
                    match_clauses.append(DetectedApplication.raw_name.ilike(f"%{pkg_base}%"))

                existing = db.query(DetectedApplication).filter(
                    (DetectedApplication.device_id == device.id) &
                    sqlalchemy.or_(*match_clauses)
                ).first()

                # Map detection method
                if "64" in det_method:
                    dm_enum = DetectionMethod.WINDOWS_REGISTRY_64
                elif "32" in det_method:
                    dm_enum = DetectionMethod.WINDOWS_REGISTRY_32
                elif "USER" in det_method:
                    dm_enum = DetectionMethod.WINDOWS_USER_REGISTRY
                elif "APPX" in det_method:
                    dm_enum = DetectionMethod.WINDOWS_APPX
                elif "WINGET" in det_method:
                    dm_enum = DetectionMethod.PACKAGE_MANAGER
                else:
                    dm_enum = DetectionMethod.ENDPOINT_AGENT

                if not existing:
                    # Insert ONE canonical application record
                    new_app = DetectedApplication(
                        device_id=device.id,
                        raw_name=raw_name,
                        raw_publisher=raw_pub or canonical_vend,
                        raw_version=raw_ver,
                        raw_package_name=pkg_fam,
                        raw_display_name=app_data.get("raw_display_name") or raw_name,
                        canonical_product=canonical_prod,
                        normalized_name=norm_name,
                        normalized_publisher=norm_pub or canonical_vend,
                        detected_version=raw_v,
                        major_version=maj_v,
                        minor_version=min_v,
                        patch_version=pat_v,
                        operating_system=device.operating_system,
                        install_location=raw_loc,
                        install_source=det_method,
                        architecture=arch,
                        detection_method=dm_enum,
                        detected_at=now,
                        first_seen_at=now,
                        last_seen_at=now,
                        status=DetectedAppStatus.ACTIVE,
                        created_at=now,
                        updated_at=now
                    )
                    db.add(new_app)
                    db.commit()
                    db.refresh(new_app)

                    # Link to DeviceApplication
                    dev_app = DeviceApplication(
                        device_id=device.id,
                        detected_application_id=new_app.id,
                        first_seen_at=now,
                        last_seen_at=now,
                        status=DetectedAppStatus.ACTIVE
                    )
                    db.add(dev_app)
                    db.commit()

                    # Identity Resolution
                    resolver.resolve_detection(db, new_app)

                    new_count += 1
                    persisted_apps.append({
                        "id": new_app.id,
                        "raw_name": raw_name,
                        "normalized_name": norm_name,
                        "canonical_product": canonical_prod,
                        "status": "NEW_APPLICATION"
                    })
                else:
                    # Update existing detection and merge canonical metadata
                    existing.last_seen_at = now
                    existing.status = DetectedAppStatus.ACTIVE
                    if canonical_prod and not existing.canonical_product:
                        existing.canonical_product = canonical_prod
                    if canonical_vend and (not existing.normalized_publisher or existing.normalized_publisher == "Unknown"):
                        existing.normalized_publisher = canonical_vend
                    if raw_v and not existing.detected_version:
                        existing.detected_version = raw_v
                        existing.major_version = maj_v
                        existing.minor_version = min_v
                        existing.patch_version = pat_v
                    if ("." in existing.raw_name or "_" in existing.raw_name) and not ("." in raw_name or "_" in raw_name):
                        existing.raw_display_name = raw_name
                        existing.raw_name = raw_name
                    db.commit()
                    updated_count += 1

            logger.info(f"[NEW APPLICATIONS FOUND: {new_count}]")
            logger.info(f"[EXISTING APPLICATIONS UPDATED: {updated_count}]")
            logger.info("[DATABASE INSERT COMPLETE]")
            logger.info("[SCAN COMPLETE]")

        duration_sec = (datetime.now(timezone.utc) - start_time).total_seconds()

        return {
            "status": "SUCCESS",
            "timestamp": now.isoformat(),
            "duration_seconds": duration_sec,
            "total_raw_discovered": len(all_raw),
            "deduplicated_count": len(deduped),
            "new_applications_added": new_count,
            "existing_applications_updated": updated_count,
            "sources": {
                "registry": len(reg_entries),
                "appx": len(pkg_entries),
                "winget": len(winget_entries),
                "start_menu_enrichment": len(sm_enrichment),
            },
            "disqualified_count": disqualified_count,
            "new_applications": persisted_apps
        }
