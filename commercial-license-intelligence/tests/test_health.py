"""Tests for FastAPI health check and configuration management."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.config.settings import get_settings
from backend.database.connection import check_db_connection


client = TestClient(app)


def test_api_health():
    """Verify that GET /api/health returns ok status and service identifier."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "commercial-license-intelligence"


def test_api_db_health():
    """Verify that GET /api/health/db returns a valid structured health response."""
    response = client.get("/api/health/db")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "connected" in data["database"]
    assert "message" in data["database"]


def test_settings_load():
    """Verify that application configuration loads default/env settings properly."""
    settings = get_settings()
    assert settings.PROJECT_NAME == "commercial-license-intelligence"
    assert settings.API_HOST is not None
    assert settings.API_PORT > 0
    assert hasattr(settings, "DATABASE_URL")


def test_database_connection_check():
    """Verify that check_db_connection handles placeholder/unconfigured DBs gracefully."""
    db_check = check_db_connection()
    assert isinstance(db_check, dict)
    assert "connected" in db_check
    assert "message" in db_check
