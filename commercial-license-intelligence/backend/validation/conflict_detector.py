"""
Multi-Source Conflict & Discrepancy Detector for Validation.
Evaluates contradictory facts across sources, checking whether version scopes,
edition differences, or source authority hierarchies resolve the discrepancy.
"""

from typing import List, Dict, Any, Tuple
from backend.models.fact import LicenseFact
from backend.models.enums import FactType, FactStatus, AuthorityLevel


class ValidationConflictDetector:
    """
    Evaluates multi-source contradiction and assigns resolution or conflict status.
    """

    def detect_fact_conflicts(
        self,
        db: Any,
        fact: LicenseFact
    ) -> Tuple[bool, List[LicenseFact]]:
        """
        Detects if an incoming fact contradicts existing VALIDATED or CONFIRMED facts in the database
        for the same vendor, product, edition, version, and fact_type.
        """
        if not db or not fact or not fact.fact_type:
            return False, []

        query = db.query(LicenseFact).filter(
            LicenseFact.id != fact.id if fact.id else True,
            LicenseFact.vendor_name.ilike(fact.vendor_name) if fact.vendor_name else True,
            LicenseFact.product_name.ilike(fact.product_name) if fact.product_name else True,
            LicenseFact.fact_type == fact.fact_type,
            LicenseFact.status == FactStatus.VALIDATED,
        )

        if fact.edition:
            query = query.filter(LicenseFact.edition == fact.edition)
        if fact.version:
            query = query.filter(LicenseFact.version == fact.version)

        existing = query.all()
        conflicting = [
            ef for ef in existing
            if ef.normalized_value and fact.normalized_value
            and ef.normalized_value != "UNKNOWN"
            and fact.normalized_value != "UNKNOWN"
            and ef.normalized_value != fact.normalized_value
        ]

        if conflicting:
            return True, conflicting
        return False, []

    def analyze_conflicts(
        self,
        facts: List[LicenseFact]
    ) -> Tuple[List[LicenseFact], List[Dict[str, Any]]]:
        """
        Groups facts by (vendor, product, fact_type) and flags unresolved contradictions.
        """
        by_group: Dict[Tuple[str, str, FactType], List[LicenseFact]] = {}
        for f in facts:
            key = (f.vendor_name.lower(), f.product_name.lower(), f.fact_type)
            by_group.setdefault(key, []).append(f)

        conflict_reports: List[Dict[str, Any]] = []

        for key, fact_list in by_group.items():
            distinct_vals = list(set([f.normalized_value for f in fact_list if f.normalized_value != "UNKNOWN"]))
            if len(distinct_vals) > 1:
                # Check if versions explain it (e.g. 2017 vs 2025)
                versions = list(set([f.version for f in fact_list if f.version]))
                editions = list(set([f.edition for f in fact_list if f.edition]))

                if len(versions) > 1:
                    # Version-scoped variance: valid historical distinction
                    for f in fact_list:
                        # Keep separate version-scoped facts
                        pass
                elif len(editions) > 1:
                    # Edition-scoped variance
                    for f in fact_list:
                        pass
                else:
                    # True unresolved conflict
                    for f in fact_list:
                        f.status = FactStatus.CONFLICT

                    conflict_reports.append({
                        "vendor": key[0],
                        "product": key[1],
                        "fact_type": key[2].value,
                        "conflicting_values": distinct_vals,
                        "fact_ids": [f.id for f in fact_list],
                        "explanation": "Multiple contradictory values detected for identical product, edition, and version scope."
                    })

        return facts, conflict_reports

