from backend.api.health import router as health_router
from backend.api.sources import router as sources_router
from backend.api.discovery import router as discovery_router
from backend.api.collectors import router as collectors_router
from backend.api.documents import router as documents_router
from backend.api.api_collectors import router as api_collectors_router
from backend.api.extraction import router as extraction_router
from backend.api.validation import router as validation_router
from backend.api.profiles import router as profiles_router
from backend.api.applications import router as applications_router
from backend.api.monitoring import router as monitoring_router
from backend.api.inventory import router as inventory_router
from backend.api.entitlement import router as entitlement_router
from backend.api.audit import router as audit_router
from backend.api.prioritization import router as prioritization_router

__all__ = [
    "health_router",
    "sources_router",
    "discovery_router",
    "collectors_router",
    "documents_router",
    "api_collectors_router",
    "extraction_router",
    "validation_router",
    "profiles_router",
    "applications_router",
    "monitoring_router",
    "inventory_router",
    "entitlement_router",
    "audit_router",
    "prioritization_router",
]
