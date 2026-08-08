"""
test_api_routes.py — Pillar 1: REST API Response & Schema Verification
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """Verify root health endpoint returns HTTP 200 and valid JSON."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "WealthQuant" in data["status"]


@pytest.mark.asyncio
async def test_dashboard_nifty_schema(async_client: AsyncClient):
    """Verify /api/dashboard/NIFTY schema compliance and required fields."""
    response = await async_client.get("/api/dashboard/NIFTY?interval=15m")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "NIFTY"
    assert data["interval"] == "15m"
    assert "prediction" in data
    assert "market_snapshot" in data
    assert "options_summary" in data
    assert "regime" in data

    # Check prediction sub-fields
    pred = data["prediction"]
    assert "signal" in pred
    assert "confidence" in pred
    assert "prediction_state" in pred or "state" in pred


@pytest.mark.asyncio
async def test_pipeline_nifty_run(async_client: AsyncClient):
    """Verify /api/pipeline/NIFTY pipeline run returns probability distribution."""
    response = await async_client.get("/api/pipeline/NIFTY?interval=15m")
    assert response.status_code == 200
    data = response.json()
    assert "symbol" in data
    assert data["symbol"] == "NIFTY"
    assert "probabilities" in data
    probs = data["probabilities"]
    assert "p_up" in probs
    assert "p_down" in probs
    assert "p_sideways" in probs
    total_p = probs["p_up"] + probs["p_down"] + probs["p_sideways"]
    assert abs(total_p - 1.0) < 0.01


@pytest.mark.asyncio
async def test_db_health_endpoint(async_client: AsyncClient):
    """Verify /api/pipeline/db-health returns 25 tables and health metric."""
    response = await async_client.get("/api/pipeline/db-health")
    assert response.status_code == 200
    data = response.json()
    assert "health" in data
    assert data["health"] in ["HEALTHY", "DEGRADED"]
    assert "total_tables_found" in data
    assert data["total_tables_found"] >= 18
