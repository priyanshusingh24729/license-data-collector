"""
Authoritative Vendor Legal Portal Registry.
Maintains direct, pre-verified links to official vendor licensing, legal terms, and EULA portals.
Ensures primary legal evidence is prioritized over third-party search results or blogs.
"""

import re
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple


@dataclass
class AuthoritativeLegalSource:
    vendor_canonical: str
    product_name: str
    legal_portal_url: str
    eula_or_terms_url: str
    evidence_type: str = "VENDOR_LEGAL_PORTAL"
    notes: str = ""


class LegalPortalRegistry:
    """
    Registry of authoritative vendor legal endpoints and verification mechanisms.
    """

    PORTAL_DIRECTORY: List[AuthoritativeLegalSource] = [
        AuthoritativeLegalSource(
            vendor_canonical="Microsoft",
            product_name="Microsoft Commercial Software",
            legal_portal_url="https://www.microsoft.com/licensing/terms/",
            eula_or_terms_url="https://www.microsoft.com/licensing/docs/view/Product-Terms",
            notes="Official Microsoft Product Terms licensing portal",
        ),
        AuthoritativeLegalSource(
            vendor_canonical="Microsoft",
            product_name="Visual Studio",
            legal_portal_url="https://visualstudio.microsoft.com/license-terms/",
            eula_or_terms_url="https://visualstudio.microsoft.com/license-terms/vs2022-ga-community/",
            notes="Visual Studio Community vs Professional vs Enterprise license agreements",
        ),
        AuthoritativeLegalSource(
            vendor_canonical="Microsoft",
            product_name="SQL Server",
            legal_portal_url="https://www.microsoft.com/en-us/sql-server/sql-server-2022-pricing",
            eula_or_terms_url="https://learn.microsoft.com/en-us/sql/sql-server/editions-and-components-of-sql-server-2022",
            notes="Official SQL Server editions and licensing rules",
        ),
        AuthoritativeLegalSource(
            vendor_canonical="Docker Inc.",
            product_name="Docker Desktop",
            legal_portal_url="https://www.docker.com/legal/docker-subscription-service-agreement/",
            eula_or_terms_url="https://www.docker.com/pricing/faq/",
            notes="Docker subscription service agreement for commercial entities",
        ),
        AuthoritativeLegalSource(
            vendor_canonical="Oracle Corporation",
            product_name="Oracle Java (JDK / JRE)",
            legal_portal_url="https://www.oracle.com/java/technologies/javase/terms/license/",
            eula_or_terms_url="https://www.oracle.com/downloads/licenses/javase-license1.html",
            notes="Oracle Java SE Universal Subscription and OTN license terms",
        ),
        AuthoritativeLegalSource(
            vendor_canonical="Oracle Corporation",
            product_name="Oracle Database",
            legal_portal_url="https://www.oracle.com/contracts/",
            eula_or_terms_url="https://www.oracle.com/corporate/pricing/specialty.html",
            notes="Oracle commercial licensing metrics and core factor tables",
        ),
        AuthoritativeLegalSource(
            vendor_canonical="Oracle Corporation",
            product_name="MySQL",
            legal_portal_url="https://www.mysql.com/about/legal/licensing/",
            eula_or_terms_url="https://www.mysql.com/about/legal/licensing/oem/",
            notes="MySQL GPL-2.0 Community vs Commercial subscription terms",
        ),
        AuthoritativeLegalSource(
            vendor_canonical="HashiCorp",
            product_name="Terraform / Vault / Consul",
            legal_portal_url="https://www.hashicorp.com/bsl-faq",
            eula_or_terms_url="https://www.hashicorp.com/terms-of-evaluation",
            notes="HashiCorp BSL FAQ and commercial competitive restrictions",
        ),
        AuthoritativeLegalSource(
            vendor_canonical="Redis Ltd",
            product_name="Redis",
            legal_portal_url="https://redis.io/legal/licenses/",
            eula_or_terms_url="https://redis.io/legal/rsalv2-agreement/",
            notes="Redis source-available RSALv2 and SSPL licensing guidelines",
        ),
        AuthoritativeLegalSource(
            vendor_canonical="MongoDB Inc.",
            product_name="MongoDB",
            legal_portal_url="https://www.mongodb.com/licensing/server-side-public-license",
            eula_or_terms_url="https://www.mongodb.com/licensing/server-side-public-license/faq",
            notes="Official SSPL v1 terms and commercial managed service conditions",
        ),
        AuthoritativeLegalSource(
            vendor_canonical="Adobe Inc.",
            product_name="Adobe Creative Cloud / Acrobat",
            legal_portal_url="https://www.adobe.com/legal/licenses-terms.html",
            eula_or_terms_url="https://www.adobe.com/legal/terms.html",
            notes="Adobe enterprise user subscription terms and EULAs",
        ),
        AuthoritativeLegalSource(
            vendor_canonical="JetBrains s.r.o.",
            product_name="IntelliJ IDEA / PyCharm / WebStorm",
            legal_portal_url="https://www.jetbrains.com/legal/agreements/",
            eula_or_terms_url="https://www.jetbrains.com/legal/agreements/user.html",
            notes="JetBrains toolbox per-user subscription and community Apache-2.0 terms",
        ),
        AuthoritativeLegalSource(
            vendor_canonical="Git Development Community",
            product_name="Git",
            legal_portal_url="https://git-scm.com/about/free-and-open-source",
            eula_or_terms_url="https://raw.githubusercontent.com/git/git/master/COPYING",
            notes="Git GPL-2.0 license declaration",
        ),
        AuthoritativeLegalSource(
            vendor_canonical="Python Software Foundation",
            product_name="Python",
            legal_portal_url="https://docs.python.org/3/license.html",
            eula_or_terms_url="https://www.python.org/psf/license/",
            notes="PSF License Agreement for Python",
        ),
        AuthoritativeLegalSource(
            vendor_canonical="Igor Pavlov",
            product_name="7-Zip",
            legal_portal_url="https://www.7-zip.org/license.txt",
            eula_or_terms_url="https://www.7-zip.org/faq.html",
            notes="7-Zip GNU LGPL license declaration",
        ),
        AuthoritativeLegalSource(
            vendor_canonical="Kitware, Inc.",
            product_name="CMake",
            legal_portal_url="https://cmake.org/licensing/",
            eula_or_terms_url="https://gitlab.kitware.com/cmake/cmake/-/raw/master/Copyright.txt",
            notes="CMake BSD 3-clause license declaration",
        ),
        AuthoritativeLegalSource(
            vendor_canonical="Tableau Software",
            product_name="Tableau Desktop",
            legal_portal_url="https://www.tableau.com/legal",
            eula_or_terms_url="https://www.tableau.com/tos",
            notes="Tableau / Salesforce creator subscription terms",
        ),
        AuthoritativeLegalSource(
            vendor_canonical="Broadcom / VMware",
            product_name="VMware Workstation",
            legal_portal_url="https://www.vmware.com/download/eula.html",
            eula_or_terms_url="https://blogs.vmware.com/workstation/",
            notes="Broadcom VMware Workstation Pro personal free / commercial subscription policy",
        ),
    ]

    AUTHORITATIVE_HOST_PATTERNS = [
        r"^https?://(?:[a-zA-Z0-9\-]+\.)?microsoft\.com/(?:licensing|legal)",
        r"^https?://(?:[a-zA-Z0-9\-]+\.)?oracle\.com/(?:contracts|legal|java|downloads/licenses)",
        r"^https?://(?:[a-zA-Z0-9\-]+\.)?adobe\.com/legal",
        r"^https?://(?:[a-zA-Z0-9\-]+\.)?docker\.com/(?:legal|pricing)",
        r"^https?://(?:[a-zA-Z0-9\-]+\.)?hashicorp\.com/bsl",
        r"^https?://(?:[a-zA-Z0-9\-]+\.)?redis\.io/legal",
        r"^https?://(?:[a-zA-Z0-9\-]+\.)?mongodb\.com/licensing",
        r"^https?://(?:[a-zA-Z0-9\-]+\.)?jetbrains\.com/legal",
        r"^https?://(?:[a-zA-Z0-9\-]+\.)?git-scm\.com",
        r"^https?://(?:[a-zA-Z0-9\-]+\.)?python\.org",
        r"^https?://(?:[a-zA-Z0-9\-]+\.)?7-zip\.org",
        r"^https?://(?:[a-zA-Z0-9\-]+\.)?cmake\.org/licensing",
        r"^https?://(?:[a-zA-Z0-9\-]+\.)?vmware\.com/(?:download/eula|legal)",
    ]

    @classmethod
    def find_legal_source(cls, app_name: str, publisher: Optional[str] = None) -> Optional[AuthoritativeLegalSource]:
        """Finds an authoritative legal source for a product or publisher."""
        if not app_name:
            return None
        low_app = app_name.lower().strip()
        low_pub = str(publisher or "").lower().strip()

        for src in cls.PORTAL_DIRECTORY:
            src_prod = src.product_name.lower()
            src_vend = src.vendor_canonical.lower()

            # Exact or substring match on product
            if src_prod in low_app or low_app in src_prod:
                return src
            # Match on vendor + keywords
            if src_vend in low_pub or src_vend in low_app:
                if any(w in low_app for w in src_prod.split()):
                    return src
        return None

    @classmethod
    def is_authoritative_legal_url(cls, url: Optional[str]) -> bool:
        """Determines if a URL originates from an authoritative vendor legal portal."""
        if not url:
            return False
        for pat in cls.AUTHORITATIVE_HOST_PATTERNS:
            if re.search(pat, url, re.IGNORECASE):
                return True
        return False

    @classmethod
    def get_evidence_source_label(cls, url: Optional[str], default_source: str = "WEB_CRAWL") -> str:
        """Returns the appropriate source priority label."""
        if not url:
            return default_source
        if cls.is_authoritative_legal_url(url):
            if url.lower().endswith(".pdf"):
                return "OFFICIAL_EULA_PDF"
            return "VENDOR_LEGAL_PORTAL"
        if "winget" in default_source.lower():
            return default_source
        return default_source
