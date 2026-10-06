"""
Search Provider Abstraction & Implementations for License Source Discovery.
Allows swapping search backends (DuckDuckGo, SerpAPI, Google, Dev/Mock) without
modifying discovery engine business logic.
"""

import logging
import time
import re
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import httpx

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """Normalized search result item."""
    url: str
    title: str
    snippet: Optional[str] = None
    engine: str = "unknown"
    rank: int = 1
    cross_validated: bool = False


class SearchProvider(ABC):
    """Abstract interface for external search providers."""

    @abstractmethod
    def is_available(self) -> bool:
        """Returns whether the search provider is properly configured and operational."""
        pass

    @abstractmethod
    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """Executes a search query and returns normalized search results."""
        pass

    def search_official_domain(
        self,
        query: str,
        domain: str,
        num_results: int = 10
    ) -> List[SearchResult]:
        """Executes a domain-restricted search query (site:<domain> query)."""
        domain_query = f"site:{domain} {query}"
        return self.search(domain_query, num_results=num_results)


class DevSearchProvider(SearchProvider):
    """
    High-fidelity development & testing search provider.
    Returns authentic, verified official documentation URLs for common commercial software targets
    when no paid external search API key is configured.
    """

    # Realistic mock search index of authoritative public vendor documentation URLs
    KNOWN_INDEX: List[Dict[str, Any]] = [
        # Adobe Acrobat Pro
        {
            "url": "https://www.adobe.com/legal/licenses-terms.html",
            "title": "Adobe Product Specific Licensing Terms",
            "snippet": "Official enterprise licensing terms, virtualization rules, and metrics for Adobe Acrobat and Creative Cloud.",
            "keywords": ["adobe", "acrobat", "pro", "2025", "licensing", "terms", "product terms"],
            "required_product": "acrobat",
        },
        {
            "url": "https://helpx.adobe.com/acrobat/kb/acrobat-licensing-faq.html",
            "title": "Adobe Acrobat Licensing FAQ & Serialized Deployment",
            "snippet": "Licensing FAQ for Acrobat Pro 2025, named user licensing, single-user access, and volume deployment.",
            "keywords": ["adobe", "acrobat", "pro", "2025", "licensing", "faq", "guide"],
            "required_product": "acrobat",
        },
        {
            "url": "https://www.adobe.com/legal/terms.html",
            "title": "Adobe General Terms of Use",
            "snippet": "General commercial terms governing all Adobe software offerings, user entitlements, and cloud services.",
            "keywords": ["adobe", "terms", "general terms", "eula"],
            "required_product": "adobe",
        },
        {
            "url": "https://helpx.adobe.com/enterprise/using/licensing.html",
            "title": "Creative Cloud and Acrobat Enterprise Licensing Models",
            "snippet": "Guide to enterprise licensing models: Named User Licensing, Shared Device, and Feature Restricted licensing.",
            "keywords": ["adobe", "acrobat", "creative cloud", "enterprise", "licensing"],
            "required_product": "acrobat",
        },
        {
            "url": "https://www.adobe.com/products/acrobatpro/pricing.html",
            "title": "Adobe Acrobat Pro Plans & Pricing",
            "snippet": "Subscription pricing, team editions, and commercial license options for Acrobat Pro.",
            "keywords": ["adobe", "acrobat", "pro", "pricing", "subscription"],
            "required_product": "acrobat",
        },
        {
            "url": "https://www.adobe.com/content/dam/cc/en/legal/documents/enterprise-licensing-guide.pdf",
            "title": "Adobe Enterprise Software Licensing Guide (PDF)",
            "snippet": "Comprehensive PDF guide detailing core licensing rules and virtualization deployment rights for Adobe products.",
            "keywords": ["adobe", "licensing", "guide", "pdf", "product terms"],
            "required_product": "acrobat",
        },

        # Microsoft SQL Server & Windows Server
        {
            "url": "https://www.microsoft.com/licensing/terms/welcome/welcome-page",
            "title": "Microsoft Commercial Product Terms Site",
            "snippet": "Master repository of Microsoft Product Terms, Universal License Terms, and core licensing definitions.",
            "keywords": ["microsoft", "product terms", "licensing", "terms", "sql server", "windows server"],
            "required_product": "microsoft",
        },
        {
            "url": "https://www.microsoft.com/licensing/docs/view/SQL-Server",
            "title": "Microsoft SQL Server Licensing Guide",
            "snippet": "Official licensing guide for SQL Server core-based licensing, Server+CAL, and virtual machine mobility.",
            "keywords": ["microsoft", "sql server", "licensing", "guide", "core"],
            "required_product": "sql",
        },
        {
            "url": "https://www.microsoft.com/licensing/docs/view/Windows-Server",
            "title": "Microsoft Windows Server Licensing Guide",
            "snippet": "Physical core licensing models, virtual OSE rights, and client access licenses for Windows Server Standard and Datacenter.",
            "keywords": ["microsoft", "windows server", "licensing", "guide"],
            "required_product": "windows server",
        },

        # Autodesk AutoCAD
        {
            "url": "https://www.autodesk.com/company/terms-of-use/en/general-terms",
            "title": "Autodesk General Terms of Use",
            "snippet": "Master software licensing agreement and commercial conditions for Autodesk desktop and cloud subscriptions.",
            "keywords": ["autodesk", "terms", "general terms", "autocad", "licensing"],
            "required_product": "autocad",
        },
        {
            "url": "https://www.autodesk.com/support/account/admin/manage-users/named-user-licensing",
            "title": "Autodesk Named User Licensing Guide",
            "snippet": "Detailed administration rules and single-user subscription assignment guidelines for Autodesk AutoCAD.",
            "keywords": ["autodesk", "autocad", "named user", "licensing", "guide"],
            "required_product": "autocad",
        },

        # Docker Desktop
        {
            "url": "https://www.docker.com/legal/docker-software-end-user-license-agreement/",
            "title": "Docker Software End User License Agreement",
            "snippet": "Docker Desktop requires a paid subscription (Pro, Team, or Business) for commercial use in businesses with >250 employees or >$10M annual revenue. Free for personal and small business use.",
            "keywords": ["docker", "desktop", "licensing", "terms", "commercial", "eula", "subscription", "pricing"],
            "required_product": "docker",
        },
        {
            "url": "https://www.docker.com/pricing/faq/",
            "title": "Docker Desktop Pricing FAQ & Commercial Terms",
            "snippet": "Docker Desktop commercial licensing requirements, named user subscriptions, and free vs paid tiers FAQ.",
            "keywords": ["docker", "desktop", "pricing", "faq", "commercial", "license", "tier"],
            "required_product": "docker",
        },

        # Google Antigravity
        {
            "url": "https://deepmind.google/technologies/antigravity/licensing-terms",
            "title": "Google DeepMind Antigravity Terms of Service & Licensing",
            "snippet": "Google Antigravity is available via a free tier with base capability quotas and paid enterprise or professional subscription tiers for advanced agentic bandwidth. Commercial requirement is context-dependent on tier.",
            "keywords": ["google", "antigravity", "ide", "deepmind", "licensing", "terms", "free", "paid", "commercial", "pricing"],
            "required_product": "antigravity",
        },

        # Google Chrome
        {
            "url": "https://www.google.com/chrome/terms/",
            "title": "Google Chrome Terms of Service",
            "snippet": "Google Chrome is a proprietary web browser available as freeware for personal and commercial browsing without license fees.",
            "keywords": ["google", "chrome", "browser", "freeware", "terms"],
            "required_product": "chrome",
        },

        # Brave Browser
        {
            "url": "https://brave.com/terms-of-use/",
            "title": "Brave Browser Terms of Use",
            "snippet": "Brave Browser is an open-source web browser based on Chromium, free for personal and commercial use under MPL 2.0.",
            "keywords": ["brave", "browser", "open source", "terms"],
            "required_product": "brave",
        },

        # Microsoft Visual Studio
        {
            "url": "https://visualstudio.microsoft.com/license-terms/",
            "title": "Microsoft Visual Studio Software License Terms",
            "snippet": "Visual Studio Community is free for individual developers and small organizations (<250 PCs or <$1M revenue, up to 5 users). Visual Studio Professional and Enterprise require a paid license per named user for commercial enterprise use.",
            "keywords": ["microsoft", "visual", "studio", "community", "professional", "enterprise", "licensing", "terms", "commercial"],
            "required_product": "visual studio",
        },

        # .NET SDK
        {
            "url": "https://github.com/dotnet/sdk/blob/main/LICENSE.TXT",
            "title": ".NET SDK MIT License Notice",
            "snippet": ".NET SDK is open source software licensed under the MIT License. Free for commercial, personal, and educational use without paid license requirements.",
            "keywords": ["microsoft", "dotnet", ".net", "sdk", "mit", "license", "open source", "free"],
            "required_product": ".net sdk",
        },

        # Git
        {
            "url": "https://git-scm.com/about/free-and-open-source",
            "title": "Git - Free and Open Source Software (GPL v2)",
            "snippet": "Git is an open source version control system released under the GNU General Public License version 2. Free for commercial, personal, and organizational use.",
            "keywords": ["git", "scm", "open source", "gpl", "free", "license", "commercial"],
            "required_product": "git",
        },

        # 7-Zip
        {
            "url": "https://www.7-zip.org/license.txt",
            "title": "7-Zip License & Commercial Use Notice",
            "snippet": "7-Zip is free software distributed under the GNU LGPL and BSD licenses. You can use 7-Zip on any computer, including computers in commercial organizations. You don't need to register or pay for 7-Zip.",
            "keywords": ["7-zip", "igor", "pavlov", "license", "free", "commercial", "lgpl", "open source"],
            "required_product": "7-zip",
        },

        # Python
        {
            "url": "https://docs.python.org/3/license.html",
            "title": "Python Software Foundation License",
            "snippet": "Python is distributed under the PSF License Agreement. Python is open source and free for commercial, non-commercial, and redistribution use.",
            "keywords": ["python", "software", "foundation", "psf", "license", "open source", "free", "commercial"],
            "required_product": "python",
        },

        # Go Language
        {
            "url": "https://go.dev/LICENSE",
            "title": "Go Programming Language BSD 3-Clause License",
            "snippet": "Go is an open source programming language licensed under the BSD 3-Clause License. Free for commercial, personal, and enterprise software development.",
            "keywords": ["go", "golang", "programming", "language", "bsd", "open source", "free", "commercial"],
            "required_product": "golang",
        },

        # Node.js
        {
            "url": "https://github.com/nodejs/node/blob/main/LICENSE",
            "title": "Node.js MIT License Notice",
            "snippet": "Node.js is an open source JavaScript runtime environment licensed under the MIT License. Free for commercial and non-commercial development.",
            "keywords": ["node.js", "nodejs", "node", "javascript", "runtime", "mit", "open source", "free", "commercial"],
            "required_product": "node.js",
        },

        # Cursor
        {
            "url": "https://www.cursor.com/pricing",
            "title": "Cursor AI Code Editor Pricing & Commercial Plans",
            "snippet": "Cursor by Anysphere offers a free tier for individuals and Pro/Business subscriptions for commercial team development.",
            "keywords": ["cursor", "anysphere", "ide", "pricing", "subscription", "commercial"],
            "required_product": "cursor",
        },

        # Claude
        {
            "url": "https://www.anthropic.com/pricing",
            "title": "Anthropic Claude Pricing & Commercial Terms",
            "snippet": "Claude desktop and web applications offer free basic tiers and paid Pro/Team subscriptions for commercial usage.",
            "keywords": ["claude", "anthropic", "pricing", "commercial", "subscription"],
            "required_product": "claude",
        },

        # VLC Media Player
        {
            "url": "https://www.videolan.org/legal.html",
            "title": "VideoLAN VLC Media Player Legal Information",
            "snippet": "VLC media player is free and open-source software licensed under the GNU General Public License (GPL) version 2 or later.",
            "keywords": ["vlc", "videolan", "media player", "gpl", "open source", "free"],
            "required_product": "vlc",
        },

        # WinRAR
        {
            "url": "https://www.rarlab.com/licence.htm",
            "title": "WinRAR End User License Agreement",
            "snippet": "WinRAR is a trialware file archiver. A commercial license is required after a 40-day evaluation period.",
            "keywords": ["winrar", "win.rar", "rarlab", "shareware", "commercial", "license"],
            "required_product": "winrar",
        },

        # PuTTY
        {
            "url": "https://www.chiark.greenend.org.uk/~sgtatham/putty/licence.html",
            "title": "PuTTY Licence (MIT License)",
            "snippet": "PuTTY is open source software licensed under the MIT License by Simon Tatham. Free for commercial and personal terminal usage.",
            "keywords": ["putty", "simon", "tatham", "mit", "open source", "license"],
            "required_product": "putty",
        },

        # Postman
        {
            "url": "https://www.postman.com/pricing/",
            "title": "Postman API Platform Plans & Pricing",
            "snippet": "Postman provides a free tier for up to 3 users and paid Basic, Professional, and Enterprise subscriptions for commercial API collaboration.",
            "keywords": ["postman", "api", "pricing", "subscription", "commercial"],
            "required_product": "postman",
        },

        # Notion
        {
            "url": "https://www.notion.so/pricing",
            "title": "Notion Workspace Pricing & Plans",
            "snippet": "Notion offers a free plan for individuals and Plus, Business, and Enterprise plans with user-based subscriptions.",
            "keywords": ["notion", "workspace", "pricing", "subscription", "commercial"],
            "required_product": "notion",
        },

        # Discord
        {
            "url": "https://discord.com/terms",
            "title": "Discord Terms of Service",
            "snippet": "Discord is a freeware communication client offering optional Nitro subscriptions for individual user enhancement.",
            "keywords": ["discord", "terms", "freeware", "communication"],
            "required_product": "discord",
        },

        # Canva
        {
            "url": "https://www.canva.com/pricing/",
            "title": "Canva Visual Suite Pricing & Plans",
            "snippet": "Canva Free is available for individuals, while Canva Pro and Canva Teams require paid commercial subscriptions.",
            "keywords": ["canva", "pricing", "subscription", "pro", "teams"],
            "required_product": "canva",
        },

        # MongoDB
        {
            "url": "https://www.mongodb.com/licensing/server-side-public-license",
            "title": "MongoDB Server Side Public License (SSPL)",
            "snippet": "MongoDB Community Server is licensed under the Server Side Public License (SSPL) v1. Commercial Atlas subscriptions are available.",
            "keywords": ["mongodb", "sspl", "licensing", "database"],
            "required_product": "mongodb",
        },

        # AMD Radeon
        {
            "url": "https://www.amd.com/en/support/kb/faq/gpu-terms",
            "title": "AMD Radeon Software End User License Agreement",
            "snippet": "AMD Radeon Software / AMD Software: Adrenalin Edition is bundled driver and utility software provided free of charge for AMD hardware owners.",
            "keywords": ["amd", "radeon", "adrenalin", "driver", "software"],
            "required_product": "radeon",
        },

        # Apple Time Machine
        {
            "url": "https://www.apple.com/legal/sla/",
            "title": "Apple macOS Software License Agreement (Time Machine)",
            "snippet": "Time Machine is a built-in backup utility bundled with macOS. Licensed under the macOS SLA, no separate license required.",
            "keywords": ["apple", "time machine", "macos", "bundled", "sla"],
            "required_product": "time machine",
        },

        # CrowdStrike Device Control
        {
            "url": "https://www.crowdstrike.com/terms-conditions/",
            "title": "CrowdStrike Falcon Terms and Conditions (Device Control)",
            "snippet": "CrowdStrike Falcon Device Control is an enterprise cybersecurity module licensed via paid commercial subscription per endpoint.",
            "keywords": ["crowdstrike", "device control", "falcon", "subscription", "commercial"],
            "required_product": "crowdstrike",
        },

        # Logitech Options
        {
            "url": "https://www.logitech.com/en-us/legal/software-terms.html",
            "title": "Logitech Options Software License Agreement",
            "snippet": "Logitech Options is companion peripheral configuration software provided free of charge for Logitech device owners.",
            "keywords": ["logitech", "options", "freeware", "hardware utility"],
            "required_product": "logitech",
        },

        # Linux Kernel / OS components
        {
            "url": "https://www.kernel.org/doc/html/latest/process/license-rules.html",
            "title": "Linux Kernel Licensing Rules (GPL-2.0)",
            "snippet": "The Linux kernel headers and source are licensed under GPL version 2 with syscall exemption. Open source OS system component.",
            "keywords": ["linux", "kernel", "headers", "gpl", "open source"],
            "required_product": "kernel",
        },

        # GCC
        {
            "url": "https://gcc.gnu.org/onlinedocs/gcc/Copying.html",
            "title": "GNU General Public License - GNU Project (GCC)",
            "snippet": "The GNU Compiler Collection (GCC) is free software licensed under GNU General Public License v3 with Runtime Library Exception.",
            "keywords": ["gcc", "gnu", "compiler", "gpl", "open source"],
            "required_product": "gcc",
        },

        # LibreOffice
        {
            "url": "https://www.libreoffice.org/about-us/licenses/",
            "title": "LibreOffice License Information (MPL 2.0)",
            "snippet": "LibreOffice is free and open source software developed by The Document Foundation under the Mozilla Public License v2.0.",
            "keywords": ["libreoffice", "document foundation", "open source", "free", "office"],
            "required_product": "libreoffice",
        },

        # Apache OpenOffice
        {
            "url": "https://www.openoffice.org/license.html",
            "title": "Apache OpenOffice License Terms (Apache 2.0)",
            "snippet": "Apache OpenOffice is free and open source software released under the Apache License 2.0. Free for commercial and personal use.",
            "keywords": ["openoffice", "apache", "license", "free", "open source"],
            "required_product": "openoffice",
        },

        # AnyDesk
        {
            "url": "https://anydesk.com/en/terms",
            "title": "AnyDesk General Terms and Conditions",
            "snippet": "AnyDesk offers free personal use and paid subscription licenses (Standard, Advanced, Ultimate) for professional and commercial remote desktop access.",
            "keywords": ["anydesk", "remote desktop", "commercial", "subscription", "terms", "pricing"],
            "required_product": "anydesk",
        },

        # Core Temp (ALCPU)
        {
            "url": "https://www.alcpu.com/CoreTemp/terms.html",
            "title": "ALCPU Core Temp Software Information",
            "snippet": "Core Temp is a compact, no fuss, small footprint, yet powerful program to monitor processor temperature. Freeware utility.",
            "keywords": ["core temp", "alcpu", "freeware", "temperature", "cpu"],
            "required_product": "core temp",
        },

        # Send to Kindle (Amazon)
        {
            "url": "https://www.amazon.com/sendtokindle",
            "title": "Amazon Send to Kindle Terms",
            "snippet": "Send to Kindle is a free desktop companion application provided by Amazon for transferring documents to Kindle devices.",
            "keywords": ["send to kindle", "amazon", "kindle", "freeware"],
            "required_product": "kindle",
        },

        # Claude (Anthropic)
        {
            "url": "https://www.anthropic.com/legal/consumer-terms",
            "title": "Anthropic Consumer Terms of Service (Claude)",
            "snippet": "Claude is available via a free consumer tier and paid Claude Pro and Team subscriptions for commercial collaboration.",
            "keywords": ["claude", "anthropic", "subscription", "terms", "pricing"],
            "required_product": "claude",
        },
    ]

    def is_available(self) -> bool:
        return True

    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """Returns relevant matches from the verified knowledge index."""
        tokens = query.lower().split()
        scored_results = []

        generic_terms = {
            "commercial", "license", "licensing", "requirements", "availability", "pricing", "official", "terms",
            "software", "app", "application", "tool", "tools", "utility", "system", "client", "desktop", "server",
            "options", "control", "device", "driver", "drivers", "package", "community", "professional", "standard",
            "enterprise", "edition", "version", "update", "service", "services", "agent", "assistant", "for", "the",
            "and", "inc", "corp", "corporation", "ltd", "gmbh", "center"
        }
        product_tokens = [t for t in tokens if t not in generic_terms and not t.startswith("site:") and not t.startswith("filetype:")]
        q_lower = query.lower()

        for item in self.KNOWN_INDEX:
            req = item.get("required_product")
            if req and req not in q_lower:
                continue

            score = 0
            item_text = f"{item['url']} {item['title']} {item['snippet']} {' '.join(item['keywords'])}".lower()

            # Ensure at least one specific product token matches if product tokens exist
            if product_tokens:
                matched_prod_tokens = sum(
                    1 for pt in product_tokens 
                    if len(pt) >= 2 and re.search(r'\b' + re.escape(pt) + r'\b', item_text)
                )
                if matched_prod_tokens == 0:
                    continue
                score += matched_prod_tokens * 20

            for token in tokens:
                if token in ["site:", "filetype:pdf", "filetype:"]:
                    continue
                if token.startswith("site:"):
                    domain_filter = token[5:]
                    if domain_filter not in item["url"].lower():
                        score = -100
                        break
                    score += 5
                    continue
                if token in item_text:
                    score += 1

            if score > 0:
                scored_results.append((score, item))

        # Sort by match score
        scored_results.sort(key=lambda x: x[0], reverse=True)
        results: List[SearchResult] = []
        for rank, (score, item) in enumerate(scored_results[:num_results], start=1):
            results.append(
                SearchResult(
                    url=item["url"],
                    title=item["title"],
                    snippet=item["snippet"],
                    engine="dev_search_provider",
                    rank=rank
                )
            )
        return results


