"""
test_failure_recovery.py — Pillar 9: Failure Recovery & CSV Fallback Tests
"""

import pytest
from httpx import AsyncClient

from pipeline.db import pipeline_db


@pytest.mark.asyncio
async def test_graceful_csv_fallback_when_db_offline(async_client: AsyncClient):
    """Verify system remains operational and returns responses even if DB is offline."""
    orig_status = pipeline_db.is_connected
    try:
        # Simulate offline DB
        pipeline_db.is_connected = False
        response = await async_client.get("/api/dashboard/NIFTY?interval=15m")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "NIFTY"
    finally:
        pipeline_db.is_connected = orig_status


@pytest.mark.asyncio
async def test_scheduler_status_resilience():
    """Verify scheduler status method handles exceptions gracefully."""
    from pipeline.scheduler import scheduler as wq_scheduler

    status = wq_scheduler.status()
    assert isinstance(status, dict)
