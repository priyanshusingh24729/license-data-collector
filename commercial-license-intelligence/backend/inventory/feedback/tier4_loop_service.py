"""Core service for the Tier 4 Human-in-the-Loop Resolution to Permanent Catalog Rule Feedback System."""

import os
import re
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text

from backend.models.tier4_feedback import PendingCatalogRule, CatalogAuditLog
from backend.models.inventory_upload import UploadLicenseResult


class Tier4Resolution(BaseModel):
    signature_id: str = Field(..., description="Normalized app signature or raw_name")
    matched_pattern: str = Field(..., description="Exact match string or pattern alias")
    canonical_name: str = Field(..., description="Canonical product name")
    vendor: str = Field(..., description="Canonical vendor name")
    license_type: str = Field(..., description="COMMERCIAL | FREEWARE | OPEN_SOURCE | FREE_AND_PAID")
    license_required: str = Field(..., description="YES | NO | CONTEXT_DEPENDENT")
    metric: str = Field("NOT_APPLICABLE", description="USER | DEVICE | EMPLOYEE | NOT_APPLICABLE")
    tier: int = Field(2, description="Target tier: 1, 2, or 3")
    evidence_url: Optional[str] = ""
    evidence_quote: Optional[str] = ""
    resolved_by: str = Field("auditor", description="Name/ID of the human auditor")
    resolved_at: Optional[datetime] = None
    confidence: str = Field("auditor_confirmed", description="auditor_confirmed | auditor_guess")
    scope: str = Field("exact_match", description="exact_match | vendor_wide | pattern_family")
    auto_promote: bool = Field(False, description="Automatically promote if high confidence exact match")


