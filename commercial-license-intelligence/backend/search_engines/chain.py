"""Search engine fallback chain orchestrator with retries, circuit breaking, and telemetry."""

import logging
import time
from typing import List, Dict, Optional, Any
import httpx
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from backend.search_engines.base import SearchEngine, load_official_domains
from backend.search_engines.searxng_engine import SearXNGEngine
from backend.search_engines.yacy_engine import YaCyEngine
from backend.search_engines.duckduckgo_engine import DuckDuckGoEngine

logger = logging.getLogger(__name__)


class SearchEngineError(Exception):
    """Base exception for search engine failures."""
    pass


class NoResultsFoundError(SearchEngineError):
    """Raised when an engine returns zero results after domain filtering."""
    pass


import os
import sqlite3
import datetime

def _get_db_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
        "license_intelligence.db"
    )

def _init_circuit_breaker_db(db_path: Optional[str] = None):
    try:
        path = db_path or _get_db_path()
        if os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        with sqlite3.connect(path, timeout=5) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS circuit_breaker_states (
                    engine_name TEXT PRIMARY KEY,
                    is_tripped INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    cooldown_expiry REAL DEFAULT 0.0,
                    cooldown_expiry_iso TEXT,
                    updated_at TEXT
                )
            """)
            conn.commit()
    except Exception as e:
        logger.debug(f"Circuit breaker DB init warning: {e}")


class SearchEngineChain:
    """
    Orchestrates search execution across an ordered fallback chain of engines:
    SearXNG -> YaCy -> DuckDuckGo HTML.

    Features:
    - Automatic fallback on connection error, timeout, or zero results after domain filtering.
    - 1-retry with backoff per engine before advancing to the next.
    - Sliding-window circuit breaker skipping chronically failing engines for a cooldown period.
    - Telemetry logging of which engine resolved each query.
    - Persisted, queryable circuit breaker state exposed via API telemetry.
    """

    def __init__(
        self,
        engines: Optional[List[SearchEngine]] = None,
        official_domains: Optional[List[str]] = None,
        max_retries_per_engine: int = 1,
        circuit_failure_threshold: int = 3,
        circuit_cooldown_seconds: int = 300,
        searxng_url: str = "http://127.0.0.1:8080",
        yacy_url: str = "http://127.0.0.1:8090",
    ):
        self.official_domains = official_domains if official_domains is not None else load_official_domains()
        self.max_retries_per_engine = max_retries_per_engine
        self.circuit_failure_threshold = circuit_failure_threshold
        self.circuit_cooldown_seconds = circuit_cooldown_seconds

        if engines is not None:
            self.engines = engines
        else:
            self.engines = [
                SearXNGEngine(base_url=searxng_url),
                YaCyEngine(base_url=yacy_url),
                DuckDuckGoEngine(),
            ]

        # Circuit breaker state: engine_name -> list of failure timestamps
        self._failures: Dict[str, List[float]] = {e.name: [] for e in self.engines}
        # Circuit breaker trip until timestamp: engine_name -> float
        self._circuit_tripped_until: Dict[str, float] = {e.name: 0.0 for e in self.engines}

        # Fast port reachability probe for local engines (SearXNG, YaCy)
        import socket
        from urllib.parse import urlparse
        for e in self.engines:
            if hasattr(e, "base_url") and ("127.0.0.1" in getattr(e, "base_url", "") or "localhost" in getattr(e, "base_url", "")):
                try:
                    parsed = urlparse(e.base_url)
                    port = parsed.port or (80 if parsed.scheme == "http" else 443)
                    with socket.create_connection((parsed.hostname or "127.0.0.1", port), timeout=0.08):
                        pass
                except Exception:
                    self._circuit_tripped_until[e.name] = time.time() + 3600
                    logger.info(f"[SearchChain] Local engine '{e.name}' at {e.base_url} is offline. Fast-tripping circuit breaker.")

        # Initialize persistent store and write initial states
        _init_circuit_breaker_db()
        for e in self.engines:
            self._persist_state(e.name)

        # Telemetry metrics
        self.metrics = {
            "total_queries": 0,
            "engine_success_counts": {e.name: 0 for e in self.engines},
            "engine_failure_counts": {e.name: 0 for e in self.engines},
            "cross_validated_agreements": 0,
            "all_engines_failed_count": 0,
        }

    def _persist_state(self, engine_name: str):
        """Persists the engine's current circuit breaker state to queryable storage."""
        now = time.time()
        tripped_until = self._circuit_tripped_until.get(engine_name, 0.0)
        is_tripped = now < tripped_until
        failure_count = len(self._failures.get(engine_name, []))
        cooldown_iso = (
            datetime.datetime.fromtimestamp(tripped_until, tz=datetime.timezone.utc).isoformat()
            if is_tripped else None
        )
        updated_at_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        try:
            db_path = _get_db_path()
            with sqlite3.connect(db_path, timeout=5) as conn:
                conn.execute("""
                    INSERT INTO circuit_breaker_states (
                        engine_name, is_tripped, failure_count, cooldown_expiry, cooldown_expiry_iso, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(engine_name) DO UPDATE SET
                        is_tripped = excluded.is_tripped,
                        failure_count = excluded.failure_count,
                        cooldown_expiry = excluded.cooldown_expiry,
                        cooldown_expiry_iso = excluded.cooldown_expiry_iso,
                        updated_at = excluded.updated_at
                """, (
                    engine_name,
                    1 if is_tripped else 0,
                    failure_count,
                    round(tripped_until, 2) if is_tripped else 0.0,
                    cooldown_iso,
                    updated_at_iso,
                ))
                conn.commit()
        except Exception as e:
            logger.debug(f"Could not persist circuit breaker state for {engine_name}: {e}")

    def get_circuit_breaker_states(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns the queryable circuit breaker state for all engines:
        which engine is currently tripped, failure count, and cooldown expiry.
        """
        states = {}
        now = time.time()
        for engine in self.engines:
            tripped_until = self._circuit_tripped_until.get(engine.name, 0.0)
            is_tripped = now < tripped_until
            failure_count = len(self._failures.get(engine.name, []))
            cooldown_iso = (
                datetime.datetime.fromtimestamp(tripped_until, tz=datetime.timezone.utc).isoformat()
                if is_tripped else None
            )
            states[engine.name] = {
                "is_tripped": is_tripped,
                "failure_count": failure_count,
                "cooldown_expiry": round(tripped_until, 2) if is_tripped else None,
                "cooldown_expiry_iso": cooldown_iso,
            }
        return states

    @classmethod
    def get_persisted_states(cls, db_path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Directly queries the persistent store for circuit breaker states.
        Queryable across processes without requiring an active in-memory chain.
        """
        states = {}
        try:
            path = db_path or _get_db_path()
            if os.path.exists(path):
                now = time.time()
                with sqlite3.connect(path, timeout=5) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT engine_name, is_tripped, failure_count, cooldown_expiry, cooldown_expiry_iso FROM circuit_breaker_states"
                    )
                    for row in cursor.fetchall():
                        eng, tripped_val, f_cnt, cd_exp, cd_iso = row
                        is_tripped = bool(tripped_val) and (now < cd_exp if cd_exp else False)
                        states[eng] = {
                            "is_tripped": is_tripped,
                            "failure_count": f_cnt,
                            "cooldown_expiry": round(cd_exp, 2) if is_tripped else None,
                            "cooldown_expiry_iso": cd_iso if is_tripped else None,
                        }
        except Exception as e:
            logger.debug(f"Could not read persisted circuit breaker states: {e}")
        return states

    def is_circuit_broken(self, engine_name: str) -> bool:
        """Checks if an engine's circuit breaker is currently open (tripped)."""
        now = time.time()
        if now < self._circuit_tripped_until.get(engine_name, 0.0):
            return True

        # Purge failure timestamps older than the cooldown window
        window_start = now - self.circuit_cooldown_seconds
        self._failures[engine_name] = [
            t for t in self._failures.get(engine_name, []) if t >= window_start
        ]

        if len(self._failures[engine_name]) >= self.circuit_failure_threshold:
            self._circuit_tripped_until[engine_name] = now + self.circuit_cooldown_seconds
            self._persist_state(engine_name)
            logger.warning(
                f"[CircuitBreaker] Engine '{engine_name}' exceeded {self.circuit_failure_threshold} failures "
                f"in {self.circuit_cooldown_seconds}s. Tripping circuit until {now + self.circuit_cooldown_seconds:.0f}."
            )
            return True

        # If it was previously tripped but cooldown has expired
        if self._circuit_tripped_until.get(engine_name, 0.0) > 0.0:
            self._circuit_tripped_until[engine_name] = 0.0
            self._persist_state(engine_name)

        return False

    def record_failure(self, engine_name: str):
        """Records a failure timestamp for the specified engine."""
        now = time.time()
        if engine_name not in self._failures:
            self._failures[engine_name] = []
        self._failures[engine_name].append(now)

        if engine_name in self.metrics.get("engine_failure_counts", {}):
            self.metrics["engine_failure_counts"][engine_name] += 1

        window_start = now - self.circuit_cooldown_seconds
        self._failures[engine_name] = [
            t for t in self._failures[engine_name] if t >= window_start
        ]

        if len(self._failures[engine_name]) >= self.circuit_failure_threshold:
            self._circuit_tripped_until[engine_name] = now + self.circuit_cooldown_seconds
            logger.warning(
                f"[CircuitBreaker] Tripped for engine '{engine_name}' after {len(self._failures[engine_name])} failures. "
                f"Cooling down for {self.circuit_cooldown_seconds}s."
            )
        self._persist_state(engine_name)

    def record_success(self, engine_name: str):
        """Resets the failure counter on a successful query."""
        self._failures[engine_name] = []
        self._circuit_tripped_until[engine_name] = 0.0
        if engine_name in self.metrics["engine_success_counts"]:
            self.metrics["engine_success_counts"][engine_name] += 1
        self._persist_state(engine_name)

    def _execute_single_engine(
        self,
        engine: SearchEngine,
        query: str,
        official_domains: Optional[List[str]],
        timeout: int
    ) -> List[Dict[str, str]]:
        """
        Executes search on a single engine with 1-retry backoff on failure or empty results.
        """
        attempts = 1 + self.max_retries_per_engine
        last_exception: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            try:
                results = engine.search(query, official_domains=official_domains, timeout=timeout)
                if not results:
                    raise NoResultsFoundError(f"Engine '{engine.name}' returned 0 results after domain filtering.")
                return results
            except Exception as ex:
                last_exception = ex
                # Fast fail on unreachable local ports and on 0 results without waiting for useless retries
                if isinstance(ex, (httpx.ConnectError, httpx.ConnectTimeout, NoResultsFoundError)):
                    break
                if attempt < attempts:
                    logger.info(
                        f"[{engine.name}] Attempt {attempt} failed ({ex}). Retrying in 0.5s before fallback..."
                    )
                    time.sleep(0.5)

        # If all attempts for this engine failed:
        if last_exception:
            raise last_exception
        raise NoResultsFoundError(f"Engine '{engine.name}' returned no results.")

    def search(
        self,
        query: str,
        official_domains: Optional[List[str]] = None,
        timeout: int = 8,
        enable_cross_validation: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Executes query along the search chain: SearXNG -> YaCy -> DuckDuckGo.
        Falls back upon connection error, timeout, or zero results after domain filtering.
        Performs cross-validation when both SearXNG and YaCy find results for the target product.
        """
        self.metrics["total_queries"] += 1
        domains_to_use = official_domains if official_domains is not None else self.official_domains

        # Fast path: If all engines are already circuit-broken, return immediately without network overhead
        if all(self.is_circuit_broken(engine.name) for engine in self.engines):
            self.metrics["all_engines_failed_count"] += 1
            return []

        for engine in self.engines:
            if self.is_circuit_broken(engine.name):
                logger.info(f"[SearchChain] Skipping '{engine.name}' (circuit breaker is OPEN).")
                continue

            try:
                results = self._execute_single_engine(
                    engine=engine,
                    query=query,
                    official_domains=domains_to_use,
                    timeout=timeout
                )
                self.record_success(engine.name)

                # Cross-validation: If SearXNG succeeded and YaCy is available, check agreement
                if engine.name == "searxng" and enable_cross_validation and len(self.engines) >= 2:
                    yacy_engine = self.engines[1]
                    if yacy_engine.name == "yacy" and not self.is_circuit_broken(yacy_engine.name):
                        try:
                            yacy_results = yacy_engine.search(query, official_domains=domains_to_use, timeout=min(timeout, 3))
                            if yacy_results:
                                from urllib.parse import urlparse
                                s_domains = {urlparse(r.get("url", "")).netloc.lower().replace("www.", "") for r in results if r.get("url")}
                                y_domains = {urlparse(r.get("url", "")).netloc.lower().replace("www.", "") for r in yacy_results if r.get("url")}
                                agreed = s_domains.intersection(y_domains)
                                if agreed:
                                    for r in results:
                                        r["cross_validated"] = True
                                        r["agreement_engines"] = ["searxng", "yacy"]
                                    self.metrics["cross_validated_agreements"] += 1
                                    logger.info(f"✓ [SearchChain] Cross-validation agreement between SearXNG & YaCy on {agreed}")
                        except Exception:
                            pass

                logger.info(
                    f"✓ [SearchChain] Query '{query}' successfully resolved by '{engine.name}' "
                    f"({len(results)} authoritative results found)."
                )
                return results

            except Exception as err:
                self.record_failure(engine.name)
                logger.warning(
                    f"⚠ [SearchChain] Engine '{engine.name}' failed for '{query}': {err}. "
                    f"Falling back to next engine in chain..."
                )

        self.metrics["all_engines_failed_count"] += 1
        logger.error(
            f"❌ [SearchChain] All search engines in fallback chain ({[e.name for e in self.engines]}) "
            f"failed or returned zero results for query: '{query}'."
        )
        return []
