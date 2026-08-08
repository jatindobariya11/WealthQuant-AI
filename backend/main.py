import os
import sys
import time
import traceback

# Load .env file before any module imports read environment variables
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Ensure local backend path is in sys.path (replaces Colab /content path)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Startup Self-Test (V11.2)
try:
    from preflight import run_preflight_checks

    run_preflight_checks()
except ImportError as e:
    print(f"[Init] Failed to load preflight checks: {e}")

import math

import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse as BaseJSONResponse


def sanitize_json_values(obj):
    if isinstance(obj, dict):
        return {k: sanitize_json_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_json_values(v) for v in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, (np.floating, np.float32, np.float64)):
        v = float(obj)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    elif isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    return obj


class SafeJSONResponse(BaseJSONResponse):
    def render(self, content) -> bytes:
        return super().render(sanitize_json_values(content))


JSONResponse = SafeJSONResponse
import asyncio
import threading
from contextlib import asynccontextmanager
from datetime import datetime

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import cache
import database as DB
import yfinance as yf
from constants import NIFTY_50
from core.limiter import limiter
from core.security import verify_token
from core.thread_pools import yahoo_pool
from data_fetcher import (
    BREEZE_API_KEY,
    TRUEDATA_USER,
    fetch_market_breadth_unified,
    get_ltp_with_fallback,
)
from data_fetchers import get_fii_dii_async, get_global_markets, get_india_vix
from groww_api import (
    get_groww_quote,
    get_holdings,
    get_order_book,
    get_positions,
    place_order,
)
from prediction_engine import analyze_fii_trends
from quant_mtf_engine import run_quant_mtf_engine, scan_with_quant_engine
from screener import run_screener, sector_summary
from signaldesk_engine import build_signaldesk

# ── Startup Cache Pre-Warmer ───────────────────────────────
_PREWARM_INDICES = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"]
_PREWARM_INTERVAL = "5m"


def _prewarm_cache():
    import time as _t

    DB.init_db()  # Ensure DB is ready
    _t.sleep(2)  # let the server fully start first
    print("[PreWarm] Starting cache pre-warm for all indices...")
    for sym in _PREWARM_INDICES:
        try:
            t0 = _t.time()
            # Pre-warm both fast and full signal for each index
            from data_fetcher import fetch_ohlc_and_indicators

            fetch_ohlc_and_indicators(sym, _PREWARM_INTERVAL)
            print(f"[PreWarm] {sym} core done in {round(_t.time() - t0, 1)}s")
        except (RuntimeError, OSError, ValueError, ConnectionError) as e:
            print(f"[PreWarm] {sym} failed: {e}")
        _t.sleep(0.5)  # minimal stagger (caching prevents rate-limiting)
    # Then warm full signal desk for the most common index
    try:
        t0 = _t.time()
        build_signaldesk("NIFTY", _PREWARM_INTERVAL)
        print(f"[PreWarm] NIFTY full signal done in {round(_t.time() - t0, 1)}s")
    except (RuntimeError, OSError, ValueError, ConnectionError) as e:
        print(f"[PreWarm] NIFTY full signal failed: {e}")
    print("[PreWarm] Cache pre-warm complete.")


from dashboard_routes import get_dashboard_perf
from dashboard_routes import router as dashboard_router
from pipeline.db import pipeline_db
from pipeline.prediction_store import prediction_store
from pipeline.scheduler import scheduler as wq_scheduler
from pipeline_routes import auth_router, explainability_router
from pipeline_routes import router as pipeline_router

# ── V9.0-V10.0 Research, Alpha, Incubation & Replay Engine ─────────────────
_research_router = None
_alpha_router = None
_incubation_router = None
_replay_router = None
try:
    from research.alpha.alpha_routes import router as _alpha_router
    from research.incubation.incubation_routes import router as _incubation_router
    from research.replay.replay_routes import router as _replay_router
    from research.research_dashboard import router as _research_router

    print("[Init] WealthQuant V10.0 Market Replay Engine: LOADED")
