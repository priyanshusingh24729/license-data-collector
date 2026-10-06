"""FastAPI application entrypoint for Commercial License Intelligence."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import get_settings
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
from backend.api.evidence import router as evidence_router
from backend.api.upload_inventory import router as upload_inventory_router
from backend.api.tier4_feedback import router as tier4_feedback_router
from backend.api.scan import router as scan_router, license_router
from backend.api.resolution_stats import router as resolution_stats_router
from backend.database.migration import init_database_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("commercial-license-intelligence")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager to run schema checks on startup."""
    logger.info("Starting Commercial License Intelligence Service...")
    init_database_tables()
    yield
    logger.info("Shutting down Commercial License Intelligence Service...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Deterministic Commercial Software Licensing Intelligence Platform",
    version="0.15.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(health_router)
app.include_router(sources_router)
app.include_router(discovery_router)
app.include_router(collectors_router)
app.include_router(documents_router)
app.include_router(api_collectors_router)
app.include_router(extraction_router)
app.include_router(validation_router)
app.include_router(profiles_router)
app.include_router(applications_router)
app.include_router(monitoring_router)
app.include_router(inventory_router)
app.include_router(entitlement_router)
app.include_router(audit_router)
app.include_router(prioritization_router)
app.include_router(evidence_router)
app.include_router(upload_inventory_router)
app.include_router(tier4_feedback_router)
app.include_router(scan_router)
app.include_router(license_router)
app.include_router(resolution_stats_router)


@app.get("/")
def root():
    """Root endpoint providing quick discovery and health links."""
    return {
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
        "health": "/api/health",
        "db_health": "/api/health/db",
        "sources": "/api/sources",
        "resolve_sources": "/api/sources/resolve",
        "discover_sources": "/api/discovery/sources",
        "web_collect": "/api/collectors/web/collect",
        "document_collect": "/api/collector/document",
        "api_collect": "/api/collector/api",
        "license_facts": "/api/license-facts",
        "extract_application": "/api/extraction/application",
        "validate_application": "/api/validation/application",
        "license_profiles": "/api/profiles",
        "applications": "/api/applications",
        "batch_research": "/api/research/batch",
        "monitoring": "/api/monitoring/sources",
        "alerts": "/api/monitoring/alerts",
        "inventory": "/api/inventory/applications",
        "ingest": "/api/inventory/ingest",
        "unresolved_queue": "/api/inventory/unresolved",
        "entitlements": "/api/entitlements",
        "consumption": "/api/consumption",
        "audit": "/api/audit/application/1",
        "quality": "/api/quality/summary",
        "upload_preview": "/api/inventory/upload/preview",
        "upload_start": "/api/inventory/upload/start",
        "upload_jobs": "/api/inventory/upload/jobs"
    }
