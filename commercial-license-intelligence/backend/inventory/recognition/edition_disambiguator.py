"""
Edition Disambiguation Engine.
Deterministically distinguishes software editions (Community, Professional, Enterprise, Express, Standard, Ultimate, etc.).
Enforces the zero-guessing rule: if an application belongs to an edition-sensitive commercial family
and the edition cannot be verified from available signatures, assigns 'EDITION_AMBIGUOUS'.
"""

import re
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple, List


@dataclass
class EditionDisambiguationResult:
    edition: Optional[str]
    is_ambiguous: bool
    is_split_product: bool
    license_model: Optional[str] = None
    classification: Optional[str] = None
    license_required: Optional[str] = None
    metric: Optional[str] = None
    spdx_id: Optional[str] = None
    reason: str = ""


class EditionDisambiguator:
    """
    Evaluates raw application names, package identifiers, and installation locations
    to resolve exact software edition and associated licensing terms.
    """

    # Edition-sensitive product families where edition directly determines license requirement & cost
    SPLIT_EDITION_PATTERNS = [
        # Visual Studio (excludes Code, Installer, Build Tools, Redistributables, .NET SDK)
        (r"\bvisual\s+studio\b(?!.*(?:code|installer|build\s+tools|redistributable|\.net|dotnet|sdk))", "visual_studio"),
        # SQL Server (excludes Compact, SSMS, VSS, Native Client, Setup, ODBC, OLE DB, Driver, Browser)
        (r"\b(?:microsoft\s+)?sql\s+server\b(?!.*(?:compact|management\s+studio|ssms|vss|native\s+client|setup|odbc|ole\s*db|driver|browser))", "sql_server"),
        # Oracle Database
        (r"\boracle(?:\s+database|\s+\d+[c-g]|\s+client)?\b(?!.*(?:virtualbox|java|jdk|jre|mysql))", "oracle_db"),
        # MySQL Server
        (r"\bmysql(?:\s+server)?\b(?!.*(?:workbench|connector|router|installer))", "mysql"),
        # MongoDB
        (r"\bmongodb\b(?!.*compass)", "mongodb"),
        # IntelliJ IDEA
        (r"\bintellij\s+idea\b", "intellij"),
        # PyCharm
        (r"\bpycharm\b", "pycharm"),
        # VMware Workstation
        (r"\bvmware\s+workstation\b", "vmware_workstation"),
        # Tableau
        (r"\btableau\b", "tableau"),
    ]

    @classmethod
    def is_split_edition_product(cls, app_name: str) -> Tuple[bool, Optional[str]]:
        """Checks whether the application belongs to a known edition-sensitive family."""
        if not app_name:
            return False, None
        low = app_name.lower().strip()

        # Strict collision guard: Client drivers, SDKs, runtimes, and background services are never split server/IDE engines
        if any(term in low for term in ("odbc", "ole db", "oledb", "driver", ".net sdk", "dotnet sdk", "installer", "browser for sql", "vss writer")):
            return False, None

        for pattern, family_id in cls.SPLIT_EDITION_PATTERNS:
            if re.search(pattern, low):
                return True, family_id
        return False, None

    @classmethod
    def disambiguate(
        cls,
        raw_name: str,
        vendor: Optional[str] = None,
        version: Optional[str] = None,
        install_location: Optional[str] = None,
    ) -> EditionDisambiguationResult:
        """
        Disambiguates software edition and returns exact licensing implications.
        If the product has split editions and no evidence confirms the edition, returns EDITION_AMBIGUOUS.
        """
        if not raw_name:
            return EditionDisambiguationResult(
                edition=None,
                is_ambiguous=False,
                is_split_product=False,
                reason="Empty application name",
            )

        name_to_check = f"{raw_name} {install_location or ''}".lower()
        is_split, family_id = cls.is_split_edition_product(raw_name)

        if not is_split:
            # Check for general edition tokens that might be present on non-split products
            ed_token = cls._extract_generic_edition(raw_name)
            return EditionDisambiguationResult(
                edition=ed_token,
                is_ambiguous=False,
                is_split_product=False,
                reason="Single-edition or non-split product",
            )

        # -------------------------------------------------------------
        # Family 1: Microsoft Visual Studio
        # -------------------------------------------------------------
        if family_id == "visual_studio":
            if "code" in name_to_check:
                return EditionDisambiguationResult(
                    edition="Code",
                    is_ambiguous=False,
                    is_split_product=True,
                    license_model="MIT License — Free/Open Source",
                    classification="OPEN_SOURCE",
                    license_required="NO",
                    metric="No License Required",
                    spdx_id="MIT",
                    reason="Visual Studio Code is open-source/permissive (MIT)",
                )
            if "community" in name_to_check:
                return EditionDisambiguationResult(
                    edition="Community",
                    is_ambiguous=False,
                    is_split_product=True,
                    license_model="Freeware",
                    classification="FREEWARE",
                    license_required="NO",
                    metric="No License Required",
                    spdx_id="Proprietary",
                    reason="Visual Studio Community is free for individuals, education, and small open-source teams",
                )
            if "professional" in name_to_check or " pro " in f" {name_to_check} ":
                return EditionDisambiguationResult(
                    edition="Professional",
                    is_ambiguous=False,
                    is_split_product=True,
                    license_model="Commercial — Per Seat Subscription",
                    classification="COMMERCIAL",
                    license_required="YES",
                    metric="Named User",
                    spdx_id="Proprietary",
                    reason="Visual Studio Professional requires commercial per-user license",
                )
            if "enterprise" in name_to_check:
                return EditionDisambiguationResult(
                    edition="Enterprise",
                    is_ambiguous=False,
                    is_split_product=True,
                    license_model="Commercial — Per Seat Subscription",
                    classification="COMMERCIAL",
                    license_required="YES",
                    metric="Named User",
                    spdx_id="Proprietary",
                    reason="Visual Studio Enterprise requires high-tier commercial per-user subscription",
                )
            # Ambiguous Visual Studio
            return EditionDisambiguationResult(
                edition="EDITION_AMBIGUOUS",
                is_ambiguous=True,
                is_split_product=True,
                license_model="Unknown",
                classification="UNKNOWN",
                license_required="YES",
                metric="UNKNOWN",
                spdx_id="Proprietary",
                reason="Visual Studio detected without explicit edition (Community vs Professional vs Enterprise). Edition proof required.",
            )

        # -------------------------------------------------------------
        # Family 2: Microsoft SQL Server
        # -------------------------------------------------------------
        if family_id == "sql_server":
            if "express" in name_to_check:
                return EditionDisambiguationResult(
                    edition="Express",
                    is_ambiguous=False,
                    is_split_product=True,
                    license_model="Freeware",
                    classification="FREEWARE",
                    license_required="NO",
                    metric="No License Required",
                    spdx_id="Proprietary",
                    reason="SQL Server Express is free/no-cost",
                )
            if "developer" in name_to_check:
                return EditionDisambiguationResult(
                    edition="Developer",
                    is_ambiguous=False,
                    is_split_product=True,
                    license_model="Commercial — Free for Development",
                    classification="FREE",
                    license_required="NO",
                    metric="No License Required",
                    spdx_id="Proprietary",
                    reason="SQL Server Developer Edition is free for non-production development/testing",
                )
            if "standard" in name_to_check:
                return EditionDisambiguationResult(
                    edition="Standard",
                    is_ambiguous=False,
                    is_split_product=True,
                    license_model="Commercial — Per Core / Server + CAL",
                    classification="COMMERCIAL",
                    license_required="YES",
                    metric="Processor Cores",
                    spdx_id="Proprietary",
                    reason="SQL Server Standard requires Core or Server+CAL commercial license",
                )
            if "enterprise" in name_to_check:
                return EditionDisambiguationResult(
                    edition="Enterprise",
                    is_ambiguous=False,
                    is_split_product=True,
                    license_model="Commercial — Per Core",
                    classification="COMMERCIAL",
                    license_required="YES",
                    metric="Processor Cores",
                    spdx_id="Proprietary",
                    reason="SQL Server Enterprise requires commercial per-core licensing",
                )
            # Ambiguous SQL Server
            return EditionDisambiguationResult(
                edition="EDITION_AMBIGUOUS",
                is_ambiguous=True,
                is_split_product=True,
                license_model="Unknown",
                classification="UNKNOWN",
                license_required="YES",
                metric="UNKNOWN",
                spdx_id="Proprietary",
                reason="SQL Server detected without explicit edition (Express vs Standard vs Enterprise). Edition proof required.",
            )

        # -------------------------------------------------------------
        # Family 3: Oracle Database
        # -------------------------------------------------------------
        if family_id == "oracle_db":
            if "express" in name_to_check or " xe" in name_to_check:
                return EditionDisambiguationResult(
                    edition="Express (XE)",
                    is_ambiguous=False,
                    is_split_product=True,
                    license_model="Freeware",
                    classification="FREEWARE",
                    license_required="NO",
                    metric="No License Required",
                    spdx_id="Proprietary",
                    reason="Oracle Database XE is free for development and limited deployment",
                )
            if "standard" in name_to_check or "se2" in name_to_check:
                return EditionDisambiguationResult(
                    edition="Standard Edition 2",
                    is_ambiguous=False,
                    is_split_product=True,
                    license_model="Commercial — Processor / Named User Plus",
                    classification="COMMERCIAL",
                    license_required="YES",
                    metric="Processors / Sockets",
                    spdx_id="Proprietary",
                    reason="Oracle SE2 is commercial socket/user licensed",
                )
            if "enterprise" in name_to_check or " ee" in name_to_check:
                return EditionDisambiguationResult(
                    edition="Enterprise Edition",
                    is_ambiguous=False,
                    is_split_product=True,
                    license_model="Commercial — Processor Core Factor",
                    classification="COMMERCIAL",
                    license_required="YES",
                    metric="Processor Cores",
                    spdx_id="Proprietary",
                    reason="Oracle Database EE requires commercial core factor licensing",
                )
            return EditionDisambiguationResult(
                edition="EDITION_AMBIGUOUS",
                is_ambiguous=True,
                is_split_product=True,
                license_model="Unknown",
                classification="UNKNOWN",
                license_required="YES",
                metric="UNKNOWN",
                spdx_id="Proprietary",
                reason="Oracle Database detected without edition proof (XE vs SE2 vs EE).",
            )

        # -------------------------------------------------------------
        # Family 4: MySQL
        # -------------------------------------------------------------
        if family_id == "mysql":
            if "commercial" in name_to_check or "enterprise" in name_to_check or "cluster" in name_to_check:
                return EditionDisambiguationResult(
                    edition="Enterprise",
                    is_ambiguous=False,
                    is_split_product=True,
                    license_model="Commercial — Annual Subscription",
                    classification="COMMERCIAL",
                    license_required="YES",
                    metric="Processors / Sockets",
                    spdx_id="Proprietary",
                    reason="Oracle MySQL Commercial/Enterprise subscription",
                )
            # Community is the open-source standard release
            return EditionDisambiguationResult(
                edition="Community",
                is_ambiguous=False,
                is_split_product=True,
                license_model="GPL-2.0 — Free/Open Source",
                classification="OPEN_SOURCE",
                license_required="NO",
                metric="No License Required",
                spdx_id="GPL-2.0-only",
                reason="MySQL Community Server is GPL-2.0 licensed",
            )

        # -------------------------------------------------------------
        # Family 5: MongoDB
        # -------------------------------------------------------------
        if family_id == "mongodb":
            if "enterprise" in name_to_check or "advanced" in name_to_check:
                return EditionDisambiguationResult(
                    edition="Enterprise Advanced",
                    is_ambiguous=False,
                    is_split_product=True,
                    license_model="Commercial — Per Server / Core",
                    classification="COMMERCIAL",
                    license_required="YES",
                    metric="Processor Cores",
                    spdx_id="Proprietary",
                    reason="MongoDB Enterprise Advanced requires commercial subscription",
                )
            return EditionDisambiguationResult(
                edition="Community",
                is_ambiguous=False,
                is_split_product=True,
                license_model="SSPL-1.0 — Free to Use",
                classification="OPEN_SOURCE",
                license_required="NO",
                metric="No License Required",
                spdx_id="SSPL-1.0",
                reason="MongoDB Community is source-available SSPL-1.0, free for internal execution",
            )

        # -------------------------------------------------------------
        # Family 6: JetBrains (IntelliJ IDEA, PyCharm)
        # -------------------------------------------------------------
        if family_id in ("intellij", "pycharm"):
            if "community" in name_to_check or " ce" in name_to_check:
                return EditionDisambiguationResult(
                    edition="Community",
                    is_ambiguous=False,
                    is_split_product=True,
                    license_model="Apache-2.0 — Free/Open Source",
                    classification="OPEN_SOURCE",
                    license_required="NO",
                    metric="No License Required",
                    spdx_id="Apache-2.0",
                    reason=f"{raw_name} Community Edition is open source under Apache-2.0",
                )
            if "ultimate" in name_to_check or "professional" in name_to_check or " pro" in name_to_check:
                return EditionDisambiguationResult(
                    edition="Ultimate" if family_id == "intellij" else "Professional",
                    is_ambiguous=False,
                    is_split_product=True,
                    license_model="Commercial — Per User Subscription",
                    classification="COMMERCIAL",
                    license_required="YES",
                    metric="Named User",
                    spdx_id="Proprietary",
                    reason=f"{raw_name} commercial edition requires paid user subscription",
                )
            return EditionDisambiguationResult(
                edition="EDITION_AMBIGUOUS",
                is_ambiguous=True,
                is_split_product=True,
                license_model="Unknown",
                classification="UNKNOWN",
                license_required="YES",
                metric="UNKNOWN",
                spdx_id="Proprietary",
                reason=f"{raw_name} detected without edition token (Community vs Commercial). Proof required.",
            )

        # -------------------------------------------------------------
        # Family 7: Tableau
        # -------------------------------------------------------------
        if family_id == "tableau":
            if "public" in name_to_check:
                return EditionDisambiguationResult(
                    edition="Public",
                    is_ambiguous=False,
                    is_split_product=True,
                    license_model="Freeware",
                    classification="FREEWARE",
                    license_required="NO",
                    metric="No License Required",
                    spdx_id="Proprietary",
                    reason="Tableau Public is free software",
                )
            if "desktop" in name_to_check or "prep" in name_to_check:
                return EditionDisambiguationResult(
                    edition="Desktop",
                    is_ambiguous=False,
                    is_split_product=True,
                    license_model="Commercial — Creator Subscription",
                    classification="COMMERCIAL",
                    license_required="YES",
                    metric="Named User",
                    spdx_id="Proprietary",
                    reason="Tableau Desktop requires paid Creator subscription",
                )

        # Fallback for other split items
        return EditionDisambiguationResult(
            edition="EDITION_AMBIGUOUS",
            is_ambiguous=True,
            is_split_product=True,
            license_model="Unknown",
            classification="UNKNOWN",
            license_required="YES",
            metric="UNKNOWN",
            reason=f"Product {raw_name} is edition-sensitive; specific edition could not be verified.",
        )

    @classmethod
    def _extract_generic_edition(cls, raw_name: str) -> Optional[str]:
        """Extracts standard edition words from general application names."""
        tokens = [
            ("Community Edition", "Community"),
            ("Community", "Community"),
            ("Professional Edition", "Professional"),
            ("Professional", "Professional"),
            ("Enterprise Edition", "Enterprise"),
            ("Enterprise", "Enterprise"),
            ("Express Edition", "Express"),
            ("Express", "Express"),
            ("Standard Edition", "Standard"),
            ("Standard", "Standard"),
            ("Ultimate Edition", "Ultimate"),
            ("Ultimate", "Ultimate"),
            ("Developer Edition", "Developer"),
            ("Developer", "Developer"),
            ("Personal Edition", "Personal"),
            ("Home Edition", "Home"),
            ("Home", "Home"),
            ("Pro Edition", "Pro"),
            ("Pro", "Pro"),
        ]
        for term, ed in tokens:
            if re.search(rf"\b{re.escape(term)}\b", raw_name, re.IGNORECASE):
                return ed
        return None