except ImportError as _re:
    print(f"[Init] Research/Replay modules not yet available: {_re}")
except (RuntimeError, OSError, SyntaxError) as _re:
    print(f"[Init] Research/Replay load error: {_re}")


async def _async_precomputation_worker():
    """Background worker that computes pipeline predictions continuously to serve the cache."""
    from pipeline.orchestrator import PipelineOrchestrator

    orchestrator = PipelineOrchestrator()
    print("[AsyncPrecompute] Background pipeline worker started.")
    while True:
        try:
            for sym in ["NIFTY", "BANKNIFTY"]:
                t0 = time.perf_counter()
                res = await orchestrator.run(sym, "5m", skip_llm=True)
                latency_ms = (time.perf_counter() - t0) * 1000

                prob_dict = res.probabilities.to_dict()
                prob_dict["latency_ms"] = round(latency_ms, 2)
                prob_dict["stage_latencies"] = {
                    k: round(v, 2) for k, v in res.stage_latencies.items()
                }
                prob_dict["cached"] = False

                prediction_store.lock(
                    sym,
                    "5m",
                    sanitize_json_values(prob_dict),
                    latency_ms,
                    namespace="pipeline_prob",
                )
            await asyncio.sleep(60)  # Precompute every 60s
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[AsyncPrecompute] Error during background prediction: {e}")
            await asyncio.sleep(60)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Modern FastAPI lifespan (replaces deprecated @on_event)."""
    # Initialize PostgreSQL pool with detailed diagnostics
    db_ok = await pipeline_db.init_pool()
    if db_ok:
        # Run health check and log table counts
        health = await pipeline_db.health_check()
        print(
            f"[Startup] Database health: {health['health']} | "
            f"Tables: {health['total_tables_found']}/18 | "
            f"Total rows: {health['total_rows']}"
        )
    else:
        print("[Startup] [WARN] Database offline - running in CSV fallback mode")

    t = threading.Thread(target=_prewarm_cache, daemon=True)
    t.start()

    # ── V7.4: Start background data collection scheduler ──
    try:
        await wq_scheduler.start()
        print(
            "[Startup] WealthQuant V7.4 Scheduler: RUNNING (24/7 data collection active)"
        )
    except Exception as sched_err:
        logger.error(f"[Startup] [CRITICAL] Scheduler failed to start: {sched_err}")
        print(f"[Startup] [CRITICAL] Scheduler failed to start: {sched_err}")
        from pipeline.scheduler import _state

        _state.running = False

    # Start Inference Background Precomputator
    precomp_task = asyncio.create_task(_async_precomputation_worker())

    yield

    precomp_task.cancel()

    # ── Graceful shutdown: stop scheduler first, then close DB ──
    try:
        await wq_scheduler.stop()
    except (RuntimeError, OSError, ConnectionError) as stop_err:
        print(f"[Shutdown] Scheduler stop error: {stop_err}")
    await pipeline_db.close()


app = FastAPI(title="WealthQuant Market Intelligence API", lifespan=_lifespan)


# FIX-009: Request Size Limits
@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH"):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 2_000_000:  # 2 MB limit
            return JSONResponse(
                status_code=413, content={"detail": "Payload Too Large"}
            )
    return await call_next(request)


# FIX-006: HTTP Security Headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = (
        "max-age=63072000; includeSubDomains; preload"
    )
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    return response


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(auth_router)
app.include_router(pipeline_router)
app.include_router(explainability_router)
app.include_router(dashboard_router)
if _research_router is not None:
    app.include_router(_research_router)
    print("[FastAPI] Research Laboratory routes registered at /api/research/*")
if _alpha_router is not None:
    app.include_router(_alpha_router)
    print("[FastAPI] Alpha Discovery Engine routes registered at /api/alpha/*")
if _incubation_router is not None:
    app.include_router(_incubation_router)
    print("[FastAPI] Incubation Platform routes registered at /api/incubation/*")
if _replay_router is not None:
    app.include_router(_replay_router)
    print("[FastAPI] Replay Engine routes registered at /api/replay/*")

# ── Production Hardened CORS ───────────────────────────────
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ── Global Exception Handler ──────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": exc.detail, "detail": exc.detail},
        )
    print(f"Global unhandled exception: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal Server Error",
            "detail": "Internal server error",
        },
    )


# ── Performance Timing Middleware ──────────────────────────
# Rolling latency window for /api/metrics
_api_latencies: list[float] = []
_api_latencies_lock = __import__("threading").Lock()


@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed_ms = round((time.time() - start) * 1000, 1)
    response.headers["X-Response-Time"] = f"{elapsed_ms}ms"
    # Track latency for metrics (skip static/health)
    path = request.url.path
    if path.startswith("/api/") and path not in ("/api/metrics",):
        with _api_latencies_lock:
            _api_latencies.append(elapsed_ms)
            if len(_api_latencies) > 500:
                _api_latencies.pop(0)
    return response


# ══════════════════════════════════════════════════════════════════
# SIGNAL BUILDER + QUALITY CHECKER (WealthQuant v2)
# ══════════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "status": "WealthQuant API running",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ─────────────────────────────────────────────
# Cache Management
# ─────────────────────────────────────────────




# ─────────────────────────────────────────────
# Platform Performance Metrics
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
# Market Context
# ─────────────────────────────────────────────


# FIX — run all three market-context fetchers concurrently with individual
# timeouts so one slow NSE/yfinance call never blocks the full 30s budget.
_MARKET_CTX_FALLBACKS = {
    "global": {"markets": {}, "bullish_count": 0, "total": 0, "bias": "MIXED"},
    "vix": {
        "vix": None,
        "change_pct": None,
        "regime": "UNKNOWN",
        "premium_multiplier": 1.0,
        "strategy_bias": "NEUTRAL",
        "history": [],
    },
    "fii_dii": {
        "fii_net": 0,
        "dii_net": 0,
        "combined": 0,
        "fii_bias": "NEUTRAL",
        "dii_bias": "NEUTRAL",
        "streak": 0,
        "streak_note": "",
        "note": "Data unavailable",
        "is_weekend": False,
        "history": [],
    },
}




# ─────────────────────────────────────────────
# Advance / Decline (Market Breadth)
# ─────────────────────────────────────────────




# Signal Desk routes are now handled by signal_desk_v2 above.


# Options and Market Data v2 are now handled above.






from fastapi.concurrency import run_in_threadpool




# FIX #3 — removed /api/sectors endpoint: it ran a full ~15s Nifty50 scan
# redundantly. Sector data is already included in /api/screener response
# under the "sectors" key. Use that instead.
# Quant MTF  — static scan routes BEFORE {symbol}
# (FIX #17, #18 — route ordering prevents /scan/nifty50 matching {symbol})
# ─────────────────────────────────────────────




# Parameterized LAST — avoids shadowing static routes above


# ─────────────────────────────────────────────
# Alpha Vantage  (secondary data source / BSE stocks)
# Free tier: 25 req/day, 5 req/min
# ─────────────────────────────────────────────






# ─────────────────────────────────────────────
# Groww Trading API  (live NSE data + order management)
# Requires: GROWW_AUTH_TOKEN set in groww_api.py
# ─────────────────────────────────────────────














# (duplicate routes removed — canonical definitions are above)

# ─────────────────────────────────────────────
# WealthQuant UI Integration Recovery Routes
# ─────────────────────────────────────────────
from fastapi import WebSocket

from api.server import engines as gamma_engines
from api.server import fetch_live_metrics, websocket_signals
from api.server import fetcher as gamma_fetcher
from institutional_detector import get_institutional_alerts










if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)