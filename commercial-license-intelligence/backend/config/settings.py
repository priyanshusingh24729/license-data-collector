"""Application configuration management using Pydantic Settings."""

import os
from functools import lru_cache
from typing import Optional, Dict
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the Commercial License Intelligence application."""

    # Project metadata
    PROJECT_NAME: str = "commercial-license-intelligence"
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql://postgres:<password>@<host>:5432/postgres"

    # Server Ports & Hosts
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    STREAMLIT_HOST: str = "127.0.0.1"
    STREAMLIT_PORT: int = 8501

    # Search Provider & Fallback Chain Configuration (SearXNG -> YaCy -> DuckDuckGo)
    SEARCH_PROVIDER: str = "SearXNG"
    SEARXNG_BASE_URL: str = "http://127.0.0.1:8080"
    SEARXNG_ENGINES: Optional[str] = None
    SEARXNG_CATEGORIES: Optional[str] = "general,it"
    SEARXNG_TIMEOUT_SECONDS: float = 8.0
    MAX_DISCOVERY_QUERIES: int = 15
    ENABLE_DEV_SEARCH_FALLBACK: bool = True

    # YaCy Configuration
    YACY_BASE_URL: str = "http://127.0.0.1:8090"
    YACY_TIMEOUT_SECONDS: float = 8.0

    # DuckDuckGo HTML Configuration
    DUCKDUCKGO_TIMEOUT_SECONDS: float = 8.0

    # Search Fallback Chain & Circuit Breaker Configuration
    SEARCH_CHAIN_RETRIES: int = 1
    SEARCH_CHAIN_CIRCUIT_FAILURE_THRESHOLD: int = 3
    SEARCH_CHAIN_CIRCUIT_COOLDOWN_SECONDS: int = 300
    OFFICIAL_DOMAINS_FILE: str = "official_domains.yaml"

    # Web Collector Configuration (Step 4)
    WEB_COLLECTOR_TIMEOUT_SECONDS: int = 20
    WEB_COLLECTOR_MAX_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB limit
    WEB_COLLECTOR_MAX_RETRIES: int = 2
    WEB_COLLECTOR_USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 (CommercialLicenseIntelligence/1.0)"
    )
    USE_TRAFILATURA_EXTRACTION: bool = True
    ENABLE_HEADLESS_BROWSER_FALLBACK: bool = True
    HEADLESS_BROWSER_TIMEOUT_SECONDS: float = 15.0

    # Document & PDF Collector Configuration (Step 5)
    MAX_DOCUMENT_BYTES: int = 25 * 1024 * 1024  # 25 MB limit for PDFs
    DOCUMENT_DOWNLOAD_TIMEOUT_SECONDS: int = 30
    MIN_TEXT_EXTRACTION_CHAR_THRESHOLD: int = 50

    # Optional Vendor API Collector Configuration (Step 6)
    API_REQUEST_DELAY_SECONDS: float = 0.5
    MAX_API_RESPONSE_BYTES: int = 10 * 1024 * 1024  # 10 MB limit
    MAX_API_REQUESTS_PER_RUN: int = 10
    API_COLLECTOR_TIMEOUT_SECONDS: int = 20
    API_COLLECTOR_MAX_RETRIES: int = 2

    # Batch Research & Concurrency Configuration (Step 11)
    MAX_CONCURRENT_RESEARCH: int = 3
    MAX_RESEARCH_RETRIES: int = 2

    # Source Monitoring & Change Detection Configuration (Step 12)
    MONITORING_ENABLED: bool = True
    DEFAULT_MONITOR_FREQUENCY: str = "WEEKLY"
    MAX_CONCURRENT_MONITORS: int = 3
    MONITOR_REQUEST_DELAY_SECONDS: float = 0.5

    # Data Storage Paths
    RAW_DATA_STORAGE_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "raw"
    )
    PROCESSED_DATA_STORAGE_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "processed"
    )

    # General Request timeouts
    REQUEST_TIMEOUT_SECONDS: int = 30

    # WinGet Package Manifest Integration Configuration
    ENABLE_WINGET_INTEGRATION: bool = True
    WINGET_CACHE_TABLE: str = "winget_manifests_cache"
    WINGET_CACHE_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "winget_cache"
    )

    # Web Collector Discovery Upgrades Configuration
    ENABLE_SITEMAP_DISCOVERY: bool = True
    ENABLE_LLMS_TXT_DISCOVERY: bool = True
    ENABLE_PDF_HARVESTING: bool = True
    MAX_SITEMAP_URLS_TO_EVALUATE: int = 25
    MAX_PDF_HARVEST_PER_PAGE: int = 3

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
