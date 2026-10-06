"""DuckDuckGo HTML scraper engine adapter for zero-setup, zero-cost search fallback."""

import logging
import re
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs, unquote
import httpx
from bs4 import BeautifulSoup

from backend.search_engines.base import SearchEngine

logger = logging.getLogger(__name__)


class DuckDuckGoEngine(SearchEngine):
    """Tertiary search fallback scraping html.duckduckgo.com/html/."""
    name: str = "duckduckgo"

    SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/"
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )

    def __init__(self, user_agent: Optional[str] = None):
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT

    @classmethod
    def _extract_target_url(cls, raw_href: str) -> str:
        """
        Extracts the destination URL from DuckDuckGo redirect wrapper links
        (e.g., //duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.adobe.com&rut=...).
        """
        if not raw_href:
            return ""

        href = raw_href.strip()
        if href.startswith("//"):
            href = "https:" + href

        # If wrapped in uddg parameter
        if "duckduckgo.com/l/?" in href and "uddg=" in href:
            parsed = urlparse(href)
            qs = parse_qs(parsed.query)
            if "uddg" in qs and qs["uddg"]:
                return unquote(qs["uddg"][0])

        return href

    def search(
        self,
        query: str,
        official_domains: Optional[List[str]] = None,
        timeout: int = 4
    ) -> List[Dict[str, str]]:
        """
        Scrapes DuckDuckGo HTML results, unpacks destination links,
        extracts titles and snippets, and applies domain whitelist.
        """
        logger.info(f"[{self.name}] Scraping DuckDuckGo HTML for '{query}'...")
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://html.duckduckgo.com/",
        }
        data = {"q": query}

        client_timeout = httpx.Timeout(float(timeout), connect=1.5)
        try:
            with httpx.Client(timeout=client_timeout, follow_redirects=True) as client:
                response = client.post(self.SEARCH_ENDPOINT, data=data, headers=headers)
                response.raise_for_status()
                html_content = response.text
        except Exception as e:
            logger.warning(f"[{self.name}] HTTP request to DuckDuckGo failed: {e}")
            raise

        try:
            soup = BeautifulSoup(html_content, "html.parser")
            results: List[Dict[str, str]] = []

            # DuckDuckGo HTML format uses .result or .web-result divs
            result_nodes = soup.find_all("div", class_=re.compile(r"result\b|results_links"))
            if not result_nodes:
                result_nodes = soup.select(".result__body") or soup.select(".links_main")

            for node in result_nodes:
                link_elem = node.select_one("a.result__a, .result__title a, h2 a, a[href]")
                if not link_elem:
                    continue

                raw_href = link_elem.get("href", "")
                final_url = self._extract_target_url(raw_href)

                if not final_url or not final_url.startswith("http"):
                    continue

                title = link_elem.get_text(strip=True)
                snippet_elem = node.select_one(".result__snippet, .snippet")
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else title

                results.append({
                    "title": title,
                    "url": final_url,
                    "snippet": snippet,
                })

            filtered = self.filter_by_domains(results, official_domains)
            logger.info(f"[{self.name}] Scraped {len(results)} raw results, {len(filtered)} matching official domains.")
            return filtered

        except Exception as parse_err:
            logger.error(f"[{self.name}] Failed to parse DuckDuckGo HTML response: {parse_err}")
            raise
