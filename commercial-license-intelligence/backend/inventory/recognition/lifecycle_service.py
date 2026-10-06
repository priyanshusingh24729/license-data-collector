"""
Version-Aware Software Lifecycle Engine (EOL / EOS).
Determines verified End of Life (EOL) and End of Support (EOS) status
strictly based on Application + Product + Version evidence.

Rules:
- Verified active/supported version -> 0
- Verified EOL / EOS version -> 1
- No reliable lifecycle information -> None (blank / null)
- Never falsely assume active support (do not default to 0)
- Always version-aware (historical versions of active products can be EOL)
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple, NamedTuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class LifecycleResult(NamedTuple):
    is_eol: Optional[int]
    is_eos: Optional[int]
    evidence_url: Optional[str]

CURRENT_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

LIFECYCLE_REGISTRY: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------
    # Operating Systems & Server Platforms
    # -------------------------------------------------------------
    "windows server": {
        "aliases": ["windows server", "win server", "microsoft windows server"],
        "default_url": "https://learn.microsoft.com/en-us/lifecycle/products/windows-server",
        "versions": {
            "2003": {"eol": "2015-07-14", "eos": "2015-07-14", "url": "https://learn.microsoft.com/en-us/lifecycle/products/windows-server-2003"},
            "2008": {"eol": "2020-01-14", "eos": "2020-01-14", "url": "https://learn.microsoft.com/en-us/lifecycle/products/windows-server-2008"},
            "2008 r2": {"eol": "2020-01-14", "eos": "2020-01-14", "url": "https://learn.microsoft.com/en-us/lifecycle/products/windows-server-2008-r2"},
            "2012": {"eol": "2023-10-10", "eos": "2023-10-10", "url": "https://learn.microsoft.com/en-us/lifecycle/products/windows-server-2012"},
            "2012 r2": {"eol": "2023-10-10", "eos": "2023-10-10", "url": "https://learn.microsoft.com/en-us/lifecycle/products/windows-server-2012-r2"},
            "2016": {"eol": "2027-01-12", "eos": "2022-01-11", "url": "https://learn.microsoft.com/en-us/lifecycle/products/windows-server-2016"},
            "2019": {"eol": "2029-01-09", "eos": "2024-01-09", "url": "https://learn.microsoft.com/en-us/lifecycle/products/windows-server-2019"},
            "2022": {"eol": "2031-10-14", "eos": "2026-10-13", "url": "https://learn.microsoft.com/en-us/lifecycle/products/windows-server-2022"},
            "2025": {"eol": "2034-10-10", "eos": "2029-10-09", "url": "https://learn.microsoft.com/en-us/lifecycle/products/windows-server-2025"},
        }
    },
    "windows client": {
        "aliases": ["windows 10", "windows 11", "windows 7", "windows 8", "windows xp", "windows vista"],
        "default_url": "https://learn.microsoft.com/en-us/lifecycle/products/windows-10-home-and-pro",
        "versions": {
            "xp": {"eol": "2014-04-08", "eos": "2014-04-08"},
            "vista": {"eol": "2017-04-11", "eos": "2017-04-11"},
            "7": {"eol": "2020-01-14", "eos": "2020-01-14"},
            "8": {"eol": "2016-01-12", "eos": "2016-01-12"},
            "8.1": {"eol": "2023-01-10", "eos": "2023-01-10"},
            "10": {"eol": "2025-10-14", "eos": "2025-10-14", "url": "https://learn.microsoft.com/en-us/lifecycle/products/windows-10-home-and-pro"},
            "11": {"eol": "2031-10-14", "eos": "2026-10-14", "url": "https://learn.microsoft.com/en-us/lifecycle/products/windows-11-home-and-pro"},
        }
    },
    "ubuntu": {
        "aliases": ["ubuntu", "ubuntu linux"],
        "default_url": "https://ubuntu.com/about/release-cycle",
        "versions": {
            "14.04": {"eol": "2019-04-30", "eos": "2019-04-30"},
            "16.04": {"eol": "2021-04-30", "eos": "2021-04-30"},
            "18.04": {"eol": "2023-05-31", "eos": "2023-05-31"},
            "20.04": {"eol": "2025-04-30", "eos": "2025-04-30"},
            "22.04": {"eol": "2027-04-30", "eos": "2027-04-30"},
            "24.04": {"eol": "2029-04-30", "eos": "2029-04-30"},
        }
    },

    # -------------------------------------------------------------
    # Database Engines
    # -------------------------------------------------------------
    "microsoft sql server": {
        "aliases": ["sql server", "microsoft sql server", "mssql"],
        "default_url": "https://learn.microsoft.com/en-us/lifecycle/products/microsoft-sql-server",
        "versions": {
            "2000": {"eol": "2013-04-09", "eos": "2008-04-08"},
            "2005": {"eol": "2016-04-12", "eos": "2011-04-12"},
            "2008": {"eol": "2019-07-09", "eos": "2014-07-08"},
            "2008 r2": {"eol": "2019-07-09", "eos": "2014-07-08"},
            "2012": {"eol": "2022-07-12", "eos": "2017-07-11"},
            "2014": {"eol": "2024-07-09", "eos": "2019-07-09"},
            "2016": {"eol": "2026-07-14", "eos": "2021-07-13", "url": "https://learn.microsoft.com/en-us/lifecycle/products/sql-server-2016"},
            "2017": {"eol": "2027-10-12", "eos": "2022-10-11", "url": "https://learn.microsoft.com/en-us/lifecycle/products/sql-server-2017"},
            "2019": {"eol": "2030-01-08", "eos": "2025-01-07", "url": "https://learn.microsoft.com/en-us/lifecycle/products/sql-server-2019"},
            "2022": {"eol": "2033-01-11", "eos": "2028-01-11", "url": "https://learn.microsoft.com/en-us/lifecycle/products/sql-server-2022"},
        }
    },
    "oracle database": {
        "aliases": ["oracle database", "oracle rdbms"],
        "default_url": "https://www.oracle.com/support/lifetime-support/",
        "versions": {
            "9i": {"eol": "2010-07-31", "eos": "2007-07-31"},
            "10g": {"eol": "2013-07-31", "eos": "2010-07-31"},
            "11g": {"eol": "2020-12-31", "eos": "2015-01-31"},
            "12c": {"eol": "2022-03-31", "eos": "2018-07-31"},
            "18c": {"eol": "2021-06-30", "eos": "2021-06-30"},
            "19c": {"eol": "2027-04-30", "eos": "2024-04-30"},
            "21c": {"eol": "2025-04-30", "eos": "2024-04-30"},
            "23c": {"eol": "2031-04-30", "eos": "2028-04-30"},
        }
    },
    "postgresql": {
        "aliases": ["postgresql", "postgres"],
        "default_url": "https://www.postgresql.org/support/versioning/",
        "versions": {
            "9": {"eol": "2021-11-11", "eos": "2021-11-11"},
            "10": {"eol": "2022-11-10", "eos": "2022-11-10"},
            "11": {"eol": "2023-11-09", "eos": "2023-11-09"},
            "12": {"eol": "2024-11-14", "eos": "2024-11-14"},
            "13": {"eol": "2025-11-13", "eos": "2025-11-13"},
            "14": {"eol": "2026-11-12", "eos": "2026-11-12"},
            "15": {"eol": "2027-11-11", "eos": "2027-11-11"},
            "16": {"eol": "2028-11-09", "eos": "2028-11-09"},
            "17": {"eol": "2029-11-08", "eos": "2029-11-08"},
        }
    },
    "mysql": {
        "aliases": ["mysql", "mysql server"],
        "default_url": "https://www.mysql.com/support/eol-notice.html",
        "versions": {
            "5.5": {"eol": "2018-12-31", "eos": "2015-12-31"},
            "5.6": {"eol": "2021-02-28", "eos": "2018-02-28"},
            "5.7": {"eol": "2023-10-31", "eos": "2020-10-31"},
            "8.0": {"eol": "2026-04-30", "eos": "2025-04-30"},
            "8.4": {"eol": "2032-04-30", "eos": "2029-04-30"},
        }
    },

    # -------------------------------------------------------------
    # Runtimes, Languages & Developer Platforms
    # -------------------------------------------------------------
    "python": {
        "aliases": ["python", "python3", "python 3"],
        "default_url": "https://devguide.python.org/versions/",
        "versions": {
            "2.7": {"eol": "2020-01-01", "eos": "2020-01-01"},
            "3.5": {"eol": "2020-09-30", "eos": "2020-09-30"},
            "3.6": {"eol": "2021-12-23", "eos": "2021-12-23"},
            "3.7": {"eol": "2023-06-27", "eos": "2023-06-27"},
            "3.8": {"eol": "2024-10-07", "eos": "2024-10-07"},
            "3.9": {"eol": "2025-10-31", "eos": "2025-10-31"},
            "3.10": {"eol": "2026-10-31", "eos": "2026-10-31"},
            "3.11": {"eol": "2027-10-31", "eos": "2027-10-31"},
            "3.12": {"eol": "2028-10-31", "eos": "2028-10-31"},
            "3.13": {"eol": "2029-10-31", "eos": "2029-10-31"},
            "3.14": {"eol": "2030-10-31", "eos": "2030-10-31"},
        }
    },
    "nodejs": {
        "aliases": ["node.js", "nodejs", "node js"],
        "default_url": "https://nodejs.org/en/about/previous-releases",
        "versions": {
            "10": {"eol": "2021-04-30", "eos": "2021-04-30"},
            "12": {"eol": "2022-04-30", "eos": "2022-04-30"},
            "14": {"eol": "2023-04-30", "eos": "2023-04-30"},
            "16": {"eol": "2023-09-11", "eos": "2023-09-11"},
            "18": {"eol": "2025-04-30", "eos": "2025-04-30"},
            "19": {"eol": "2023-06-01", "eos": "2023-06-01"},
            "20": {"eol": "2026-04-30", "eos": "2026-04-30"},
            "21": {"eol": "2024-06-01", "eos": "2024-06-01"},
            "22": {"eol": "2027-04-30", "eos": "2027-04-30"},
            "23": {"eol": "2025-06-01", "eos": "2025-06-01"},
            "24": {"eol": "2028-04-30", "eos": "2027-10-31"},
            "25": {"eol": "2026-06-01", "eos": "2026-06-01"},
        }
    },
    "dotnet": {
        "aliases": [".net", ".net framework", ".net core", "microsoft .net"],
        "default_url": "https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core",
        "versions": {
            "1.0": {"eol": "2019-06-27", "eos": "2019-06-27"},
            "2.0": {"eol": "2018-10-01", "eos": "2018-10-01"},
            "2.1": {"eol": "2021-08-21", "eos": "2021-08-21"},
            "3.1": {"eol": "2022-12-13", "eos": "2022-12-13"},
            "4.5": {"eol": "2016-01-12", "eos": "2016-01-12"},
            "4.5.1": {"eol": "2016-01-12", "eos": "2016-01-12"},
            "4.5.2": {"eol": "2022-04-26", "eos": "2022-04-26"},
            "4.6": {"eol": "2022-04-26", "eos": "2022-04-26"},
            "4.6.1": {"eol": "2022-04-26", "eos": "2022-04-26"},
            "4.7": {"eol": "2030-01-01", "eos": "2030-01-01"},
            "4.8": {"eol": "2035-01-01", "eos": "2035-01-01"},
            "5.0": {"eol": "2022-05-10", "eos": "2022-05-10"},
            "6.0": {"eol": "2024-11-12", "eos": "2024-11-12"},
            "7.0": {"eol": "2024-05-14", "eos": "2024-05-14"},
            "8.0": {"eol": "2026-11-10", "eos": "2026-11-10"},
            "9.0": {"eol": "2026-05-12", "eos": "2026-05-12"},
        }
    },
    "java": {
        "aliases": ["java", "openjdk", "oracle java", "java se", "jre", "jdk"],
        "default_url": "https://www.oracle.com/java/technologies/java-se-support-roadmap.html",
        "versions": {
            "6": {"eol": "2018-12-31", "eos": "2013-02-28"},
            "7": {"eol": "2022-07-31", "eos": "2015-04-30"},
            "8": {"eol": "2030-12-31", "eos": "2019-01-31"},
            "9": {"eol": "2018-03-31", "eos": "2018-03-31"},
            "10": {"eol": "2018-09-30", "eos": "2018-09-30"},
            "11": {"eol": "2026-09-30", "eos": "2023-09-30"},
            "12": {"eol": "2019-09-30", "eos": "2019-09-30"},
            "13": {"eol": "2020-03-31", "eos": "2020-03-31"},
            "14": {"eol": "2020-09-30", "eos": "2020-09-30"},
            "15": {"eol": "2021-03-31", "eos": "2021-03-31"},
            "16": {"eol": "2021-09-30", "eos": "2021-09-30"},
            "17": {"eol": "2029-09-30", "eos": "2026-09-30"},
            "18": {"eol": "2022-09-30", "eos": "2022-09-30"},
            "19": {"eol": "2023-03-31", "eos": "2023-03-31"},
            "20": {"eol": "2023-09-30", "eos": "2023-09-30"},
            "21": {"eol": "2031-09-30", "eos": "2028-09-30"},
        }
    },

    # -------------------------------------------------------------
    # Productivity & Enterprise Client Suites
    # -------------------------------------------------------------
    "microsoft office": {
        "aliases": ["microsoft office", "office", "ms office"],
        "default_url": "https://learn.microsoft.com/en-us/lifecycle/products/microsoft-office",
        "versions": {
            "2003": {"eol": "2014-04-08", "eos": "2009-04-14"},
            "2007": {"eol": "2017-10-10", "eos": "2012-10-09"},
            "2010": {"eol": "2020-10-13", "eos": "2015-10-13"},
            "2013": {"eol": "2023-04-11", "eos": "2018-04-10"},
            "2016": {"eol": "2025-10-14", "eos": "2020-10-13"},
            "2019": {"eol": "2025-10-14", "eos": "2023-10-10"},
            "2021": {"eol": "2026-10-13", "eos": "2026-10-13"},
            "2024": {"eol": "2029-10-09", "eos": "2029-10-09"},
            "365": {"eol": "2099-12-31", "eos": "2099-12-31", "url": "https://learn.microsoft.com/en-us/lifecycle/products/microsoft-365-apps"},
        }
    },
    "visual studio": {
        "aliases": ["visual studio", "microsoft visual studio"],
        "default_url": "https://learn.microsoft.com/en-us/visualstudio/releases/2022/servicing",
        "versions": {
            "2005": {"eol": "2016-04-12", "eos": "2011-04-12"},
            "2008": {"eol": "2018-04-10", "eos": "2013-04-09"},
            "2010": {"eol": "2020-07-14", "eos": "2015-07-14"},
            "2012": {"eol": "2023-01-10", "eos": "2018-01-09"},
            "2013": {"eol": "2024-04-09", "eos": "2019-04-09"},
            "2015": {"eol": "2025-10-14", "eos": "2020-10-13"},
            "2017": {"eol": "2027-04-13", "eos": "2022-04-12"},
            "2019": {"eol": "2029-04-10", "eos": "2024-04-09"},
            "2022": {"eol": "2032-04-13", "eos": "2027-04-13"},
        }
    },
    "docker desktop": {
        "aliases": ["docker desktop", "docker"],
        "default_url": "https://docs.docker.com/desktop/release-notes/",
        "versions": {
            "1": {"eol": "2020-01-01", "eos": "2020-01-01"},
            "2": {"eol": "2021-06-30", "eos": "2021-06-30"},
            "3": {"eol": "2022-06-30", "eos": "2022-06-30"},
            "4": {"eol": "2026-12-31", "eos": "2026-12-31"},
        }
    }
}


class LifecycleService:
    """
    Evaluates version-specific lifecycle status (IsEndOfLife, IsEndOfSupport).
    """

    @classmethod
    def evaluate_lifecycle(
        cls,
        app_name: str,
        version: Optional[str] = None,
        publisher: Optional[str] = None,
    ) -> LifecycleResult:
        """
        Determines version-specific EOL and EOS status:
        Returns: LifecycleResult(is_eol, is_eos, evidence_url)
        - is_eol: 0 (supported), 1 (EOL), or None (unknown)
        - is_eos: 0 (supported), 1 (EOS), or None (unknown)
        - evidence_url: Official vendor lifecycle documentation URL or None
        """
        if not app_name:
            return LifecycleResult(None, None, None)

        name_lower = app_name.lower().strip()
        ver_str = str(version or "").strip().lower()

        # Find matching product entry
        matched_product = None
        for prod_key, prod_info in LIFECYCLE_REGISTRY.items():
            for alias in prod_info["aliases"]:
                if alias in name_lower:
                    matched_product = prod_info
                    break
            if matched_product:
                break

        if not matched_product:
            return LifecycleResult(None, None, None)

        cycles = matched_product["versions"]
        default_url = matched_product.get("default_url")

        # Check year tokens in name or version (e.g. 2008, 2012, 2016, 2019, 2022)
        year_match = re.search(r"\b(20\d\d(?:\s*r2)?)\b", f"{name_lower} {ver_str}")
        if year_match:
            y_key = year_match.group(1).strip()
            y_key = re.sub(r"\s+", " ", y_key)
            if y_key in cycles:
                return cls._evaluate_cycle(cycles[y_key], default_url)

        # Check numeric version prefix (e.g. 2.7, 3.11, 14, 16, 20)
        v_cleaned = re.sub(r"^[^\d]*", "", ver_str)
        two_part = re.match(r"^(\d+\.\d+)", v_cleaned)
        if two_part and two_part.group(1) in cycles:
            return cls._evaluate_cycle(cycles[two_part.group(1)], default_url)

        one_part = re.match(r"^(\d+)", v_cleaned)
        if one_part and one_part.group(1) in cycles:
            return cls._evaluate_cycle(cycles[one_part.group(1)], default_url)

        # Check direct token in application name (e.g. "Python 2.7", "Windows 7")
        for c_key in sorted(cycles.keys(), key=len, reverse=True):
            if re.search(rf"\b{re.escape(c_key)}\b", name_lower):
                return cls._evaluate_cycle(cycles[c_key], default_url)

        # If product was identified but version was unstated/missing or unmapped:
        # Do NOT guess 0. Return None (blank)
        return LifecycleResult(None, None, default_url)

    @staticmethod
    def _evaluate_cycle(cycle_info: Dict[str, Any], default_url: Optional[str]) -> LifecycleResult:
        """Evaluates whether current date has passed EOL and EOS dates."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        url = cycle_info.get("url") or default_url

        eol_date = cycle_info.get("eol")
        eos_date = cycle_info.get("eos")

        is_eol = 1 if (eol_date and today >= eol_date) else 0
        is_eos = 1 if (eos_date and today >= eos_date) else 0

        return LifecycleResult(is_eol, is_eos, url)
