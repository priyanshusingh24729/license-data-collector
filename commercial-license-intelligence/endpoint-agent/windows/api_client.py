"""
HTTP client for uploading endpoint inventory payloads to backend service.
Provides timeout safety, optional API key authentication, and offline fallback.
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple
import urllib.request
import urllib.error
from .config import AgentConfig

logger = logging.getLogger(__name__)


class IngestionApiClient:
    """Uploads collected inventory to backend ingestion endpoint."""

    def __init__(self, config: AgentConfig):
        self.config = config

    def upload_inventory(self, payload: Dict[str, Any]) -> Tuple[bool, int, Dict[str, Any]]:
        """
        Submits inventory JSON payload to POST /api/inventory/ingest.
        Returns success boolean, status code/message, and response data.
        """
        url = f"{self.config.backend_url.rstrip('/')}/api/inventory/ingest"
        data_bytes = json.dumps(payload).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"CommercialLicenseAgent/{self.config.agent_version}",
        }
        if self.config.api_key:
            headers["X-Agent-Key"] = self.config.api_key

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                resp_body = resp.read().decode("utf-8")
                resp_json = json.loads(resp_body) if resp_body else {}
                return True, resp.status, resp_json
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="replace")
            logger.error(f"Backend HTTP error {he.code}: {err_body}")
            return False, he.code, {"error": err_body}
        except urllib.error.URLError as ue:
            logger.warning(f"Backend connection failed ({url}): {ue.reason}")
            return False, 0, {"error": str(ue.reason)}
        except Exception as ex:
            logger.error(f"Unexpected upload failure: {ex}")
            return False, 500, {"error": str(ex)}


# Tuple response type definition
Tuple_Response = Any
