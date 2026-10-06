"""
Export Validation & Lint Engine for License Intelligence Pipeline.
Runs on every export to catch data quality issues before the file is finalized.

Checks:
1. Duplicate rows (keyed on application + vendor + version)
2. Contradictory entity records (same app, different classification)
3. Out-of-domain enum values per column
4. Implausible version strings
5. Evidence consistency (VERIFIED must have version + license model)
6. Encoding integrity (detect mojibake patterns)
7. License model fallback detection (flag generic labels)
"""

import re
import unicodedata
import logging
from typing import Dict, Any, List, Tuple, Optional, Set

logger = logging.getLogger(__name__)

# Valid domain values per column (Issue #7)
VALID_CLASSIFICATIONS: Set[str] = {
    "COMMERCIAL", "COMMERCIAL_COMPONENT", "OPEN_SOURCE", "FREEWARE",
    "OS_BUNDLED", "FREE_AND_PAID", "TRIAL", "EDUCATIONAL",
    "PROPRIETARY", "NON_COMMERCIAL", "PUBLIC_DOMAIN", "UNKNOWN",
}

VALID_LICENSE_REQUIRED: Set[str] = {
    "YES", "NO", "CONTEXT_DEPENDENT", "UNKNOWN",
}

VALID_EVIDENCE_STATUS: Set[str] = {
    "VERIFIED", "PARTIAL", "MISSING",
}

VALID_CONFIDENCE: Set[str] = {
    "VERY_HIGH", "HIGH", "MEDIUM", "LOW", "UNKNOWN",
}

VALID_METRICS: Set[str] = {
    "USER", "DEVICE", "CORE", "PROCESSOR", "INSTALLATION",
    "INSTANCE", "CONCURRENT_USER", "CONCURRENT_DEVICE",
    "SUBSCRIPTION", "SITE", "ORGANIZATION", "NAMED_USER",
    "CPU", "SOCKET", "SERVER", "VM", "NONE",
    "NOT_APPLICABLE", "CONTEXT_DEPENDENT", "UNKNOWN",
}

# Generic fallback labels that may indicate unverified data (Issue #3)
SUSPICIOUS_LICENSE_MODELS: Set[str] = {
    "Permissive / Bundled",
    "Freeware Application",
    "Standard",
    "Standard Commercial",
}

# Mojibake detection patterns (Issue #6)
MOJIBAKE_PATTERNS = [
    re.compile(r"Â®"),       # ® read as Latin-1
    re.compile(r"â„¢"),       # ™ read as Latin-1
    re.compile(r"Â©"),       # © read as Latin-1
    re.compile(r"Ã¤|Ã¶|Ã¼"), # German umlauts
    re.compile(r"Ã©|Ã¨|Ã "),  # French accents
]

# Version plausibility: max reasonable major version per known vendor prefix
VERSION_MAX_MAJOR: Dict[str, int] = {
    ".net": 10,
    "python": 4,
    "node": 30,
    "go": 2,
    "php": 9,
    "java": 25,
    "git": 3,
}


class ExportValidationIssue:
    """A single validation issue found during export lint."""

    def __init__(
        self,
        severity: str,
        issue_type: str,
        message: str,
        record: Optional[Dict[str, Any]] = None,
        field: Optional[str] = None,
        value: Optional[str] = None,
    ):
        self.severity = severity  # "ERROR", "WARNING", "INFO"
        self.issue_type = issue_type
        self.message = message
        self.record = record
        self.field = field
        self.value = value

    def __repr__(self) -> str:
        app = self.record.get("Application", "?") if self.record else "?"
        return f"<{self.severity}:{self.issue_type}> {app}: {self.message}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "issue_type": self.issue_type,
            "message": self.message,
            "field": self.field,
            "value": self.value,
            "application": self.record.get("Application") if self.record else None,
        }


