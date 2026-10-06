"""
Tests for SearchEngineChain circuit breaker persistence and resolution-stats telemetry.
"""

import time
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.search_engines.chain import SearchEngineChain
from backend.search_engines.base import SearchEngine
from backend.main import app


def test_circuit_breaker_persists_failure_and_trip_state(tmp_path):
    """Verify that failure count, trip state, and cooldown are persisted and queryable."""
    test_db = str(tmp_path / "test_cb.db")

    engine1 = MagicMock(spec=SearchEngine)
    engine1.name = "test_engine"
    engine1.search.side_effect = Exception("Service unavailable")

    chain = SearchEngineChain(
        engines=[engine1],
        circuit_failure_threshold=2,
        circuit_cooldown_seconds=60,
        max_retries_per_engine=0
    )

    # 1. Initial state
    states = chain.get_circuit_breaker_states()
    assert "test_engine" in states
    assert states["test_engine"]["is_tripped"] is False
    assert states["test_engine"]["failure_count"] == 0

    # 2. Record 1 failure
    chain.record_failure("test_engine")
    states = chain.get_circuit_breaker_states()
    assert states["test_engine"]["failure_count"] == 1
    assert states["test_engine"]["is_tripped"] is False

    # 3. Record 2nd failure -> exceeds threshold 2 -> circuit trips
    chain.record_failure("test_engine")
    states = chain.get_circuit_breaker_states()
    assert states["test_engine"]["is_tripped"] is True
    assert states["test_engine"]["failure_count"] == 2
    assert states["test_engine"]["cooldown_expiry"] is not None
    assert states["test_engine"]["cooldown_expiry_iso"] is not None

    # 4. Check queryable classmethod across processes
    persisted = SearchEngineChain.get_persisted_states()
    assert "test_engine" in persisted
    assert persisted["test_engine"]["is_tripped"] is True
    assert persisted["test_engine"]["failure_count"] == 2

    # 5. Success resets
    chain.record_success("test_engine")
    states = chain.get_circuit_breaker_states()
    assert states["test_engine"]["is_tripped"] is False
    assert states["test_engine"]["failure_count"] == 0


def test_resolution_stats_endpoint_includes_detailed_circuit_breaker_telemetry():
    """Verify that the API endpoint exposes the circuit breaker states with failure counts and cooldown."""
    client = TestClient(app)
    response = client.get("/api/inventory/resolution-stats")
    assert response.status_code == 200
    data = response.json()
    assert "search_chain_telemetry" in data
    telemetry = data["search_chain_telemetry"]
    assert "circuit_breaker_states" in telemetry
    cb_states = telemetry["circuit_breaker_states"]

    # Each engine in cb_states should expose is_tripped, failure_count, and cooldown_expiry
    for eng_name, eng_state in cb_states.items():
        assert "is_tripped" in eng_state
        assert "failure_count" in eng_state
        assert "cooldown_expiry" in eng_state
