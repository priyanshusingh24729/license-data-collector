"""
Column Mapping and Detection Engine for Software Inventory Uploads.
Automatically identifies and maps varied inventory column headers to standardized fields:
- Application (Required)
- Vendor / Publisher (Optional)
- Version (Optional)
- Hostname / Machine Name (Optional)
- Install Date (Optional)
- Install Location (Optional)
"""

import re
from typing import Dict, List, Optional, Any, Tuple


class ColumnMapper:
    """
    Intelligent column header detection and mapping for diverse inventory exports.
    """

    # Normalized synonym patterns (ordered from highest priority exact matches to looser matches)
    FIELD_SYNONYMS: Dict[str, List[str]] = {
        "application": [
            "application_name",
            "application name",
            "application",
            "software_name",
            "software name",
            "software",
            "display_name",
            "display name",
            "product_name",
            "product name",
            "product",
            "app_name",
            "app name",
            "app",
            "sw_name",
            "program_name",
            "program",
            "package_name",
            "package",
            "raw_name",
            "name",
            "installed software",
            "installed application",
            "title",
        ],
        "vendor": [
            "publisher_name",
            "publisher name",
            "publisher",
            "vendor_name",
            "vendor name",
            "vendor",
            "manufacturer_name",
            "manufacturer name",
            "manufacturer",
            "company_name",
            "company",
            "author",
            "creator",
            "mfr",
            "pub",
            "vend",
            "raw_vendor",
            "raw_publisher",
        ],
        "version": [
            "display_version",
            "display version",
            "product_version",
            "product version",
            "software_version",
            "software version",
            "app_version",
            "app version",
            "version",
            "ver",
            "raw_version",
            "release",
            "build",
            "revision",
        ],
        "hostname": [
            "hostname",
            "host_name",
            "host name",
            "host",
            "computer_name",
            "computer name",
            "computer",
            "machine_name",
            "machine name",
            "machine",
            "device_name",
            "device name",
            "device_id",
            "device id",
            "device",
            "endpoint_name",
            "endpoint",
            "pc_name",
            "pc name",
            "pc",
            "unique_id",
            "unique id",
            "serial_number",
            "serial",
            "ip_address",
            "ip",
        ],
        "install_date": [
            "install_date",
            "install date",
            "installed_on",
            "installed on",
            "installation_date",
            "installation date",
            "install_time",
            "date_installed",
            "date",
        ],
        "install_location": [
            "install_location",
            "install location",
            "installation_path",
            "install_path",
            "install path",
            "path",
            "directory",
            "folder",
            "location",
        ],
    }

    @classmethod
    def clean_header(cls, header: str) -> str:
        """Cleans and normalizes header strings for robust matching."""
        if not header:
            return ""
        # Remove BOM, punctuation, multiple spaces
        cleaned = header.strip().lower()
        cleaned = re.sub(r"[\ufeff\r\n\t]", "", cleaned)
        cleaned = re.sub(r"[\s_-]+", " ", cleaned).strip()
        return cleaned

    @classmethod
    def auto_detect_columns(cls, headers: List[str]) -> Dict[str, Optional[str]]:
        """
        Auto-detects the best matching header column for each standardized target field.
        Returns a dict mapping: { 'application': 'Actual Header', 'vendor': 'Actual Header', ... }
        """
        if not headers:
            return {field: None for field in cls.FIELD_SYNONYMS}

        mapping: Dict[str, Optional[str]] = {
            "application": None,
            "vendor": None,
            "version": None,
            "hostname": None,
            "install_date": None,
            "install_location": None,
        }

        used_headers = set()

        # Priority 1: Exact / High-confidence synonym match
        for field, synonyms in cls.FIELD_SYNONYMS.items():
            for raw_h in headers:
                if raw_h in used_headers:
                    continue
                clean_h = cls.clean_header(raw_h)
                if clean_h in synonyms:
                    mapping[field] = raw_h
                    used_headers.add(raw_h)
                    break

        # Priority 2: Substring containment match for still-unassigned fields
        for field, synonyms in cls.FIELD_SYNONYMS.items():
            if mapping[field] is not None:
                continue
            for raw_h in headers:
                if raw_h in used_headers:
                    continue
                clean_h = cls.clean_header(raw_h)
                for syn in synonyms:
                    if len(syn) >= 3 and (syn in clean_h or clean_h in syn):
                        mapping[field] = raw_h
                        used_headers.add(raw_h)
                        break
                if mapping[field] is not None:
                    break

        return mapping

    @classmethod
    def calculate_confidence(cls, headers: List[str], mapping: Dict[str, Optional[str]]) -> Dict[str, Any]:
        """
        Calculates mapping quality and confidence score.
        """
        has_app = bool(mapping.get("application"))
        has_vendor = bool(mapping.get("vendor"))
        has_version = bool(mapping.get("version"))
        has_host = bool(mapping.get("hostname"))

        score = 0
        if has_app:
            score += 50
        if has_vendor:
            score += 20
        if has_version:
            score += 15
        if has_host:
            score += 15

        confidence_tier = "HIGH" if score >= 85 else "MEDIUM" if score >= 50 else "LOW"

        return {
            "is_valid": has_app,
            "score": score,
            "confidence": confidence_tier,
            "missing_fields": [f for f in ["application", "vendor", "version", "hostname"] if not mapping.get(f)],
            "mapping": mapping,
        }

    @classmethod
    def extract_row_data(
        cls,
        raw_row: Dict[str, Any],
        mapping: Dict[str, Optional[str]],
        row_index: int = 0
    ) -> Dict[str, Any]:
        """
        Extracts and normalizes standardized fields from a raw row dict using the mapping.
        """
        app_col = mapping.get("application")
        vendor_col = mapping.get("vendor")
        ver_col = mapping.get("version")
        host_col = mapping.get("hostname")
        date_col = mapping.get("install_date")
        loc_col = mapping.get("install_location")

        def _get_val(col_name: Optional[str]) -> Optional[str]:
            if not col_name or col_name not in raw_row:
                return None
            val = raw_row[col_name]
            if val is None:
                return None
            s = str(val).strip()
            if s.lower() in ("n/a", "none", "null", "unknown", "undefined", "-", "--", ""):
                return None
            return s

        app_name = _get_val(app_col)
        vendor = _get_val(vendor_col)
        version = _get_val(ver_col)
        hostname = _get_val(host_col) or "UNKNOWN_HOST"
        install_date = _get_val(date_col)
        install_loc = _get_val(loc_col)

        return {
            "row_index": row_index,
            "raw_application": app_name,
            "raw_vendor": vendor,
            "raw_version": version,
            "hostname": hostname,
            "install_date": install_date,
            "install_location": install_loc,
            "raw_data": raw_row,
        }
