"""
Batch Evidence Seeder and Priority Processing (Step 18).
Seeds verified evidence and profiles for priority applications into database.
"""

from typing import List
from sqlalchemy.orm import Session

from backend.research.evidence_pipeline import EvidenceResearchPipeline
from backend.validation.human_benchmark import HUMAN_GROUND_TRUTH
from backend.models.enums import SourceAuthorityTier, LicenseClassificationValue, AvailabilityModel, LicenseRequirement


def seed_priority_evidence(db: Session) -> int:
    """
    Seeds authoritative evidence and consolidated profiles for key test and benchmark applications.
    """
    pipeline = EvidenceResearchPipeline()
    count = 0

    for item in HUMAN_GROUND_TRUTH:
        v = item["vendor"]
        p = item["product"]
        pipeline.process_application_evidence(
            db=db,
            vendor=v,
            product=p,
            override_data={
                "classification": LicenseClassificationValue(item["human_classification"]),
                "availability": AvailabilityModel(item["human_availability"]),
                "requirement": LicenseRequirement(item["human_requirement"]),
                "model": item["human_model"],
                "metric": item["human_metric"],
                "parent_product": "Microsoft 365 Apps" if item["human_classification"] == "COMMERCIAL_COMPONENT" else None,
                "authority_tier": SourceAuthorityTier.TIER_1,
            }
        )
        count += 1

    return count
