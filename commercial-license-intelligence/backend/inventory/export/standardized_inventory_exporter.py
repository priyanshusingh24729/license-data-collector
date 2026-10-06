"""
Standardized Application Inventory Export Engine.
Produces consistent, Excel-ready CSV and XLSX exports strictly matching the required 17-column schema:

App_ID, Name, OSType, Version, Normalized_Application, Created_At,
Operating_System, Major_Version, Minor_Version, Patch_Version,
NoLicenseRequired, IsEndOfLife, IsEndOfSupport, Metric,
Classification, License Required, License Model
"""

import io
import re
import unicodedata
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd

from backend.inventory.recognition.lifecycle_service import LifecycleService
from backend.validation.license_validation_layer import LicenseValidationLayer

logger = logging.getLogger(__name__)

STANDARDIZED_COLUMNS: List[str] = [
    "App_ID",
    "Name",
    "OSType",
    "Version",
    "Normalized_Application",
    "Created_At",
    "Operating_System",
    "Major_Version",
    "Minor_Version",
    "Patch_Version",
    "NoLicenseRequired",
    "IsEndOfLife",
    "IsEndOfSupport",
    "Metric",
    "Classification",
    "License Required",
    "License Model",
]

# Standard Commercial License Intelligence output schema (Section 12)
FINAL_OUTPUT_COLUMNS: List[str] = [
    "Application Name",
    "Version",
    "OS",
    "License Required",
    "End of Support",
    "End of Life",
    "Metric",
    "Classification",
    "License Model",
    "Evidence URL",
]

# Numeric OSType codes matching reference SRS database / Excel formatting
OS_TYPE_NUMERIC_MAP: Dict[str, int] = {
    "windows": 0,
    "win": 0,
    "win32": 0,
    "win64": 0,
    "macos": 1,
    "mac": 1,
    "osx": 1,
    "os x": 1,
    "darwin": 1,
    "apple": 1,
    "linux": 2,
    "ubuntu": 2,
    "debian": 2,
    "centos": 2,
    "rhel": 2,
    "redhat": 2,
    "fedora": 2,
    "arch": 2,
    "suse": 2,
    "alpine": 2,
    "unix": 2,
    "solaris": 3,
    "hp-ux": 4,
    "hpux": 4,
    "aix": 5,
    "ios": 8,
    "iphone": 8,
    "ipad": 8,
    "android": 9,
}

# Regex patterns for platform tag detection and removal
PLATFORM_TAG_PATTERNS = [
    re.compile(r"\s*[\(\[](?:mac(?:os)?|os\s*x|darwin|apple)[\.\)\]]*", re.IGNORECASE),
    re.compile(r"\s*[\(\[](?:linux|ubuntu|debian|centos|rhel|redhat|fedora)[\.\)\]]*", re.IGNORECASE),
    re.compile(r"\s*[\(\[](?:windows|win(?:32|64)?)[\.\)\]]*", re.IGNORECASE),
    re.compile(r"\s*[\(\[](?:android|ios|unix)[\.\)\]]*", re.IGNORECASE),
    re.compile(r"\s+for\s+(?:mac(?:os)?|os\s*x|linux|windows|win|android|ios)\b", re.IGNORECASE),
    re.compile(r"\s*-\s*(?:mac(?:os)?|linux|windows|win)\b", re.IGNORECASE),
]

# Regex patterns for architecture tag removal
ARCH_TAG_PATTERNS = [
    re.compile(r"\s*[\(\[](?:64[\-\s]*bit|32[\-\s]*bit|x64|x86|amd64|arm64|ia32|neutral|arm)[\)\]]", re.IGNORECASE),
    re.compile(r"\b(?:64[\-\s]*bit|32[\-\s]*bit|x64|x86|amd64|arm64)\b", re.IGNORECASE),
]

# Regex patterns for installer/runtime noise removal
INSTALLER_TAG_PATTERNS = [
    re.compile(r"\s*[\(\[](?:en-us|en-gb|multilingual|setup|installer|standalone|portable|runtime|reg|exe)[\)\]]", re.IGNORECASE),
    re.compile(r"\s*-\s*(?:setup|installer|standalone|portable)\b", re.IGNORECASE),
    re.compile(r"\s*\((?:reg|exe)\)\s*$", re.IGNORECASE),
]

# Known brand names that naturally contain numbers which must NOT be removed as version numbers
BRAND_PROTECTED_TOKENS = {
    "7-zip", "winrar", "3ds max", "8x8", "c++", "directx", "mp3", "h.264",
    "layer 2", "layer 3", "ipv6", "ipv4", "sha-256", "base64", "visual studio 2022",
    "visual studio 2019", "office 2021", "office 2019", "office 365", "microsoft 365",
}


