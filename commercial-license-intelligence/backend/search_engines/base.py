"""Abstract base class and domain filtering helpers for search engine adapters."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse
from pathlib import Path
import yaml
import logging

logger = logging.getLogger(__name__)


def load_official_domains(yaml_path: Optional[str] = None) -> List[str]:
    """Loads authoritative vendor domains from official_domains.yaml."""
    if not yaml_path:
        default_path = Path(__file__).resolve().parent.parent.parent / "official_domains.yaml"
        yaml_path = str(default_path)

    p = Path(yaml_path)
    if not p.exists():
        return []

    try:
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("official_domains", []) or []
    except Exception as e:
        logger.warning(f"Could not load official domains from {yaml_path}: {e}")
        return []


class SearchEngine(ABC):
    """Abstract base class for all search engine implementations."""
    name: str = "base"

    @abstractmethod
    def search(
        self,
        query: str,
        official_domains: Optional[List[str]] = None,
        timeout: int = 8
    ) -> List[Dict[str, str]]:
        """
        Returns list of {"title": str, "url": str, "snippet": str}.
        Raises an exception on connection failure, timeout, or server error.
        """
        pass

    @staticmethod
    def is_url_in_domains(url: str, official_domains: Optional[List[str]]) -> bool:
        """Verifies if candidate URL hostname matches any domain in the whitelist."""
        if not official_domains:
            return True
        if not url:
            return False
        try:
            netloc = urlparse(url.strip()).netloc.lower().split(":")[0]
            if netloc.startswith("www."):
                netloc = netloc[4:]
            for domain in official_domains:
                d = domain.lower().strip()
                if d.startswith("www."):
                    d = d[4:]
                if netloc == d or netloc.endswith(f".{d}"):
                    return True
            return False
        except Exception:
            return False

    @classmethod
    def filter_by_domains(
        cls,
        results: List[Dict[str, str]],
        official_domains: Optional[List[str]]
    ) -> List[Dict[str, str]]:
        """Filters results to include only those within official domains."""
        if not official_domains:
            return results
        return [r for r in results if cls.is_url_in_domains(r.get("url", ""), official_domains)]
