"""YaCy peer-to-peer search engine adapter."""

import logging
from typing import List, Dict, Optional, Any
import httpx

from backend.search_engines.base import SearchEngine

logger = logging.getLogger(__name__)


class YaCyEngine(SearchEngine):
    """Secondary search engine adapter querying self-hosted YaCy instance."""
    name: str = "yacy"

    def __init__(self, base_url: str = "http://127.0.0.1:8090"):
        self.base_url = base_url.strip().rstrip("/")

    def search(
        self,
        query: str,
        official_domains: Optional[List[str]] = None,
        timeout: int = 8
    ) -> List[Dict[str, str]]:
        """
        Queries YaCy search API (/yacysearch.json), parses channel items,
        normalizes results, and applies official domain whitelist.
        """
        search_url = f"{self.base_url}/yacysearch.json"
        params: Dict[str, Any] = {
            "query": query,
            "maximumRecords": 10,
            "resource": "global",
            "verify": "false",
        }

        # If domain whitelist is provided, append site restrictions if supported
        is_local = "127.0.0.1" in self.base_url or "localhost" in self.base_url
        connect_to = 0.3 if is_local else 2.0
        client_timeout = httpx.Timeout(float(timeout), connect=connect_to)

        with httpx.Client(timeout=client_timeout) as client:
            response = client.get(search_url, params=params)
            response.raise_for_status()
            data = response.json()

        normalized: List[Dict[str, str]] = []
        channels = data.get("channels", [])

        for channel in channels:
            # YaCy returns items as either 'items' or 'item'
            items = channel.get("items") or channel.get("item") or []
            if isinstance(items, dict):
                items = [items]

            for item in items:
                link = item.get("link") or item.get("url", "")
                if not link:
                    continue
                normalized.append({
                    "title": item.get("title", ""),
                    "url": link,
                    "snippet": item.get("description", "") or item.get("snippet", "") or item.get("title", ""),
                })

        filtered = self.filter_by_domains(normalized, official_domains)
        logger.info(f"[{self.name}] Found {len(normalized)} raw results, {len(filtered)} matching official domains.")
        return filtered
