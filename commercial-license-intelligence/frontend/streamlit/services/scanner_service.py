"""
Frontend Scanner Service.
Coordinates system scanning by communicating with the FastAPI backend scanner API,
with in-process fallback capability if the backend is temporarily offline.
"""

import sys
import os
import json
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

BACKEND_API_BASE = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


class ScannerService:
    """Client service for the local computer software scanner."""

    @classmethod
    def get_device_info(cls) -> Dict[str, Any]:
        """Fetches local device metadata from backend API or local system fallback."""
        url = f"{BACKEND_API_BASE}/api/scan/device-info"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "StreamlitFrontend/1.0"}, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass

        # Local in-process fallback
        try:
            from backend.api.scan import get_local_device_info
            return get_local_device_info()
        except Exception:
            import platform
            return {
                "operating_system": f"{platform.system()} {platform.release()}",
                "device_name": platform.node(),
                "scan_source": "Local Machine",
                "is_windows": sys.platform == "win32",
            }

    @classmethod
    def start_scan(cls, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Starts a system scan via backend API, or spawns in-process scanner."""
        url = f"{BACKEND_API_BASE}/api/scan/start"
        payload = json.dumps(options or {}).encode("utf-8")
        headers = {"Content-Type": "application/json", "User-Agent": "StreamlitFrontend/1.0"}

        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status in (200, 202):
                    return json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass

        # In-process execution fallback
        from backend.api.scan import start_system_scan, ScanStartRequest
        req_obj = ScanStartRequest(**(options or {}))
        res = start_system_scan(request=req_obj)
        return res.dict()

    @classmethod
    def get_scan_status(cls, scan_id: str) -> Optional[Dict[str, Any]]:
        """Queries live status, progress, and step states for a scan."""
        url = f"{BACKEND_API_BASE}/api/scan/status/{scan_id}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "StreamlitFrontend/1.0"}, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass

        # In-process memory lookup fallback
        try:
            from backend.api.scan import get_scan_status
            res = get_scan_status(scan_id)
            return res.dict()
        except Exception:
            return None
