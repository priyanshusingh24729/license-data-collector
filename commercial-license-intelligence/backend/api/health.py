"""Health check endpoints for API and Database status."""

from fastapi import APIRouter
from backend.database.connection import check_db_connection

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health")
def get_health():
    """Returns basic system health status."""
    return {
        "status": "ok",
        "service": "commercial-license-intelligence"
    }


@router.get("/health/db")
def get_db_health():
    """Returns the reachability status of the PostgreSQL/Supabase database."""
    db_status = check_db_connection()
    return {
        "status": "ok" if db_status.get("connected") else "unreachable",
        "service": "commercial-license-intelligence",
        "database": db_status
    }
