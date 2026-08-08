"""
test_performance.py — Pillar 6: Performance Latency & Memory Profiling Tests
"""

import time

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_dashboard_cache_hit_latency(async_client: AsyncClient):
    """Verify warm dashboard cache responds in < 10.0 ms."""
    # Warm up cache first
    await async_client.get("/api/dashboard/NIFTY?interval=15m")

    t0 = time.perf_counter()
    response = await async_client.get("/api/dashboard/NIFTY?interval=15m")
    latency_ms = (time.perf_counter() - t0) * 1000.0

    assert response.status_code == 200
    assert latency_ms < 10.0


@pytest.mark.asyncio
async def test_metrics_p95_latency(async_client: AsyncClient):
    """Verify dashboard performance tracker records p50 and p95 latency."""
    response = await async_client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "dashboard" in data
    dash = data["dashboard"]
    assert "latency_p50_ms" in dash
    assert "latency_p95_ms" in dash