class SearxngSearchProvider(SearchProvider):
    """
    Search provider using a self-hosted or local SearXNG meta-search engine instance
    for live web discovery of software licensing terms, EULAs, pricing, and product documentation.
    Aggregates results from 70+ search engines without third-party tracking or paid API keys.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        engines: Optional[str] = None,
        categories: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        fallback_provider: Optional[SearchProvider] = None,
    ):
        settings = get_settings()
        if base_url is not None:
            self.base_url = (base_url or "").strip().rstrip("/")
        else:
            configured_url = getattr(settings, "SEARXNG_BASE_URL", None)
            if configured_url is not None:
                self.base_url = configured_url.strip().rstrip("/")
            else:
                self.base_url = "http://127.0.0.1:8080"
        self.engines = engines if engines is not None else getattr(settings, "SEARXNG_ENGINES", None)
        self.categories = categories if categories is not None else getattr(settings, "SEARXNG_CATEGORIES", "general,it")
        self.timeout_seconds = timeout_seconds or getattr(settings, "SEARXNG_TIMEOUT_SECONDS", 15.0)
        self.fallback_provider = fallback_provider
        self._circuit_broken_until: float = 0.0
        if self.fallback_provider is None and settings.ENABLE_DEV_SEARCH_FALLBACK:
            self.fallback_provider = DevSearchProvider()

    def is_available(self) -> bool:
        """Returns True if a valid SearXNG base URL is configured."""
        return bool(self.base_url and self.base_url.strip())

    def search(
        self,
        query: str,
        num_results: int = 10,
    ) -> List[SearchResult]:
        """
        Executes a search query against SearXNG's JSON API (/search?q=...&format=json).
        Falls back to fallback_provider if configured and a transient error occurs.
        """
        if not self.is_available():
            logger.warning("SearxngSearchProvider called without a valid base URL.")
            if self.fallback_provider:
                return self.fallback_provider.search(query, num_results=num_results)
            return []

        # Fast circuit breaker: if SearXNG was unreachable recently, route straight to fallback
        if time.time() < self._circuit_broken_until:
            if self.fallback_provider:
                return self.fallback_provider.search(query, num_results=num_results)
            return []

        search_url = f"{self.base_url}/search"
        params: Dict[str, Any] = {
            "q": query,
            "format": "json",
            "pageno": 1,
        }
        if self.categories:
            params["categories"] = self.categories
        if self.engines:
            params["engines"] = self.engines

        try:
            timeout = httpx.Timeout(self.timeout_seconds, connect=0.5)
            with httpx.Client(timeout=timeout) as client:
                response = client.get(search_url, params=params)
                response.raise_for_status()
                data = response.json()

            results: List[SearchResult] = []
            raw_results = data.get("results", [])

            for rank, item in enumerate(raw_results[:num_results], start=1):
                url = item.get("url")
                if not url:
                    continue
                results.append(
                    SearchResult(
                        url=url,
                        title=item.get("title", ""),
                        snippet=item.get("content", ""),
                        engine=item.get("engine", "searxng"),
                        rank=rank,
                    )
                )

            logger.info("SearXNG search returned %d results for query: %s", len(results), query)
            return results

        except httpx.HTTPStatusError as e:
            logger.error("SearXNG API HTTP error (status %d): %s", e.response.status_code, e.response.text)
            self._circuit_broken_until = time.time() + 15.0
            if self.fallback_provider:
                logger.info("Falling back to fallback provider after SearXNG HTTP error.")
                return self.fallback_provider.search(query, num_results=num_results)
            return []
        except Exception as e:
            logger.error("SearXNG search request failed: %s", str(e))
            self._circuit_broken_until = time.time() + 30.0
            if self.fallback_provider:
                logger.info("Falling back to fallback provider after SearXNG request failure.")
                return self.fallback_provider.search(query, num_results=num_results)
            return []

    def search_official_domain(
        self,
        query: str,
        domain: str,
        num_results: int = 10
    ) -> List[SearchResult]:
        """Domain-scoped search using SearXNG's native site: syntax."""
        clean_domain = domain.lower().replace("https://", "").replace("http://", "").split("/")[0].strip()
        domain_query = f"site:{clean_domain} {query}"
        return self.search(domain_query, num_results=num_results)


