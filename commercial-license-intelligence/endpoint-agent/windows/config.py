"""
Configuration management for Windows Endpoint Agent.
Loads settings from environment variables or command-line overrides with safe defaults.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

AGENT_VERSION = "1.0.0"
DEFAULT_BACKEND_URL = "http://localhost:8000"
DEFAULT_TIMEOUT_SECONDS = 30


@dataclass
class AgentConfig:
    """Runtime configuration for Windows Endpoint Collector."""
    backend_url: str = os.getenv("BACKEND_URL", DEFAULT_BACKEND_URL)
    api_key: Optional[str] = os.getenv("AGENT_API_KEY", None)
    timeout_seconds: int = int(os.getenv("API_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    agent_version: str = AGENT_VERSION
    dry_run: bool = False
    output_file: Optional[str] = None
    quiet: bool = False
    include_packages: bool = True
    deduplicate: bool = True
    device_key_file: str = ".device_key"
