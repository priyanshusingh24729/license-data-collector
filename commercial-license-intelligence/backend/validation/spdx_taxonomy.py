"""
SPDX License Taxonomy Service.
Standardizes and maps software licenses to Linux Foundation SPDX 3.0 canonical identifiers.
Categorizes licenses into Permissive, Copyleft, Source-Available, and Commercial/Proprietary.
"""

import re
from dataclasses import dataclass
from typing import Optional, Dict, Tuple, List


@dataclass
class SPDXInfo:
    spdx_id: str
    license_name: str
    category: str  # PERMISSIVE, WEAK_COPYLEFT, STRONG_COPYLEFT, SOURCE_AVAILABLE, PROPRIETARY, UNKNOWN
    is_open_source: bool
    is_source_available: bool
    is_commercial_proprietary: bool
    default_classification: str


class SPDXTaxonomyService:
    """
    Normalizes arbitrary license text strings to official SPDX identifiers and classifications.
    """

    # Primary SPDX mapping table
    SPDX_MAP: Dict[str, SPDXInfo] = {
        "mit": SPDXInfo("MIT", "MIT License", "PERMISSIVE", True, False, False, "OPEN_SOURCE"),
        "apache-2.0": SPDXInfo("Apache-2.0", "Apache License 2.0", "PERMISSIVE", True, False, False, "OPEN_SOURCE"),
        "apache 2.0": SPDXInfo("Apache-2.0", "Apache License 2.0", "PERMISSIVE", True, False, False, "OPEN_SOURCE"),
        "apache": SPDXInfo("Apache-2.0", "Apache License 2.0", "PERMISSIVE", True, False, False, "OPEN_SOURCE"),
        "bsd-3-clause": SPDXInfo("BSD-3-Clause", "BSD 3-Clause 'New' or 'Revised' License", "PERMISSIVE", True, False, False, "OPEN_SOURCE"),
        "bsd 3-clause": SPDXInfo("BSD-3-Clause", "BSD 3-Clause License", "PERMISSIVE", True, False, False, "OPEN_SOURCE"),
        "bsd-2-clause": SPDXInfo("BSD-2-Clause", "BSD 2-Clause 'Simplified' License", "PERMISSIVE", True, False, False, "OPEN_SOURCE"),
        "bsd": SPDXInfo("BSD-3-Clause", "BSD License", "PERMISSIVE", True, False, False, "OPEN_SOURCE"),
        "isc": SPDXInfo("ISC", "ISC License", "PERMISSIVE", True, False, False, "OPEN_SOURCE"),
        "postgresql": SPDXInfo("PostgreSQL", "PostgreSQL License", "PERMISSIVE", True, False, False, "OPEN_SOURCE"),
        "psf-2.0": SPDXInfo("PSF-2.0", "Python Software Foundation License 2.0", "PERMISSIVE", True, False, False, "OPEN_SOURCE"),
        "python": SPDXInfo("PSF-2.0", "Python Software Foundation License 2.0", "PERMISSIVE", True, False, False, "OPEN_SOURCE"),
        "unlicense": SPDXInfo("Unlicense", "The Unlicense", "PERMISSIVE", True, False, False, "OPEN_SOURCE"),
        "cc0-1.0": SPDXInfo("CC0-1.0", "Creative Commons Zero v1.0 Universal", "PERMISSIVE", True, False, False, "OPEN_SOURCE"),
        
        # Weak Copyleft
        "lgpl-2.1": SPDXInfo("LGPL-2.1-only", "GNU Lesser General Public License v2.1", "WEAK_COPYLEFT", True, False, False, "OPEN_SOURCE"),
        "lgpl-3.0": SPDXInfo("LGPL-3.0-only", "GNU Lesser General Public License v3.0", "WEAK_COPYLEFT", True, False, False, "OPEN_SOURCE"),
        "lgpl": SPDXInfo("LGPL-3.0-only", "GNU Lesser General Public License", "WEAK_COPYLEFT", True, False, False, "OPEN_SOURCE"),
        "mpl-2.0": SPDXInfo("MPL-2.0", "Mozilla Public License 2.0", "WEAK_COPYLEFT", True, False, False, "OPEN_SOURCE"),
        "epl-2.0": SPDXInfo("EPL-2.0", "Eclipse Public License 2.0", "WEAK_COPYLEFT", True, False, False, "OPEN_SOURCE"),
        
        # Strong Copyleft
        "gpl-2.0": SPDXInfo("GPL-2.0-only", "GNU General Public License v2.0", "STRONG_COPYLEFT", True, False, False, "OPEN_SOURCE"),
        "gpl-3.0": SPDXInfo("GPL-3.0-only", "GNU General Public License v3.0", "STRONG_COPYLEFT", True, False, False, "OPEN_SOURCE"),
        "gpl": SPDXInfo("GPL-3.0-only", "GNU General Public License", "STRONG_COPYLEFT", True, False, False, "OPEN_SOURCE"),
        "agpl-3.0": SPDXInfo("AGPL-3.0-only", "GNU Affero General Public License v3.0", "STRONG_COPYLEFT", True, False, False, "OPEN_SOURCE"),
        "agpl": SPDXInfo("AGPL-3.0-only", "GNU Affero General Public License v3.0", "STRONG_COPYLEFT", True, False, False, "OPEN_SOURCE"),

        # Source-Available / Non-OSI
        "sspl-1.0": SPDXInfo("SSPL-1.0", "Server Side Public License v1", "SOURCE_AVAILABLE", False, True, False, "OPEN_SOURCE"),
        "sspl": SPDXInfo("SSPL-1.0", "Server Side Public License v1", "SOURCE_AVAILABLE", False, True, False, "OPEN_SOURCE"),
        "server side public license": SPDXInfo("SSPL-1.0", "Server Side Public License v1", "SOURCE_AVAILABLE", False, True, False, "OPEN_SOURCE"),
        "bsl-1.1": SPDXInfo("BSL-1.1", "Business Source License 1.1", "SOURCE_AVAILABLE", False, True, False, "COMMERCIAL"),
        "bsl": SPDXInfo("BSL-1.1", "Business Source License 1.1", "SOURCE_AVAILABLE", False, True, False, "COMMERCIAL"),
        "business source license": SPDXInfo("BSL-1.1", "Business Source License 1.1", "SOURCE_AVAILABLE", False, True, False, "COMMERCIAL"),
        "elastic-2.0": SPDXInfo("Elastic-2.0", "Elastic License 2.0", "SOURCE_AVAILABLE", False, True, False, "OPEN_SOURCE"),

        # Proprietary / Commercial
        "proprietary": SPDXInfo("Proprietary", "Proprietary Commercial License", "PROPRIETARY", False, False, True, "COMMERCIAL"),
        "commercial": SPDXInfo("Proprietary", "Commercial License", "PROPRIETARY", False, False, True, "COMMERCIAL"),
        "freeware": SPDXInfo("Proprietary", "Freeware / No-Fee Proprietary", "PROPRIETARY", False, False, True, "FREEWARE"),
    }

    @classmethod
    def normalize_spdx(cls, raw_license: Optional[str]) -> str:
        """
        Normalizes any arbitrary license string or expression into an official SPDX identifier.
        Defaults to 'UNKNOWN' if no valid license identifier matches.
        """
        if not raw_license or str(raw_license).strip().upper() in ("", "NONE", "UNKNOWN", "NULL", "N/A"):
            return "UNKNOWN"

        clean = str(raw_license).strip().lower()

        # Direct map hit
        if clean in cls.SPDX_MAP:
            return cls.SPDX_MAP[clean].spdx_id

        # Regex heuristic matches
        if re.search(r"\bmit\b", clean):
            return "MIT"
        if re.search(r"\bapache\b", clean):
            return "Apache-2.0"
        if re.search(r"\bagpl\s*v?3(?:\.0)?\b|\bagpl\b", clean):
            return "AGPL-3.0-only"
        if re.search(r"\blgpl\s*v?3(?:\.0)?\b", clean):
            return "LGPL-3.0-only"
        if re.search(r"\blgpl\s*v?2(?:\.1)?\b", clean):
            return "LGPL-2.1-only"
        if re.search(r"\blgpl\b", clean):
            return "LGPL-3.0-only"
        if re.search(r"\bgpl\s*v?3(?:\.0)?\b", clean):
            return "GPL-3.0-only"
        if re.search(r"\bgpl\s*v?2(?:\.0)?\b", clean):
            return "GPL-2.0-only"
        if re.search(r"\bgpl\b", clean):
            return "GPL-3.0-only"
        if re.search(r"\bbsd\s*3(?:\-clause)?\b", clean):
            return "BSD-3-Clause"
        if re.search(r"\bbsd\s*2(?:\-clause)?\b", clean):
            return "BSD-2-Clause"
        if re.search(r"\bbsd\b", clean):
            return "BSD-3-Clause"
        if re.search(r"\bmpl(?:\s*2(?:\.0)?)?\b", clean):
            return "MPL-2.0"
        if re.search(r"\bsspl\b|\bserver\s+side\s+public\s+license\b", clean):
            return "SSPL-1.0"
        if re.search(r"\bbsl(?:\s*1(?:\.1)?)?\b|\bbusiness\s+source\s+license\b", clean):
            return "BSL-1.1"
        if re.search(r"\bpostgres\b", clean):
            return "PostgreSQL"
        if re.search(r"\bpython\b|\bpsf\b", clean):
            return "PSF-2.0"
        if re.search(r"\bisc\b", clean):
            return "ISC"
        if re.search(r"\bunlicense\b", clean):
            return "Unlicense"
        if re.search(r"\bproprietary\b|\bcommercial\b|\beula\b|\bpaid\b|\bsubscription\b", clean):
            return "Proprietary"

        return "UNKNOWN"

    @classmethod
    def is_valid_spdx_id(cls, identifier: Optional[str]) -> bool:
        """
        Returns True ONLY if the identifier is a recognized canonical SPDX license ID.
        'Proprietary', 'Commercial', and 'UNKNOWN' are NOT valid SPDX identifiers.
        """
        if not identifier:
            return False
        clean = str(identifier).strip()
        if clean.upper() in ("UNKNOWN", "PROPRIETARY", "COMMERCIAL", "FREEWARE", "NONE", "N/A", ""):
            return False
        # Valid SPDX list items supported in this engine
        valid_spdx = {
            "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "PostgreSQL",
            "PSF-2.0", "Unlicense", "CC0-1.0", "LGPL-2.1-only", "LGPL-3.0-only",
            "MPL-2.0", "EPL-2.0", "GPL-2.0-only", "GPL-3.0-only", "AGPL-3.0-only",
            "SSPL-1.0", "BSL-1.1", "Elastic-2.0"
        }
        return clean in valid_spdx or clean.startswith("LicenseRef-")

    @classmethod
    def get_valid_spdx_id(cls, raw_license: Optional[str]) -> Optional[str]:
        """
        Extracts a valid canonical SPDX identifier if present.
        Returns None for proprietary, commercial, or unmapped licenses.
        Prevents corrupting the SPDX schema with 'Proprietary'.
        """
        norm = cls.normalize_spdx(raw_license)
        if cls.is_valid_spdx_id(norm):
            return norm
        return None

    @classmethod
    def get_license_type(cls, raw_license: Optional[str], classification: Optional[str] = None) -> str:
        """
        Determines the appropriate human-readable License Type (legal family),
        e.g. 'Proprietary', 'Open Source (MIT)', 'Freeware'.
        """
        valid_spdx = cls.get_valid_spdx_id(raw_license)
        if valid_spdx:
            return f"Open Source ({valid_spdx})" if valid_spdx not in ("SSPL-1.0", "BSL-1.1") else f"Source-Available ({valid_spdx})"
        
        c = (classification or "").upper()
        if c in ("OPEN_SOURCE",):
            return "Open Source"
        if c in ("FREEWARE", "OS_BUNDLED"):
            return "Freeware"
        return "Proprietary"

    @classmethod
    def get_spdx_info(cls, spdx_id: Optional[str]) -> SPDXInfo:
        """Returns structured metadata for a normalized SPDX ID."""
        norm_id = cls.normalize_spdx(spdx_id)
        for _, info in cls.SPDX_MAP.items():
            if info.spdx_id.lower() == norm_id.lower():
                return info
        return SPDXInfo(
            spdx_id=norm_id,
            license_name=norm_id if norm_id != "UNKNOWN" else "Unknown License",
            category="UNKNOWN",
            is_open_source=False,
            is_source_available=False,
            is_commercial_proprietary=False,
            default_classification="UNKNOWN",
        )
