"""
Snow SRS Master Lookup Service.
Provides high-speed, deterministic, hierarchical matching against the 907,437-row
Snow Software Recognition Service (SRS) catalog in 'data/snow_srs_master.db'.

Resolution Flow:
Application + Vendor + Version/Edition + OS
-> Tier 1: Exact Name + Version + OS
-> Tier 2: Exact Name + Version
-> Tier 3: Exact Name
-> Tier 4: Exact Normalized Application + Version + OS
-> Tier 5: Exact Normalized Application + Version
-> Tier 6: Exact Normalized Application + OS
-> Tier 7: Exact Normalized Application
-> Tier 8: Leading Vendor Strip / Prepend
-> Tier 9: Product Family Prefix / Substring Match (e.g. CData ODBC Driver for MongoDB 20xx, Teradata 14)

Deterministic Ranking:
1. Non-empty Metric ('Installations', 'Users', 'Devices', 'No license required')
2. Matching target Edition tokens (Community, Standard, Enterprise, Express, etc.)
3. Matching Operating System
4. Lowest App_ID (deterministic tie-breaker)
"""

import os
import re
import sqlite3
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

import threading

logger = logging.getLogger(__name__)

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data/snow_srs_master.db"))


@dataclass
class SnowBaselineRecord:
    app_id: int
    name: str
    ostype: Optional[int]
    version_name: Optional[str]
    normalized_application: str
    operating_system: Optional[str]
    major_version: Optional[str]
    minor_version: Optional[str]
    patch_version: Optional[str]
    no_license_required: int
    is_end_of_life: Optional[int]
    is_end_of_support: Optional[int]
    metric: Optional[str]
    match_tier: str
    confidence: float

    @property
    def license_required(self) -> str:
        return "NO" if self.no_license_required == 1 else "YES"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "App_ID": self.app_id,
            "name": self.name,
            "Name": self.name,
            "ostype": self.ostype,
            "OSType": self.ostype,
            "version_name": self.version_name,
            "normalized_application": self.normalized_application,
            "Normalized_Application": self.normalized_application,
            "operating_system": self.operating_system,
            "Operating_System": self.operating_system,
            "major_version": self.major_version,
            "minor_version": self.minor_version,
            "patch_version": self.patch_version,
            "no_license_required": self.no_license_required,
            "NoLicenseRequired": self.no_license_required,
            "license_required": self.license_required,
            "is_end_of_life": self.is_end_of_life,
            "IsEndOfLife": self.is_end_of_life,
            "is_end_of_support": self.is_end_of_support,
            "IsEndOfSupport": self.is_end_of_support,
            "metric": self.metric,
            "Metric": self.metric,
            "match_tier": self.match_tier,
            "confidence": self.confidence,
        }