class StandardizedInventoryExporter:
    """
    Constructs, validates, and serializes standardized 17-column Application Inventory records.
    Implements the 8-layer processing pipeline:
    Raw Application Name -> Normalization -> Version Extraction -> OS Detection ->
    Version Breakdown -> License Classification -> License Model -> Final Result
    """

    @classmethod
    def get_catalog_rule(cls, app_name: str, publisher: Optional[str] = None) -> Optional[Any]:
        """Safely queries CatalogRecognitionEngine for authoritative catalog metadata."""
        if not app_name:
            return None
        try:
            from backend.inventory.recognition.catalog import RecognitionCatalog
            return RecognitionCatalog.find_rule_by_name(app_name, publisher)
        except Exception:
            return None

    @classmethod
    def detect_os_and_type(
        cls,
        raw_name: str,
        install_location: Optional[str] = None,
        device_os: Optional[str] = None,
        provided_ostype: Optional[Union[int, str]] = None,
        provided_os: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[int]]:
        """
        Layer 4: OS Detection.
        Detects specific Operating_System string and consistent numeric OSType code.
        Returns: (Operating_System, OSType_int)
        """
        # 1. If explicit numeric OSType provided, respect it
        if provided_ostype is not None:
            try:
                ost_int = int(provided_ostype)
                op_sys = provided_os
                if not op_sys:
                    if ost_int == 0:
                        op_sys = "Windows"
                    elif ost_int == 1:
                        op_sys = "macOS"
                    elif ost_int == 2:
                        op_sys = "Linux"
                    elif ost_int == 5:
                        op_sys = "AIX"
                    elif ost_int in (8, 9):
                        op_sys = None
                return op_sys, ost_int
            except (ValueError, TypeError):
                pass

        name_clean = raw_name or ""
        low_name = name_clean.lower()
        loc_clean = (install_location or "").lower()

        # 2. Check explicit tags in name or installation location
        if re.search(r"[\(\[\s\-]mac(?:os)?[\)\]\s\.]|\bos\s*x\b|\bdarwin\b|\(mac\.?\)", low_name) or "/applications/" in loc_clean:
            return "macOS", 1

        if re.search(r"[\(\[\s\-]linux[\)\]\s\.]|\(linux\)|\bubuntu\b|\bdebian\b|\brhel\b|\bcentos\b", low_name) or "/usr/bin" in loc_clean or "/opt/" in loc_clean:
            if "ubuntu" in low_name:
                return "Ubuntu Linux", 2
            if "debian" in low_name:
                return "Debian Linux", 2
            if "rhel" in low_name or "redhat" in low_name:
                return "Red Hat Enterprise Linux", 2
            return "Linux", 2

        if re.search(r"[\(\[\s\-]ios[\)\]\s\.]|\(ios\)|\biphone\b|\bipad\b", low_name):
            # In reference SRS dataset, iOS apps have OSType=8 and Operating_System=NULL
            return None, 8

        if re.search(r"[\(\[\s\-]android[\)\]\s\.]|\(android\)|\.apk\b", low_name):
            # In reference SRS dataset, Android apps have OSType=9 and Operating_System=NULL
            return None, 9

        if re.search(r"[\(\[\s\-]windows[\)\]\s\.]|\(win(?:32|64)?\)|\bwin32\b|\bwin64\b", low_name) or "c:\\" in loc_clean or "program files" in loc_clean:
            return "Windows", 0

        if re.search(r"[\(\[\s\-]solaris[\)\]\s\.]", low_name):
            return None, 3

        if re.search(r"[\(\[\s\-]hp-ux[\)\]\s\.]|\bhpux\b", low_name):
            return None, 4

        if re.search(r"[\(\[\s\-]aix[\)\]\s\.]", low_name):
            return "AIX", 5

        if re.search(r"[\(\[\s\-]unix[\)\]\s\.]|\bfreebsd\b|\bopenbsd\b", low_name):
            return "Unix", 2

        # 3. Fall back to provided Operating_System or device context if available
        candidate_os = provided_os or device_os
        if candidate_os and str(candidate_os).strip() and str(candidate_os).strip().lower() not in ("unknown", "none", "n/a", "null", ""):
            clean_dev_os = str(candidate_os).strip()
            dev_low = clean_dev_os.lower()
            for k, code in OS_TYPE_NUMERIC_MAP.items():
                if k in dev_low:
                    if code == 0:
                        return "Windows", 0
                    elif code == 1:
                        return "macOS", 1
                    elif code == 2:
                        return "Linux", 2
                    elif code == 5:
                        return "AIX", 5
                    elif code in (8, 9):
                        return None, code
                    return clean_dev_os, code
            return clean_dev_os, 0

        # Default fallback for Windows scan collector environment
        return "Windows", 0

    @classmethod
    def extract_and_split_version(
        cls,
        raw_name: str,
        provided_version: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[int], Optional[int], Optional[int]]:
        """
        Layer 3 & 5: Version Extraction & Breakdown.
        Extracts clean version string and splits into (Major_Version, Minor_Version, Patch_Version).
        Returns: (version_str, major, minor, patch)
        """
        v_str: Optional[str] = None

        # 1. Prefer provided_version if valid
        if provided_version and str(provided_version).strip():
            candidate = str(provided_version).strip()
            if candidate.lower() not in ("n/a", "unknown", "none", "null", "undefined", ""):
                v_str = candidate

        # 2. If no valid provided version, extract from raw application name
        if not v_str and raw_name:
            # First look for semantic version (e.g. 3.11.4, 24.05, 1.89.1)
            sem_match = re.search(r"\b(\d+(?:\.\d+)+[a-z0-9_\-]*)\b", raw_name, re.IGNORECASE)
            if sem_match:
                v_str = sem_match.group(1)
            else:
                # Look for standalone number between product tokens (e.g. 'Adobe Acrobat 7 Standard', 'Weston 3')
                tokens = raw_name.split()
                for i, token in enumerate(tokens):
                    clean_tok = token.strip("()[].,")
                    if clean_tok.isdigit() and len(clean_tok) <= 4:
                        # Check previous and next tokens to ensure it's not a brand
                        is_brand = False
                        prev_tok = tokens[i - 1].lower() if i > 0 else ""
                        next_tok = tokens[i + 1].lower() if i + 1 < len(tokens) else ""
                        if prev_tok in ("layer", "part", "x") or f"{clean_tok}-{next_tok}" in BRAND_PROTECTED_TOKENS:
                            is_brand = True
                        if not is_brand:
                            v_str = clean_tok
                            break

        if not v_str:
            return None, None, None, None

        # Clean version string
        clean_v = v_str.strip()
        clean_v = re.sub(r"^(?:v|ver|version)[\.\s]*", "", clean_v, flags=re.IGNORECASE)
        # Strip trailing architecture suffixes
        clean_v = re.sub(r"[\s\-_]+(?:64[\-\s]*bit|32[\-\s]*bit|x64|x86|amd64|arm64|ia32)$", "", clean_v, flags=re.IGNORECASE).strip()

        if not clean_v:
            return None, None, None, None

        # Parse major, minor, patch breakdown
        digits = re.findall(r"\d+", clean_v)
        major = int(digits[0]) if len(digits) > 0 else None
        minor = int(digits[1]) if len(digits) > 1 else None
        patch = int(digits[2]) if len(digits) > 2 else None

        return clean_v, major, minor, patch

    @classmethod
    def normalize_application(
        cls,
        raw_name: str,
        extracted_version: Optional[str] = None,
        canonical_hint: Optional[str] = None,
    ) -> str:
        """
        Layer 2: Normalization.
        Canonicalizes application names by removing platform tags, architecture tags,
        installer noise, and redundant version numbers while preserving product identity.
        Examples:
          "Adobe Acrobat 7 Standard (Mac.)" -> "Adobe Acrobat Standard"
          "Weston 3 (Linux)" -> "Weston"
          "TS-LogRhythm Web Console 6" -> "TS LogRhythm Web Console"
          "7-Zip 24.05" -> "7-Zip"
          "Spotlight on Web Servers 3.0 (reg)" -> "Spotlight on Web Servers"
        """
        if not raw_name:
            return ""

        # Strip registry delimiter noise (e.g. "Vendor | Product" -> "Product")
        s = raw_name
        if "|" in s:
            s = s.split("|")[-1].strip()

        # Normalize unicode NFKC
        s = unicodedata.normalize("NFKC", s).strip()

        # 1. Strip platform tags
        for pat in PLATFORM_TAG_PATTERNS:
            s = pat.sub("", s)

        # 2. Strip architecture tags
        for pat in ARCH_TAG_PATTERNS:
            s = pat.sub("", s)

        # 3. Strip installer/package noise
        for pat in INSTALLER_TAG_PATTERNS:
            s = pat.sub("", s)

        # Clean hyphens inside prefix e.g. "TS-LogRhythm" -> "TS LogRhythm" if followed by capital
        s = re.sub(r"\bTS-([A-Z])", r"TS \1", s)

        # 4. Remove duplicate version information from name if extracted
        s_clean = s
        if extracted_version:
            ev_clean = extracted_version.strip()
            # If the exact version string is inside the name, remove it
            esc_v = re.escape(ev_clean)
            s_clean = re.sub(rf"\b{esc_v}\b", "", s_clean, flags=re.IGNORECASE)

            # If version has a major number (e.g. 7 or 3 in 'Adobe Acrobat 7 Standard' or 'Weston 3')
            digits = re.findall(r"\d+", ev_clean)
            if digits:
                major_digit = digits[0]
                # Protect brands like 7-Zip, 3ds Max, etc.
                is_brand_digit = False
                low_s = s_clean.lower()
                for bp in BRAND_PROTECTED_TOKENS:
                    if bp in low_s and major_digit in bp:
                        is_brand_digit = True
                        break

                if not is_brand_digit:
                    # Remove standalone major digit preceded and followed by spaces or start/end
                    s_clean = re.sub(rf"(?<=\s){re.escape(major_digit)}(?=\s|$)", "", s_clean)
                    s_clean = re.sub(rf"^{re.escape(major_digit)}(?=\s)", "", s_clean)
                    s_clean = re.sub(rf"\s+{re.escape(major_digit)}$", "", s_clean)

        # 5. Clean extra whitespace
        normalized = " ".join(s_clean.split()).strip()

        # If normalization removed everything, fallback to raw without brackets
        if not normalized:
            normalized = " ".join(re.sub(r"[\(\[].*?[\)\]]", "", raw_name).split()).strip() or raw_name.strip()

        return normalized

    @classmethod
    def evaluate_classification(
        cls,
        record: Dict[str, Any],
        norm_app: str,
        catalog_rule: Optional[Any] = None,
    ) -> str:
        """
        Layer 6: Classification.
        Allowed values: COMMERCIAL, FREE, FREE_AND_PAID, OPEN_SOURCE, TRIAL, UNKNOWN.
        Do not guess when there is insufficient evidence.
        """
        # 1. Existing record classification
        raw_class = record.get("Classification") or record.get("classification") or record.get("license_type") or ""
        class_clean = str(raw_class).strip().upper()

        if class_clean in ("COMMERCIAL", "PROPRIETARY", "COMMERCIAL_COMPONENT", "PAID"):
            return "COMMERCIAL"
        if class_clean in ("OPEN_SOURCE", "OSS", "GPL", "MIT", "APACHE", "BSD"):
            return "OPEN_SOURCE"
        if class_clean in ("FREE", "FREEWARE", "OS_BUNDLED", "BUNDLED", "SYSTEM"):
            return "FREE"
        if class_clean in ("FREE_AND_PAID", "FREEMIUM", "DUAL_LICENSE"):
            return "FREE_AND_PAID"
        if class_clean in ("TRIAL", "EVALUATION"):
            return "TRIAL"

        # 2. Check catalog rule
        if catalog_rule:
            rule_cls = getattr(catalog_rule, "classification", "")
            rule_cls_clean = str(rule_cls).strip().upper()
            if rule_cls_clean in ("COMMERCIAL", "COMMERCIAL_COMPONENT"):
                return "COMMERCIAL"
            if rule_cls_clean in ("OPEN_SOURCE", "OSS"):
                return "OPEN_SOURCE"
            if rule_cls_clean in ("FREEWARE", "FREE", "OS_BUNDLED"):
                return "FREE"
            if rule_cls_clean in ("FREE_AND_PAID", "FREEMIUM"):
                return "FREE_AND_PAID"
            if rule_cls_clean in ("TRIAL", "EVALUATION"):
                return "TRIAL"

        # 3. Check Windows OS component or hardware driver
        try:
            from backend.inventory.recognition.catalog import RecognitionCatalog
            if RecognitionCatalog.is_windows_os_component(app_name=norm_app) or RecognitionCatalog.is_oem_hardware_component(app_name=norm_app):
                return "FREE"
        except Exception:
            pass

        # 4. Check explicit NoLicenseRequired in record
        nlr = record.get("NoLicenseRequired") or record.get("no_license_required")
        if nlr is not None and str(nlr).strip() in ("1", "True", "true"):
            return "FREE"

        return "UNKNOWN"

    @classmethod
    def evaluate_license_required(
        cls,
        record: Dict[str, Any],
        classification: Optional[str] = None,
        catalog_rule: Optional[Any] = None,
        no_license_required_val: Optional[int] = None,
    ) -> str:
        """
        Layer 7: License Required.
        Strictly returns ONLY 'YES' or 'NO'. Never UNKNOWN, CONTEXT_DEPENDENT, N/A, or blank.
        Customer Business Rule: If an application has ANY applicable commercial/organizational
        usage scenario requiring a paid license, subscription, or commercial plan, the value MUST be YES.
        """
        # 1. Classification & Commercial Entitlement Check:
        c_upper = str(classification or "").strip().upper()
        if c_upper in ("COMMERCIAL", "FREE_AND_PAID", "TRIAL", "PROPRIETARY", "PAID"):
            return "YES"

        # 2. Check record's explicit license_required field
        rec_req = (
            record.get("License Required")
            or record.get("license_required")
            or record.get("license_requirement")
        )
        if rec_req:
            req_str = str(rec_req).strip().upper()
            if req_str in ("YES", "TRUE", "1", "REQUIRED", "COMMERCIAL"):
                return "YES"
            if req_str in ("NO", "FALSE", "0", "NOT_REQUIRED", "FREE"):
                return "NO"

        # 3. Check explicit NoLicenseRequired flag for non-commercial software
        if no_license_required_val == 1:
            return "NO"
        if no_license_required_val == 0:
            return "YES"

        # 4. Check catalog recognition rule
        if catalog_rule:
            rule_req = getattr(catalog_rule, "license_required", None)
            if rule_req is not None:
                val_str = getattr(rule_req, "value", str(rule_req)).strip().upper()
                if val_str in ("YES", "COMMERCIAL", "TRUE", "REQUIRED"):
                    return "YES"
                if val_str in ("NO", "FREE", "FALSE", "NOT_REQUIRED"):
                    return "NO"

        # 5. Non-commercial classifications
        if c_upper in ("FREE", "OPEN_SOURCE", "FREEWARE", "OS_BUNDLED"):
            return "NO"

        # 6. Look for open source or freeware cues in application name
        app_name_lower = str(
            record.get("Name")
            or record.get("raw_name")
            or record.get("Application")
            or ""
        ).lower()
        if any(w in app_name_lower for w in ("open source", "opensource", "freeware", "gpl", "mit license")):
            return "NO"

        # Default for commercial enterprise inventory: commercial license required
        return "YES"

    @classmethod
    def evaluate_license_model(
        cls,
        record: Dict[str, Any],
        classification: str,
        license_required: str,
        catalog_rule: Optional[Any] = None,
        metric: Optional[str] = None,
    ) -> str:
        """
        Layer 7: License Model.
        Controlled vocabulary:
          Per User, Per Device, Per Installation, Subscription,
          Per Core, Per Processor, Concurrent User, Concurrent Device,
          CAL, PVU, Free / Open Source, No License Required, or blank "".
        Never return UNKNOWN. Must logically agree with Metric.
        """
        raw_model = (
            record.get("License Model")
            or record.get("license_model")
            or (getattr(catalog_rule, "licensing_model", None) if catalog_rule else None)
            or ""
        )
        app_name = (
            record.get("Application Name")
            or record.get("Normalized_Application")
            or record.get("Name")
            or record.get("raw_name")
            or record.get("raw_application")
            or ""
        )
        pub = (
            record.get("Vendor")
            or record.get("raw_vendor")
            or record.get("publisher")
            or ""
        )

        # 1. Authoritative catalog entry rule check
        if not catalog_rule and app_name:
            try:
                from backend.inventory.recognition.catalog import RecognitionCatalog
                catalog_rule = RecognitionCatalog.find_rule_by_name(app_name, pub) or RecognitionCatalog.find_rule_by_name(app_name)
            except Exception:
                pass

        if catalog_rule:
            try:
                from backend.inventory.recognition.catalog import RecognitionCatalog
                combined = RecognitionCatalog.derive_combined_license_model(catalog_rule)
                if combined and combined != "Unknown":
                    return combined
            except Exception:
                pass

        # 2. Build combined model using LicenseValidationLayer
        combined = LicenseValidationLayer.build_combined_license_model(
            raw_model=raw_model,
            metric=metric,
            classification=classification,
            app_name=app_name,
        )
        if combined and combined not in ("Unknown", "Free / Open Source"):
            return combined

        app_lower = app_name.lower()
        if "python" in app_lower:
            return "PSF License — Free/Open Source"
        if "mongodb" in app_lower:
            return "SSPL-1.0 — Free to Use"
        if "mysql" in app_lower:
            return "GPL-2.0 — Free/Open Source"
        if any(j in app_lower for j in ("openjdk", "temurin", "corretto", "adoptium", "zulu")):
            return "GPL-2.0 with Classpath Exception — Free/Open Source"
        if "steam" in app_lower:
            return "Freeware"

        if combined and combined != "Unknown":
            return combined

        if license_required == "NO":
            c_upper = str(classification or "").strip().upper()
            if c_upper in ("FREEWARE", "FREE"):
                return "Freeware"
            if c_upper in ("OPEN_SOURCE", "OPEN SOURCE"):
                return "Free / Open Source"
            return "No License Required"

        return ""

    @classmethod
    def evaluate_license_metadata(
        cls,
        record: Dict[str, Any],
        catalog_rule: Optional[Any] = None,
        classification: Optional[str] = None,
        extracted_version: Optional[str] = None,
        norm_app: Optional[str] = None,
        raw_name: Optional[str] = None,
        publisher: Optional[str] = None,
    ) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[str], Optional[str]]:
        """
        Extracts license and support metadata matching reference SRS formatting (0, 1, or None):
        Returns: (NoLicenseRequired, IsEndOfLife, IsEndOfSupport, Metric, Evidence_URL)
        - IsEndOfLife / IsEndOfSupport: 0 (supported), 1 (EOL), or None (unknown)
        - Never defaults to 0 without evidence!
        """
        no_license_required: Optional[int] = None
        is_end_of_life: Optional[int] = None
        is_end_of_support: Optional[int] = None
        metric: Optional[str] = None
        evidence_url: Optional[str] = (
            record.get("Evidence URL")
            or record.get("evidence_url")
            or record.get("source_url")
            or record.get("primary_source_url")
        )

        # 1. NoLicenseRequired evaluation
        nlr_raw = record.get("NoLicenseRequired")
        if nlr_raw is None:
            nlr_raw = record.get("no_license_required")

        if nlr_raw is not None:
            if isinstance(nlr_raw, bool):
                no_license_required = 1 if nlr_raw else 0
            elif str(nlr_raw).strip() in ("1", "True", "true", "yes", "YES"):
                no_license_required = 1
            elif str(nlr_raw).strip() in ("0", "False", "false", "no", "NO"):
                no_license_required = 0
        else:
            req = record.get("license_requirement") or record.get("license_required") or record.get("License Required")
            if req:
                req_str = str(req).strip().upper()
                if req_str in ("NO", "FALSE", "0", "NOT_REQUIRED", "FREE"):
                    no_license_required = 1
                elif req_str in ("YES", "TRUE", "1", "REQUIRED", "COMMERCIAL"):
                    no_license_required = 0
            elif classification:
                c_u = str(classification).upper()
                if c_u in ("OPEN_SOURCE", "FREE", "FREEWARE", "OS_BUNDLED"):
                    no_license_required = 1
                elif c_u in ("COMMERCIAL", "TRIAL", "FREE_AND_PAID", "PROPRIETARY", "PAID"):
                    no_license_required = 0

        # 2. Check explicit IsEndOfLife in record
        eol_raw = record.get("IsEndOfLife") if "IsEndOfLife" in record else record.get("is_end_of_life", record.get("End of Life", record.get("eol")))
        if eol_raw is not None:
            if isinstance(eol_raw, bool):
                is_end_of_life = 1 if eol_raw else 0
            elif str(eol_raw).strip().lower() in ("true", "yes", "1", "eol"):
                is_end_of_life = 1
            elif str(eol_raw).strip().lower() in ("false", "no", "0"):
                is_end_of_life = 0

        # 3. Check explicit IsEndOfSupport in record
        eos_raw = record.get("IsEndOfSupport") if "IsEndOfSupport" in record else record.get("is_end_of_support", record.get("End of Support", record.get("eos")))
        if eos_raw is not None:
            if isinstance(eos_raw, bool):
                is_end_of_support = 1 if eos_raw else 0
            elif str(eos_raw).strip().lower() in ("true", "yes", "1", "eos"):
                is_end_of_support = 1
            elif str(eos_raw).strip().lower() in ("false", "no", "0"):
                is_end_of_support = 0

        # 4. Version-aware lifecycle evaluation via LifecycleService
        life_eol, life_eos, life_url = LifecycleService.evaluate_lifecycle(
            app_name=norm_app or raw_name or "",
            version=extracted_version,
            publisher=publisher,
        )
        if is_end_of_life is None and life_eol is not None:
            is_end_of_life = life_eol
        if is_end_of_support is None and life_eos is not None:
            is_end_of_support = life_eos
        if life_url and not evidence_url:
            evidence_url = life_url

        if is_end_of_life is None or is_end_of_support is None:
            try:
                from backend.inventory.recognition.snow_srs_service import SnowSRSMasterService
                snow_m = SnowSRSMasterService.lookup(raw_name=norm_app or raw_name, vendor=publisher, version=extracted_version)
                if snow_m:
                    if is_end_of_life is None and snow_m.is_end_of_life is not None:
                        is_end_of_life = snow_m.is_end_of_life
                    if is_end_of_support is None and snow_m.is_end_of_support is not None:
                        is_end_of_support = snow_m.is_end_of_support
            except Exception:
                pass

        # 5. Metric evaluation (controlled vocabulary, never inferred from quantity)
        raw_metric = record.get("Metric") or record.get("metric") or record.get("license_metric")
        if raw_metric and str(raw_metric).strip():
            metric = LicenseValidationLayer.normalize_metric(raw_metric)

        if not metric:
            raw_lm = str(record.get("License Model") or record.get("license_model") or "").lower()
            if "core" in raw_lm:
                metric = "Processor Cores"
            elif "device" in raw_lm:
                metric = "Devices"
            elif "user" in raw_lm or "seat" in raw_lm:
                metric = "Users"
            elif "installation" in raw_lm:
                metric = "Installations"
            else:
                # Query Snow SRS Master Service before leaving blank
                from backend.inventory.recognition.snow_srs_service import SnowSRSMasterService
                snow_m = SnowSRSMasterService.lookup(raw_name=raw_name, vendor=publisher, version=extracted_version)
                if snow_m and snow_m.metric and str(snow_m.metric).strip() not in ("", "None", "nan", "NULL", "UNKNOWN"):
                    metric = LicenseValidationLayer.normalize_metric(snow_m.metric)
                elif no_license_required == 1:
                    metric = "No License Required"
            # Do NOT guess metric if unestablished - leave as None/blank

        return no_license_required, is_end_of_life, is_end_of_support, metric, evidence_url

    @classmethod
    def transform_record(
        cls,
        record: Dict[str, Any],
        row_id: int,
        scan_timestamp: Optional[str] = None,
        device_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Layer 8: Final Result generation for a single application record.
        Transforms record through all 8 pipeline layers and validates via LicenseValidationLayer.
        """
        # FAST-PATH & PRESERVATION: If record was already resolved by the intelligence engine,
        # strictly preserve the authoritative backend licensing decision, baseline fields, and metrics.
        if record.get("is_already_resolved") or (record.get("conflict_status") and "License Required" in record):
            app_id_val = record.get("App_ID") or record.get("app_id") or row_id
            raw_name = (
                record.get("raw_application")
                or record.get("Application Name")
                or record.get("Application_Name")
                or record.get("Name")
                or "Unknown"
            ).strip()
            norm_app = record.get("Normalized_Application") or record.get("Application") or raw_name
            prov_version = record.get("Version") or record.get("raw_version") or record.get("version")
            v_str, major, minor, patch = cls.extract_and_split_version(raw_name, prov_version)
            if record.get("Major_Version") is not None and str(record.get("Major_Version")).strip():
                major = record.get("Major_Version")
            if record.get("Minor_Version") is not None and str(record.get("Minor_Version")).strip():
                minor = record.get("Minor_Version")
            if record.get("Patch_Version") is not None and str(record.get("Patch_Version")).strip():
                patch = record.get("Patch_Version")

            op_system = record.get("Operating_System") or (device_context or {}).get("operating_system") or "Windows"
            os_type = record.get("OSType")
            if os_type is None or str(os_type).strip() == "":
                _, os_type = cls.detect_os_and_type(raw_name, device_os=op_system, provided_os=op_system)

            created_at = record.get("Created_At") or scan_timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            classification = record.get("Classification") or ""
            license_required = str(record.get("License Required") or "YES").strip().upper()
            if license_required not in ("YES", "NO"):
                license_required = "YES"

            metric = record.get("Metric") or record.get("metric") or ""
            license_model = record.get("License Model") or record.get("license_model") or ""
            is_eol = record.get("IsEndOfLife") if "IsEndOfLife" in record else record.get("is_end_of_life")
            is_eos = record.get("IsEndOfSupport") if "IsEndOfSupport" in record else record.get("is_end_of_support")

            # Check Snow SRS Master database for authentic baseline lifecycle and metric preservation
            # Skip if record is already resolved and has metric and lifecycle already established
            needs_snow_check = (
                (is_eol is None and is_eos is None)
                or (not metric or metric in ("UNKNOWN", "", None))
            ) and not record.get("is_already_resolved")
            if needs_snow_check:
                try:
                    from backend.inventory.recognition.snow_srs_service import SnowSRSMasterService
                    snow_m = SnowSRSMasterService.lookup(
                        raw_name=raw_name,
                        vendor=record.get("Vendor") or record.get("canonical_vendor") or record.get("raw_vendor"),
                        version=v_str,
                    )
                    if snow_m:
                        if is_eol is None and snow_m.is_end_of_life is not None:
                            is_eol = snow_m.is_end_of_life
                        if is_eos is None and snow_m.is_end_of_support is not None:
                            is_eos = snow_m.is_end_of_support
                        if norm_app in (raw_name, "Unknown", "") and snow_m.normalized_application:
                            norm_app = snow_m.normalized_application
                        if license_required == "YES" and snow_m.metric and str(snow_m.metric).strip() not in ("", "NULL", "nan", "UNKNOWN", "No license required", "No License Required"):
                            metric = snow_m.metric
                            if license_model in ("Commercial — Subscription", "Commercial — Per Seat Subscription"):
                                if metric == "Installations":
                                    license_model = "Commercial — Per Installation"
                                elif metric == "Devices":
                                    license_model = "Commercial — Per Device"
                                elif metric == "Processor Cores":
                                    license_model = "Commercial — Per Core"
                except Exception:
                    pass

            # Fallback lifecycle check if still unpopulated
            if is_eol is None or is_eos is None:
                try:
                    from backend.inventory.recognition.lifecycle_service import LifecycleService
                    l_res = LifecycleService.evaluate_lifecycle(
                        app_name=norm_app or raw_name,
                        version=v_str,
                        publisher=record.get("Vendor") or record.get("canonical_vendor") or record.get("raw_vendor"),
                    )
                    if is_eol is None and l_res.is_eol is not None:
                        is_eol = l_res.is_eol
                    if is_eos is None and l_res.is_eos is not None:
                        is_eos = l_res.is_eos
                except Exception:
                    pass

            # Ensure strict logical consistency between NoLicenseRequired, Metric, and License Required
            if license_required == "YES":
                no_lic_req = 0
                if not metric or metric in ("No license required", "No License Required", "UNKNOWN"):
                    metric = "Users"
            else:
                no_lic_req = 1
                if not metric or metric in ("Installations", "Devices", "Users", "UNKNOWN"):
                    metric = "No license required"

            evidence_url = record.get("Evidence URL") or record.get("evidence_url") or ""

            return {
                "App_ID": app_id_val,
                "Name": raw_name,
                "OSType": os_type,
                "Version": v_str,
                "Normalized_Application": norm_app,
                "Created_At": created_at,
                "Operating_System": op_system,
                "Major_Version": major,
                "Minor_Version": minor,
                "Patch_Version": patch,
                "NoLicenseRequired": no_lic_req,
                "IsEndOfLife": is_eol,
                "IsEndOfSupport": is_eos,
                "Metric": metric,
                "Classification": classification,
                "License Required": license_required,
                "License Model": license_model,
                "Evidence URL": evidence_url,
            }

        # Layer 1: Raw Application Name (Preserve original scanned application name)
        raw_name = (
            record.get("Application Name")
            or record.get("Application_Name")
            or record.get("Name")
            or record.get("raw_name")
            or record.get("raw_application_name")
            or record.get("raw_application")
            or record.get("Application")
            or record.get("application")
            or "Unknown"
        ).strip()

        # Layer 3 & 5: Version Extraction & Breakdown
        prov_version = record.get("Version") or record.get("raw_version") or record.get("version")
        v_str, major, minor, patch = cls.extract_and_split_version(raw_name, prov_version)

        # Layer 2: Normalization
        norm_app = cls.normalize_application(raw_name, extracted_version=v_str)

        # Catalog lookup hook
        publisher = (
            record.get("Vendor")
            or record.get("raw_vendor")
            or record.get("publisher")
            or record.get("Publisher")
        )
        catalog_rule = cls.get_catalog_rule(norm_app or raw_name, publisher=publisher)

        # Layer 4: OS Detection
        dev_os = (device_context or {}).get("operating_system") or record.get("Operating_System") or record.get("operating_system") or record.get("OS")
        install_loc = record.get("install_location") or record.get("Install Location")
        prov_ostype = record.get("OSType") or record.get("ostype")
        op_system, os_type = cls.detect_os_and_type(
            raw_name,
            install_location=install_loc,
            device_os=dev_os,
            provided_ostype=prov_ostype,
            provided_os=record.get("Operating_System") or record.get("OS"),
        )

        # Created_At
        created_at = scan_timestamp or record.get("Created_At") or record.get("created_at")
        if not created_at:
            created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # Layer 6: License Classification
        raw_class = cls.evaluate_classification(record, norm_app=norm_app, catalog_rule=catalog_rule)
        classification = LicenseValidationLayer.normalize_classification(raw_class)

        # License Metadata (NoLicenseRequired, IsEndOfLife, IsEndOfSupport, Metric, Evidence_URL)
        no_lic_req, is_eol, is_eos, metric, evidence_url = cls.evaluate_license_metadata(
            record,
            catalog_rule=catalog_rule,
            classification=classification,
            extracted_version=v_str,
            norm_app=norm_app,
            raw_name=raw_name,
            publisher=publisher,
        )

        # Layer 7: License Required & License Model
        license_required = cls.evaluate_license_required(
            record,
            classification=classification,
            catalog_rule=catalog_rule,
            no_license_required_val=no_lic_req,
        )

        license_model = cls.evaluate_license_model(
            record,
            classification=classification,
            license_required=license_required,
            catalog_rule=catalog_rule,
            metric=metric,
        )

        # Harmonize NoLicenseRequired flag with License Required
        app_id_val = record.get("App_ID")
        if app_id_val is None:
            app_id_val = record.get("app_id", row_id)

        # Harmonize NoLicenseRequired flag with License Required unless flagged as discrepancy
        if record.get("conflict_status") != "DISCREPANCY_FLAGGED":
            if license_required == "NO":
                no_lic_req = 1
            elif license_required == "YES":
                no_lic_req = 0

        initial_transformed = {
            "App_ID": app_id_val,
            "Name": raw_name,
            "OSType": os_type,
            "Version": v_str,
            "Normalized_Application": norm_app,
            "Created_At": created_at,
            "Operating_System": op_system,
            "Major_Version": major,
            "Minor_Version": minor,
            "Patch_Version": patch,
            "NoLicenseRequired": no_lic_req,
            "IsEndOfLife": is_eol,
            "IsEndOfSupport": is_eos,
            "Metric": metric,
            "Classification": classification,
            "License Required": license_required,
            "License Model": license_model,
            "Evidence URL": evidence_url,
        }

        # Run through LicenseValidationLayer for guaranteed consistency
        validated = LicenseValidationLayer.validate_and_sanitize(
            initial_transformed,
            lifecycle_override=(is_eol, is_eos, evidence_url),
        )

        return validated

    @classmethod
    def transform_inventory(
        cls,
        records: List[Union[Dict[str, Any], Any]],
        scan_timestamp: Optional[str] = None,
        device_context: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """
        Transforms an entire inventory list into a validated DataFrame strictly matching the 17-column schema.
        Keeps every application record as a separate row.
        """
        rows: List[Dict[str, Any]] = []
        ts = scan_timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        for idx, item in enumerate(records, start=1):
            if hasattr(item, "__dict__"):
                d = {k: v for k, v in item.__dict__.items() if not k.startswith("_")}
            elif isinstance(item, dict):
                d = dict(item)
            else:
                d = {"Name": str(item)}

            row_transformed = cls.transform_record(
                record=d,
                row_id=idx,
                scan_timestamp=ts,
                device_context=device_context,
            )
            rows.append(row_transformed)

        df = pd.DataFrame(rows, columns=STANDARDIZED_COLUMNS)

        # Ensure integer columns serialize cleanly without float decimals (.0)
        df["App_ID"] = pd.to_numeric(df["App_ID"], errors="coerce").fillna(pd.Series(range(1, len(df) + 1), index=df.index)).astype("int64")
        df["OSType"] = pd.to_numeric(df["OSType"], errors="coerce").astype("Int64")
        for col in ("Major_Version", "Minor_Version", "Patch_Version"):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

        for col in ("NoLicenseRequired", "IsEndOfLife", "IsEndOfSupport"):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

        # In standardized 17-column format, leave unknown Classification & License Model as None / NaN (Section 10)
        for col in ("Classification", "License Model"):
            df[col] = df[col].apply(lambda x: None if pd.isna(x) or str(x).strip().upper() in ("", "NONE", "UNKNOWN", "NULL", "NAN") else x)

        cls.validate_schema(df)
        return df

    @classmethod
    def validate_schema(cls, df: pd.DataFrame):
        """
        Validates that all 17 required columns exist, in exact order, with no extra columns.
        """
        if list(df.columns) != STANDARDIZED_COLUMNS:
            raise ValueError(
                f"Export schema violation!\nExpected columns: {STANDARDIZED_COLUMNS}\nActual columns: {list(df.columns)}"
            )

    @classmethod
    def transform_to_final_schema(
        cls,
        records: List[Union[Dict[str, Any], Any]],
        scan_timestamp: Optional[str] = None,
        device_context: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """
        Transforms records directly into the required 10-column Final Output Schema (Section 12):
        Application Name, Version, OS, License Required, End of Support, End of Life,
        Metric, Classification, License Model, Evidence URL.
        Missing intelligence fields serialize cleanly as blank ("").
        """
        final_rows = []
        ts = scan_timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        for idx, item in enumerate(records, start=1):
            if hasattr(item, "__dict__"):
                d = {k: v for k, v in item.__dict__.items() if not k.startswith("_")}
            elif isinstance(item, dict):
                d = dict(item)
            else:
                d = {"Name": str(item)}

            row_transformed = cls.transform_record(
                record=d,
                row_id=idx,
                scan_timestamp=ts,
                device_context=device_context,
            )

            app_name = str(row_transformed.get("Application Name") or row_transformed.get("Name") or d.get("Application Name") or d.get("Application_Name") or d.get("raw_application") or "").strip()
            ver_val = "" if pd.isna(row_transformed.get("Version")) or str(row_transformed.get("Version")).strip() in ("NULL", "None", "nan") else str(row_transformed.get("Version")).strip()
            os_val = "" if pd.isna(row_transformed.get("Operating_System")) or str(row_transformed.get("Operating_System")).strip() in ("NULL", "None", "nan") else str(row_transformed.get("Operating_System")).strip()
            lic_req = str(row_transformed.get("License Required") or "YES").strip()
            if lic_req not in ("YES", "NO"):
                lic_req = "YES"

            eos_raw = row_transformed.get("IsEndOfSupport")
            eos_val = "" if pd.isna(eos_raw) or str(eos_raw).strip() in ("NULL", "None", "nan", "") else int(eos_raw)

            eol_raw = row_transformed.get("IsEndOfLife")
            eol_val = "" if pd.isna(eol_raw) or str(eol_raw).strip() in ("NULL", "None", "nan", "") else int(eol_raw)

            met_val = "" if pd.isna(row_transformed.get("Metric")) or str(row_transformed.get("Metric")).strip() in ("NULL", "None", "nan", "UNKNOWN") else str(row_transformed.get("Metric")).strip()
            cls_val = "" if pd.isna(row_transformed.get("Classification")) or str(row_transformed.get("Classification")).strip() in ("NULL", "None", "nan", "UNKNOWN") else str(row_transformed.get("Classification")).strip()
            model_val = "" if pd.isna(row_transformed.get("License Model")) or str(row_transformed.get("License Model")).strip() in ("NULL", "None", "nan", "UNKNOWN") else str(row_transformed.get("License Model")).strip()
            if not model_val:
                model_val = "Unknown"
            
            raw_url = row_transformed.get("Evidence URL") or d.get("Evidence URL") or d.get("evidence_url") or d.get("source_url") or d.get("primary_source_url")
            ev_url = "" if pd.isna(raw_url) or str(raw_url).strip() in ("NULL", "None", "nan") else str(raw_url).strip()
            # Double-check evidence URL validity
            sanitized_url = LicenseValidationLayer.validate_evidence_url(ev_url) or ""

            final_rows.append({
                "Application Name": app_name,
                "Version": ver_val,
                "OS": os_val,
                "License Required": lic_req,
                "End of Support": eos_val,
                "End of Life": eol_val,
                "Metric": met_val,
                "Classification": cls_val,
                "License Model": model_val,
                "Evidence URL": sanitized_url,
            })

        return pd.DataFrame(final_rows, columns=FINAL_OUTPUT_COLUMNS)

    @classmethod
    def to_csv_bytes(cls, df: pd.DataFrame, na_rep: str = "NULL") -> bytes:
        """
        Generates clean UTF-8 BOM CSV bytes.
        Defaults na_rep='NULL' for backward compatibility with 17-column reference tests,
        or supports na_rep='' for clean blank representations.
        """
        if list(df.columns) == STANDARDIZED_COLUMNS:
            cls.validate_schema(df)
        out = io.StringIO()
        out.write("\ufeff")  # UTF-8 BOM for Excel
        df.to_csv(out, index=False, na_rep=na_rep)
        return out.getvalue().encode("utf-8")

    @classmethod
    def to_final_csv_bytes(cls, df: pd.DataFrame) -> bytes:
        """
        Generates UTF-8 BOM CSV for the 10-column Final Output Schema with clean blanks for missing values.
        """
        out = io.StringIO()
        out.write("\ufeff")  # UTF-8 BOM for Excel
        df.to_csv(out, index=False, na_rep="")
        return out.getvalue().encode("utf-8")

    @classmethod
    def to_final_excel_bytes(cls, df: pd.DataFrame) -> bytes:
        """
        Generates styled Excel workbook for the 10-column Final Output Schema with clean blanks.
        """
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="License Intelligence", na_rep="")
            ws = writer.sheets["License Intelligence"]

            try:
                from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
                header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
                header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
                header_alignment = Alignment(horizontal="left", vertical="center")
                data_font = Font(name="Segoe UI", size=9)

                thin_border = Border(
                    left=Side(style='thin', color='E0E0E0'),
                    right=Side(style='thin', color='E0E0E0'),
                    top=Side(style='thin', color='E0E0E0'),
                    bottom=Side(style='thin', color='E0E0E0')
                )

                for cell in ws[1]:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = header_alignment

                for col in ws.columns:
                    max_len = max(len(str(cell.value or '')) for cell in col)
                    col_letter = col[0].column_letter
                    ws.column_dimensions[col_letter].width = max(max_len + 3, 14)

                    for cell in col[1:]:
                        cell.font = data_font
                        cell.border = thin_border
            except Exception as e:
                logger.debug(f"Excel styling hook exception: {e}")

        return output.getvalue()

    @classmethod
    def to_excel_bytes(cls, df: pd.DataFrame) -> bytes:
        """
        Generates formatted, Excel-ready .xlsx bytes with styled header row and auto-adjusted columns.
        Missing values serialize as 'NULL'.
        """
        cls.validate_schema(df)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Application Inventory", na_rep="NULL")
            ws = writer.sheets["Application Inventory"]

            # Style header row
            try:
                from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
                header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
                header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
                header_alignment = Alignment(horizontal="left", vertical="center")
                data_font = Font(name="Segoe UI", size=9)
                data_alignment = Alignment(horizontal="left", vertical="center")

                thin_border = Border(
                    left=Side(style='thin', color='E0E0E0'),
                    right=Side(style='thin', color='E0E0E0'),
                    top=Side(style='thin', color='E0E0E0'),
                    bottom=Side(style='thin', color='E0E0E0')
                )

                for cell in ws[1]:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = header_alignment

                # Format data cells and auto-adjust widths
                for col in ws.columns:
                    max_len = max(len(str(cell.value or '')) for cell in col)
                    col_letter = col[0].column_letter
                    ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

                    for cell in col[1:]:
                        cell.font = data_font
                        cell.border = thin_border
            except Exception as e:
                logger.debug(f"Excel styling optional hook error: {e}")

        return output.getvalue()