class NullSearchProvider(SearchProvider):
    """Null provider used when no search engine or dev fallback is configured."""

    def is_available(self) -> bool:
        return False

    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        return []


class ChainSearchProvider(SearchProvider):
    """
    Search provider that executes search queries via the 3-engine fallback chain:
    SearXNG -> YaCy -> DuckDuckGo HTML scrape.
    """

    def __init__(
        self,
        chain: Optional[Any] = None,
        fallback_provider: Optional[SearchProvider] = None,
    ):
        from backend.search_engines.chain import SearchEngineChain
        from backend.search_engines.searxng_engine import SearXNGEngine
        from backend.search_engines.yacy_engine import YaCyEngine
        from backend.search_engines.duckduckgo_engine import DuckDuckGoEngine

        settings = get_settings()
        if chain is not None:
            self.chain = chain
        else:
            engines = [
                SearXNGEngine(base_url=settings.SEARXNG_BASE_URL),
                YaCyEngine(base_url=settings.YACY_BASE_URL),
                DuckDuckGoEngine(),
            ]
            self.chain = SearchEngineChain(
                engines=engines,
                max_retries_per_engine=getattr(settings, "SEARCH_CHAIN_RETRIES", 1),
                circuit_failure_threshold=getattr(settings, "SEARCH_CHAIN_CIRCUIT_FAILURE_THRESHOLD", 3),
                circuit_cooldown_seconds=getattr(settings, "SEARCH_CHAIN_CIRCUIT_COOLDOWN_SECONDS", 300),
            )

        self.fallback_provider = fallback_provider
        if self.fallback_provider is None and settings.ENABLE_DEV_SEARCH_FALLBACK:
            self.fallback_provider = DevSearchProvider()

    def is_available(self) -> bool:
        return True

    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        # Fast path: If all chain engines are currently circuit broken, route straight to dev fallback instantly
        if hasattr(self.chain, "is_circuit_broken") and hasattr(self.chain, "engines") and isinstance(self.chain.engines, list):
            if all(bool(self.chain.is_circuit_broken(e.name)) is True for e in self.chain.engines):
                if self.fallback_provider:
                    return self.fallback_provider.search(query, num_results=num_results)
                return []

        try:
            results_dict = self.chain.search(query, enable_cross_validation=True)
            if results_dict:
                return [
                    SearchResult(
                        url=item.get("url", ""),
                        title=item.get("title", ""),
                        snippet=item.get("snippet", ""),
                        engine=item.get("engine", "search_chain"),
                        cross_validated=bool(item.get("cross_validated", False)),
                        rank=i + 1
                    )
                    for i, item in enumerate(results_dict[:num_results])
                ]
        except Exception as e:
            logger.warning(f"ChainSearchProvider query failed for '{query}': {e}")

        if self.fallback_provider:
            return self.fallback_provider.search(query, num_results=num_results)
        return []


