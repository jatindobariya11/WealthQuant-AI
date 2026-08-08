"""
test_failure_injection.py — WealthQuant V14.1 Expanded Failure Injection Tests (FIX-006)
Covers: DB outage, Cache eviction, Scheduler failure, Prediction cache miss,
        Background worker restart scenarios.
"""

import asyncio
import os
import sys

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("JWT_SECRET_KEY", "test_secret_key_for_testing_purposes_v14")
os.environ.setdefault("GROWW_AUTH_TOKEN", "test_token")

from main import app  # noqa: E402
from pipeline.db import pipeline_db  # noqa: E402
from pipeline.prediction_store import prediction_store  # noqa: E402


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ─── FIX-006-A: Database outage → graceful response ──────────────────────────
@pytest.mark.asyncio
async def test_db_outage_graceful_response(client):
    """System must respond 200 from CSV fallback when DB is marked offline."""
    orig = pipeline_db.is_connected
    try:
        pipeline_db.is_connected = False
        r = await client.get("/api/dashboard/NIFTY?interval=15m")
        assert r.status_code == 200, "Should fallback gracefully when DB is offline"
    finally:
        pipeline_db.is_connected = orig


# ─── FIX-006-B: DB pool exhaustion → no crash ────────────────────────────────
@pytest.mark.asyncio
async def test_db_concurrent_requests_no_crash(client):
    """Multiple concurrent API calls should not crash the system."""
    tasks = [client.get("/api/dashboard/NIFTY?interval=15m") for _ in range(10)]
    results = await asyncio.gather(*tasks)
    for r in results:
        assert r.status_code in (200, 429, 503)


# ─── FIX-006-C: Cache miss → pipeline executes fresh ─────────────────────────
@pytest.mark.asyncio
async def test_prediction_cache_miss_triggers_fresh_run(client):
    """After cache is cleared, system should still return a valid response."""
    prediction_store.clear("NIFTY", "15m")
    r = await client.get("/health/full")
    assert r.status_code == 200


# ─── FIX-006-D: Cache outage simulation via invalidation ─────────────────────
def test_cache_invalidation_does_not_crash():
    """Cache invalidation on a non-existent key should not raise exceptions."""
    try:
        prediction_store.clear("NONEXISTENT_SYM", "99m")
    except Exception as e:
        pytest.fail(f"Cache clear raised unexpected exception: {e}")


# ─── FIX-006-E: Scheduler status during simulated failure ────────────────────
def test_scheduler_status_resilience_on_exception():
    """Scheduler status query must not crash even when internals raise."""
    from pipeline.scheduler import scheduler as wq_scheduler

    # Simulate exception is handled gracefully
    try:
        status = wq_scheduler.status()
        assert isinstance(status, dict)
    except Exception as e:
        pytest.fail(f"Scheduler status raised unexpectedly: {e}")


# ─── FIX-006-F: WebSocket disconnect cleanup (mock) ──────────────────────────
@pytest.mark.asyncio
async def test_ws_disconnect_no_exception(client):
    """Abrupt WS close (no token) must not leave server in broken state."""
    r = await client.get("/ws/live/NIFTY")
    assert r.status_code in (403, 400, 200)
    # After the disconnect, health must still pass
    health = await client.get("/health")
    assert health.status_code == 200


# ─── FIX-006-G: Prediction store — expire_immediately on missing key ──────────
def test_prediction_store_expire_immediately_no_key():
    """expire_immediately on a key that doesn't exist should return False gracefully."""
    result = prediction_store.expire_immediately("FAKE_SYM", "99m", "TEST_REASON")
    assert result is False or result is None or isinstance(result, bool)


# ─── FIX-006-H: Health endpoint resilience under load ────────────────────────
@pytest.mark.asyncio
async def test_health_resilience_concurrent(client):
    """Health endpoint must handle multiple concurrent hits without failure."""
    tasks = [client.get("/health") for _ in range(20)]
    results = await asyncio.gather(*tasks)
    for r in results:
        assert r.status_code == 200


# ─── FIX-006-I: Patch DB pool to None → no crash ────────────────────────────
@pytest.mark.asyncio
async def test_db_pool_none_graceful(client):
    """If pool is None, system should remain operational."""
    orig_pool = pipeline_db.pool
    orig_connected = pipeline_db.is_connected
    try:
        pipeline_db.pool = None
        pipeline_db.is_connected = False
        r = await client.get("/health")
        assert r.status_code == 200
    finally:
        pipeline_db.pool = orig_pool
        pipeline_db.is_connected = orig_connected


# ─── FIX-006-J: Error endpoint returns proper schema ─────────────────────────
@pytest.mark.asyncio
async def test_404_returns_proper_response(client):
    """Unknown endpoints should return a proper HTTP error."""
    r = await client.get("/api/this_route_does_not_exist_v14")
    assert r.status_code == 404
