"""
Targeted Query Builder for Official Commercial License Discovery.
Generates controlled, high-precision search queries across licensing terminology.
Works generically for any vendor.
"""

from typing import List, Optional


class QueryBuilder:
    """
    Constructs high-intent discovery search queries for commercial software targets.
    """

    # Core discovery intent keyword templates
    CORE_INTENTS = [
        "product terms",
        "licensing terms",
        "licensing guide",
        "license terms",
        "EULA terms",
        "subscription licensing",
        "enterprise deployment licensing",
        "licensing guide filetype:pdf",
    ]

    def build_queries(
        self,
        vendor: str,
        product: Optional[str] = None,
        edition: Optional[str] = None,
        version: Optional[str] = None,
        os: Optional[str] = None,
        official_domain: Optional[str] = None,
        max_queries: int = 15,
    ) -> List[str]:
        """
        Generates a deduplicated, prioritized list of search queries.
        """
        clean_vendor = vendor.strip()
        clean_product = product.strip() if product else ""
        clean_edition = edition.strip() if edition else ""
        clean_version = version.strip() if version else ""
        clean_os = os.strip() if os else ""

        # Construct target identity tokens
        identity_parts = [clean_vendor]
        if clean_product:
            identity_parts.append(clean_product)
        if clean_edition:
            identity_parts.append(clean_edition)
        if clean_version:
            identity_parts.append(clean_version)

        full_target = " ".join(identity_parts)
        queries: List[str] = []

        # 1. Add domain-restricted site queries first if official domain is known
        if official_domain:
            clean_domain = official_domain.strip().lower()
            if clean_domain.startswith("www."):
                clean_domain = clean_domain[4:]
            
            domain_target = f"{clean_product} {clean_edition} {clean_version}".strip() or clean_vendor
            site_intents = [
                f"site:{clean_domain} {domain_target} licensing",
                f'site:{clean_domain} {domain_target} ("licensing guide" OR "licensing model" OR "terms of service")',
                f'site:{clean_domain} {domain_target} ("per core" OR "per seat" OR "named user" OR "perpetual")',
                f'site:{clean_domain} filetype:pdf ("licensing brief" OR "product terms" OR "EULA")',
                f"site:{clean_domain} {domain_target} terms",
                f"site:{clean_domain} {domain_target} product terms",
                f"site:{clean_domain} {domain_target} EULA",
            ]
            for sq in site_intents:
                if sq not in queries:
                    queries.append(sq)

        # 2. High precision target + intent queries
        for intent in self.CORE_INTENTS:
            query = f"{full_target} {intent}".strip()
            if query not in queries:
                queries.append(query)

        # 3. If OS is specified and relevant
        if clean_os and len(queries) < max_queries:
            os_query = f"{full_target} {clean_os} licensing guide"
            if os_query not in queries:
                queries.append(os_query)

        return queries[:max_queries]
