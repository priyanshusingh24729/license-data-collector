"""
Official Domain Validation Engine.
Strictly validates whether a discovered URL belongs to an authoritative vendor domain.
Prevents lookalike, third-party, and spoofed domains from polluting the source registry.
"""

from typing import Optional, Dict, Set
from urllib.parse import urlparse
from backend.models.enums import DomainValidationStatus


class DomainValidator:
    """
    Validates domain authority against verified vendor primary domains and subdomains.
    """

    # Known authoritative vendor primary root domains
    KNOWN_VENDOR_DOMAINS: Dict[str, Set[str]] = {
        "adobe": {"adobe.com"},
        "microsoft": {"microsoft.com", "office.com", "azure.com"},
        "autodesk": {"autodesk.com"},
        "oracle": {"oracle.com", "java.com"},
        "vmware": {"vmware.com", "broadcom.com"},
        "citrix": {"citrix.com"},
        "ibm": {"ibm.com", "redhat.com"},
        "salesforce": {"salesforce.com"},
        "servicenow": {"servicenow.com"},
        "sap": {"sap.com"},
        "atlassian": {"atlassian.com"},
        "cisco": {"cisco.com"},
        "splunk": {"splunk.com"},
    }

    # Known trusted official subdomains or specialized documentation hosts
    TRUSTED_OFFICIAL_SUBDOMAINS: Dict[str, Set[str]] = {
        "adobe": {"helpx.adobe.com", "business.adobe.com", "helpx.corp.adobe.com", "www.adobe.com"},
        "microsoft": {"learn.microsoft.com", "docs.microsoft.com", "support.microsoft.com", "www.microsoft.com"},
        "autodesk": {"knowledge.autodesk.com", "help.autodesk.com", "www.autodesk.com"},
    }

    def extract_netloc(self, url: str) -> str:
        """Extracts cleaned hostname/netloc from a URL."""
        if not url:
            return ""
        parsed = urlparse(url.strip())
        netloc = parsed.netloc.lower().split(":")[0]
        return netloc

    def get_known_official_domain(self, vendor: str) -> Optional[str]:
        """Returns the primary known official domain for a vendor if registered."""
        clean_vendor = vendor.strip().lower()
        if clean_vendor in self.KNOWN_VENDOR_DOMAINS:
            return sorted(list(self.KNOWN_VENDOR_DOMAINS[clean_vendor]))[0]
        return None

    def validate_domain(
        self,
        url: str,
        vendor: str,
        expected_official_domain: Optional[str] = None
    ) -> DomainValidationStatus:
        """
        Evaluates the domain validity of a URL against vendor expectations.
        
        Returns:
        - DomainValidationStatus.OFFICIAL: Exact match or verified subdomain of official root.
        - DomainValidationStatus.RELATED_OFFICIAL: Verified related/subsidiary domain for the vendor.
        - DomainValidationStatus.NOT_OFFICIAL: Unrelated or lookalike domain (e.g. adobe-crack.com).
        - DomainValidationStatus.UNKNOWN: Unable to determine.
        """
        if not url:
            return DomainValidationStatus.UNKNOWN

        netloc = self.extract_netloc(url)
        if not netloc:
            return DomainValidationStatus.UNKNOWN

        clean_vendor = vendor.strip().lower()

        # Build candidate root domains
        candidate_roots: Set[str] = set()

        if expected_official_domain:
            clean_expected = expected_official_domain.strip().lower()
            if clean_expected.startswith("www."):
                clean_expected = clean_expected[4:]
            candidate_roots.add(clean_expected)

        if clean_vendor in self.KNOWN_VENDOR_DOMAINS:
            candidate_roots.update(self.KNOWN_VENDOR_DOMAINS[clean_vendor])

        # If no known root domain exists, infer standard pattern <vendor>.com
        if not candidate_roots:
            inferred_root = f"{clean_vendor.replace(' ', '')}.com"
            candidate_roots.add(inferred_root)

        # Check each candidate root
        for root in candidate_roots:
            # 1. Exact match (e.g. adobe.com or www.adobe.com)
            if netloc == root or netloc == f"www.{root}":
                return DomainValidationStatus.OFFICIAL

            # 2. Strict Subdomain check (e.g. helpx.adobe.com or learn.microsoft.com)
            if netloc.endswith(f".{root}"):
                return DomainValidationStatus.OFFICIAL

        # Check trusted secondary/related official hosts for vendor
        if clean_vendor in self.TRUSTED_OFFICIAL_SUBDOMAINS:
            if netloc in self.TRUSTED_OFFICIAL_SUBDOMAINS[clean_vendor]:
                return DomainValidationStatus.RELATED_OFFICIAL

        # If it contains vendor name in a lookalike fashion (e.g. adobe-licensing.org or fakeadobe.com)
        # but fails strict root/subdomain checks, explicitly classify NOT_OFFICIAL
        return DomainValidationStatus.NOT_OFFICIAL