class Tier4LoopService:
    FIXTURES_PATH = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "confirmed_resolutions.json"
    CATALOG_FILE_PATH = Path(__file__).resolve().parent.parent / "recognition" / "catalog.py"

    @classmethod
    def get_tier4_queue(cls, db: Session, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieves frequency-weighted review queue of unresolved Tier 4 signatures across the fleet.
        """
        try:
            # Group by raw_application and raw_vendor for unresolved items
            query = (
                db.query(
                    UploadLicenseResult.raw_application,
                    UploadLicenseResult.raw_vendor,
                    func.count(UploadLicenseResult.id).label("occurrences"),
                    func.max(UploadLicenseResult.created_at).label("latest_seen"),
                    func.max(UploadLicenseResult.raw_version).label("sample_version"),
                    func.max(UploadLicenseResult.hostname).label("sample_hostname"),
                )
                .filter(
                    (UploadLicenseResult.classification == None) |
                    (UploadLicenseResult.classification == "UNKNOWN") |
                    (UploadLicenseResult.evidence_status == "MISSING")
                )
                .group_by(UploadLicenseResult.raw_application, UploadLicenseResult.raw_vendor)
                .order_by(desc("occurrences"))
                .limit(limit)
            )

            results = []
            for row in query.all():
                results.append({
                    "signature_id": row.raw_application,
                    "raw_application": row.raw_application,
                    "raw_vendor": row.raw_vendor or "UNKNOWN",
                    "occurrences": row.occurrences,
                    "latest_seen": row.latest_seen.isoformat() if row.latest_seen else None,
                    "sample_version": row.sample_version or "N/A",
                    "sample_hostname": row.sample_hostname or "N/A",
                })
            return results
        except Exception as e:
            return []

    @classmethod
    def get_signature_frequency(cls, signature_id: str, db: Session) -> int:
        """Counts how many times a given application signature appears across the inventory."""
        try:
            cnt = db.query(func.count(UploadLicenseResult.id)).filter(
                func.lower(UploadLicenseResult.raw_application) == signature_id.strip().lower()
            ).scalar()
            return cnt or 1
        except Exception:
            return 1

    @classmethod
    def generate_catalog_py_entry(cls, rule: Union[PendingCatalogRule, Tier4Resolution]) -> str:
        """
        Generates programmatic Python code for a CatalogRecognitionEntry ready for catalog.py.
        """
        is_oss = rule.license_type.upper() == "OPEN_SOURCE"
        comm_allowed = rule.license_type.upper() in ("FREEWARE", "OPEN_SOURCE", "FREE_AND_PAID")

        avail_map = {
            "COMMERCIAL": "PAID_ONLY",
            "FREEWARE": "FREE",
            "OPEN_SOURCE": "FREE",
            "FREE_AND_PAID": "FREE_AND_PAID",
        }
        avail_model = avail_map.get(rule.license_type.upper(), "FREE_AND_PAID")

        status_enum = "LICENSE_REQUIRED_YES" if rule.license_required.upper() == "YES" else (
            "LICENSE_REQUIRED_NO" if rule.license_required.upper() == "NO" else "LICENSE_REQUIRED_YES"
        )

        clean_pattern = rule.matched_pattern.strip()
        alias_list = [clean_pattern.lower()]
        if rule.canonical_name.lower() != clean_pattern.lower():
            alias_list.append(rule.canonical_name.lower())

        alias_str = ",\n".join([f'            "{a}"' for a in alias_list])

        code_snippet = f"""    CatalogRecognitionEntry(
        canonical_name="{rule.canonical_name}",
        canonical_vendor="{rule.vendor}",
        classification="{rule.license_type.upper()}",
        availability_model="{avail_model}",
        license_requirement="{rule.license_required.upper()}",
        license_required=FinalLicenseStatus.{status_enum},
        licensing_model="{rule.license_type.title()} Application",
        licensing_metric="{rule.metric.upper()}",
        commercial_use_allowed={comm_allowed},
        confidence=ExtractionConfidence.VERY_HIGH,
        method=ResolutionMethod.DETERMINISTIC_RULE,
        terms_summary="Human verified via Tier 4 feedback loop by {rule.resolved_by}.",
        primary_url="{rule.evidence_url or ''}",
        evidence_quote="{rule.evidence_quote or 'Confirmed by auditor resolution.'}",
        is_open_source={is_oss},
        source_type="AUDITOR_RESOLUTION",
        aliases=[
{alias_str}
        ]
    ),"""
        return code_snippet

    @classmethod
    def submit_resolution(cls, resolution: Tier4Resolution, db: Session) -> Dict[str, Any]:
        """
        Captures structured resolution, stages it in pending_catalog_rules,
        and immediately updates existing inventory rows in the database.
        """
        rule_id = f"rule_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        occ_count = cls.get_signature_frequency(resolution.signature_id, db)
        diff_preview = cls.generate_catalog_py_entry(resolution)

        pending_rule = PendingCatalogRule(
            rule_id=rule_id,
            signature_id=resolution.signature_id,
            matched_pattern=resolution.matched_pattern,
            canonical_name=resolution.canonical_name,
            vendor=resolution.vendor,
            license_type=resolution.license_type.upper(),
            license_required=resolution.license_required.upper(),
            metric=resolution.metric.upper(),
            tier=resolution.tier,
            evidence_url=resolution.evidence_url or "",
            evidence_quote=resolution.evidence_quote or "",
            resolved_by=resolution.resolved_by,
            resolved_at=now,
            confidence=resolution.confidence,
            scope=resolution.scope,
            status="pending_review",
            occurrence_count=occ_count,
            diff_preview=diff_preview,
        )

        db.add(pending_rule)
        db.commit()
        db.refresh(pending_rule)

        # 1. Immediately fix the *existing* rows in the inventory
        rows_updated = cls.apply_resolution_to_existing_rows(resolution, db)

        # 2. Log in catalog audit log
        audit_entry = CatalogAuditLog(
            action="rule_staged",
            rule_id=rule_id,
            rule_json=json.dumps(pending_rule.to_dict()),
            performed_by=resolution.resolved_by,
            source_resolutions_count=rows_updated,
            details=f"Staged resolution for '{resolution.canonical_name}' ({resolution.scope}). {rows_updated} rows updated immediately."
        )
        db.add(audit_entry)
        db.commit()

        # 3. Check for auto-promotion if exact match and auditor confirmed
        is_auto_promoted = False
        if resolution.auto_promote and resolution.confidence == "auditor_confirmed" and resolution.scope == "exact_match":
            cls.promote_to_catalog(rule_id, approved_by=f"auto_approved ({resolution.resolved_by})", db=db)
            is_auto_promoted = True

        return {
            "status": "SUCCESS",
            "rule_id": rule_id,
            "is_auto_promoted": is_auto_promoted,
            "existing_rows_updated": rows_updated,
            "diff_preview": diff_preview,
            "rule": pending_rule.to_dict(),
        }

    @classmethod
    def apply_resolution_to_existing_rows(cls, resolution: Tier4Resolution, db: Session) -> int:
        """
        Directly updates matching existing rows in upload_license_results so the dashboard reflects reality immediately.
        """
        try:
            query = db.query(UploadLicenseResult)
            if resolution.scope == "exact_match":
                query = query.filter(
                    (func.lower(UploadLicenseResult.raw_application) == resolution.signature_id.strip().lower()) |
                    (func.lower(UploadLicenseResult.raw_application) == resolution.matched_pattern.strip().lower())
                )
            elif resolution.scope == "pattern_family":
                pattern_escaped = resolution.matched_pattern.strip().replace("*", "%").lower()
                query = query.filter(func.lower(UploadLicenseResult.raw_application).like(f"%{pattern_escaped}%"))
            elif resolution.scope == "vendor_wide":
                query = query.filter(func.lower(UploadLicenseResult.raw_vendor) == resolution.vendor.strip().lower())
            else:
                query = query.filter(
                    func.lower(UploadLicenseResult.raw_application) == resolution.signature_id.strip().lower()
                )

            updated_count = query.update(
                {
                    UploadLicenseResult.canonical_product: resolution.canonical_name,
                    UploadLicenseResult.canonical_vendor: resolution.vendor,
                    UploadLicenseResult.classification: resolution.license_type.upper(),
                    UploadLicenseResult.license_required: resolution.license_required.upper(),
                    UploadLicenseResult.license_metric: resolution.metric.upper(),
                    UploadLicenseResult.metric: resolution.metric.upper(),
                    UploadLicenseResult.evidence_url: resolution.evidence_url or "",
                    UploadLicenseResult.evidence_quote: resolution.evidence_quote or f"Human auditor confirmed Tier {resolution.tier} resolution.",
                    UploadLicenseResult.evidence_status: "VERIFIED",
                    UploadLicenseResult.confidence: "VERY_HIGH" if resolution.confidence == "auditor_confirmed" else "MEDIUM",
                    UploadLicenseResult.override_reason: f"Tier 4 Loop: Confirmed by {resolution.resolved_by} ({resolution.scope})",
                },
                synchronize_session=False
            )
            db.commit()
            return updated_count
        except Exception as e:
            db.rollback()
            return 0

    @classmethod
    def promote_to_catalog(cls, rule_id: str, approved_by: str, db: Session) -> Dict[str, Any]:
        """
        Promotes a staged pending rule to permanent status:
        1. Appends entry to catalog.py.
        2. Dynamically registers the rule in memory in RECOGNITION_RULES.
        3. Appends entry to confirmed_resolutions.json regression fixture.
        4. Marks pending rule as 'merged'.
        5. Records event in catalog_audit_log.
        """
        rule = db.query(PendingCatalogRule).filter(PendingCatalogRule.rule_id == rule_id).first()
        if not rule:
            raise ValueError(f"Rule {rule_id} not found in pending_catalog_rules.")

        now = datetime.now(timezone.utc)
        code_entry = cls.generate_catalog_py_entry(rule)

        # 1. Append entry to catalog.py
        if cls.CATALOG_FILE_PATH.exists():
            with open(cls.CATALOG_FILE_PATH, "r", encoding="utf-8") as f:
                content = f.read()

            target_anchor = "RECOGNITION_RULES: List[CatalogRecognitionEntry] = ["
            if target_anchor in content:
                # Insert right below the anchor
                parts = content.split(target_anchor, 1)
                new_content = parts[0] + target_anchor + "\n    # Added via Tier 4 Feedback Loop\n" + code_entry + parts[1]
                with open(cls.CATALOG_FILE_PATH, "w", encoding="utf-8") as f:
                    f.write(new_content)

        # 2. Dynamically inject into runtime RECOGNITION_RULES in memory
        try:
            from backend.inventory.recognition.catalog import RECOGNITION_RULES, CatalogRecognitionEntry
            from backend.models.enums import FinalLicenseStatus, ExtractionConfidence, ResolutionMethod

            status_enum = FinalLicenseStatus.LICENSE_REQUIRED_YES if rule.license_required.upper() == "YES" else (
                FinalLicenseStatus.LICENSE_REQUIRED_NO if rule.license_required.upper() == "NO" else FinalLicenseStatus.LICENSE_REQUIRED_YES
            )
            avail_map = {
                "COMMERCIAL": "PAID_ONLY",
                "FREEWARE": "FREE",
                "OPEN_SOURCE": "FREE",
                "FREE_AND_PAID": "FREE_AND_PAID",
            }
            avail_model = avail_map.get(rule.license_type.upper(), "FREE_AND_PAID")

            entry = CatalogRecognitionEntry(
                canonical_name=rule.canonical_name,
                canonical_vendor=rule.vendor,
                classification=rule.license_type.upper(),
                availability_model=avail_model,
                license_requirement=rule.license_required.upper(),
                license_required=status_enum,
                licensing_model=f"{rule.license_type.title()} Application",
                licensing_metric=rule.metric.upper(),
                commercial_use_allowed=rule.license_type.upper() in ("FREEWARE", "OPEN_SOURCE", "FREE_AND_PAID"),
                confidence=ExtractionConfidence.VERY_HIGH,
                method=ResolutionMethod.DETERMINISTIC_RULE,
                terms_summary=f"Human verified via Tier 4 feedback loop by {rule.resolved_by}.",
                primary_url=rule.evidence_url or "",
                evidence_quote=rule.evidence_quote or "Confirmed by auditor resolution.",
                is_open_source=rule.license_type.upper() == "OPEN_SOURCE",
                source_type="AUDITOR_RESOLUTION",
                aliases=[rule.matched_pattern.lower(), rule.canonical_name.lower()]
            )
            RECOGNITION_RULES.insert(0, entry)
        except Exception as e:
            pass

        # 3. Append to regression test fixtures
        cls.append_to_regression_fixtures(rule)

        # 4. Update status in database
        rule.status = "merged"
        rule.approved_by = approved_by
        rule.approved_at = now
        db.commit()

        # 5. Log audit entry
        audit_entry = CatalogAuditLog(
            action="rule_merged",
            rule_id=rule.rule_id,
            rule_json=json.dumps(rule.to_dict()),
            performed_by=approved_by,
            source_resolutions_count=rule.occurrence_count,
            details=f"Promoted and merged rule '{rule.canonical_name}' into catalog.py and regression fixtures."
        )
        db.add(audit_entry)
        db.commit()

        return {
            "status": "MERGED",
            "rule_id": rule_id,
            "approved_by": approved_by,
            "approved_at": now.isoformat(),
            "diff_applied": code_entry,
        }

    @classmethod
    def reject_rule(cls, rule_id: str, rejected_by: str, reason: str, db: Session) -> Dict[str, Any]:
        """Marks a pending rule as rejected."""
        rule = db.query(PendingCatalogRule).filter(PendingCatalogRule.rule_id == rule_id).first()
        if not rule:
            raise ValueError(f"Rule {rule_id} not found.")

        rule.status = "rejected"
        rule.rejection_reason = reason
        db.commit()

        audit_entry = CatalogAuditLog(
            action="rule_rejected",
            rule_id=rule.rule_id,
            rule_json=json.dumps(rule.to_dict()),
            performed_by=rejected_by,
            details=f"Rejected rule '{rule.canonical_name}': {reason}"
        )
        db.add(audit_entry)
        db.commit()

        return {"status": "REJECTED", "rule_id": rule_id, "reason": reason}

    @classmethod
    def append_to_regression_fixtures(cls, rule: PendingCatalogRule):
        """Appends confirmed rule to regression fixture JSON file."""
        cls.FIXTURES_PATH.parent.mkdir(parents=True, exist_ok=True)
        fixtures = []
        if cls.FIXTURES_PATH.exists():
            try:
                with open(cls.FIXTURES_PATH, "r", encoding="utf-8") as f:
                    fixtures = json.load(f)
            except Exception:
                fixtures = []

        # Avoid duplicates
        tier_names = {
            1: "Tier 1: Commercial & Billable",
            2: "Tier 2: Freeware & Developer Open Source",
            3: "Tier 3: OS & System Infrastructure",
        }
        expected_tier = tier_names.get(rule.tier, f"Tier {rule.tier}")

        entry_record = {
            "signature_id": rule.signature_id,
            "matched_pattern": rule.matched_pattern,
            "canonical_name": rule.canonical_name,
            "vendor": rule.vendor,
            "expected_classification": rule.license_type,
            "expected_license_required": rule.license_required,
            "expected_tier": expected_tier,
            "added_by": rule.resolved_by,
            "added_date": rule.resolved_at.strftime("%Y-%m-%d") if rule.resolved_at else datetime.now().strftime("%Y-%m-%d"),
        }

        # Replace existing or append
        existing_idx = next((i for i, item in enumerate(fixtures) if item["signature_id"].lower() == rule.signature_id.lower()), None)
        if existing_idx is not None:
            fixtures[existing_idx] = entry_record
        else:
            fixtures.append(entry_record)

        with open(cls.FIXTURES_PATH, "w", encoding="utf-8") as f:
            json.dump(fixtures, f, indent=2)

    @classmethod
    def load_confirmed_resolutions(cls) -> List[Dict[str, Any]]:
        """Loads all confirmed resolutions from regression fixture file."""
        if not cls.FIXTURES_PATH.exists():
            return []
        try:
            with open(cls.FIXTURES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
