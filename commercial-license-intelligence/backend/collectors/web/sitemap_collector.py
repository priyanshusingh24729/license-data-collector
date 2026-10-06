"""
Sitemap and robots.txt Discovery Collector.
Discovers and filters licensing, pricing, and terms pages from vendor sitemaps.
"""

import logging
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
from typing import List, Optional, Set
import httpx

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)

# Keywords in URL paths that indicate licensing relevance
LICENSING_PATH_KEYWORDS = [
    "licensing",
    "license",
    "terms",
    "eula",
    "pricing",
    "legal",
    "subscriptions",
    "subscription",
    "product-terms",
    "agreements",
    "commercial-terms",
]


class SitemapCollector:
    """
    Parses robots.txt and sitemaps to discover authoritative licensing and terms URLs.
    """

    def __init__(self, timeout_seconds: float = 8.0):
        settings = get_settings()
        self.timeout_seconds = timeout_seconds or getattr(settings, "WEB_COLLECTOR_TIMEOUT_SECONDS", 10.0)
        self.user_agent = getattr(
            settings,
            "WEB_COLLECTOR_USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        self.max_urls = getattr(settings, "MAX_SITEMAP_URLS_TO_EVALUATE", 25)

    def _get_base_domain_url(self, url: str) -> str:
        parsed = urlparse(url)
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc
        return f"{scheme}://{netloc}"

    def discover_sitemap_urls_from_robots(self, base_url: str) -> List[str]:
        """Parses robots.txt to discover declared Sitemap URLs."""
        robots_url = urljoin(base_url, "/robots.txt")
        sitemaps: List[str] = []
        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True, headers={"User-Agent": self.user_agent}) as client:
                resp = client.get(robots_url)
                if resp.status_code == 200 and resp.text:
                    for line in resp.text.splitlines():
                        clean = line.strip()
                        if clean.lower().startswith("sitemap:"):
                            parts = clean.split(":", 1)
                            if len(parts) == 2 and parts[1].strip():
                                sitemaps.append(parts[1].strip())
        except Exception as e:
            logger.debug(f"[SitemapCollector] robots.txt check failed for {robots_url}: {e}")

        # Fallback to standard sitemap.xml if none declared
        if not sitemaps:
            sitemaps.append(urljoin(base_url, "/sitemap.xml"))

        return sitemaps

    def fetch_and_filter_sitemap(self, sitemap_url: str, depth: int = 0) -> List[str]:
        """
        Fetches an XML sitemap (or sitemap index) and returns URLs matching licensing keywords.
        Recurses up to depth 1 for sitemap indices.
        """
        matched_urls: Set[str] = set()
        if depth > 1:
            return []

        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True, headers={"User-Agent": self.user_agent}) as client:
                resp = client.get(sitemap_url)
                if resp.status_code != 200 or not resp.text:
                    return []

                # Parse XML
                root = ET.fromstring(resp.content)
                # Strip XML namespace if present
                tag_name = root.tag.split("}")[-1] if "}" in root.tag else root.tag

                # 1. Sitemap Index (<sitemapindex><sitemap><loc>...</loc></sitemap></sitemapindex>)
                if tag_name == "sitemapindex":
                    child_sitemaps = []
                    for sitemap_node in root:
                        for child in sitemap_node:
                            c_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                            if c_tag == "loc" and child.text:
                                c_url = child.text.strip()
                                # Only follow child sitemaps that might contain pages/legal
                                if any(k in c_url.lower() for k in ["page", "legal", "main", "en", "doc", "default"]):
                                    child_sitemaps.append(c_url)

                    for cs in child_sitemaps[:3]:  # Limit child sitemap traversal
                        sub_matches = self.fetch_and_filter_sitemap(cs, depth=depth + 1)
                        matched_urls.update(sub_matches)
                        if len(matched_urls) >= self.max_urls:
                            break

                # 2. Standard URL set (<urlset><url><loc>...</loc></url></urlset>)
                elif tag_name == "urlset":
                    for url_node in root:
                        for child in url_node:
                            c_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                            if c_tag == "loc" and child.text:
                                loc = child.text.strip()
                                loc_lower = loc.lower()
                                if any(f"/{kw}" in loc_lower or f"-{kw}" in loc_lower or f"/{kw}/" in loc_lower for kw in LICENSING_PATH_KEYWORDS):
                                    matched_urls.add(loc)
                                if len(matched_urls) >= self.max_urls:
                                    break

        except Exception as e:
            logger.debug(f"[SitemapCollector] Sitemap fetch error for {sitemap_url}: {e}")

        return sorted(list(matched_urls))[:self.max_urls]

    def discover_licensing_urls(self, target_url_or_domain: str) -> List[str]:
        """
        High-level entry point: finds sitemaps from robots.txt and returns filtered licensing URLs.
        """
        base_url = self._get_base_domain_url(target_url_or_domain)
        sitemap_candidates = self.discover_sitemap_urls_from_robots(base_url)
        all_discovered: Set[str] = set()

        for sm in sitemap_candidates[:2]:
            urls = self.fetch_and_filter_sitemap(sm)
            all_discovered.update(urls)
            if len(all_discovered) >= self.max_urls:
                break

        return sorted(list(all_discovered))[:self.max_urls]

    # Alias for discovery engine integration
    discover_licensing_sitemap_urls = discover_licensing_urls
