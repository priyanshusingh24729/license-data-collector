"""Top-level search_engines package re-exporting backend.search_engines."""

from backend.search_engines.base import SearchEngine, load_official_domains
from backend.search_engines.searxng_engine import SearXNGEngine
from backend.search_engines.yacy_engine import YaCyEngine
from backend.search_engines.duckduckgo_engine import DuckDuckGoEngine
from backend.search_engines.chain import SearchEngineChain, SearchEngineError, NoResultsFoundError

__all__ = [
    "SearchEngine",
    "load_official_domains",
    "SearXNGEngine",
    "YaCyEngine",
    "DuckDuckGoEngine",
    "SearchEngineChain",
    "SearchEngineError",
    "NoResultsFoundError",
]
