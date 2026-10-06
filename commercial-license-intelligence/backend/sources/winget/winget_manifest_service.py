"""
WinGet Package Manifest Integration Service.
Integrates Microsoft's open-source winget-pkgs repository as a high-confidence metadata source.
Provides local SQLite/file caching, CLI & REST resolution, package matching, and source-priority conflict handling.
"""

import os
import re
import time
import json
import sqlite3
import logging
import subprocess
import shutil
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List, Tuple

from backend.config.settings import get_settings
from backend.inventory.detection.detection_normalizer import DetectionNormalizer

logger = logging.getLogger(__name__)


@dataclass
class WinGetManifest:
    """Structured licensing & package metadata extracted from a WinGet manifest."""
    package_id: str
    package_name: str
    publisher: str
    version: Optional[str] = None
    license: Optional[str] = None
    license_url: Optional[str] = None
    installer_url: Optional[str] = None
    installer_sha256: Optional[str] = None
    installer_type: Optional[str] = None
    homepage: Optional[str] = None
    description: Optional[str] = None
    copyright: Optional[str] = None
    moniker: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    raw_manifest: Dict[str, Any] = field(default_factory=dict)
    confidence: str = "VERY_HIGH"
    provenance: str = "winget"
    is_cached: bool = False


class WinGetManifestService:
    """
    Service for querying, parsing, caching, and matching software against WinGet package manifests.
    """

    _INITIALIZED_DBS = set()
    _consecutive_failures: int = 0
    _circuit_open_until: float = 0.0

    def __init__(self, db_path: Optional[str] = None, cache_dir: Optional[str] = None):
        settings = get_settings()
        self.db_path = db_path or os.path.abspath(
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data", "license_intelligence.db")
        )
        self.cache_dir = cache_dir or getattr(settings, "WINGET_CACHE_DIR", os.path.abspath("data/winget_cache"))
        self.enabled = getattr(settings, "ENABLE_WINGET_INTEGRATION", True)
        self.has_winget_cli = bool(shutil.which("winget"))
        self._init_cache()

    def _init_cache(self):
        """Initializes persistent SQLite cache table and directory."""
        if self.db_path in WinGetManifestService._INITIALIZED_DBS:
            return
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            os.makedirs(self.cache_dir, exist_ok=True)
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS winget_manifests_cache (
                        package_id TEXT PRIMARY KEY,
                        normalized_name TEXT,
                        normalized_publisher TEXT,
                        package_name TEXT,
                        publisher TEXT,
                        version TEXT,
                        license TEXT,
                        license_url TEXT,
                        installer_url TEXT,
                        installer_sha256 TEXT,
                        installer_type TEXT,
                        homepage TEXT,
                        description TEXT,
                        raw_json TEXT,
                        created_at TEXT
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_wg_name ON winget_manifests_cache(normalized_name)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_wg_pub ON winget_manifests_cache(normalized_publisher)")
                conn.commit()
            WinGetManifestService._INITIALIZED_DBS.add(self.db_path)
        except Exception as e:
            logger.warning(f"[WinGetManifestService] Cache table initialization notice: {e}")

    def get_cached_manifest(self, package_id: str) -> Optional[WinGetManifest]:
        """Retrieves a cached manifest by Package ID."""
        try:
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                cur = conn.cursor()
                row = cur.execute("""
                    SELECT package_id, package_name, publisher, version, license, 
                           license_url, installer_url, installer_sha256, installer_type, 
                           homepage, description, raw_json 
                    FROM winget_manifests_cache 
                    WHERE package_id = ?
                """, (package_id,)).fetchone()
                if row:
                    raw_data = json.loads(row[11]) if row[11] else {}
                    return WinGetManifest(
                        package_id=row[0],
                        package_name=row[1],
                        publisher=row[2],
                        version=row[3],
                        license=row[4],
                        license_url=row[5],
                        installer_url=row[6],
                        installer_sha256=row[7],
                        installer_type=row[8],
                        homepage=row[9],
                        description=row[10],
                        raw_manifest=raw_data,
                        confidence="VERY_HIGH",
                        provenance=f"winget_cache:{row[0]}",
                        is_cached=True,
                    )
        except Exception as e:
            logger.debug(f"[WinGetManifestService] Cache read error for {package_id}: {e}")
        return None

    def get_cached_manifest_by_name(self, app_name: str, publisher: Optional[str] = None) -> Optional[WinGetManifest]:
        """Retrieves a cached manifest by normalized application name and optional publisher."""
        norm_name = DetectionNormalizer.normalize_name(app_name).strip().lower()
        norm_pub = DetectionNormalizer.normalize_publisher(publisher).strip().lower() if publisher else None

        try:
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                cur = conn.cursor()
                if norm_pub:
                    row = cur.execute("""
                        SELECT package_id, package_name, publisher, version, license, 
                               license_url, installer_url, installer_sha256, installer_type, 
                               homepage, description, raw_json 
                        FROM winget_manifests_cache 
                        WHERE normalized_name = ? AND (normalized_publisher = ? OR normalized_publisher IS NULL)
                        LIMIT 1
                    """, (norm_name, norm_pub)).fetchone()
                else:
                    row = cur.execute("""
                        SELECT package_id, package_name, publisher, version, license, 
                               license_url, installer_url, installer_sha256, installer_type, 
                               homepage, description, raw_json 
                        FROM winget_manifests_cache 
                        WHERE normalized_name = ?
                        LIMIT 1
                    """, (norm_name,)).fetchone()

                if row:
                    raw_data = json.loads(row[11]) if row[11] else {}
                    return WinGetManifest(
                        package_id=row[0],
                        package_name=row[1],
                        publisher=row[2],
                        version=row[3],
                        license=row[4],
                        license_url=row[5],
                        installer_url=row[6],
                        installer_sha256=row[7],
                        installer_type=row[8],
                        homepage=row[9],
                        description=row[10],
                        raw_manifest=raw_data,
                        confidence="VERY_HIGH",
                        provenance=f"winget_cache:{row[0]}",
                        is_cached=True,
                    )
        except Exception as e:
            logger.debug(f"[WinGetManifestService] Cache search error for {app_name}: {e}")
        return None

    def save_to_cache(self, manifest: WinGetManifest):
        """Saves a WinGet manifest to SQLite and disk cache."""
        try:
            norm_name = DetectionNormalizer.normalize_name(manifest.package_name).strip().lower()
            norm_pub = DetectionNormalizer.normalize_publisher(manifest.publisher).strip().lower() if manifest.publisher else None
            now_iso = datetime.now(timezone.utc).isoformat()
            raw_str = json.dumps(manifest.raw_manifest or asdict(manifest))

            with sqlite3.connect(self.db_path, timeout=5) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO winget_manifests_cache (
                        package_id, normalized_name, normalized_publisher, package_name,
                        publisher, version, license, license_url, installer_url,
                        installer_sha256, installer_type, homepage, description, raw_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    manifest.package_id,
                    norm_name,
                    norm_pub,
                    manifest.package_name,
                    manifest.publisher,
                    manifest.version,
                    manifest.license,
                    manifest.license_url,
                    manifest.installer_url,
                    manifest.installer_sha256,
                    manifest.installer_type,
                    manifest.homepage,
                    manifest.description,
                    raw_str,
                    now_iso
                ))
                conn.commit()

            # Optional file snapshot
            f_path = os.path.join(self.cache_dir, f"{manifest.package_id}.json")
            with open(f_path, "w", encoding="utf-8") as f:
                json.dump(asdict(manifest), f, indent=2)

        except Exception as e:
            logger.warning(f"[WinGetManifestService] Failed to cache manifest {manifest.package_id}: {e}")

    def parse_winget_show_output(self, stdout_text: str) -> Optional[WinGetManifest]:
        """Parses the YAML-like key-value output of `winget show <package>`."""
        if not stdout_text or "Found " not in stdout_text:
            return None

        lines = stdout_text.splitlines()
        first_line = lines[0].strip()
        # Pattern: Found <Package Name> [<Package.Id>]
        match_header = re.search(r"Found\s+(.+?)\s+\[([A-Za-z0-9\._\-]+)\]", first_line)
        if not match_header:
            return None

        pkg_name = match_header.group(1).strip()
        pkg_id = match_header.group(2).strip()

        data: Dict[str, str] = {}
        installer_data: Dict[str, str] = {}
        in_installer = False

        for line in lines[1:]:
            if not line.strip():
                continue
            if line.startswith("Installer:"):
                in_installer = True
                continue
            
            kv_match = re.match(r"^\s*([A-Za-z0-9\s/]+?):\s*(.+)$", line)
            if kv_match:
                k = kv_match.group(1).strip().lower().replace(" ", "_")
                v = kv_match.group(2).strip()
                if in_installer:
                    installer_data[k] = v
                else:
                    data[k] = v

        manifest = WinGetManifest(
            package_id=pkg_id,
            package_name=pkg_name,
            publisher=data.get("publisher", ""),
            version=data.get("version"),
            license=data.get("license"),
            license_url=data.get("license_url"),
            installer_url=installer_data.get("installer_url") or data.get("installer_url"),
            installer_sha256=installer_data.get("installer_sha256") or data.get("installer_sha256"),
            installer_type=installer_data.get("installer_type"),
            homepage=data.get("homepage"),
            description=data.get("description"),
            copyright=data.get("copyright"),
            moniker=data.get("moniker"),
            raw_manifest={"general": data, "installer": installer_data},
            confidence="VERY_HIGH",
            provenance=f"winget:{pkg_id}",
            is_cached=False,
        )
        return manifest

    def execute_winget_show(self, package_id: str) -> Optional[WinGetManifest]:
        """Executes `winget show <package_id> --exact` with timeout and parsing."""
        if not self.has_winget_cli or not self.enabled:
            return None

        # Check circuit breaker and env flag
        if os.environ.get("ENABLE_WINGET_CLI_SEARCH", "true").lower() not in ("true", "1", "yes"):
            return None
        if time.time() < WinGetManifestService._circuit_open_until:
            return None

        try:
            cmd = ["winget", "show", package_id, "--exact", "--accept-source-agreements"]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=4,
                encoding="utf-8",
                errors="replace"
            )
            if res.returncode == 0 and res.stdout:
                manifest = self.parse_winget_show_output(res.stdout)
                if manifest:
                    WinGetManifestService._consecutive_failures = 0
                    self.save_to_cache(manifest)
                    return manifest
        except subprocess.TimeoutExpired:
            WinGetManifestService._consecutive_failures += 1
            if WinGetManifestService._consecutive_failures >= 2:
                WinGetManifestService._circuit_open_until = time.time() + 300.0
                logger.warning("[WinGetManifestService] Circuit breaker tripped for winget CLI after 2 timeouts. Pausing live CLI calls for 300s.")
            else:
                logger.warning(f"[WinGetManifestService] Timeout running winget show for {package_id}")
        except Exception as e:
            logger.warning(f"[WinGetManifestService] Error running winget show for {package_id}: {e}")
        return None

    def execute_winget_search(self, query: str) -> List[Tuple[str, str, str]]:
        """
        Executes `winget search <query>` and returns matching candidates as list of (Name, Id, Version).
        """
        if not self.has_winget_cli or not self.enabled:
            return []

        # Check circuit breaker and env flag
        if os.environ.get("ENABLE_WINGET_CLI_SEARCH", "true").lower() not in ("true", "1", "yes"):
            return []
        if time.time() < WinGetManifestService._circuit_open_until:
            return None or []

        try:
            cmd = ["winget", "search", query, "--accept-source-agreements"]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=4,
                encoding="utf-8",
                errors="replace"
            )
            if res.returncode != 0 or not res.stdout:
                return []

            WinGetManifestService._consecutive_failures = 0
            lines = res.stdout.splitlines()
            results: List[Tuple[str, str, str]] = []
            parsing_table = False

            for line in lines:
                if "---" in line and not parsing_table:
                    parsing_table = True
                    continue
                if parsing_table and line.strip():
                    parts = re.split(r"\s{2,}", line.strip())
                    if len(parts) >= 3:
                        name = parts[0].strip()
                        pkg_id = parts[1].strip()
                        ver = parts[2].strip()
                        results.append((name, pkg_id, ver))
            return results

        except subprocess.TimeoutExpired:
            WinGetManifestService._consecutive_failures += 1
            if WinGetManifestService._consecutive_failures >= 2:
                WinGetManifestService._circuit_open_until = time.time() + 300.0
                logger.warning("[WinGetManifestService] Circuit breaker tripped for winget CLI after 2 timeouts. Pausing live CLI calls for 300s.")
            else:
                logger.warning(f"[WinGetManifestService] Timeout running winget search for '{query}'")
            return []
        except Exception as e:
            logger.warning(f"[WinGetManifestService] Error searching winget for '{query}': {e}")
            return []

    def resolve_application(
        self,
        app_name: str,
        publisher: Optional[str] = None,
        version: Optional[str] = None
    ) -> Optional[WinGetManifest]:
        """
        End-to-end application matcher against WinGet metadata.
        1. Checks cache by package_id / normalized name.
        2. Tries exact package ID heuristics (e.g. Git.Git, Python.Python.3.11, Google.Chrome).
        3. Executes search query and evaluates top candidate.
        """
        if not self.enabled:
            return None

        # Clean search term
        clean_name = re.sub(r"\s*\((?:64-bit|32-bit|x64|x86)\)", "", app_name, flags=re.IGNORECASE).strip()
        clean_name = re.sub(r"\s+Development\s+Libraries.*", "", clean_name, flags=re.IGNORECASE).strip()
        clean_name = re.sub(r"\s+Standard\s+Library.*", "", clean_name, flags=re.IGNORECASE).strip()
        clean_name = re.sub(r"\s+Core\s+Interpreter.*", "", clean_name, flags=re.IGNORECASE).strip()
        clean_name = re.sub(r"\s+Utility\s+Scripts.*", "", clean_name, flags=re.IGNORECASE).strip()

        # Fast exit for non-Windows platforms/apps
        if re.search(r"\b(mac|macos|osx|linux|ubuntu|debian|rhel|centos|redhat|ios|android)\b", clean_name, re.IGNORECASE):
            return None

        # 1. Check persistent cache
        cached = self.get_cached_manifest_by_name(clean_name, publisher)
        if cached:
            return cached

        # 2. Heuristic common Package IDs
        known_pkg_ids = []
        name_lower = clean_name.lower()
        if "python 3.11" in name_lower:
            known_pkg_ids.append("Python.Python.3.11")
        elif "python 3.12" in name_lower:
            known_pkg_ids.append("Python.Python.3.12")
        elif "python 3.10" in name_lower:
            known_pkg_ids.append("Python.Python.3.10")
        elif "git" == name_lower:
            known_pkg_ids.append("Git.Git")
        elif "google chrome" in name_lower:
            known_pkg_ids.append("Google.Chrome")
        elif "mongodb compass" in name_lower:
            known_pkg_ids.append("MongoDB.Compass.Full")
        elif "mysql server" in name_lower:
            known_pkg_ids.append("Oracle.MySQLServer")
        elif "steam" == name_lower:
            known_pkg_ids.append("Valve.Steam")
        elif "docker desktop" in name_lower:
            known_pkg_ids.append("Docker.DockerDesktop")
        elif "visual studio code" in name_lower or "vs code" in name_lower:
            known_pkg_ids.append("Microsoft.VisualStudioCode")
        elif "7-zip" in name_lower or "7zip" in name_lower:
            known_pkg_ids.append("7zip.7zip")
        elif "vlc" in name_lower:
            known_pkg_ids.append("VideoLAN.VLC")
        elif "notepad++" in name_lower:
            known_pkg_ids.append("Notepad++.Notepad++")

        for pkg_id in known_pkg_ids:
            manifest = self.execute_winget_show(pkg_id)
            if manifest:
                return manifest

        # 3. Dynamic WinGet search
        search_query = clean_name
        search_results = self.execute_winget_search(search_query)
        if not search_results and publisher:
            search_results = self.execute_winget_search(f"{publisher} {clean_name}")

        if search_results:
            # Score candidates
            best_pkg_id = search_results[0][1]
            for cand_name, cand_id, cand_ver in search_results:
                if cand_name.lower() == clean_name.lower():
                    best_pkg_id = cand_id
                    break
                if publisher and publisher.lower() in cand_id.lower():
                    best_pkg_id = cand_id
                    break
            
            manifest = self.execute_winget_show(best_pkg_id)
            if manifest:
                return manifest

        return None

    @classmethod
    def apply_winget_enrichment(
        cls,
        record: Dict[str, Any],
        manifest: WinGetManifest,
        has_catalog_ground_truth: bool = False
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Applies WinGet manifest data to a record following the source priority hierarchy.
        Does NOT blindly overwrite verified catalog ground truth.
        Returns: (enriched_record, conflict_or_provenance_logs)
        """
        enriched = dict(record)
        logs: List[str] = []

        # Always attach WinGet Package ID
        enriched["winget_package_id"] = manifest.package_id

        # Ground truth preservation
        if has_catalog_ground_truth:
            # Enrich missing installer and package details only
            if manifest.installer_url and not enriched.get("installer_url"):
                enriched["installer_url"] = manifest.installer_url
                logs.append(f"[Provenance] installer_url enriched from winget:{manifest.package_id}")
            if manifest.installer_sha256 and not enriched.get("installer_sha256"):
                enriched["installer_sha256"] = manifest.installer_sha256
                logs.append(f"[Provenance] installer_sha256 enriched from winget:{manifest.package_id}")
            if not enriched.get("evidence_url") and manifest.license_url:
                enriched["evidence_url"] = manifest.license_url
                logs.append(f"[Provenance] evidence_url enriched from winget:{manifest.package_id}")
            
            # Check for conflict
            cat_model = enriched.get("license_model", "")
            if manifest.license and manifest.license.lower() not in cat_model.lower():
                enriched["conflict_status"] = "CONFLICT_PRESERVED"
                enriched["override_reason"] = f"Catalog verified '{cat_model}' retained over WinGet manifest license '{manifest.license}' for {manifest.package_id}."
                logs.append(f"[Conflict] Catalog verified '{cat_model}' retained over WinGet manifest license '{manifest.license}' for {manifest.package_id}.")
            else:
                enriched["conflict_status"] = "VERIFIED"
            return enriched, logs

        enriched["conflict_status"] = "VERIFIED"
        # Otherwise, WinGet acts as high-confidence ground truth
        if manifest.publisher and (not enriched.get("canonical_vendor") or enriched.get("canonical_vendor") in ("UNKNOWN", "", None)):
            enriched["canonical_vendor"] = manifest.publisher
            logs.append(f"[Provenance] canonical_vendor enriched from winget:{manifest.package_id}")

        if manifest.package_name and (not enriched.get("canonical_product") or enriched.get("canonical_product") in ("UNKNOWN", "", None)):
            enriched["canonical_product"] = manifest.package_name
            logs.append(f"[Provenance] canonical_product enriched from winget:{manifest.package_id}")

        if manifest.license_url and not enriched.get("evidence_url"):
            enriched["evidence_url"] = manifest.license_url
            logs.append(f"[Provenance] evidence_url set to WinGet LicenseUrl from {manifest.package_id}")

        if manifest.installer_url:
            enriched["installer_url"] = manifest.installer_url
        if manifest.installer_sha256:
            enriched["installer_sha256"] = manifest.installer_sha256

        # License mapping from manifest
        if manifest.license:
            lic_clean = manifest.license.strip()
            # If current license model is empty or unknown
            curr_model = enriched.get("license_model")
            if not curr_model or curr_model == "Unknown" or curr_model == "UNKNOWN":
                lic_lower = lic_clean.lower()
                if any(oss in lic_lower for oss in ["mit", "apache", "gpl", "bsd", "mpl", "psf", "sspl"]):
                    enriched["classification"] = "OPEN_SOURCE"
                    enriched["license_required"] = "NO"
                    enriched["license_metric"] = "No License Required"
                    if "mit" in lic_lower:
                        enriched["license_model"] = "MIT — Free/Open Source"
                    elif "apache" in lic_lower:
                        enriched["license_model"] = "Apache-2.0 — Free/Open Source"
                    elif "gpl-3" in lic_lower:
                        enriched["license_model"] = "GPL-3.0 — Free/Open Source"
                    elif "gpl" in lic_lower:
                        enriched["license_model"] = "GPL-2.0 — Free/Open Source"
                    elif "psf" in lic_lower:
                        enriched["license_model"] = "PSF License — Free/Open Source"
                    elif "sspl" in lic_lower:
                        enriched["license_model"] = "SSPL-1.0 — Free to Use"
                    else:
                        enriched["license_model"] = f"{lic_clean} — Free/Open Source"
                elif "freemium" in lic_lower or "in-app" in lic_lower or "subscription" in lic_lower:
                    enriched["classification"] = "FREE_AND_PAID"
                    enriched["license_required"] = "YES"
                    enriched["license_metric"] = "Users"
                    enriched["license_model"] = "Freemium / Subscription"
                elif "trial" in lic_lower:
                    enriched["classification"] = "TRIAL"
                    enriched["license_required"] = "YES"
                    enriched["license_metric"] = "Users"
                    enriched["license_model"] = "Trial / Subscription"
                elif "proprietary" in lic_lower or "commercial" in lic_lower or "eula" in lic_lower or "paid" in lic_lower:
                    enriched["classification"] = "COMMERCIAL"
                    enriched["license_required"] = "YES"
                    enriched["license_metric"] = "Users"
                    enriched["license_model"] = "Commercial — Subscription"
                elif "freeware" in lic_lower or "free" in lic_lower:
                    enriched["classification"] = "FREEWARE"
                    enriched["license_required"] = "NO"
                    enriched["license_metric"] = "No License Required"
                    enriched["license_model"] = "Freeware"
                else:
                    enriched["license_model"] = lic_clean

                enriched["confidence"] = "HIGH"
                enriched["source_type"] = "WINGET"
                enriched["reliability_score"] = 96.0
                logs.append(f"[Provenance] license_model resolved as '{enriched.get('license_model')}' via winget:{manifest.package_id}")

        return enriched, logs
