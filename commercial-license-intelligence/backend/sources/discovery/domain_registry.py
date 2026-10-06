"""
Official Domain Registry Service (Step 18).
Manages dynamic lookup and validation of authoritative vendor domains,
preventing hardcoding and rejecting non-official / snippet sources.
"""

from typing import Dict, List, Optional, Set, Any
from urllib.parse import urlparse
from sqlalchemy.orm import Session
import re

from backend.models.domain_registry import OfficialDomainRegistry
from backend.search_engines.base import load_official_domains


# Default Seed Definitions for Initial Registry Initialization
SEED_OFFICIAL_DOMAINS: List[Dict[str, Any]] = [
    # --- Original 40 & Core Ecosystem ---
    {
        "vendor": "Microsoft",
        "official_domain": "microsoft.com",
        "alternate_domains": [
            "learn.microsoft.com", "support.microsoft.com", "dotnet.microsoft.com",
            "office.com", "azure.com", "visualstudio.com", "live.com", "windows.com",
            "onedrive.live.com", "linkedin.com"
        ]
    },
    {
        "vendor": "Adobe",
        "official_domain": "adobe.com",
        "alternate_domains": ["helpx.adobe.com", "adobe.io", "behance.net", "figma.com"]
    },
    {
        "vendor": "Docker",
        "official_domain": "docker.com",
        "alternate_domains": ["docker.io"]
    },
    {
        "vendor": "Google",
        "official_domain": "google.com",
        "alternate_domains": ["deepmind.google", "go.dev", "golang.org", "chromium.org"]
    },
    {
        "vendor": "Python Software Foundation",
        "official_domain": "python.org",
        "alternate_domains": ["pypi.org"]
    },
    {
        "vendor": "The Go Authors",
        "official_domain": "go.dev",
        "alternate_domains": ["golang.org"]
    },
    {
        "vendor": "OpenJS Foundation",
        "official_domain": "nodejs.org",
        "alternate_domains": ["openjsf.org", "npmjs.com"]
    },
    {
        "vendor": "Node.js Foundation",
        "official_domain": "nodejs.org",
        "alternate_domains": ["nodejs.com", "npmjs.com"]
    },
    {
        "vendor": "Node.js",
        "official_domain": "nodejs.org",
        "alternate_domains": ["nodejs.com", "npmjs.com"]
    },
    {
        "vendor": "Git Community",
        "official_domain": "git-scm.com",
        "alternate_domains": ["github.com/git"]
    },
    {
        "vendor": "The Git Development Community",
        "official_domain": "git-scm.com",
        "alternate_domains": ["github.com/git", "git-scm.org"]
    },
    {
        "vendor": "JetBrains",
        "official_domain": "jetbrains.com",
        "alternate_domains": ["jetbrains.org"]
    },
    {
        "vendor": "Oracle",
        "official_domain": "oracle.com",
        "alternate_domains": ["java.com", "mysql.com"]
    },
    {
        "vendor": "Autodesk",
        "official_domain": "autodesk.com",
        "alternate_domains": []
    },
    {
        "vendor": "Zoom",
        "official_domain": "zoom.us",
        "alternate_domains": ["zoom.com"]
    },
    {
        "vendor": "Slack",
        "official_domain": "slack.com",
        "alternate_domains": []
    },
    {
        "vendor": "Salesforce",
        "official_domain": "salesforce.com",
        "alternate_domains": ["slack.com"]
    },
    {
        "vendor": "Citrix",
        "official_domain": "citrix.com",
        "alternate_domains": ["docs.citrix.com"]
    },
    {
        "vendor": "Trellix",
        "official_domain": "trellix.com",
        "alternate_domains": ["mcafee.com", "fireeye.com"]
    },
    {
        "vendor": "CrowdStrike",
        "official_domain": "crowdstrike.com",
        "alternate_domains": []
    },
    {
        "vendor": "Flexera",
        "official_domain": "flexera.com",
        "alternate_domains": ["snowsoftware.com"]
    },
    {
        "vendor": "Snow Software",
        "official_domain": "snowsoftware.com",
        "alternate_domains": ["flexera.com"]
    },
    {
        "vendor": "AnyDesk Software GmbH",
        "official_domain": "anydesk.com",
        "alternate_domains": []
    },
    {
        "vendor": "Notion Labs",
        "official_domain": "notion.so",
        "alternate_domains": ["notion.com"]
    },
    {
        "vendor": "Canva",
        "official_domain": "canva.com",
        "alternate_domains": []
    },
    {
        "vendor": "Figma",
        "official_domain": "figma.com",
        "alternate_domains": []
    },
    {
        "vendor": "Anthropic",
        "official_domain": "anthropic.com",
        "alternate_domains": ["claude.ai"]
    },
    {
        "vendor": "OpenAI",
        "official_domain": "openai.com",
        "alternate_domains": ["chatgpt.com"]
    },
    {
        "vendor": "VideoLAN",
        "official_domain": "videolan.org",
        "alternate_domains": []
    },
    {
        "vendor": "Simon Tatham",
        "official_domain": "greenend.org.uk",
        "alternate_domains": ["chiark.greenend.org.uk"]
    },
    {
        "vendor": "ALCPU",
        "official_domain": "alcpu.com",
        "alternate_domains": []
    },
    {
        "vendor": "win.rar GmbH",
        "official_domain": "rarlab.com",
        "alternate_domains": ["win-rar.com"]
    },
    {
        "vendor": "WinZip Computing",
        "official_domain": "winzip.com",
        "alternate_domains": ["corel.com"]
    },
    {
        "vendor": "Igor Pavlov",
        "official_domain": "7-zip.org",
        "alternate_domains": []
    },
    {
        "vendor": "Don Ho",
        "official_domain": "notepad-plus-plus.org",
        "alternate_domains": []
    },
    {
        "vendor": "Postman",
        "official_domain": "postman.com",
        "alternate_domains": []
    },
    {
        "vendor": "Zscaler",
        "official_domain": "zscaler.com",
        "alternate_domains": []
    },
    {
        "vendor": "Netskope",
        "official_domain": "netskope.com",
        "alternate_domains": []
    },
    {
        "vendor": "Ivanti",
        "official_domain": "ivanti.com",
        "alternate_domains": ["pulsesecure.net"]
    },
    {
        "vendor": "ManageEngine",
        "official_domain": "manageengine.com",
        "alternate_domains": ["zoho.com"]
    },
    {
        "vendor": "Zoho",
        "official_domain": "zoho.com",
        "alternate_domains": ["manageengine.com"]
    },
    {
        "vendor": "Omnissa",
        "official_domain": "omnissa.com",
        "alternate_domains": ["vmware.com"]
    },

    # --- Apple / OS ---
    {
        "vendor": "Apple",
        "official_domain": "apple.com",
        "alternate_domains": ["support.apple.com"]
    },
    {
        "vendor": "Apple Inc.",
        "official_domain": "apple.com",
        "alternate_domains": ["support.apple.com"]
    },

    # --- Browsers ---
    {
        "vendor": "Mozilla",
        "official_domain": "mozilla.org",
        "alternate_domains": ["mozilla.com", "firefox.com"]
    },
    {
        "vendor": "Mozilla Corporation",
        "official_domain": "mozilla.org",
        "alternate_domains": ["mozilla.com", "firefox.com"]
    },
    {
        "vendor": "Mozilla Foundation",
        "official_domain": "mozilla.org",
        "alternate_domains": ["mozilla.com", "firefox.com"]
    },
    {
        "vendor": "Opera",
        "official_domain": "opera.com",
        "alternate_domains": ["operasoftware.com"]
    },
    {
        "vendor": "Opera Software",
        "official_domain": "opera.com",
        "alternate_domains": ["operasoftware.com"]
    },
    {
        "vendor": "Brave Software",
        "official_domain": "brave.com",
        "alternate_domains": []
    },
    {
        "vendor": "Brave Software Inc",
        "official_domain": "brave.com",
        "alternate_domains": []
    },
    {
        "vendor": "Vivaldi Technologies",
        "official_domain": "vivaldi.com",
        "alternate_domains": []
    },
    {
        "vendor": "Coc Coc",
        "official_domain": "coccoc.com",
        "alternate_domains": []
    },
    {
        "vendor": "FrontMotion",
        "official_domain": "frontmotion.com",
        "alternate_domains": []
    },

    # --- Cloud Storage & Collaboration ---
    {
        "vendor": "Dropbox",
        "official_domain": "dropbox.com",
        "alternate_domains": []
    },
    {
        "vendor": "Box",
        "official_domain": "box.com",
        "alternate_domains": []
    },

    # --- Consumer / Social ---
    {
        "vendor": "Meta Platforms, Inc.",
        "official_domain": "meta.com",
        "alternate_domains": ["facebook.com", "messenger.com", "instagram.com", "whatsapp.com"]
    },
    {
        "vendor": "Facebook",
        "official_domain": "facebook.com",
        "alternate_domains": ["messenger.com", "instagram.com", "meta.com", "whatsapp.com"]
    },
    {
        "vendor": "Strava",
        "official_domain": "strava.com",
        "alternate_domains": []
    },
    {
        "vendor": "Spotify",
        "official_domain": "spotify.com",
        "alternate_domains": []
    },
    {
        "vendor": "Spotify AB",
        "official_domain": "spotify.com",
        "alternate_domains": []
    },
    {
        "vendor": "LinkedIn",
        "official_domain": "linkedin.com",
        "alternate_domains": ["microsoft.com"]
    },
    {
        "vendor": "Netflix",
        "official_domain": "netflix.com",
        "alternate_domains": []
    },
    {
        "vendor": "Netflix, Inc.",
        "official_domain": "netflix.com",
        "alternate_domains": []
    },
    {
        "vendor": "Discord",
        "official_domain": "discord.com",
        "alternate_domains": []
    },
    {
        "vendor": "Discord Inc.",
        "official_domain": "discord.com",
        "alternate_domains": []
    },

    # --- Dev / Data Tools ---
    {
        "vendor": "PostgreSQL Global Development Group",
        "official_domain": "postgresql.org",
        "alternate_domains": []
    },
    {
        "vendor": "Eclipse Foundation",
        "official_domain": "eclipse.org",
        "alternate_domains": []
    },
    {
        "vendor": "Red Hat",
        "official_domain": "redhat.com",
        "alternate_domains": []
    },
    {
        "vendor": "Red Hat, Inc.",
        "official_domain": "redhat.com",
        "alternate_domains": []
    },
    {
        "vendor": "Splunk",
        "official_domain": "splunk.com",
        "alternate_domains": []
    },
    {
        "vendor": "Splunk, Inc.",
        "official_domain": "splunk.com",
        "alternate_domains": []
    },
    {
        "vendor": "FileZilla Project",
        "official_domain": "filezilla-project.org",
        "alternate_domains": []
    },
    {
        "vendor": "Tim Kosse",
        "official_domain": "filezilla-project.org",
        "alternate_domains": []
    },
    {
        "vendor": "GAMS Development Corp.",
        "official_domain": "gams.com",
        "alternate_domains": []
    },
    {
        "vendor": "Mendix",
        "official_domain": "mendix.com",
        "alternate_domains": []
    },
    {
        "vendor": "MongoDB",
        "official_domain": "mongodb.com",
        "alternate_domains": []
    },
    {
        "vendor": "OpenSSL Project",
        "official_domain": "openssl.org",
        "alternate_domains": []
    },
    {
        "vendor": "Apache Software Foundation",
        "official_domain": "apache.org",
        "alternate_domains": ["openoffice.org"]
    },
    {
        "vendor": "Insecure.Com LLC",
        "official_domain": "nmap.org",
        "alternate_domains": []
    },
    {
        "vendor": "Nmap Project",
        "official_domain": "nmap.org",
        "alternate_domains": []
    },
    {
        "vendor": "Ngrok",
        "official_domain": "ngrok.com",
        "alternate_domains": []
    },
    {
        "vendor": "Ngrok Inc.",
        "official_domain": "ngrok.com",
        "alternate_domains": []
    },
    {
        "vendor": "Ollama",
        "official_domain": "ollama.com",
        "alternate_domains": []
    },
    {
        "vendor": "Anysphere",
        "official_domain": "cursor.com",
        "alternate_domains": ["cursor.sh"]
    },
    {
        "vendor": "Perplexity AI",
        "official_domain": "perplexity.ai",
        "alternate_domains": []
    },

    # --- Creative / Media ---
    {
        "vendor": "The Foundry",
        "official_domain": "foundry.com",
        "alternate_domains": []
    },
    {
        "vendor": "Descript",
        "official_domain": "descript.com",
        "alternate_domains": []
    },
    {
        "vendor": "Moritz Bunkus",
        "official_domain": "mkvtoolnix.download",
        "alternate_domains": ["bunkus.org"]
    },
    {
        "vendor": "MKVToolNix",
        "official_domain": "mkvtoolnix.download",
        "alternate_domains": ["bunkus.org"]
    },
    {
        "vendor": "SteelSeries",
        "official_domain": "steelseries.com",
        "alternate_domains": []
    },
    {
        "vendor": "Dolby Laboratories",
        "official_domain": "dolby.com",
        "alternate_domains": []
    },
    {
        "vendor": "OBS Project",
        "official_domain": "obsproject.com",
        "alternate_domains": []
    },
    {
        "vendor": "Krita Foundation",
        "official_domain": "krita.org",
        "alternate_domains": []
    },

    # --- Office / Productivity ---
    {
        "vendor": "The Document Foundation",
        "official_domain": "documentfoundation.org",
        "alternate_domains": ["libreoffice.org"]
    },
    {
        "vendor": "LibreOffice",
        "official_domain": "libreoffice.org",
        "alternate_domains": ["documentfoundation.org"]
    },

    # --- Security / Endpoint ---
    {
        "vendor": "Cisco",
        "official_domain": "cisco.com",
        "alternate_domains": ["webex.com"]
    },
    {
        "vendor": "Cisco Systems, Inc.",
        "official_domain": "cisco.com",
        "alternate_domains": ["webex.com"]
    },
    {
        "vendor": "Broadcom",
        "official_domain": "broadcom.com",
        "alternate_domains": ["vmware.com", "symantec.com"]
    },
    {
        "vendor": "Fortinet",
        "official_domain": "fortinet.com",
        "alternate_domains": []
    },
    {
        "vendor": "Fortinet, Inc.",
        "official_domain": "fortinet.com",
        "alternate_domains": []
    },
    {
        "vendor": "McAfee, LLC",
        "official_domain": "mcafee.com",
        "alternate_domains": []
    },
    {
        "vendor": "Sophos",
        "official_domain": "sophos.com",
        "alternate_domains": []
    },
    {
        "vendor": "Tenable",
        "official_domain": "tenable.com",
        "alternate_domains": []
    },
    {
        "vendor": "Pulse Secure",
        "official_domain": "pulsesecure.net",
        "alternate_domains": ["ivanti.com"]
    },

    # --- Hardware / OEM ---
    {
        "vendor": "NVIDIA Corporation",
        "official_domain": "nvidia.com",
        "alternate_domains": []
    },
    {
        "vendor": "Lenovo",
        "official_domain": "lenovo.com",
        "alternate_domains": []
    },
    {
        "vendor": "Dell",
        "official_domain": "dell.com",
        "alternate_domains": []
    },
    {
        "vendor": "HP",
        "official_domain": "hp.com",
        "alternate_domains": []
    },
    {
        "vendor": "Intel",
        "official_domain": "intel.com",
        "alternate_domains": []
    },
    {
        "vendor": "Intel Corporation",
        "official_domain": "intel.com",
        "alternate_domains": []
    },
    {
        "vendor": "Advanced Micro Devices, Inc.",
        "official_domain": "amd.com",
        "alternate_domains": []
    },
    {
        "vendor": "AMD",
        "official_domain": "amd.com",
        "alternate_domains": []
    },
    {
        "vendor": "Realtek",
        "official_domain": "realtek.com",
        "alternate_domains": []
    },
    {
        "vendor": "Realtek Semiconductor Corp",
        "official_domain": "realtek.com",
        "alternate_domains": []
    },
    {
        "vendor": "Logitech",
        "official_domain": "logitech.com",
        "alternate_domains": []
    },
    {
        "vendor": "Gigabyte",
        "official_domain": "gigabyte.com",
        "alternate_domains": []
    },
    {
        "vendor": "GIGA-BYTE Technology Co., Ltd.",
        "official_domain": "gigabyte.com",
        "alternate_domains": []
    },
    {
        "vendor": "Wacom",
        "official_domain": "wacom.com",
        "alternate_domains": []
    },

    # --- Misc Utilities ---
    {
        "vendor": "Corel",
        "official_domain": "corel.com",
        "alternate_domains": ["winzip.com"]
    },
    {
        "vendor": "Corel Corporation",
        "official_domain": "corel.com",
        "alternate_domains": ["winzip.com"]
    },
    {
        "vendor": "BitTorrent",
        "official_domain": "bittorrent.com",
        "alternate_domains": []
    },
    {
        "vendor": "BitTorrent, Inc.",
        "official_domain": "bittorrent.com",
        "alternate_domains": []
    },
    {
        "vendor": "Epic Games",
        "official_domain": "epicgames.com",
        "alternate_domains": []
    },
    {
        "vendor": "Epic Games, Inc.",
        "official_domain": "epicgames.com",
        "alternate_domains": []
    },
    {
        "vendor": "TeamViewer",
        "official_domain": "teamviewer.com",
        "alternate_domains": []
    },
    {
        "vendor": "TeamViewer Germany GmbH",
        "official_domain": "teamviewer.com",
        "alternate_domains": []
    },
    {
        "vendor": "CCleaner",
        "official_domain": "ccleaner.com",
        "alternate_domains": []
    },
    {
        "vendor": "Piriform",
        "official_domain": "ccleaner.com",
        "alternate_domains": []
    },
    {
        "vendor": "qBittorrent",
        "official_domain": "qbittorrent.org",
        "alternate_domains": []
    },
    {
        "vendor": "The qBittorrent Project",
        "official_domain": "qbittorrent.org",
        "alternate_domains": []
    },
    {
        "vendor": "ServiceNow",
        "official_domain": "servicenow.com",
        "alternate_domains": []
    },
    {
        "vendor": "ServiceNow, Inc.",
        "official_domain": "servicenow.com",
        "alternate_domains": []
    },

    # --- Open Source / Community ---
    {
        "vendor": "Canonical",
        "official_domain": "canonical.com",
        "alternate_domains": ["ubuntu.com", "packages.ubuntu.com"]
    },
    {
        "vendor": "Ubuntu Community",
        "official_domain": "ubuntu.com",
        "alternate_domains": ["packages.ubuntu.com", "canonical.com"]
    },
    {
        "vendor": "Debian Project",
        "official_domain": "debian.org",
        "alternate_domains": ["packages.debian.org"]
    },
    {
        "vendor": "Free Software Foundation",
        "official_domain": "gnu.org",
        "alternate_domains": ["gcc.gnu.org", "fsf.org"]
    },
    {
        "vendor": "Linux Foundation",
        "official_domain": "linuxfoundation.org",
        "alternate_domains": ["osquery.io", "kernel.org"]
    },
    {
        "vendor": "PHP Group",
        "official_domain": "php.net",
        "alternate_domains": []
    },
]


