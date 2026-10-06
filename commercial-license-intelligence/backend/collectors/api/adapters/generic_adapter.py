"""
Generic Vendor API Adapter.
Handles standard JSON/XML REST APIs and resolves credentials strictly from environment variables.
"""

import os
import json
import re
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Any, Tuple, Optional
from backend.models.source import LicenseSource
from backend.models.enums import AuthenticationType, AccessType
from backend.collectors.api.adapters.base_adapter import VendorApiAdapter

logger = logging.getLogger(__name__)


def xml_to_dict(element: ET.Element) -> Any:
    """Converts an XML Element tree recursively into a clean JSON-serializable Python dictionary."""
    children = list(element)
    if not children:
        return element.text or ""
    result: Dict[str, Any] = {}
    for child in children:
        child_data = xml_to_dict(child)
        if child.tag in result:
            if isinstance(result[child.tag], list):
                result[child.tag].append(child_data)
            else:
                result[child.tag] = [result[child.tag], child_data]
        else:
            result[child.tag] = child_data
    return result


class GenericVendorApiAdapter(VendorApiAdapter):
    """
    Standard adapter for public and authenticated REST/JSON/XML vendor endpoints.
    """

    def _get_env_credential(self, vendor_name: str, key_suffix: str) -> Optional[str]:
        """Resolves vendor credential from environment variables."""
        sanitized_vendor = re.sub(r"[^A-Za-z0-9]", "_", vendor_name.strip()).upper()
        # Check patterns: ADOBE_API_KEY, API_KEY_ADOBE, etc.
        candidates = [
            f"{sanitized_vendor}_{key_suffix}",
            f"{key_suffix}_{sanitized_vendor}",
            f"VENDOR_{sanitized_vendor}_{key_suffix}"
        ]
        for env_name in candidates:
            val = os.environ.get(env_name)
            if val:
                return val.strip()
        return None

    def has_credentials(self, source: LicenseSource) -> bool:
        """Determines if the required authentication credentials exist in the environment."""
        auth_type = getattr(source, "authentication_type", AuthenticationType.NONE)
        access_type = getattr(source, "access_type", AccessType.PUBLIC)

        if auth_type == AuthenticationType.NONE and access_type == AccessType.PUBLIC:
            return True

        if auth_type == AuthenticationType.API_KEY:
            return bool(self._get_env_credential(source.vendor_name, "API_KEY"))
        elif auth_type == AuthenticationType.BEARER_TOKEN or auth_type == AuthenticationType.OAUTH2:
            return bool(
                self._get_env_credential(source.vendor_name, "BEARER_TOKEN") or
                self._get_env_credential(source.vendor_name, "ACCESS_TOKEN") or
                self._get_env_credential(source.vendor_name, "API_KEY")
            )
        elif auth_type == AuthenticationType.BASIC:
            return bool(self._get_env_credential(source.vendor_name, "BASIC_AUTH"))

        # If access_type is PAID or AUTHENTICATED but auth_type is UNKNOWN, check generic API key
        if access_type in [AccessType.PAID, AccessType.AUTHENTICATED]:
            return bool(self._get_env_credential(source.vendor_name, "API_KEY"))

        return False

    def get_auth_headers(self, source: LicenseSource) -> Dict[str, str]:
        """Constructs headers dynamically in-memory without saving to database."""
        headers: Dict[str, str] = {
            "Accept": "application/json, application/xml, text/xml;q=0.9, */*;q=0.8"
        }
        auth_type = getattr(source, "authentication_type", AuthenticationType.NONE)
        vendor = source.vendor_name

        if auth_type == AuthenticationType.API_KEY:
            key = self._get_env_credential(vendor, "API_KEY")
            if key:
                headers["X-API-Key"] = key
        elif auth_type in [AuthenticationType.BEARER_TOKEN, AuthenticationType.OAUTH2]:
            token = (
                self._get_env_credential(vendor, "BEARER_TOKEN") or
                self._get_env_credential(vendor, "ACCESS_TOKEN") or
                self._get_env_credential(vendor, "API_KEY")
            )
            if token:
                headers["Authorization"] = f"Bearer {token}"
        elif auth_type == AuthenticationType.BASIC:
            basic = self._get_env_credential(vendor, "BASIC_AUTH")
            if basic:
                headers["Authorization"] = f"Basic {basic}"

        return headers

    def build_request(
        self,
        source: LicenseSource
    ) -> Tuple[str, str, Dict[str, str], Optional[Dict[str, Any]]]:
        """Assembles URL, method, headers and empty payload for safe retrieval."""
        url = source.source_url
        method = (getattr(source, "http_method", "GET") or "GET").upper()
        if method not in ["GET", "POST"]:
            method = "GET"
        headers = self.get_auth_headers(source)
        return url, method, headers, None

    def parse_payload(self, content_type: str, raw_text: str) -> Tuple[Optional[Any], Optional[str]]:
        """Parses JSON or XML payloads into a structured object."""
        if not raw_text or not raw_text.strip():
            return None, None

        ct = content_type.lower()
        cleaned_text = raw_text.strip()

        # JSON parsing
        if "json" in ct or cleaned_text.startswith("{") or cleaned_text.startswith("["):
            try:
                parsed = json.loads(cleaned_text)
                return parsed, None
            except json.JSONDecodeError as json_err:
                return None, f"JSON parse error: {json_err}"

        # XML parsing
        if "xml" in ct or cleaned_text.startswith("<"):
            try:
                root = ET.fromstring(cleaned_text)
                parsed = {root.tag: xml_to_dict(root)}
                return parsed, None
            except ET.ParseError as xml_err:
                return None, f"XML parse error: {xml_err}"

        return None, "Unrecognized structured format (neither JSON nor XML)"
