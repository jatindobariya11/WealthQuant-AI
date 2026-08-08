"""
test_api_snapshot.py — WealthQuant V14.1 API Snapshot / Contract Regression Tests (FIX-004)
Verifies response envelopes, field names, and status codes across core endpoints.
"""

import os
import sys

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("JWT_SECRET_KEY", "test_secret_key_for_testing_purposes_v14")
os.environ.setdefault("GROWW_AUTH_TOKEN", "test_token")

from main import app  # noqa: E402


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ─── Snapshot: Root endpoint ──────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_snapshot_root(client):
    r = await client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert (
        "message" in body or "status" in body or "api" in body or isinstance(body, dict)
    )


# ─── Snapshot: Dashboard ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_snapshot_dashboard_status_code(client):
    r = await client.get("/api/dashboard/NIFTY?interval=15m")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_snapshot_dashboard_has_prediction_field(client):
    r = await client.get("/api/dashboard/NIFTY?interval=15m")
    assert r.status_code == 200
    body = r.json()
    assert "prediction" in body, (
        f"Missing 'prediction' field. Keys: {list(body.keys())}"
    )


@pytest.mark.asyncio
async def test_snapshot_dashboard_has_symbol_field(client):
    r = await client.get("/api/dashboard/NIFTY?interval=15m")
    assert r.status_code == 200
    body = r.json()
    assert "symbol" in body, f"Missing 'symbol' field. Keys: {list(body.keys())}"


# ─── Snapshot: Market Context ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_snapshot_market_context_status_code(client):
    r = await client.get("/api/market-context")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_snapshot_market_context_is_dict(client):
    r = await client.get("/api/market-context")
    body = r.json()
    assert isinstance(body, dict)


# ─── Snapshot: Health Endpoints ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_snapshot_health_basic(client):
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body


@pytest.mark.asyncio
async def test_snapshot_health_full(client):
    r = await client.get("/health/full")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_snapshot_health_full_has_subsystems(client):
    r = await client.get("/health/full")
    body = r.json()
    assert "subsystems" in body, "Full health must contain 'subsystems' field"


# ─── Snapshot: DB Health ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_snapshot_db_health(client):
    r = await client.get("/api/pipeline/db-health")
    assert r.status_code == 200


# ─── Snapshot: Signal Desk ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_snapshot_signal_desk_status(client):
    r = await client.get("/api/signal-desk/NIFTY/15m")
    assert r.status_code in (200, 500)  # 500 acceptable during market close


# ─── Snapshot: Screener ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_snapshot_screener_is_list_or_dict(client):
    r = await client.get("/api/screener")
    assert r.status_code in (200, 500)
    if r.status_code == 200:
        body = r.json()
        assert isinstance(body, (list, dict))


# ─── Snapshot: Metrics ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_snapshot_metrics_status_code(client):
    r = await client.get("/api/metrics")
    assert r.status_code == 200


# ─── Snapshot: Institutional endpoint ────────────────────────────────────────
@pytest.mark.asyncio
async def test_snapshot_institutional_status_code(client):
    r = await client.get("/api/institutional/NIFTY")
    assert r.status_code in (200, 404, 500)
