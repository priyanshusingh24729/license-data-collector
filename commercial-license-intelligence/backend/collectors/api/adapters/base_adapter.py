"""
Base Adapter Interface for Vendor API Integration.
Ensures credential decoupling, request preparation, and structured response parsing.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional
from backend.models.source import LicenseSource


class VendorApiAdapter(ABC):
    """
    Abstract interface for vendor-specific API adapters.
    """

    @abstractmethod
    def has_credentials(self, source: LicenseSource) -> bool:
        """Checks whether credentials required for this source are configured in the environment."""
        pass

    @abstractmethod
    def get_auth_headers(self, source: LicenseSource) -> Dict[str, str]:
        """
        Dynamically constructs authentication headers from environment variables.
        Never stored in database or logged.
        """
        pass

    @abstractmethod
    def build_request(
        self,
        source: LicenseSource
    ) -> Tuple[str, str, Dict[str, str], Optional[Dict[str, Any]]]:
        """
        Builds the request components: (url, http_method, headers, json_payload).
        """
        pass

    @abstractmethod
    def parse_payload(self, content_type: str, raw_text: str) -> Tuple[Optional[Any], Optional[str]]:
        """
        Parses JSON or XML responses into structured dictionary/list.
        Returns: (parsed_data, error_message)
        """
        pass
