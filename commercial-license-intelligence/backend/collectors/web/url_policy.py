"""
URL Safety & Domain Policy Engine.
Enforces strict anti-SSRF protections, scheme whitelisting, and vendor official domain validation.
"""

import socket
import ipaddress
import logging
from urllib.parse import urlparse
from typing import Tuple, Optional
from backend.models.enums import CollectionStatus, DomainValidationStatus
from backend.sources.discovery.domain_validator import DomainValidator

logger = logging.getLogger(__name__)

# Private and non-routable IP networks to block (SSRF protection)
BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),     # Carrier-grade NAT
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local / Cloud metadata (AWS, Azure, GCP 169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),    # Private
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),      # TEST-NET-1
    ipaddress.ip_network("192.88.99.0/24"),    # 6to4 relay
    ipaddress.ip_network("192.168.0.0/16"),   # Private
    ipaddress.ip_network("198.18.0.0/15"),     # Benchmark testing
    ipaddress.ip_network("198.51.100.0/24"),   # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),    # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),       # Multicast
    ipaddress.ip_network("240.0.0.0/4"),       # Reserved
    ipaddress.ip_network("255.255.255.255/32"),
    # IPv6 blocked ranges
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),          # Loopback
    ipaddress.ip_network("fc00::/7"),         # Unique local
    ipaddress.ip_network("fe80::/10"),        # Link-local
    ipaddress.ip_network("ff00::/8"),         # Multicast
]

BLOCKED_HOSTNAMES = {
    "localhost", "localhost.localdomain", "127.0.0.1", "::1", "0.0.0.0",
    "metadata.google.internal", "instance-data", "metadata"
}


class UrlPolicy:
    """
    Validates safety, scheme, network routability, and domain authority of URLs.
    """

    def __init__(self, domain_validator: Optional[DomainValidator] = None):
        self.domain_validator = domain_validator or DomainValidator()

    def is_ip_blocked(self, ip_str: str) -> bool:
        """Checks whether an IP address belongs to any blocked/private network."""
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            for net in BLOCKED_IP_NETWORKS:
                if ip_obj in net:
                    return True
            return False
        except ValueError:
            return True

    def validate_url(
        self,
        url: str,
        vendor: Optional[str] = None,
        expected_official_domain: Optional[str] = None
    ) -> Tuple[bool, CollectionStatus, str]:
        """
        Comprehensive URL validation.
        
        Returns:
        (is_valid: bool, status: CollectionStatus, message: str)
        """
        if not url or not isinstance(url, str):
            return False, CollectionStatus.INVALID_CONTENT, "URL is empty or invalid."

        parsed = urlparse(url.strip())

        # 1. Scheme Check
        if parsed.scheme.lower() not in ["http", "https"]:
            return False, CollectionStatus.SSRF_REJECTED, f"Unsupported URL scheme: '{parsed.scheme}'. Only http/https allowed."

        hostname = parsed.hostname
        if not hostname:
            return False, CollectionStatus.INVALID_CONTENT, "URL is missing a valid hostname."

        clean_host = hostname.lower().strip()

        # 2. Blocked Hostname Check
        if clean_host in BLOCKED_HOSTNAMES:
            return False, CollectionStatus.SSRF_REJECTED, f"Blocked internal or local hostname: '{clean_host}'."

        # 3. Direct IP Check
        try:
            ip_obj = ipaddress.ip_address(clean_host)
            if self.is_ip_blocked(str(ip_obj)):
                return False, CollectionStatus.SSRF_REJECTED, f"Target resolves to private or blocked IP address: {ip_obj}."
        except ValueError:
            # It's a domain name, not a raw IP
            pass

        # 4. Official Domain Verification if Vendor is specified
        if vendor:
            domain_status = self.domain_validator.validate_domain(
                url=url,
                vendor=vendor,
                expected_official_domain=expected_official_domain
            )
            if domain_status == DomainValidationStatus.NOT_OFFICIAL:
                return False, CollectionStatus.DOMAIN_REJECTED, f"Domain '{clean_host}' is not an authorized official domain for vendor '{vendor}'."

        return True, CollectionStatus.COLLECTED, "URL passed safety and domain policy validation."