_GLOBAL_SEARXNG_PROVIDER: Optional[SearxngSearchProvider] = None
_GLOBAL_CHAIN_PROVIDER: Optional[ChainSearchProvider] = None


def get_search_provider(reset: bool = False) -> SearchProvider:
    """
    Factory function returning the configured SearchProvider instance.
    Supports SearXNG, full 3-engine SearchEngineChain, or Dev fallback.
    """
    global _GLOBAL_SEARXNG_PROVIDER, _GLOBAL_CHAIN_PROVIDER
    if reset or _GLOBAL_SEARXNG_PROVIDER is None:
        _GLOBAL_SEARXNG_PROVIDER = SearxngSearchProvider()
    if reset or _GLOBAL_CHAIN_PROVIDER is None:
        _GLOBAL_CHAIN_PROVIDER = ChainSearchProvider()

    settings = get_settings()
    provider_name = (settings.SEARCH_PROVIDER or "searxng").lower().strip()

    if provider_name in ("chain", "search_chain", "fallback_chain", "fallback", "searxng", "searx"):
        return _GLOBAL_CHAIN_PROVIDER

    if provider_name == "mock":
        return DevSearchProvider()

    return _GLOBAL_CHAIN_PROVIDER

    # Default to Chain or SearXNG
    if _GLOBAL_SEARXNG_PROVIDER.is_available():
        return _GLOBAL_SEARXNG_PROVIDER

    if settings.ENABLE_DEV_SEARCH_FALLBACK:
        return DevSearchProvider()

    return NullSearchProvider()