class ExportValidator:
    """
    Validates export data for quality issues.
    Runs before CSV is finalized and flags problems.
    """

    @classmethod
    def validate_batch(
        cls,
        records: List[Dict[str, Any]],
        *,
        check_dedup: bool = True,
        check_schema: bool = True,
        check_versions: bool = True,
        check_evidence: bool = True,
        check_encoding: bool = True,
        check_contradictions: bool = True,
        check_fallback_labels: bool = True,
    ) -> List[ExportValidationIssue]:
        """
        Runs all configured validation checks on a batch of export records.
        Returns a list of issues found.
        """
        issues: List[ExportValidationIssue] = []

        if check_dedup:
            issues.extend(cls.check_duplicates(records))
        if check_schema:
            issues.extend(cls.check_schema_constraints(records))
        if check_versions:
            issues.extend(cls.check_version_plausibility(records))
        if check_evidence:
            issues.extend(cls.check_evidence_consistency(records))
        if check_encoding:
            issues.extend(cls.check_encoding_integrity(records))
        if check_contradictions:
            issues.extend(cls.check_entity_contradictions(records))
        if check_fallback_labels:
            issues.extend(cls.check_fallback_license_labels(records))

        return issues

    @classmethod
    def deduplicate_records(
        cls,
        records: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Deduplicates resolved records by (Application, Vendor, Version).
        When duplicates are found, keeps the record with higher confidence/reliability.
        """
        seen: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        result: List[Dict[str, Any]] = []
        duplicates_removed = 0

        confidence_rank = {"VERY_HIGH": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}

        for rec in records:
            app = (rec.get("Application") or "").strip()
            vendor = (rec.get("Vendor") or "").strip()
            version = (rec.get("Version") or "").strip()
            key = (app.lower(), vendor.lower(), version.lower())

            if key in seen:
                existing = seen[key]
                existing_conf = confidence_rank.get(existing.get("Confidence", "UNKNOWN"), 0)
                new_conf = confidence_rank.get(rec.get("Confidence", "UNKNOWN"), 0)
                if new_conf > existing_conf:
                    # Replace with higher-confidence record
                    idx = result.index(existing)
                    result[idx] = rec
                    seen[key] = rec
                duplicates_removed += 1
            else:
                seen[key] = rec
                result.append(rec)

        if duplicates_removed > 0:
            logger.info(f"Export dedup: removed {duplicates_removed} duplicate record(s)")

        return result

    @classmethod
    def check_duplicates(
        cls,
        records: List[Dict[str, Any]],
    ) -> List[ExportValidationIssue]:
        """Flags exact duplicate rows by (Application, Vendor, Version)."""
        issues: List[ExportValidationIssue] = []
        seen: Dict[Tuple[str, str, str], int] = {}

        for rec in records:
            app = (rec.get("Application") or "").strip().lower()
            vendor = (rec.get("Vendor") or "").strip().lower()
            version = (rec.get("Version") or "").strip().lower()
            key = (app, vendor, version)

            if key in seen:
                seen[key] += 1
                issues.append(ExportValidationIssue(
                    severity="ERROR",
                    issue_type="DUPLICATE_ROW",
                    message=f"Duplicate row #{seen[key]} for ({rec.get('Application')}, {rec.get('Vendor')}, {rec.get('Version')})",
                    record=rec,
                ))
            else:
                seen[key] = 1

        return issues

    @classmethod
    def check_schema_constraints(
        cls,
        records: List[Dict[str, Any]],
    ) -> List[ExportValidationIssue]:
        """Validates field values against allowed enum domains."""
        issues: List[ExportValidationIssue] = []

        field_constraints = {
            "Classification": VALID_CLASSIFICATIONS,
            "License Required": VALID_LICENSE_REQUIRED,
            "Evidence Status": VALID_EVIDENCE_STATUS,
            "Confidence": VALID_CONFIDENCE,
            "Metric": VALID_METRICS,
        }

        for rec in records:
            for field_name, valid_values in field_constraints.items():
                value = rec.get(field_name)
                if value and value not in valid_values:
                    issues.append(ExportValidationIssue(
                        severity="ERROR",
                        issue_type="SCHEMA_VIOLATION",
                        message=f"'{field_name}' has invalid value '{value}'. Allowed: {sorted(valid_values)}",
                        record=rec,
                        field=field_name,
                        value=value,
                    ))

        return issues

    @classmethod
    def check_version_plausibility(
        cls,
        records: List[Dict[str, Any]],
    ) -> List[ExportValidationIssue]:
        """Flags implausible version strings."""
        issues: List[ExportValidationIssue] = []

        for rec in records:
            version = rec.get("Version") or ""
            app_name = (rec.get("Application") or "").lower()

            if not version or version in ("N/A", "UNKNOWN", ""):
                continue

            # Check for bitness suffix still present
            if re.search(r"-(?:64|32|x64|x86)$", version, re.IGNORECASE):
                issues.append(ExportValidationIssue(
                    severity="WARNING",
                    issue_type="VERSION_BITNESS_SUFFIX",
                    message=f"Version '{version}' contains architecture suffix that should be a separate field",
                    record=rec,
                    field="Version",
                    value=version,
                ))

            # Check major version plausibility for known products
            major_match = re.match(r"(\d+)", version)
            if major_match:
                major = int(major_match.group(1))
                for product_prefix, max_major in VERSION_MAX_MAJOR.items():
                    if product_prefix in app_name and major > max_major:
                        issues.append(ExportValidationIssue(
                            severity="WARNING",
                            issue_type="VERSION_IMPLAUSIBLE",
                            message=f"Version '{version}' has major version {major} for {rec.get('Application')} "
                                    f"(max expected: {max_major}). Possible wrong version field read.",
                            record=rec,
                            field="Version",
                            value=version,
                        ))
                        break

        return issues

    @classmethod
    def check_evidence_consistency(
        cls,
        records: List[Dict[str, Any]],
    ) -> List[ExportValidationIssue]:
        """
        Checks consistency between evidence status and required fields.
        If Evidence Status = VERIFIED, Version and License Model must be populated.
        """
        issues: List[ExportValidationIssue] = []

        for rec in records:
            ev_status = rec.get("Evidence Status")
            if ev_status != "VERIFIED":
                continue

            version = rec.get("Version") or ""
            if version in ("N/A", "", "UNKNOWN"):
                issues.append(ExportValidationIssue(
                    severity="WARNING",
                    issue_type="EVIDENCE_INCONSISTENCY",
                    message=f"Evidence Status is VERIFIED but Version is '{version}'. Should downgrade to PARTIAL.",
                    record=rec,
                    field="Version",
                    value=version,
                ))

            license_model = rec.get("License Model") or ""
            if license_model in ("UNKNOWN", ""):
                issues.append(ExportValidationIssue(
                    severity="WARNING",
                    issue_type="EVIDENCE_INCONSISTENCY",
                    message=f"Evidence Status is VERIFIED but License Model is '{license_model}'. Should downgrade to PARTIAL.",
                    record=rec,
                    field="License Model",
                    value=license_model,
                ))

            confidence = rec.get("Confidence")
            if confidence == "VERY_HIGH" and version in ("N/A", ""):
                issues.append(ExportValidationIssue(
                    severity="ERROR",
                    issue_type="EVIDENCE_INCONSISTENCY",
                    message=f"Confidence is VERY_HIGH but Version is missing — contradictory.",
                    record=rec,
                    field="Confidence",
                    value=confidence,
                ))

        return issues

    @classmethod
    def check_encoding_integrity(
        cls,
        records: List[Dict[str, Any]],
    ) -> List[ExportValidationIssue]:
        """Detects mojibake (UTF-8 misread as Latin-1) in string fields."""
        issues: List[ExportValidationIssue] = []
        text_fields = ["Application", "Vendor", "License Model"]

        for rec in records:
            for field_name in text_fields:
                value = rec.get(field_name) or ""
                for pattern in MOJIBAKE_PATTERNS:
                    if pattern.search(value):
                        issues.append(ExportValidationIssue(
                            severity="ERROR",
                            issue_type="ENCODING_MOJIBAKE",
                            message=f"Mojibake detected in '{field_name}': '{value}'. "
                                    f"Likely UTF-8 read as Latin-1.",
                            record=rec,
                            field=field_name,
                            value=value,
                        ))
                        break

        return issues

    @classmethod
    def check_entity_contradictions(
        cls,
        records: List[Dict[str, Any]],
    ) -> List[ExportValidationIssue]:
        """
        Flags the same canonical application appearing with different classifications.
        Groups by normalized app name and checks for conflicting values.
        """
        issues: List[ExportValidationIssue] = []
        app_groups: Dict[str, List[Dict[str, Any]]] = {}

        for rec in records:
            app = (rec.get("Application") or "").strip().lower()
            if app and app not in ("unknown", "unresolved"):
                app_groups.setdefault(app, []).append(rec)

        for app_key, group in app_groups.items():
            if len(group) < 2:
                continue

            classifications = {r.get("Classification") for r in group} - {None}
            if len(classifications) > 1:
                issues.append(ExportValidationIssue(
                    severity="ERROR",
                    issue_type="ENTITY_CONTRADICTION",
                    message=f"Application '{group[0].get('Application')}' has contradictory classifications: {classifications}",
                    record=group[0],
                    field="Classification",
                ))

            requirements = {r.get("License Required") for r in group} - {None}
            if len(requirements) > 1:
                issues.append(ExportValidationIssue(
                    severity="WARNING",
                    issue_type="ENTITY_CONTRADICTION",
                    message=f"Application '{group[0].get('Application')}' has contradictory license requirements: {requirements}",
                    record=group[0],
                    field="License Required",
                ))

        return issues

    @classmethod
    def check_fallback_license_labels(
        cls,
        records: List[Dict[str, Any]],
    ) -> List[ExportValidationIssue]:
        """Flags records using generic fallback license model labels that may be unverified."""
        issues: List[ExportValidationIssue] = []

        for rec in records:
            model = rec.get("License Model") or ""
            if model in SUSPICIOUS_LICENSE_MODELS:
                issues.append(ExportValidationIssue(
                    severity="WARNING",
                    issue_type="FALLBACK_LABEL",
                    message=f"License Model '{model}' appears to be a generic fallback rather than a verified classification. "
                            f"Consider verifying against actual license terms.",
                    record=rec,
                    field="License Model",
                    value=model,
                ))

        return issues

    @classmethod
    def enforce_evidence_consistency(
        cls,
        records: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Mutates records to enforce evidence consistency rules:
        - If VERIFIED but Version=N/A or License Model=UNKNOWN → downgrade to PARTIAL
        - If MISSING but Confidence=HIGH/VERY_HIGH → downgrade confidence to LOW
        """
        for rec in records:
            ev_status = rec.get("Evidence Status")
            version = rec.get("Version") or ""
            license_model = rec.get("License Model") or ""

            if ev_status == "VERIFIED":
                if version in ("N/A", "", "UNKNOWN") or license_model in ("UNKNOWN", ""):
                    rec["Evidence Status"] = "PARTIAL"
                    logger.debug(
                        f"Downgraded evidence status to PARTIAL for {rec.get('Application')} "
                        f"(version={version}, model={license_model})"
                    )

            if ev_status == "MISSING":
                if rec.get("Confidence") in ("HIGH", "VERY_HIGH"):
                    rec["Confidence"] = "LOW"

        return records

    @classmethod
    def fix_schema_violations(
        cls,
        records: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Fixes known schema violations by mapping invalid values to correct ones.
        e.g. License Required = "NOT_APPLICABLE" → "NO"
        """
        for rec in records:
            lr = rec.get("License Required")
            if lr and lr not in VALID_LICENSE_REQUIRED:
                if lr == "NOT_APPLICABLE":
                    rec["License Required"] = "NO"
                else:
                    rec["License Required"] = "UNKNOWN"

        return records
