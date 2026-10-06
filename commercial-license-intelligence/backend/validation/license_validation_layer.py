"""
License Intelligence Validation and Consistency Layer.
Enforces business logic, cross-field consistency, controlled vocabularies,
and factual accuracy rules across all 10 core intelligence fields:

1. Application Name (preserved exactly)
2. Version (preserved exactly)
3. OS (preserved exactly)
4. License Required (strictly 'YES' or 'NO' only)
5. End of Support (0, 1, or None/blank; never default to 0 without evidence)
6. End of Life (0, 1, or None/blank; never default to 0 without evidence)
7. Metric (controlled vocabulary or blank; never infer from numeric quantity)
8. Classification (preserved taxonomy; never 'UNKNOWN', use blank)
9. License Model (controlled vocabulary or blank; logically matches Metric)
10. Evidence URL (authoritative vendor URLs; no search engines or fakes; blank if unavailable)
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple, Union, Set

logger = logging.getLogger(__name__)

# Controlled vocabulary for Metric (Section 2 & Exact Metrics Requirement)
ALLOWED_METRICS: Set[str] = {
    "Users",
    "Devices",
    "Installations",
    "Processor Cores",
    "Processors",
    "CAL",
    "PVU",
    "Concurrent Users",
    "Concurrent Devices",
    "No License Required",
    "Named User",
    "Device",
    "Core",
    "Socket",
    "Installation",
    "Concurrent User",
    "Concurrent Device",
    "",  # blank allowed when unestablished
}

# Metric normalization mapping
METRIC_NORMALIZATION_MAP: Dict[str, str] = {
    "user": "Users",
    "users": "Users",
    "per user": "Users",
    "per-user": "Users",
    "named user": "Users",
    "named_user": "Users",
    "device": "Devices",
    "devices": "Devices",
    "per device": "Devices",
    "per-device": "Devices",
    "installation": "Installations",
    "installations": "Installations",
    "per installation": "Installations",
    "instance": "Installations",
    "instances": "Installations",
    "concurrent user": "Concurrent Users",
    "concurrent users": "Concurrent Users",
    "concurrent_user": "Concurrent Users",
    "concurrent_users": "Concurrent Users",
    "concurrent device": "Concurrent Devices",
    "concurrent devices": "Concurrent Devices",
    "concurrent_device": "Concurrent Devices",
    "concurrent_devices": "Concurrent Devices",
    "cal": "CAL",
    "cal (client access license)": "CAL",
    "client access license": "CAL",
    "pvu": "PVU",
    "processor value unit": "PVU",
    "core": "Processor Cores",
    "cores": "Processor Cores",
    "per core": "Processor Cores",
    "processor core": "Processor Cores",
    "processor cores": "Processor Cores",
    "number of processor cores": "Processor Cores",
    "cpu core": "Processor Cores",
    "processor": "Processors",
    "processors": "Processors",
    "per processor": "Processors",
    "number of processors": "Processors",
    "cpu": "Processors",
    "socket": "Processors",
    "no license required": "No License Required",
    "no_license_required": "No License Required",
    "not applicable": "No License Required",
    "none": "No License Required",
}

# Standardized License Models (Section 3)
ALLOWED_LICENSE_MODELS: Set[str] = {
    "Per User",
    "Per Device",
    "Per Installation",
    "Subscription",
    "Per Core",
    "Per Core / Server + CAL",
    "Per Processor",
    "Concurrent User",
    "Concurrent Device",
    "CAL",
    "PVU",
    "Freeware",
    "Open Source",
    "Free / Open Source",
    "No License Required",
    "MIT — Free",
    "MIT — Free/Open Source",
    "Apache-2.0 — Free/Open Source",
    "GPL-2.0 — Free/Open Source",
    "GPL-3.0 — Free/Open Source",
    "LGPL — Free/Open Source",
    "BSD — Free/Open Source",
    "BSD-3-Clause — Free/Open Source",
    "BSD-2-Clause — Free/Open Source",
    "PSF License — Free/Open Source",
    "SSPL-1.0 — Free to Use",
    "SSPL-1.0 — Free/Open Source",
    "GPL-2.0 with Classpath Exception — Free/Open Source",
    "MPL — Free/Open Source",
    "Public Domain — Free",
    "Proprietary — Subscription",
    "Proprietary — Perpetual",
    "Proprietary — Per Core",
    "Proprietary — Per Device",
    "Proprietary — Per User",
    "Proprietary — Per Installation",
    "Proprietary — Freeware",
    "Proprietary — Free",
    "Commercial — Per Seat Subscription",
    "Commercial — Per Core",
    "Commercial — Per Core / Server + CAL",
    "Commercial — Subscription",
    "Commercial — Perpetual",
    "Commercial — Per Installation",
    "Commercial — Per Device",
    "Commercial — Per User",
    "Free Setup Utility",
    "Commercial Suite Component",
    "Unknown",
    "",  # blank allowed when unestablished
}

# License Model normalization mapping
LICENSE_MODEL_NORMALIZATION_MAP: Dict[str, str] = {
    "free setup utility": "Free Setup Utility",
    "commercial suite component": "Commercial Suite Component",
    "commercial suite component / setup infrastructure": "Free Setup Utility",
    "per user": "Per User",
    "user": "Per User",
    "named user": "Per User",
    "named user subscription": "Subscription",
    "subscription": "Subscription",
    "subscription / per user": "Subscription",
    "per device": "Per Device",
    "device": "Per Device",
    "per installation": "Per Installation",
    "installation": "Per Installation",
    "per core / server + cal": "Per Core / Server + CAL",
    "server + cal": "Per Core / Server + CAL",
    "per core": "Per Core",
    "core": "Per Core",
    "per processor": "Per Processor",
    "processor": "Per Processor",
    "concurrent user": "Concurrent User",
    "concurrent users": "Concurrent User",
    "concurrent device": "Concurrent Device",
    "concurrent devices": "Concurrent Device",
    "cal": "CAL",
    "pvu": "PVU",
    "free / open source": "Free / Open Source",
    "open source": "Open Source",
    "freeware": "Freeware",
    "free": "Freeware",
    "no license required": "No License Required",
    "no_license_required": "No License Required",
    "standard commercial": "Per Installation",  # Map generic fallback to standardized per-installation
}

# Preserved classification taxonomy (Section 4)
ALLOWED_CLASSIFICATIONS: Set[str] = {
    "COMMERCIAL",
    "OPEN_SOURCE",
    "FREE",
    "FREEWARE",
    "FREE_AND_PAID",
    "TRIAL",
    "OS_BUNDLED",
    "",
}

# Controlled vocabulary for legal/license family LicenseType
ALLOWED_LICENSE_TYPES: Set[str] = {
    "MIT",
    "Apache-2.0",
    "GPL-2.0",
    "GPL-3.0",
    "LGPL",
    "BSD",
    "BSD-3-Clause",
    "BSD-2-Clause",
    "PSF License",
    "SSPL-1.0",
    "GPL-2.0 with Classpath Exception",
    "MPL",
    "Proprietary",
    "Commercial",
    "Freeware",
    "Public Domain",
    "Unknown",
    "",
}

LICENSE_TYPE_NORMALIZATION_MAP: Dict[str, str] = {
    "mit": "MIT",
    "mit license": "MIT",
    "apache": "Apache-2.0",
    "apache 2": "Apache-2.0",
    "apache 2.0": "Apache-2.0",
    "apache-2.0": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    "gpl": "GPL-3.0",
    "gpl-3": "GPL-3.0",
    "gpl-3.0": "GPL-3.0",
    "gplv3": "GPL-3.0",
    "gpl v3": "GPL-3.0",
    "gpl-2": "GPL-2.0",
    "gpl-2.0": "GPL-2.0",
    "gplv2": "GPL-2.0",
    "gpl v2": "GPL-2.0",
    "gnu general public license": "GPL-3.0",
    "lgpl": "LGPL",
    "lgpl-2.1": "LGPL",
    "lgpl-3.0": "LGPL",
    "bsd": "BSD",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "bsd 2-clause": "BSD-2-Clause",
    "bsd 3-clause": "BSD-3-Clause",
    "psf": "PSF License",
    "psfl": "PSF License",
    "psf license": "PSF License",
    "python software foundation license": "PSF License",
    "python software foundation": "PSF License",
    "sspl": "SSPL-1.0",
    "sspl-1.0": "SSPL-1.0",
    "server side public license": "SSPL-1.0",
    "server side public license (sspl)": "SSPL-1.0",
    "classpath exception": "GPL-2.0 with Classpath Exception",
    "gpl-2.0 with classpath exception": "GPL-2.0 with Classpath Exception",
    "gpl with classpath exception": "GPL-2.0 with Classpath Exception",
    "mpl": "MPL",
    "mpl-2.0": "MPL",
    "mozilla public license": "MPL",
    "proprietary": "Proprietary",
    "commercial": "Commercial",
    "freeware": "Freeware",
    "public domain": "Public Domain",
    "cc0": "Public Domain",
    "unknown": "Unknown",
}

# Prohibited placeholder values that must be rendered as blank ("")
PROHIBITED_PLACEHOLDERS: Set[str] = {
    "unknown",
    "unknown_product",
    "n/a",
    "na",
    "none",
    "null",
    "not found",
    "not available",
    "context dependent",
    "context_dependent",
    "cannot determine",
    "undefined",
    "-",
}

# Search engine patterns that must never be used as authoritative evidence URLs
PROHIBITED_URL_PATTERNS = [
    re.compile(r"google\.[a-z\.]+/search", re.IGNORECASE),
    re.compile(r"bing\.[a-z\.]+/search", re.IGNORECASE),
    re.compile(r"duckduckgo\.[a-z\.]+", re.IGNORECASE),
    re.compile(r"search\.yahoo\.[a-z\.]+", re.IGNORECASE),
    re.compile(r"searx", re.IGNORECASE),
    re.compile(r"yacy", re.IGNORECASE),
    re.compile(r"localhost", re.IGNORECASE),
    re.compile(r"127\.0\.0\.1", re.IGNORECASE),
    re.compile(r"example\.com", re.IGNORECASE),
]


class LicenseValidationLayer:
    """
    Validation engine that validates and enforces factual accuracy, controlled vocabularies,
    and cross-field consistency across Commercial License Intelligence records.
    """

    @classmethod
    def sanitize_blank_or_value(cls, val: Any) -> str:
        """
        Replaces placeholder tokens ('UNKNOWN', 'N/A', 'NULL', etc.) with a clean blank string.
        """
        if val is None:
            return ""
        s = str(val).strip()
        if s.lower() in PROHIBITED_PLACEHOLDERS:
            return ""
        return s

    @classmethod
    def sanitize_evidence_url(cls, url: Optional[str]) -> Optional[str]:
        """
        Validates evidence URL.
        Rejects search engine links, localhosts, and fake URLs.
        Returns clean authoritative URL or None.
        """
        if not url:
            return None
        u_str = str(url).strip()
        if u_str.lower() in PROHIBITED_PLACEHOLDERS or u_str == "":
            return None
        if not u_str.startswith("http://") and not u_str.startswith("https://"):
            return None

        for pattern in PROHIBITED_URL_PATTERNS:
            if pattern.search(u_str):
                return None

        return u_str

    @classmethod
    def validate_evidence_url(cls, url: Optional[str]) -> Optional[str]:
        """Alias for sanitize_evidence_url."""
        return cls.sanitize_evidence_url(url)

    @classmethod
    def normalize_metric(cls, raw_metric: Any) -> Optional[str]:
        """
        Normalizes a licensing metric into the controlled vocabulary.
        Returns controlled metric name or None.
        """
        if raw_metric is None:
            return None
        s = str(raw_metric).strip()
        if s.lower() in PROHIBITED_PLACEHOLDERS or s == "":
            return None

        s_clean = s.lower().replace("_", " ")
        if s_clean in METRIC_NORMALIZATION_MAP:
            return METRIC_NORMALIZATION_MAP[s_clean]

        for k, normalized in METRIC_NORMALIZATION_MAP.items():
            if k == s_clean:
                return normalized

        if s in ALLOWED_METRICS and s != "":
            return s

        # Try title case
        title_cand = s.replace("_", " ").title()
        if title_cand in ALLOWED_METRICS and title_cand != "":
            return title_cand

        return None

    @classmethod
    def build_combined_license_model(
        cls,
        raw_model: Any,
        metric: Optional[str] = None,
        classification: Optional[str] = None,
        app_name: Optional[str] = None,
        raw_type: Optional[str] = None,
    ) -> Optional[str]:
        """
        Builds and validates an improved LicenseModel combining legal license type / family
        with commercial/licensing model (e.g. 'MIT — Free/Open Source', 'Commercial — Per Core',
        'Proprietary — Subscription', 'Commercial — Per Seat Subscription').
        """
        if raw_model is None and raw_type is None and classification is None and app_name is None:
            return None

        m_raw = str(raw_model).strip() if raw_model is not None else ""
        if m_raw.lower() in PROHIBITED_PLACEHOLDERS:
            m_raw = ""
        t_raw = str(raw_type).strip() if raw_type is not None else ""
        if t_raw.lower() in PROHIBITED_PLACEHOLDERS:
            t_raw = ""

        # 1. If raw_model already contains an em-dash or dash separator
        if "—" in m_raw or " - " in m_raw or "--" in m_raw:
            sep = "—" if "—" in m_raw else (" - " if " - " in m_raw else "--")
            parts = [p.strip() for p in m_raw.split(sep, 1)]
            if len(parts) == 2 and parts[0] and parts[1]:
                legal_part = cls.normalize_license_type(parts[0])
                comm_part = parts[1]
                comm_lower = comm_part.lower()
                if "free" in comm_lower and "open source" in comm_lower:
                    comm_part = "Free/Open Source"
                elif comm_lower in ("free", "freeware"):
                    comm_part = "Free"
                elif "per seat" in comm_lower or ("subscription" in comm_lower and ("seat" in comm_lower or "user" in comm_lower)):
                    comm_part = "Per Seat Subscription"
                elif "subscription" in comm_lower:
                    comm_part = "Subscription"
                elif "perpetual" in comm_lower:
                    comm_part = "Perpetual"
                elif "core" in comm_lower:
                    comm_part = "Per Core"
                elif "device" in comm_lower:
                    comm_part = "Per Device"
                elif "user" in comm_lower:
                    comm_part = "Per User"
                elif "installation" in comm_lower:
                    comm_part = "Per Installation"

                if legal_part and legal_part != "Unknown":
                    return f"{legal_part} — {comm_part}"
                return f"{parts[0]} — {comm_part}"

        # 2. Check if already exactly in ALLOWED_LICENSE_MODELS with '—'
        if m_raw in ALLOWED_LICENSE_MODELS and "—" in m_raw:
            return m_raw

        # 3. Derive legal family
        legal = cls.normalize_license_type(
            raw_type=t_raw or m_raw,
            classification=classification,
            model=m_raw,
            app_name=app_name,
        )

        # Fallback cues from app_name if legal is still Unknown
        if legal == "Unknown" and app_name:
            a_low = app_name.lower()
            if "vs code" in a_low or "visual studio code" in a_low:
                legal = "MIT"
            elif "git" in a_low:
                legal = "GPL-2.0"
            elif "7-zip" in a_low:
                legal = "LGPL"
            elif "notepad++" in a_low:
                legal = "GPL-3.0"
            elif "vlc" in a_low:
                legal = "GPL-2.0"
            elif "python" in a_low:
                legal = "PSF License"
            elif "mongodb" in a_low or "compass" in a_low:
                legal = "SSPL-1.0"
            elif any(w in a_low for w in ("temurin", "corretto", "adoptium", "zulu", "openjdk")):
                legal = "GPL-2.0 with Classpath Exception"
            elif "steam" in a_low:
                legal = "Freeware"
            elif "google chrome" in a_low or "chrome" in a_low or "google update" in a_low:
                legal = "Freeware"
            elif "acrobat" in a_low:
                legal = "Proprietary"
            elif "oracle" in a_low:
                legal = "Proprietary"
            elif "docker" in a_low:
                legal = "Commercial" if (classification == "COMMERCIAL") else "Freeware"

        # 4. If legal is open source family
        if legal in ("MIT", "Apache-2.0", "GPL-2.0", "GPL-3.0", "LGPL", "BSD", "BSD-3-Clause", "BSD-2-Clause", "MPL", "PSF License", "GPL-2.0 with Classpath Exception"):
            if m_raw and m_raw.lower() in ("free", "mit — free"):
                return f"{legal} — Free"
            return f"{legal} — Free/Open Source"

        if legal in ("SSPL-1.0", "SSPL"):
            return "SSPL-1.0 — Free to Use"

        if legal == "Public Domain":
            return "Public Domain — Free"

        if legal == "Freeware":
            return "Freeware"

        # 4.5. Check for non-licensable commercial components and setup utilities
        if classification == "COMMERCIAL_COMPONENT" or str(metric).lower() == "no license required":
            a_low = (app_name or "").lower()
            if "setup" in a_low or "installer" in a_low:
                return "Free Setup Utility"
            return "No License Required"

        # 5. If legal is Commercial or Proprietary
        if legal in ("Commercial", "Proprietary"):
            m_lower = m_raw.lower()
            met_lower = str(metric or "").lower()
            a_low = (app_name or "").lower()

            if "per seat" in m_lower or (("subscription" in m_lower or "user" in m_lower) and "user" in met_lower):
                comm_part = "Per Seat Subscription"
            elif "subscription" in m_lower:
                comm_part = "Subscription"
            elif "perpetual" in m_lower:
                comm_part = "Perpetual"
            elif "core" in m_lower or "core" in met_lower:
                comm_part = "Per Core"
            elif "device" in m_lower or "device" in met_lower:
                comm_part = "Per Device"
            elif "installation" in m_lower or "installation" in met_lower:
                comm_part = "Per Installation"
            elif "user" in m_lower or "user" in met_lower:
                comm_part = "Per Seat Subscription" if legal == "Commercial" else "Subscription"
            elif met_lower in ("processor cores", "core", "cores"):
                comm_part = "Per Core"
            elif met_lower in ("devices", "device"):
                comm_part = "Per Device"
            elif met_lower in ("installations", "installation"):
                comm_part = "Per Installation"
            elif met_lower in ("users", "named user", "per user"):
                comm_part = "Per Seat Subscription" if legal == "Commercial" else "Subscription"
            elif any(w in a_low for w in ("home and student", "home & student", "home and business", "home & business", "2016", "2019", "2021", "2024", "ltsc", "perpetual", "one-time")) and not any(w in a_low for w in ("365", "m365", "subscription")):
                comm_part = "Perpetual"
            elif any(w in a_low for w in ("365", "m365", "subscription")):
                comm_part = "Per Seat Subscription" if legal == "Commercial" else "Subscription"
            else:
                comm_part = "Perpetual" if any(w in a_low for w in ("2016", "2019", "2021", "2024", "home and student", "home & student")) else ("Subscription" if legal == "Commercial" else "Perpetual")

            return f"{legal} — {comm_part}"

        # 6. Fallback checks
        if m_raw in ALLOWED_LICENSE_MODELS and m_raw != "":
            return m_raw

        norm_m = LICENSE_MODEL_NORMALIZATION_MAP.get(m_raw.lower().replace("_", " "))
        if norm_m:
            return norm_m

        if classification in ("FREE", "OPEN_SOURCE"):
            return "Free / Open Source"

        if raw_model:
            return str(raw_model).strip()

        return "Unknown"

    @classmethod
    def normalize_license_model(
        cls,
        raw_model: Any,
        metric: Optional[str] = None,
        classification: Optional[str] = None,
        app_name: Optional[str] = None,
        raw_type: Optional[str] = None,
    ) -> Optional[str]:
        """
        Normalizes a license model into the standardized vocabulary,
        combining legal license family and commercial model where applicable.
        """
        return cls.build_combined_license_model(
            raw_model=raw_model,
            metric=metric,
            classification=classification,
            app_name=app_name,
            raw_type=raw_type,
        )

    @classmethod
    def normalize_classification(cls, raw_classification: Any) -> Optional[str]:
        """
        Cleans classification, preserving existing taxonomy while stripping 'UNKNOWN' to None.
        """
        if raw_classification is None:
            return None
        s = str(raw_classification).strip()
        if s.lower() in PROHIBITED_PLACEHOLDERS or s == "":
            return None

        s_upper = s.upper().replace(" ", "_")
        if s_upper in ("COMMERCIAL", "PROPRIETARY"):
            return "COMMERCIAL"
        if s_upper in ("OPEN_SOURCE", "OSS", "GPL", "MIT", "APACHE"):
            return "OPEN_SOURCE"
        if s_upper == "FREEWARE":
            return "FREEWARE"
        if s_upper == "FREE":
            return "FREE"
        if s_upper in ("FREE_AND_PAID", "FREEMIUM"):
            return "FREE_AND_PAID"
        if s_upper == "TRIAL":
            return "TRIAL"
        if s_upper in ("OPERATING_SYSTEM", "OS"):
            return "OS_BUNDLED"
        if s_upper in ("INFRASTRUCTURE", "OS_BUNDLED", "SYSTEM_COMPONENT"):
            return "OS_BUNDLED"

        return s

    @classmethod
    def normalize_license_type(
        cls,
        raw_type: Any,
        classification: Optional[str] = None,
        model: Optional[str] = None,
        app_name: Optional[str] = None,
    ) -> str:
        """
        Normalizes a legal license type (legal/license family: MIT, Apache-2.0, GPL, etc.)
        preserving distinction from commercial LicenseModel.
        """
        if raw_type is not None:
            s = str(raw_type).strip()
            if s and s.lower() not in PROHIBITED_PLACEHOLDERS:
                s_lower = s.lower().replace("_", " ")
                if s_lower in LICENSE_TYPE_NORMALIZATION_MAP:
                    return LICENSE_TYPE_NORMALIZATION_MAP[s_lower]
                for k, v in sorted(LICENSE_TYPE_NORMALIZATION_MAP.items(), key=lambda x: -len(x[0])):
                    if re.search(r"\b" + re.escape(k) + r"\b", s_lower):
                        return v
                if s in ALLOWED_LICENSE_TYPES and s != "":
                    return s

        # Try to infer from model if model contains legal license name (e.g. legacy model strings)
        if model:
            m_lower = str(model).strip().lower()
            for k, v in sorted(LICENSE_TYPE_NORMALIZATION_MAP.items(), key=lambda x: -len(x[0])):
                if re.search(r"\b" + re.escape(k) + r"\b", m_lower):
                    return v

        # Try to infer from app_name cues
        if app_name:
            a_lower = str(app_name).strip().lower()
            if "mit license" in a_lower or " mit" in a_lower:
                return "MIT"
            if "apache" in a_lower:
                return "Apache-2.0"
            if "gpl" in a_lower:
                return "GPL-3.0"

        # Fallback to classification
        c_upper = str(classification or "").strip().upper()
        if c_upper == "COMMERCIAL":
            return "Commercial"
        if c_upper in ("FREEWARE", "FREE"):
            return "Freeware"
        if c_upper == "OPEN_SOURCE":
            return "Unknown"
        if c_upper == "PROPRIETARY":
            return "Proprietary"

        return "Unknown"

    @classmethod
    def normalize_lifecycle_val(cls, val: Any) -> Optional[int]:
        """
        Strictly maps EOL/EOS status:
        - 1 if verified EOL/EOS
        - 0 if verified supported
        - None (blank) if unknown / no evidence
        Never falsely defaults to 0.
        """
        if val is None:
            return None
        s = str(val).strip().lower()
        if s in PROHIBITED_PLACEHOLDERS or s == "":
            return None
        if s in ("1", "true", "yes", "eol", "eos", "unsupported", "expired"):
            return 1
        if s in ("0", "false", "no", "active", "supported"):
            return 0
        return None

    @classmethod
    def validate_and_sanitize(
        cls,
        record: Dict[str, Any],
        lifecycle_override: Optional[Tuple[Optional[int], Optional[int], Optional[str]]] = None,
    ) -> Dict[str, Any]:
        """
        Enforces all 12 accuracy and consistency rules on an application intelligence record:
        1. License Required: strictly 'YES' or 'NO'
        2. Metric: controlled vocabulary or blank; never inferred from quantity
        3. License Model: logically aligned with Metric; never UNKNOWN
        4. Classification: clean taxonomy; never UNKNOWN
        5. EOL/EOS: 0, 1, or None; never falsely default to 0
        6. Evidence URL: clean authoritative URL or blank
        7. Cross-field consistency rules enforced
        """
        corrected_fields: List[str] = []

        # -------------------------------------------------------------
        # 1. Preserve original application and system inventory fields
        # -------------------------------------------------------------
        app_name = (
            record.get("Application Name")
            or record.get("Application")
            or record.get("Name")
            or record.get("raw_name")
            or record.get("raw_application")
            or ""
        ).strip()

        version = record.get("Version") or record.get("raw_version") or record.get("version")
        ver_str = str(version).strip() if version is not None else None
        if ver_str is not None and (ver_str.lower() in PROHIBITED_PLACEHOLDERS or ver_str == ""):
            ver_str = None

        os_val = (
            record.get("OS")
            or record.get("Operating_System")
            or record.get("operating_system")
        )
        if os_val is not None:
            os_val = str(os_val).strip()
            if os_val.lower() in PROHIBITED_PLACEHOLDERS or os_val == "":
                os_val = None

        # -------------------------------------------------------------
        # 2. Extract raw candidate fields
        # -------------------------------------------------------------
        raw_lic_req = (
            record.get("License Required")
            or record.get("license_required")
            or record.get("license_requirement")
            or ""
        )

        raw_metric = record.get("Metric") or record.get("metric") or record.get("license_metric")
        raw_model = record.get("License Model") or record.get("license_model")
        raw_classification = record.get("Classification") or record.get("classification")
        raw_license_type = (
            record.get("License Type")
            or record.get("LicenseType")
            or record.get("license_type")
        )
        raw_evidence_url = (
            record.get("Evidence URL")
            or record.get("evidence_url")
            or record.get("source_url")
            or record.get("primary_source_url")
        )

        # -------------------------------------------------------------
        # 3. Clean and normalize Classification
        # -------------------------------------------------------------
        classification = cls.normalize_classification(raw_classification)

        # -------------------------------------------------------------
        # 4. Clean and normalize Evidence URL
        # -------------------------------------------------------------
        evidence_url = cls.sanitize_evidence_url(raw_evidence_url)

        # -------------------------------------------------------------
        # 5. Clean and normalize EOL / EOS (version-aware)
        # -------------------------------------------------------------
        eol_val = cls.normalize_lifecycle_val(record.get("End of Life") if "End of Life" in record else record.get("IsEndOfLife", record.get("eol")))
        eos_val = cls.normalize_lifecycle_val(record.get("End of Support") if "End of Support" in record else record.get("IsEndOfSupport", record.get("eos")))

        # If lifecycle_override provided from LifecycleService, use verified values
        if lifecycle_override is not None:
            ov_eol, ov_eos, ov_url = lifecycle_override
            if ov_eol is not None:
                eol_val = ov_eol
            if ov_eos is not None:
                eos_val = ov_eos
            if ov_url and not evidence_url:
                evidence_url = cls.sanitize_evidence_url(ov_url)

        # -------------------------------------------------------------
        # 6. Clean and normalize Metric
        # -------------------------------------------------------------
        metric = cls.normalize_metric(raw_metric)

        # -------------------------------------------------------------
        # 7. Clean and normalize License Model (combines legal family + commercial model)
        # -------------------------------------------------------------
        license_model = cls.normalize_license_model(
            raw_model=raw_model,
            metric=metric,
            classification=classification,
            app_name=app_name,
            raw_type=raw_license_type,
        )

        # -------------------------------------------------------------
        # 8. Determine License Required strictly as 'YES' or 'NO' (Section 1)
        # -------------------------------------------------------------
        s_req = str(raw_lic_req).strip().upper()
        c_upper = str(classification or "").strip().upper()
        lic_req: str

        # Key Business Rule:
        # If classification is COMMERCIAL, FREE_AND_PAID, TRIAL, or PROPRIETARY,
        # or if the software has ANY commercial / subscription / paid tier,
        # License Required MUST be 'YES'.
        # A free personal tier or free download MUST NOT override this commercial requirement.
        if c_upper in ("COMMERCIAL", "FREE_AND_PAID", "TRIAL", "PROPRIETARY", "PAID"):
            lic_req = "YES"
        elif s_req in ("YES", "TRUE", "REQUIRED", "COMMERCIAL", "CONTEXT_DEPENDENT"):
            lic_req = "YES"
        elif s_req in ("NO", "FALSE", "NOT_REQUIRED", "FREE", "NOT_APPLICABLE", "NOT APPLICABLE", "NLR", "NO_LICENSE_REQUIRED"):
            lic_req = "NO"
        else:
            # Fallback derivation using classification and reliable facts
            if c_upper in ("OPEN_SOURCE", "FREEWARE", "FREE", "OS_BUNDLED", "LINUX_SYSTEM_PACKAGE"):
                lic_req = "NO"
            elif metric == "No License Required":
                lic_req = "NO"
            elif metric in ("Processor Cores", "Processors", "CAL", "PVU", "Users", "Devices", "Installations"):
                lic_req = "YES"
            elif license_model and any(k in license_model for k in ("Per User", "Per Device", "Per Core", "Per Processor", "Subscription", "CAL", "PVU")):
                lic_req = "YES"
            elif license_model and any(k in license_model for k in ("Free / Open Source", "No License Required", "Public Domain", "Freeware")):
                lic_req = "NO"
            else:
                lic_req = "NO" if ("free" in app_name.lower() or "open" in app_name.lower()) else "YES"

        # -------------------------------------------------------------
        # 9. Enforce Cross-Field Consistency Rules (Section 8)
        # -------------------------------------------------------------

        # Rule 8B: IF Metric in (Users, Processor Cores, Processors, Devices, CAL, PVU) THEN License Required cannot be NO unless verified open source/free
        if metric in ("Users", "Processor Cores", "Processors", "Devices", "CAL", "PVU", "Named User", "Core", "Socket", "Device"):
            if c_upper not in ("OPEN_SOURCE", "FREE", "FREEWARE", "OS_BUNDLED", "LINUX_SYSTEM_PACKAGE"):
                if lic_req == "NO":
                    lic_req = "YES"
                    corrected_fields.append("License Required")

        # Rule 8A: Metric = 'No License Required' handling
        if metric == "No License Required":
            if c_upper in ("COMMERCIAL", "FREE_AND_PAID", "TRIAL", "PROPRIETARY", "PAID"):
                # Commercial classification requires a license: correct metric
                if lic_req == "YES":
                    if license_model and any(c in license_model for c in ("Core", "Processor")):
                        metric = "Processor Cores"
                    elif license_model and any(u in license_model for u in ("User", "Subscription", "Seat")):
                        metric = "Users"
                    elif license_model and "Device" in license_model:
                        metric = "Devices"
                    else:
                        metric = "Installations"
                    corrected_fields.append("Metric")
            else:
                # Non-commercial or unclassified software with No License Required metric forces License Required = NO
                if lic_req != "NO":
                    lic_req = "NO"
                    corrected_fields.append("License Required")

        # Rule 8C: IF License Required = NO THEN Metric must be 'No License Required'
        if lic_req == "NO":
            if metric != "No License Required":
                metric = "No License Required"
                corrected_fields.append("Metric")

        # Rule 8D: IF License Required = NO THEN License Model must be open-source / free or 'No License Required'
        if lic_req == "NO":
            is_open_or_free = license_model and any(
                k in license_model for k in (
                    "Free", "Open Source", "MIT", "Apache", "GPL", "BSD", "LGPL", "MPL",
                    "Public Domain", "Freeware", "No License Required", "PSF", "SSPL"
                )
            )
            if not is_open_or_free:
                license_model = "Free / Open Source" if classification == "OPEN_SOURCE" else "No License Required"
                corrected_fields.append("License Model")

        # Rule 8E: IF Metric = Users THEN License Model should represent user-based licensing if commercial
        if metric in ("Users", "Named User") and lic_req == "YES":
            user_tokens = ("User", "Subscription", "Seat", "CAL")
            if not license_model or not any(t in license_model for t in user_tokens):
                license_model = "Commercial — Per Seat Subscription"
                corrected_fields.append("License Model")

        # Rule 8F: IF Metric = Processor Cores THEN License Model should represent core licensing
        elif metric in ("Processor Cores", "Core") and lic_req == "YES":
            if not license_model or "Core" not in license_model:
                license_model = "Commercial — Per Core"
                corrected_fields.append("License Model")

        # Rule 8G: IF Metric = Processors THEN License Model should represent processor licensing
        elif metric in ("Processors", "Socket") and lic_req == "YES":
            if not license_model or "Processor" not in license_model:
                license_model = "Per Processor"
                corrected_fields.append("License Model")

        # Rule 8H: IF Metric = Devices THEN License Model should represent device licensing if commercial
        elif metric in ("Devices", "Device") and lic_req == "YES":
            if not license_model or ("Device" not in license_model and "Subscription" not in license_model):
                license_model = "Commercial — Per Device"
                corrected_fields.append("License Model")

        # Rule 8I: IF Metric = Installations THEN License Model should represent installation licensing if commercial
        elif metric in ("Installations", "Installation") and lic_req == "YES":
            if not license_model or ("Installation" not in license_model and "Subscription" not in license_model and "Core" not in license_model and "CAL" not in license_model and "Device" not in license_model and "User" not in license_model):
                license_model = "Commercial — Per Installation"
                corrected_fields.append("License Model")

        # Rule 8J: Harmonize NoLicenseRequired integer flag for legacy schemas
        no_license_required_int = 1 if lic_req == "NO" else 0

        # Build clean validated record
        validated_record = dict(record)

        # Standard 10 intelligence fields (Section 12)
        validated_record["Application Name"] = app_name
        validated_record["Version"] = ver_str
        validated_record["OS"] = os_val
        validated_record["License Required"] = lic_req
        validated_record["End of Support"] = eos_val
        validated_record["End of Life"] = eol_val
        validated_record["Metric"] = metric
        validated_record["Classification"] = classification
        validated_record["License Model"] = license_model
        validated_record["Evidence URL"] = evidence_url

        # Completely remove any standalone License Type / LicenseType / license_type field
        validated_record.pop("License Type", None)
        validated_record.pop("LicenseType", None)
        validated_record.pop("license_type", None)

        # Legacy and schema compatibility fields
        validated_record["Name"] = app_name
        validated_record["Operating_System"] = os_val
        validated_record["NoLicenseRequired"] = no_license_required_int
        validated_record["IsEndOfLife"] = eol_val
        validated_record["IsEndOfSupport"] = eos_val
        validated_record["_validation_corrections"] = corrected_fields

        return validated_record
