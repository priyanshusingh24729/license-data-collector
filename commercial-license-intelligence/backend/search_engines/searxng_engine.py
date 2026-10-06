"""SearXNG metasearch engine adapter."""

import logging
from typing import List, Dict, Optional
import httpx

from backend.search_engines.base import SearchEngine

logger = logging.getLogger(__name__)


class SearXNGEngine(SearchEngine):
    """Primary metasearch engine adapter querying local SearXNG."""
    name: str = "searxng"

    def __init__(self, base_url: str = "http://127.0.0.1:8080"):
        self.base_url = base_url.strip().rstrip("/")

    def search(
        self,
        query: str,
        official_domains: Optional[List[str]] = None,
        timeout: int = 8
    ) -> List[Dict[str, str]]:
        """
        Queries SearXNG JSON API, normalizes results, and applies domain whitelist.
        """
        search_url = f"{self.base_url}/search"
        params = {
            "q": query,
            "format": "json",
            "pageno": 1,
        }

        is_local = "127.0.0.1" in self.base_url or "localhost" in self.base_url
        connect_to = 0.3 if is_local else 2.0
        client_timeout = httpx.Timeout(float(timeout), connect=connect_to)

        with httpx.Client(timeout=client_timeout) as client:
            response = client.get(search_url, params=params)
            response.raise_for_status()
            data = response.json()

        raw_results = data.get("results", [])
        normalized: List[Dict[str, str]] = []

        for item in raw_results:
            url = item.get("url", "")
            if not url:
                continue
            normalized.append({
                "title": item.get("title", ""),
                "url": url,
                "snippet": item.get("content", "") or item.get("title", ""),
            })

        filtered = self.filter_by_domains(normalized, official_domains)
        logger.info(f"[{self.name}] Found {len(normalized)} raw results, {len(filtered)} matching official domains.")
        return filtered
