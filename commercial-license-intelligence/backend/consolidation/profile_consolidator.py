"""
Main License Knowledge Consolidation Engine.
Consolidates validated licensing facts into a version- and edition-aware application profile.
Preserves complete provenance, tracks profile snapshots, and detects genuine conflicts.
"""

import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.enums import (
    FactType,
    FactStatus,
    ProfileStatus,
    ExtractionConfidence,
    ScopeType,
)
from backend.models.fact import LicenseFact, LicenseEvidence
from backend.models.profile import LicenseProfile, LicenseProfileFact, ProfileVersion
from backend.models.source import LicenseSource
from backend.consolidation.profile_schemas import (
    FieldExplanation,
    LicenseProfileResponse,
    ProfileSummaryBlock,
    ProfileVersionResponse,
)
from backend.consolidation.confidence_calculator import ProfileConfidenceCalculator

logger = logging.getLogger(__name__)


def compute_profile_hash(data: Dict[str, Any]) -> str:
    """Computes deterministic SHA-256 hash from canonical JSON representation."""
    canonical = json.dumps(data, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class LicenseProfileConsolidator:
    """
    Consolidates validated licensing facts into a deterministic, auditable LicenseProfile.
    """

    def __init__(self, confidence_calculator: Optional[ProfileConfidenceCalculator] = None):
        self.confidence_calc = confidence_calculator or ProfileConfidenceCalculator()

    def _is_fact_scope_applicable(
        self,
        fact: LicenseFact,
        target_edition: Optional[str],
        target_version: Optional[str]
    ) -> bool:
        """
        Determines whether a fact's scope applies to the requested (edition, version) target.
        """
        t_ed = (target_edition or "").strip().lower()
        t_ver = (target_version or "").strip().lower()

        f_ed = (fact.edition or "").strip().lower()
        f_ver = (fact.version or "").strip().lower()

        # Edition matching
        if t_ed and f_ed and f_ed != "all" and f_ed != t_ed and f_ed not in t_ed:
            return False

        # Version matching
        if t_ver and f_ver and f_ver != "all" and f_ver != "all_versions" and f_ver != t_ver:
            # Check version year differences
            if any(y in f_ver for y in ["201", "202"]) and any(y in t_ver for y in ["201", "202"]) and f_ver != t_ver:
                return False

        return True

    def consolidate_profile(
        self,
        db: Session,
        vendor: str,
        product: str,
        edition: Optional[str] = None,
        version: Optional[str] = None
    ) -> LicenseProfileResponse:
        """
        Generates or updates the consolidated LicenseProfile for an application target.
        """
        clean_v = vendor.strip()
        clean_p = product.strip()
        clean_ed = edition.strip() if edition else None
        clean_ver = version.strip() if version else None

        # 1. Fetch all candidate facts for this vendor and product
        query = db.query(LicenseFact).filter(
            func.lower(LicenseFact.vendor_name) == clean_v.lower(),
            func.lower(LicenseFact.product_name) == clean_p.lower()
        )
        all_facts = query.all()

        # 2. Filter applicable facts for requested scope
        applicable_facts = [
            f for f in all_facts if self._is_fact_scope_applicable(f, clean_ed, clean_ver)
        ]

        # Counts
        validated_facts = [f for f in applicable_facts if f.status == FactStatus.VALIDATED]
        review_facts = [f for f in applicable_facts if f.status == FactStatus.REVIEW_REQUIRED]
        conflict_facts = [f for f in applicable_facts if f.status == FactStatus.CONFLICT]
        unknown_facts = [f for f in applicable_facts if f.normalized_value == "UNKNOWN"]

        # Group validated facts by FactType
        by_type: Dict[FactType, List[LicenseFact]] = {}
        for f in validated_facts:
            by_type.setdefault(f.fact_type, []).append(f)

        explanations: Dict[str, FieldExplanation] = {}
        consolidated_values: Dict[str, str] = {}
        has_conflicts = len(conflict_facts) > 0
        used_fact_ids: List[int] = []

        # List of all fact types to evaluate
        all_fact_types = [
            (FactType.LICENSE_CLASSIFICATION, "license_classification"),
            (FactType.LICENSE_REQUIRED, "license_required"),
            (FactType.LICENSE_MODEL, "license_model"),
            (FactType.LICENSE_METRIC, "license_metric"),
            (FactType.LICENSE_DURATION, "license_duration"),
            (FactType.COMMERCIAL_USE, "commercial_use"),
            (FactType.EDUCATIONAL_USE, "educational_use"),
            (FactType.TRIAL_AVAILABLE, "trial_available"),
        ]

        for ft, attr_name in all_fact_types:
            facts_for_type = by_type.get(ft, [])

            if not facts_for_type:
                consolidated_values[attr_name] = "UNKNOWN"
                explanations[ft.value] = FieldExplanation(
                    value="UNKNOWN",
                    confidence=ExtractionConfidence.UNKNOWN,
                    supporting_fact_ids=[]
                )
                continue

            # Check for distinct values among validated facts
            distinct_vals = list(set([f.normalized_value for f in facts_for_type if f.normalized_value != "UNKNOWN"]))

            if len(distinct_vals) > 1:
                # Contradiction between validated facts
                consolidated_values[attr_name] = "CONFLICT"
                has_conflicts = True
                f_ids = [f.id for f in facts_for_type]
                used_fact_ids.extend(f_ids)
                explanations[ft.value] = FieldExplanation(
                    value="CONFLICT",
                    confidence=ExtractionConfidence.LOW,
                    supporting_fact_ids=f_ids,
                    conflicting_values=distinct_vals
                )
            elif len(distinct_vals) == 1:
                val = distinct_vals[0]
                consolidated_values[attr_name] = val
                # Select highest confidence
                highest_conf_fact = max(facts_for_type, key=lambda x: x.confidence_score)
                f_ids = [f.id for f in facts_for_type]
                used_fact_ids.extend(f_ids)
                explanations[ft.value] = FieldExplanation(
                    value=val,
                    confidence=highest_conf_fact.confidence,
                    supporting_fact_ids=f_ids
                )
            else:
                consolidated_values[attr_name] = "UNKNOWN"
                explanations[ft.value] = FieldExplanation(
                    value="UNKNOWN",
                    confidence=ExtractionConfidence.UNKNOWN,
                    supporting_fact_ids=[f.id for f in facts_for_type]
                )

        # 3. Overall Confidence & Profile Status
        profile_status, overall_conf = self.confidence_calc.calculate(
            explanations=explanations,
            has_conflicts=has_conflicts,
            has_review_required=(len(review_facts) > 0),
            validated_fact_count=len(validated_facts)
        )

        # 4. Calculate Profile Hash
        hash_payload = {
            "vendor": clean_v,
            "product": clean_p,
            "edition": clean_ed or "",
            "version": clean_ver or "",
            "values": consolidated_values,
        }
        profile_hash = compute_profile_hash(hash_payload)

        # 5. Persist or Update LicenseProfile
        existing_profile = db.query(LicenseProfile).filter(
            func.lower(LicenseProfile.vendor_name) == clean_v.lower(),
            func.lower(LicenseProfile.product_name) == clean_p.lower(),
            func.coalesce(LicenseProfile.edition, "") == (clean_ed or ""),
            func.coalesce(LicenseProfile.version, "") == (clean_ver or ""),
        ).first()

        now = datetime.now(timezone.utc)

        if not existing_profile:
            profile = LicenseProfile(
                vendor_name=clean_v,
                product_name=clean_p,
                edition=clean_ed,
                version=clean_ver,
                license_classification=consolidated_values["license_classification"],
                availability_model=consolidated_values.get("availability_model", "UNKNOWN"),
                license_required=consolidated_values["license_required"],
                license_model=consolidated_values["license_model"],
                license_metric=consolidated_values["license_metric"],
                license_duration=consolidated_values["license_duration"],
                commercial_use=consolidated_values["commercial_use"],
                educational_use=consolidated_values["educational_use"],
                trial_available=consolidated_values["trial_available"],
                overall_confidence=overall_conf,
                profile_status=profile_status,
                validated_fact_count=len(validated_facts),
                review_fact_count=len(review_facts),
                conflict_fact_count=len(conflict_facts),
                unknown_fact_count=len(unknown_facts),
                profile_hash=profile_hash,
                explanation_json={k: v.model_dump() for k, v in explanations.items()},
                generated_at=now,
                updated_at=now
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)

            # Store initial version snapshot
            v_snap = ProfileVersion(
                profile_id=profile.id,
                profile_hash=profile_hash,
                profile_data=hash_payload,
                generated_at=now
            )
            db.add(v_snap)
            db.commit()

        else:
            profile = existing_profile
            # Check if profile changed
            if profile.profile_hash != profile_hash:
                # Save historical snapshot before updating
                v_snap = ProfileVersion(
                    profile_id=profile.id,
                    profile_hash=profile_hash,
                    profile_data=hash_payload,
                    generated_at=now
                )
                db.add(v_snap)

            profile.license_classification = consolidated_values["license_classification"]
            profile.license_required = consolidated_values["license_required"]
            profile.license_model = consolidated_values["license_model"]
            profile.license_metric = consolidated_values["license_metric"]
            profile.license_duration = consolidated_values["license_duration"]
            profile.commercial_use = consolidated_values["commercial_use"]
            profile.educational_use = consolidated_values["educational_use"]
            profile.trial_available = consolidated_values["trial_available"]
            profile.overall_confidence = overall_conf
            profile.profile_status = profile_status
            profile.validated_fact_count = len(validated_facts)
            profile.review_fact_count = len(review_facts)
            profile.conflict_fact_count = len(conflict_facts)
            profile.unknown_fact_count = len(unknown_facts)
            profile.profile_hash = profile_hash
            profile.explanation_json = {k: v.model_dump() for k, v in explanations.items()}
            profile.updated_at = now
            db.commit()
            db.refresh(profile)

        # 6. Synchronize Profile Fact Associations
        db.query(LicenseProfileFact).filter(LicenseProfileFact.profile_id == profile.id).delete()
        for fid in set(used_fact_ids):
            db.add(LicenseProfileFact(profile_id=profile.id, license_fact_id=fid, created_at=now))
        db.commit()

        # 7. Supporting facts detail with evidence for drill-down
        supporting_facts_payload = []
        for fid in set(used_fact_ids):
            fact_obj = db.query(LicenseFact).filter(LicenseFact.id == fid).first()
            if fact_obj:
                src_name = None
                src_url = None
                if fact_obj.source_id:
                    src = db.query(LicenseSource).filter(LicenseSource.id == fact_obj.source_id).first()
                    if src:
                        src_name = src.source_name
                        src_url = src.source_url

                supporting_facts_payload.append({
                    "id": fact_obj.id,
                    "fact_type": fact_obj.fact_type.value,
                    "value": fact_obj.normalized_value,
                    "confidence": fact_obj.confidence.value,
                    "status": fact_obj.status.value,
                    "source_name": src_name,
                    "source_url": src_url,
                    "document_id": fact_obj.document_id,
                    "page_number": fact_obj.page_number,
                    "evidence_text": fact_obj.evidence_text
                })

        summary_block = ProfileSummaryBlock(
            required=profile.license_required,
            classification=profile.license_classification,
            model=profile.license_model,
            metric=profile.license_metric,
            duration=profile.license_duration
        )

        return LicenseProfileResponse(
            id=profile.id,
            vendor=profile.vendor_name,
            product=profile.product_name,
            edition=profile.edition,
            version=profile.version,
            license_classification=profile.license_classification,
            license_required=profile.license_required,
            license_model=profile.license_model,
            license_metric=profile.license_metric,
            license_duration=profile.license_duration,
            commercial_use=profile.commercial_use,
            educational_use=profile.educational_use,
            trial_available=profile.trial_available,
            overall_confidence=profile.overall_confidence,
            profile_status=profile.profile_status,
            validated_fact_count=profile.validated_fact_count,
            review_fact_count=profile.review_fact_count,
            conflict_fact_count=profile.conflict_fact_count,
            unknown_fact_count=profile.unknown_fact_count,
            profile_hash=profile.profile_hash,
            explanations=explanations,
            supporting_facts=supporting_facts_payload,
            license_summary=summary_block,
            generated_at=profile.generated_at
        )

    def get_profile_history(self, db: Session, profile_id: int) -> List[ProfileVersionResponse]:
        """Retrieves historical version snapshots for a profile."""
        versions = db.query(ProfileVersion).filter(
            ProfileVersion.profile_id == profile_id
        ).order_by(ProfileVersion.id.desc()).all()

        return [
            ProfileVersionResponse(
                id=v.id,
                profile_id=v.profile_id,
                profile_hash=v.profile_hash,
                profile_data=v.profile_data,
                generated_at=v.generated_at
            ) for v in versions
        ]