class SnowSRSMasterService:
    """Thread-safe fast lookup service for the 907k Snow SRS Master Database."""

    _db_path: str = DB_PATH
    _SHARED_CONN: Optional[sqlite3.Connection] = None
    _LOCK = threading.Lock()
    _CACHE: Dict[Tuple[str, str, str, str, int], Optional[SnowBaselineRecord]] = {}
    _CACHE_MAX_SIZE: int = 32768

    @classmethod
    def set_db_path(cls, path: str):
        with cls._LOCK:
            cls._db_path = os.path.abspath(path)
            cls._SHARED_CONN = None
            cls._CACHE.clear()

    @classmethod
    def clear_cache(cls):
        with cls._LOCK:
            cls._CACHE.clear()

    @classmethod
    def get_db_connection(cls) -> Optional[sqlite3.Connection]:
        if not os.path.exists(cls._db_path):
            return None
        with cls._LOCK:
            try:
                if cls._SHARED_CONN is not None:
                    cls._SHARED_CONN.execute("SELECT 1;")
            except Exception:
                cls._SHARED_CONN = None

            if cls._SHARED_CONN is None:
                cls._SHARED_CONN = sqlite3.connect(cls._db_path, timeout=10.0, check_same_thread=False)
                cls._SHARED_CONN.row_factory = sqlite3.Row
            return cls._SHARED_CONN

    @classmethod
    def clean_key(cls, text: str) -> str:
        """Normalizes an application name key for exact index matching."""
        if not text:
            return ""
        s = str(text).strip()
        if s.upper().startswith("TS-"):
            s = s[3:].strip()
        elif s.upper().startswith("TS "):
            s = s[3:].strip()
        s = re.sub(r"\s*\(reg\)\s*$", "", s, flags=re.IGNORECASE)
        # Strip installer metadata suffixes
        s = re.sub(r"\s+from\s+visual\s+studio.*$", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s+\((?:x64|x86|arm64|win32)\)$", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s+\b(?:amd64|x86_64|x64)\b", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s+setup$", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s+", " ", s).strip().lower()
        return s

    @classmethod
    def clean_os_key(cls, os_val: Optional[str]) -> str:
        if not os_val:
            return ""
        s = str(os_val).strip().lower()
        if "win" in s:
            return "windows"
        if "mac" in s or "darwin" in s or "osx" in s:
            return "mac"
        if "linux" in s or "unix" in s:
            return "linux"
        if "ios" in s:
            return "ios"
        if "android" in s:
            return "android"
        return s

    @classmethod
    def extract_major_version(cls, version_str: Optional[str], raw_name: Optional[str] = None) -> Optional[str]:
        """Extracts major version string (e.g. '17', '2022', '4')."""
        if version_str and str(version_str).strip() not in ("", "N/A", "None", "NULL"):
            clean_v = str(version_str).strip()
            m = re.match(r"^v?(\d+)", clean_v)
            if m:
                return m.group(1)

        if raw_name:
            m_year = re.search(r"\b(20\d{2}|19\d{2})\b", raw_name)
            if m_year:
                return m_year.group(1)
            m_ver = re.search(r"\b(?:v|version)?\s*(\d+)(?:\.\d+)?\b", raw_name, flags=re.IGNORECASE)
            if m_ver:
                return m_ver.group(1)
        return None

    @classmethod
    def extract_edition_tokens(cls, raw_name: str) -> List[str]:
        """Extracts significant edition tokens to boost relevant match ranking."""
        s = raw_name.lower()
        editions = ["community", "express", "developer", "standard", "enterprise", "ultimate", "professional", "pro", "business", "home", "trial", "evaluation"]
        return [ed for ed in editions if re.search(rf"\b{ed}\b", s)]

    @classmethod
    def _row_to_record(cls, row: sqlite3.Row, match_tier: str, confidence: float) -> SnowBaselineRecord:
        return SnowBaselineRecord(
            app_id=int(row["app_id"]),
            name=str(row["name"]),
            ostype=row["ostype"] if row["ostype"] is not None else None,
            version_name=row["version_name"],
            normalized_application=str(row["normalized_application"]),
            operating_system=row["operating_system"],
            major_version=row["major_version"],
            minor_version=row["minor_version"],
            patch_version=row["patch_version"],
            no_license_required=int(row["no_license_required"]),
            is_end_of_life=row["is_end_of_life"],
            is_end_of_support=row["is_end_of_support"],
            metric=row["metric"],
            match_tier=match_tier,
            confidence=confidence,
        )

    @classmethod
    def strip_version_suffix(cls, name: str) -> str:
        """Strips trailing version string if leaving a meaningful product name."""
        if not name:
            return ""
        # Matches " 10.0.400", " 2.1", " 2022", " v3.0", etc. at end of name
        res = re.sub(r"\s+v?(?:\d+\.)+\d+.*$", "", name, flags=re.IGNORECASE).strip()
        if res == name:
            res = re.sub(r"\s+(?:20\d{2}|19\d{2})\b.*$", "", name).strip()
        VENDOR_ONLY = {"microsoft", "adobe", "google", "apple", "oracle", "ibm", "cdata", "intel", "lenovo", "hewlett-packard", "hp"}
        if res.lower() in VENDOR_ONLY or len(res) < 3:
            return ""
        return res

    @classmethod
    def lookup(
        cls,
        raw_name: str,
        vendor: Optional[str] = None,
        version: Optional[str] = None,
        os_name: Optional[str] = None,
        ostype: Optional[int] = None,
    ) -> Optional[SnowBaselineRecord]:
        """
        Main entry point for Snow SRS Master Lookup.
        Executes hierarchical deterministic matching with edition-aware ranking and LRU caching.
        """
        if not raw_name or not str(raw_name).strip():
            return None

        raw_stripped = str(raw_name).strip()
        if re.match(r"^\{?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}?$", raw_stripped):
            return None
        if len(raw_stripped) < 3:
            return None

        cache_key = (
            raw_stripped.lower(),
            (vendor or "").strip().lower(),
            (version or "").strip().lower(),
            (os_name or "").strip().lower(),
            int(ostype) if ostype is not None else 0,
        )
        if cache_key in cls._CACHE:
            return cls._CACHE[cache_key]

        res = cls._execute_lookup(raw_name, vendor, version, os_name, ostype)
        if len(cls._CACHE) < cls._CACHE_MAX_SIZE:
            cls._CACHE[cache_key] = res
        return res

    @classmethod
    def _execute_lookup(
        cls,
        raw_name: str,
        vendor: Optional[str] = None,
        version: Optional[str] = None,
        os_name: Optional[str] = None,
        ostype: Optional[int] = None,
    ) -> Optional[SnowBaselineRecord]:
        conn = cls.get_db_connection()
        if not conn:
            return None

        clean_name = cls.clean_key(raw_name)
        if not clean_name or len(clean_name) < 3:
            return None
        if clean_name in ("microsoft", "adobe", "google", "apple", "oracle", "ibm", "cdata", "intel", "lenovo"):
            return None
        clean_os = cls.clean_os_key(os_name)
        maj_ver = cls.extract_major_version(version, raw_name)
        edition_tokens = cls.extract_edition_tokens(raw_name)

        try:
            cursor = conn.cursor()

            order_clause = """
            ORDER BY
                CASE WHEN metric IS NOT NULL AND metric != '' AND metric != 'UNKNOWN' THEN 1 ELSE 2 END ASC,
                CASE WHEN clean_os = ? THEN 1 ELSE 2 END ASC,
                app_id ASC
            LIMIT 15
            """

            def select_best_match(rows: List[sqlite3.Row], match_tier: str, base_conf: float) -> Optional[SnowBaselineRecord]:
                if not rows:
                    return None
                scored = []
                for r in rows:
                    r_name = str(r["name"]).lower()
                    score = 0
                    is_q_ts = raw_name.lower().startswith("ts-") or raw_name.lower().startswith("ts ")
                    is_r_ts = r_name.startswith("ts-") or r_name.startswith("ts ")
                    if not is_q_ts and is_r_ts:
                        score -= 20
                    if edition_tokens:
                        score += sum(10 for ed in edition_tokens if re.search(rf"\b{ed}\b", r_name))
                    if r["metric"] and r["metric"] != "UNKNOWN":
                        score += 5
                    if clean_os and r["clean_os"] == clean_os:
                        score += 3
                    scored.append((score, r))
                scored.sort(key=lambda x: (-x[0], x[1]["app_id"]))
                best_row = scored[0][1]
                return cls._row_to_record(best_row, match_tier, base_conf)

            # -----------------------------------------------------------------
            # Tier 1: Exact Name + Major Version + OS
            # -----------------------------------------------------------------
            if maj_ver and clean_os:
                cursor.execute(
                    f"SELECT * FROM snow_srs_master WHERE clean_name = ? AND major_version = ? AND clean_os = ? {order_clause}",
                    (clean_name, maj_ver, clean_os, clean_os)
                )
                res = select_best_match(cursor.fetchall(), "TIER_1_NAME_VER_OS", 0.98)
                if res:
                    return res

            # -----------------------------------------------------------------
            # Tier 2: Exact Name + Major Version
            # -----------------------------------------------------------------
            if maj_ver:
                cursor.execute(
                    f"SELECT * FROM snow_srs_master WHERE clean_name = ? AND major_version = ? {order_clause}",
                    (clean_name, maj_ver, clean_os)
                )
                res = select_best_match(cursor.fetchall(), "TIER_2_NAME_VER", 0.95)
                if res:
                    return res

            # -----------------------------------------------------------------
            # Tier 3: Exact Name Match
            # -----------------------------------------------------------------
            cursor.execute(
                f"SELECT * FROM snow_srs_master WHERE clean_name = ? {order_clause}",
                (clean_name, clean_os)
            )
            res = select_best_match(cursor.fetchall(), "TIER_3_NAME_EXACT", 0.92)
            if res:
                return res

            # -----------------------------------------------------------------
            # Tier 4 to 7: Exact Normalized Application Match
            # -----------------------------------------------------------------
            norm_keys = [clean_name]
            stripped_ver = re.sub(r"\s*v?\d+(?:\.\d+)*\s*", " ", clean_name).strip()
            if stripped_ver and stripped_ver not in norm_keys:
                norm_keys.append(stripped_ver)

            for nk in norm_keys:
                if maj_ver and clean_os:
                    cursor.execute(
                        f"SELECT * FROM snow_srs_master WHERE clean_norm_app = ? AND major_version = ? AND clean_os = ? {order_clause}",
                        (nk, maj_ver, clean_os, clean_os)
                    )
                    res = select_best_match(cursor.fetchall(), "TIER_4_NORM_VER_OS", 0.90)
                    if res:
                        return res

                if maj_ver:
                    cursor.execute(
                        f"SELECT * FROM snow_srs_master WHERE clean_norm_app = ? AND major_version = ? {order_clause}",
                        (nk, maj_ver, clean_os)
                    )
                    res = select_best_match(cursor.fetchall(), "TIER_5_NORM_VER", 0.88)
                    if res:
                        return res

                if clean_os:
                    cursor.execute(
                        f"SELECT * FROM snow_srs_master WHERE clean_norm_app = ? AND clean_os = ? {order_clause}",
                        (nk, clean_os, clean_os)
                    )
                    res = select_best_match(cursor.fetchall(), "TIER_6_NORM_OS", 0.85)
                    if res:
                        return res

                cursor.execute(
                    f"SELECT * FROM snow_srs_master WHERE clean_norm_app = ? {order_clause}",
                    (nk, clean_os)
                )
                res = select_best_match(cursor.fetchall(), "TIER_7_NORM_EXACT", 0.82)
                if res:
                    return res

                # Try stripping trailing version numbers from normalized app name
                # E.g. "Microsoft .NET SDK 10.0.400" -> "Microsoft .NET SDK"
                nk_no_ver = cls.strip_version_suffix(nk)
                if nk_no_ver and nk_no_ver != nk:
                    cursor.execute(
                        f"SELECT * FROM snow_srs_master WHERE clean_norm_app = ? {order_clause}",
                        (nk_no_ver, clean_os)
                    )
                    res = select_best_match(cursor.fetchall(), "TIER_7_NORM_STRIPPED_VER", 0.82)
                    if res:
                        return res

            # -----------------------------------------------------------------
            # Tier 8: Strip Leading Vendor Prefix / Add Vendor Prefix Match
            # E.g. "Microsoft ODBC Driver 17 for SQL Server" -> "ODBC Driver 17 for SQL Server"
            # E.g. "SQL Server Management Studio" -> "Microsoft SQL Server Management Studio"
            # -----------------------------------------------------------------
            m_vendor = re.sub(r"^(microsoft|adobe|cdata|devart|ibm|oracle|google|lenovo|intel|apple)\s+", "", clean_name, flags=re.IGNORECASE)
            if m_vendor and m_vendor != clean_name:
                cursor.execute(
                    f"SELECT * FROM snow_srs_master WHERE clean_name = ? OR clean_norm_app = ? {order_clause}",
                    (m_vendor, m_vendor, clean_os)
                )
                res = select_best_match(cursor.fetchall(), "TIER_8_STRIPPED_VENDOR", 0.80)
                if res:
                    return res

            # Test prepending vendor or major publisher prefixes
            v_prefixes = []
            if vendor:
                v_first = cls.clean_key(vendor).split()[0] if cls.clean_key(vendor) else ""
                if v_first and not clean_name.startswith(v_first):
                    v_prefixes.append(f"{v_first} ")
            for p in ["microsoft ", "cdata ", "devart ", "oracle ", "ibm ", "adobe ", "intel "]:
                if p not in v_prefixes and not clean_name.startswith(p.strip()):
                    v_prefixes.append(p)

            for prefix in v_prefixes:
                prefixed = f"{prefix}{clean_name}"
                cursor.execute(
                    f"SELECT * FROM snow_srs_master WHERE clean_name = ? OR clean_norm_app = ? {order_clause}",
                    (prefixed, prefixed, clean_os)
                )
                res = select_best_match(cursor.fetchall(), "TIER_8_ADDED_VENDOR_PREFIX", 0.80)
                if res:
                    return res

                # Also try prefixed without trailing version
                prefixed_no_ver = cls.strip_version_suffix(prefixed)
                if prefixed_no_ver and prefixed_no_ver != prefixed:
                    cursor.execute(
                        f"SELECT * FROM snow_srs_master WHERE clean_name = ? OR clean_norm_app = ? {order_clause}",
                        (prefixed_no_ver, prefixed_no_ver, clean_os)
                    )
                    res = select_best_match(cursor.fetchall(), "TIER_8_ADDED_VENDOR_PREFIX_NO_VER", 0.80)
                    if res:
                        return res

            # -----------------------------------------------------------------
            # Tier 9: Prefix / Substring Match for Product Families
            # E.g. "CData ODBC Driver for MongoDB" matching "cdata odbc driver for mongodb %"
            # E.g. "ODBC Driver for Teradata" matching "odbc driver for teradata %"
            # -----------------------------------------------------------------
            prefix_pattern = f"{clean_name} %"
            cursor.execute(
                f"SELECT * FROM snow_srs_master WHERE clean_name LIKE ? OR clean_norm_app LIKE ? {order_clause}",
                (prefix_pattern, prefix_pattern, clean_os)
            )
            res = select_best_match(cursor.fetchall(), "TIER_9_PREFIX_MATCH", 0.78)
            if res:
                return res

            if m_vendor and m_vendor != clean_name:
                v_prefix_pattern = f"{m_vendor} %"
                cursor.execute(
                    f"SELECT * FROM snow_srs_master WHERE clean_name LIKE ? OR clean_norm_app LIKE ? {order_clause}",
                    (v_prefix_pattern, v_prefix_pattern, clean_os)
                )
                res = select_best_match(cursor.fetchall(), "TIER_9_PREFIX_STRIPPED_VENDOR", 0.76)
                if res:
                    return res

            # Specific family fallbacks
            if "ole db driver" in clean_name and "sql server" in clean_name:
                cursor.execute(
                    f"SELECT * FROM snow_srs_master WHERE clean_name LIKE '%ole db driver%sql server%' {order_clause}",
                    (clean_os,)
                )
                res = select_best_match(cursor.fetchall(), "TIER_9_FAMILY_FALLBACK", 0.78)
                if res:
                    return res

            if "odbc driver" in clean_name and "sql server" in clean_name:
                cursor.execute(
                    f"SELECT * FROM snow_srs_master WHERE clean_name LIKE '%odbc driver%sql server%' {order_clause}",
                    (clean_os,)
                )
                res = select_best_match(cursor.fetchall(), "TIER_9_FAMILY_FALLBACK", 0.78)
                if res:
                    return res

            if "visual c++" in clean_name and "redistributable" in clean_name:
                cursor.execute(
                    f"SELECT * FROM snow_srs_master WHERE clean_name LIKE '%visual c++%redistributable%' {order_clause}",
                    (clean_os,)
                )
                res = select_best_match(cursor.fetchall(), "TIER_9_FAMILY_FALLBACK", 0.85)
                if res:
                    return res

            if "power bi desktop" in clean_name:
                cursor.execute(
                    f"SELECT * FROM snow_srs_master WHERE clean_name LIKE '%power bi desktop%' {order_clause}",
                    (clean_os,)
                )
                res = select_best_match(cursor.fetchall(), "TIER_9_FAMILY_FALLBACK", 0.85)
                if res:
                    return res

            return None

        except Exception as e:
            logger.error(f"Error during Snow SRS lookup for '{raw_name}': {e}")
            return None
        finally:
            try:
                cursor.close()
            except Exception:
                pass
