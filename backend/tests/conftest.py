"""
conftest.py — Pytest Configuration & Global Fixtures for WealthQuant V14.1
"""

import asyncio
import os
import sys
import time

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

# ── FIX-002/003: Set required env vars BEFORE any app imports ───────────────
os.environ.setdefault("JWT_SECRET_KEY", "test_secret_key_for_testing_purposes_v14")
os.environ.setdefault("GROWW_AUTH_TOKEN", "test_token")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app  # noqa: E402
from pipeline.db import pipeline_db  # noqa: E402

_TEST_SECRET = os.environ["JWT_SECRET_KEY"]
_ALGORITHM = "HS256"


# ── JWT token factories ───────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def admin_token() -> str:
    """Generate a valid admin JWT for tests requiring elevated permissions."""
    payload = {
        "sub": "test_admin",
        "roles": ["admin", "trader", "risk_manager"],
        "exp": time.time() + 3600,
    }
    return jwt.encode(payload, _TEST_SECRET, algorithm=_ALGORITHM)


@pytest.fixture(scope="session")
def trader_token() -> str:
    """Generate a valid trader JWT for authenticated tests."""
    payload = {
        "sub": "test_trader",
        "roles": ["trader"],
        "exp": time.time() + 3600,
    }
    return jwt.encode(payload, _TEST_SECRET, algorithm=_ALGORITHM)


@pytest.fixture(scope="session")
def expired_token() -> str:
    """Generate an expired JWT for negative auth tests."""
    payload = {
        "sub": "test_expired",
        "roles": ["trader"],
        "exp": time.time() - 60,
    }
    return jwt.encode(payload, _TEST_SECRET, algorithm=_ALGORITHM)


# ── Event loop ────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop():
    """Create session-scoped event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ── Database ──────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
async def init_test_database():
    """Ensure database connection pool is initialized for testing."""
    await pipeline_db.init_pool()
    yield
    await pipeline_db.close()


# ── HTTP client ───────────────────────────────────────────────────────────────
@pytest.fixture
async def async_client():
    """Unauthenticated async HTTP client for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def admin_client(admin_token: str):
    """Authenticated (admin) async HTTP client."""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {admin_token}"}
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=headers
    ) as client:
        yield client


@pytest.fixture
async def trader_client(trader_token: str):
    """Authenticated (trader) async HTTP client."""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {trader_token}"}
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=headers
    ) as client:
        yield client