class DomainRegistryService:
    """
    Provides dynamic query and domain verification against official vendor registrations.
    """

    @classmethod
    def seed_registry_if_empty(cls, db: Session) -> int:
        """Seeds initial official domain records into database and syncs any missing vendors."""
        existing = {r.vendor.lower(): r for r in db.query(OfficialDomainRegistry).all()}
        inserted = 0
        for item in SEED_OFFICIAL_DOMAINS:
            v_key = item["vendor"].lower()
            if v_key not in existing:
                entry = OfficialDomainRegistry(
                    vendor=item["vendor"],
                    official_domain=item["official_domain"],
                    alternate_domains=item.get("alternate_domains", []),
                    enabled=True
                )
                db.add(entry)
                inserted += 1
            else:
                rec = existing[v_key]
                curr_alts = set(rec.alternate_domains or [])
                new_alts = set(item.get("alternate_domains", []))
                if not new_alts.issubset(curr_alts):
                    rec.alternate_domains = list(curr_alts.union(new_alts))
        if inserted > 0 or db.dirty:
            db.commit()
        return inserted

    @staticmethod
    def _vendor_matches(candidate: str, target: str) -> bool:
        """Helper to match vendor names safely without substring false positives."""
        c = candidate.strip().lower()
        t = target.strip().lower()
        if not c or not t:
            return False
        if c == t:
            return True

        c_words = set(re.findall(r'\b[a-z0-9]+\b', c))
        t_words = set(re.findall(r'\b[a-z0-9]+\b', t))
        corp_noise = {"inc", "corp", "corporation", "ltd", "limited", "llc", "gmbh", "co", "the", "technologies", "software", "systems", "group"}
        common = {w for w in c_words.intersection(t_words) if len(w) >= 3 or w in ("amd", "hp", "go")}
        distinctive = common - corp_noise
        return bool(distinctive)

    @classmethod
    def get_official_domains(cls, vendor_name: str) -> Set[str]:
        """Convenience method to retrieve official domains without explicit db session."""
        return cls.get_official_domains_for_vendor(None, vendor_name)

    @classmethod
    def get_official_domains_for_vendor(cls, db: Optional[Session], vendor_name: str) -> Set[str]:
        """
        Retrieves all valid domains (primary + alternates) for a given vendor.
        """
        if not vendor_name:
            return set()

        v_clean = vendor_name.strip().lower()
        domains: Set[str] = set()

        if db is not None:
            try:
                records = db.query(OfficialDomainRegistry).filter(
                    OfficialDomainRegistry.enabled == True
                ).all()
                for rec in records:
                    if cls._vendor_matches(rec.vendor, v_clean):
                        domains.add(rec.official_domain.lower())
                        for alt in (rec.alternate_domains or []):
                            domains.add(alt.lower())
            except Exception:
                pass

        # Fallback to in-memory seeds if DB query returned nothing
        if not domains:
            for item in SEED_OFFICIAL_DOMAINS:
                if cls._vendor_matches(item["vendor"], v_clean):
                    domains.add(item["official_domain"].lower())
                    for alt in item.get("alternate_domains", []):
                        domains.add(alt.lower())

        return domains

    @classmethod
    def is_trusted_official_domain(cls, url: str) -> bool:
        """
        Returns True if the URL's hostname matches any domain in the whitelist.
        """
        if not url:
            return False
        try:
            parsed = urlparse(url.strip())
            netloc = parsed.netloc.lower().split(":")[0]
            if netloc.startswith("www."):
                netloc = netloc[4:]
            whitelist = [d.lower().strip() for d in load_official_domains()]
            for d in whitelist:
                if d.startswith("www."):
                    d = d[4:]
                if netloc == d or netloc.endswith(f".{d}"):
                    return True
            return False
        except Exception:
            return False

    @classmethod
    def is_official_domain(cls, db: Optional[Session], url: str, vendor_name: str) -> bool:
        """
        Returns True if URL's hostname belongs to the registered official domains for the vendor.
        """
        if not url:
            return False

        parsed = urlparse(url.strip())
        netloc = parsed.netloc.lower().split(":")[0]
        if netloc.startswith("www."):
            netloc = netloc[4:]

        if not vendor_name:
            # Check against global trusted whitelist if vendor is absent
            return cls.is_trusted_official_domain(url)

        valid_domains = cls.get_official_domains_for_vendor(db, vendor_name)
        if valid_domains:
            for vd in valid_domains:
                if netloc == vd or netloc.endswith(f".{vd}"):
                    return True

        # Check repository owners on code hosting platforms
        if netloc in ("github.com", "gitlab.com"):
            path_parts = [p for p in parsed.path.lower().strip("/").split("/") if p]
            if path_parts:
                repo_owner = path_parts[0]
                v_toks = set(re.findall(r'[a-z0-9]+', vendor_name.lower())) - {"inc", "corp", "llc", "foundation", "ltd", "project", "community", "the", "software", "technologies"}
                if any(t in repo_owner for t in v_toks if len(t) >= 3):
                    return True

        # If domain is in official_domains whitelist and vendor words match domain
        if cls.is_trusted_official_domain(url):
            v_toks = set(re.findall(r'[a-z0-9]+', vendor_name.lower())) - {"inc", "corp", "llc", "foundation", "ltd", "project", "community", "the", "software", "technologies"}
            d_toks = set(re.findall(r'[a-z0-9]+', netloc.replace(".com", "").replace(".org", "").replace(".net", "").replace(".io", "").replace(".download", "")))
            if any(t in d_toks for t in v_toks if len(t) >= 3 or t in ("amd", "hp", "go")):
                return True

        return False
