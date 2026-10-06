"""
llms.txt Discovery Collector.
Probes vendor domains for the emerging /llms.txt and /llms-full.txt standards
to extract pristine Markdown documentation, licensing links, and product terms.
"""

import logging
import re
from urllib.parse import urlparse, urljoin
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import httpx

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LlmsTxtResult:
    """Structured output from llms.txt discovery."""
    source_url: str
    content_raw: str
    licensing_links: List[str] = field(default_factory=list)
    licensing_sections: List[str] = field(default_factory=list)
    has_llms_txt: bool = False

    @property
    def is_available(self) -> bool:
        return self.has_llms_txt

    @property
    def url(self) -> str:
        return self.source_url

    @property
    def extracted_links(self) -> List[tuple]:
        return [(l, "") for l in self.licensing_links]


class LlmsTxtCollector:
    """
    Checks for and parses llms.txt files on vendor domains.
    """

    def __init__(self, timeout_seconds: float = 6.0):
        settings = get_settings()
        self.timeout_seconds = timeout_seconds or 6.0
        self.user_agent = getattr(
            settings,
            "WEB_COLLECTOR_USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )

    def _get_base_domain_url(self, url: str) -> str:
        parsed = urlparse(url)
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc
        return f"{scheme}://{netloc}"

    def check_llms_txt(self, base_url_or_domain: str) -> Optional[LlmsTxtResult]:
        """
        Probes /llms.txt and /llms-full.txt on the given domain.
        Returns parsed links and licensing sections if found.
        """
        base_url = self._get_base_domain_url(base_url_or_domain)
        probe_paths = ["/llms.txt", "/llms-full.txt"]

        for path in probe_paths:
            target_url = urljoin(base_url, path)
            try:
                with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True, headers={"User-Agent": self.user_agent}) as client:
                    resp = client.get(target_url)
                    # Must be 200 and return plain text or markdown (not an HTML 404 error page)
                    content_type = resp.headers.get("content-type", "").lower()
                    if resp.status_code == 200 and resp.text and ("text/plain" in content_type or "text/markdown" in content_type or not ("<html" in resp.text.lower()[:200])):
                        text = resp.text
                        if len(text.strip()) > 30 and not ("page not found" in text.lower()[:200] or "404" in text.lower()[:200]):
                            return self._parse_llms_content(target_url, text)
            except Exception as e:
                logger.debug(f"[LlmsTxtCollector] Failed probe for {target_url}: {e}")

        return None

    # Alias for discovery engine integration
    discover = check_llms_txt

    def _parse_llms_content(self, source_url: str, text: str) -> LlmsTxtResult:
        """Parses llms.txt markdown for licensing links and relevant sections."""
        licensing_links: List[str] = []
        licensing_sections: List[str] = []

        # Find markdown links: [Title](URL)
        link_matches = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', text)
        for title, link in link_matches:
            combined = f"{title} {link}".lower()
            if any(k in combined for k in ["license", "licensing", "terms", "eula", "pricing", "legal", "subscription"]):
                licensing_links.append(link)

        # Also find plain URLs
        plain_urls = re.findall(r'https?://[^\s\)]+', text)
        for u in plain_urls:
            u_clean = u.rstrip(".,;:")
            if u_clean not in licensing_links:
                if any(k in u_clean.lower() for k in ["licensing", "license", "eula", "terms"]):
                    licensing_links.append(u_clean)

        # Extract sections mentioning licensing
        sections = text.split("\n## ")
        for sec in sections:
            sec_lower = sec.lower()
            if any(k in sec_lower for k in ["license", "licensing", "commercial terms", "pricing model", "subscription"]):
                licensing_sections.append(sec.strip())

        return LlmsTxtResult(
            source_url=source_url,
            content_raw=text,
            licensing_links=licensing_links[:10],
            licensing_sections=licensing_sections[:5],
            has_llms_txt=True,
        )
