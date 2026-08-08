"""
╔══════════════════════════════════════════════════════════════════════════╗
║  WealthQuant — Dashboard Routes                                          ║
║                                                                          ║
║  MISSION: Single aggregated API endpoint for the entire dashboard.       ║
║                                                                          ║
║  GET /api/dashboard/{symbol}                                             ║
║    Returns: prediction, market_snapshot, options_summary, regime,        ║
║             explainability, confidence, system_health, scheduler_status, ║
║             performance, timestamp                                        ║
║                                                                          ║
║  Strategy:                                                                ║
║    1. Check DashboardCache (in-memory) → return instantly on hit         ║
║    2. Cold cache: parallel read from existing cache.py TTL store         ║
║    3. One async DB query for latest options + regime metadata            ║
║    4. Inject PredictionStore metadata (lock state, valid_until)          ║
║    5. Store result in DashboardCache                                     ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

import cache
from core.health_monitor import HealthMonitor
from core.thread_pools import yahoo_pool
from dashboard_cache import dashboard_cache
from data_fetcher import get_ltp_with_fallback
from pipeline.db import pipeline_db
from pipeline.prediction_store import prediction_store
from pipeline.scheduler import scheduler as wq_scheduler

logger = logging.getLogger("wealthquant.dashboard")

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


# ── Performance tracking ──────────────────────────────────────────────────
import threading

_perf = {
    "total_requests": 0,
    "cache_hits": 0,
    "latencies_ms": [],  # Rolling window (last 200)
}
_perf_lock = threading.Lock()
_MAX_LATENCY_SAMPLES = 200


def _record_latency(ms: float, cache_hit: bool):
    with _perf_lock:
        _perf["total_requests"] += 1
        if cache_hit:
            _perf["cache_hits"] += 1
        _perf["latencies_ms"].append(ms)
        if len(_perf["latencies_ms"]) > _MAX_LATENCY_SAMPLES:
            _perf["latencies_ms"].pop(0)


def get_dashboard_perf() -> dict:
    """Return dashboard performance stats (used by /api/metrics)."""
    lats = _perf["latencies_ms"]
    if not lats:
        return {
            "total_requests": 0,
            "cache_hit_ratio": 0.0,
            "latency_p50_ms": 0,
            "latency_p95_ms": 0,
        }
    sorted_lats = sorted(lats)
    n = len(sorted_lats)
    p50 = sorted_lats[int(n * 0.50)]
    p95 = sorted_lats[min(int(n * 0.95), n - 1)]
    hit_ratio = (
        round(_perf["cache_hits"] / _perf["total_requests"], 4)
        if _perf["total_requests"] > 0
        else 0.0
    )
    return {
        "total_requests": _perf["total_requests"],
        "cache_hit_ratio": hit_ratio,
        "latency_p50_ms": round(p50, 1),
        "latency_p95_ms": round(p95, 1),
    }


# ── DB helpers ────────────────────────────────────────────────────────────
async def _fetch_dashboard_db_metadata(
    symbol: str,
) -> tuple[dict | None, dict | None, str | None]:
    """Fetch prediction, options intelligence, and snapshot age in a single connection checkout."""
    if not pipeline_db.is_connected or not pipeline_db.pool:
        return None, None, None
    sym = symbol.upper()
    db_pred, db_opts, market_data_age = None, None, None
    try:
        async with pipeline_db.pool.acquire() as conn:
            # 1. Prediction row
            row_pred = await conn.fetchrow(
                """
                SELECT signal, p_up, p_down, p_sideways, expected_return,
                       signal_confidence, regime, kelly_fraction, created_at
                FROM predictions
                WHERE symbol = $1
                ORDER BY created_at DESC
                LIMIT 1
            """,
                sym,
            )
            if row_pred:
                db_pred = {
                    "signal": row_pred["signal"],
                    "p_up": float(row_pred["p_up"] or 0),
                    "p_down": float(row_pred["p_down"] or 0),
                    "p_sideways": float(row_pred["p_sideways"] or 0),
                    "expected_return": float(row_pred["expected_return"] or 0),
                    "signal_confidence": float(row_pred["signal_confidence"] or 0),
                    "regime": row_pred["regime"],
                    "kelly_fraction": float(row_pred["kelly_fraction"] or 0),
                    "db_created_at": row_pred["created_at"].isoformat()
                    if row_pred["created_at"]
                    else None,
                }

            # 2. Options row
            row_opts = await conn.fetchrow(
                """
                SELECT pcr, call_wall, put_wall, atm_iv,
                       gamma_pressure, dealer_pressure, forecast, timestamp
                FROM options_intelligence
                WHERE symbol = $1
                ORDER BY timestamp DESC
                LIMIT 1
            """,
                sym,
            )
            if row_opts:
                db_opts = {
                    "pcr": float(row_opts["pcr"] or 0),
                    "call_wall": float(row_opts["call_wall"] or 0),
                    "put_wall": float(row_opts["put_wall"] or 0),
                    "atm_iv": float(row_opts["atm_iv"] or 0),
                    "gamma_pressure": float(row_opts["gamma_pressure"] or 0),
                    "dealer_pressure": float(row_opts["dealer_pressure"] or 0),
                    "forecast": row_opts["forecast"],
                    "timestamp": row_opts["timestamp"].isoformat()
                    if row_opts["timestamp"]
                    else None,
                }

            # 3. Market snapshot age
            ts_snap = await conn.fetchval(
                """
                SELECT MAX(timestamp) FROM market_snapshots WHERE symbol = $1
            """,
                sym,
            )
            if ts_snap:
                market_data_age = ts_snap.isoformat()
    except Exception as e:
        logger.warning(f"[Dashboard] Consolidated DB metadata fetch failed: {e}")

    return db_pred, db_opts, market_data_age


async def _fetch_latest_prediction_from_db(symbol: str) -> dict | None:
    p, _, _ = await _fetch_dashboard_db_metadata(symbol)
    return p


async def _fetch_latest_options_from_db(symbol: str) -> dict | None:
    _, o, _ = await _fetch_dashboard_db_metadata(symbol)
    return o


async def _fetch_market_snapshot_age(symbol: str) -> str | None:
    _, _, a = await _fetch_dashboard_db_metadata(symbol)
    return a


# ── Main Dashboard Builder ────────────────────────────────────────────────


def _get_signal_and_prediction(sym: str, interval: str):
    fast_cache_key = f"fast_signal:{sym}:{interval}"
    full_cache_key = f"signal_desk_v2:{sym}:{interval}"
    live_rec = prediction_store.get_live(sym, interval, namespace="signal_desk")
    if live_rec and live_rec.data:
        pred_meta = live_rec.to_metadata()
        signal_data = live_rec.data
    else:
        fast_data = cache.get(fast_cache_key) or {}
        full_data = cache.get(full_cache_key) or {}
        signal_data = full_data if full_data else fast_data
        pred_meta = prediction_store.get_metadata(
            sym, interval, namespace="signal_desk"
        )
    return live_rec, pred_meta, signal_data


async def _get_ltp_fallback(sym: str, signal_data: dict):
    ltp_cache_key = f"ltp_fallback:{sym}"
    ltp_cached = cache.get(ltp_cache_key)
    ltp = (ltp_cached or {}).get("ltp") or signal_data.get("price") or 0
    if not ltp:
        try:
            loop = asyncio.get_running_loop()
            ltp_res = await asyncio.wait_for(
                loop.run_in_executor(yahoo_pool, get_ltp_with_fallback, sym),
                timeout=3.0,
            )
            ltp = ltp_res.get("ltp") or 0
        except Exception as e:
            logger.warning(
                f"[Dashboard] LTP fetch fallback timed out or failed for {sym}: {e}"
            )
            ltp = 0
    return ltp


def _get_system_health():
    try:
        if not wq_scheduler.is_running():
            asyncio.create_task(wq_scheduler.start())
        sched_status = wq_scheduler.status()
    except Exception as e:
        logger.error(f"Scheduler check failed: {e}")
        sched_status = {"running": False, "is_running": False}

    try:
        health_metrics = {
            "db_connected": pipeline_db.is_connected,
            "scheduler_active": sched_status.get(
                "running", sched_status.get("is_running", False)
            ),
        }
        system_health = HealthMonitor.calculate_system_status(health_metrics)
    except Exception as e:
        logger.error(f"Health calculation failed: {e}")
        system_health = {"health_score": 0, "status": "OFFLINE"}

    return sched_status, system_health


def _synthesize_prediction(sig, db_pred, pred_meta, interval, sym):
    if not sig and db_pred:
        sig = {
            "signal": db_pred.get("signal", "NEUTRAL"),
            "confidence": {"score": db_pred.get("signal_confidence", 0)},
        }

    if not pred_meta and db_pred and db_pred.get("db_created_at"):
        _interval_minutes = {
            "1m": 1,
            "3m": 3,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "1d": 1440,
        }
        _mins = _interval_minutes.get(interval, 15)
        _now = datetime.now()
        _total_mins = _now.hour * 60 + _now.minute
        _next_close_mins = ((_total_mins // _mins) + 1) * _mins
        _valid_until = _now.replace(
            hour=_next_close_mins // 60 % 24,
            minute=_next_close_mins % 60,
            second=0,
            microsecond=0,
        )
        if _next_close_mins >= 1440:
            _valid_until += timedelta(days=1)
        _secs_remaining = max(0.0, round((_valid_until - _now).total_seconds(), 1))
        pred_meta = {
            "prediction_id": "db-"
            + (
                db_pred.get("db_created_at", "")[:16]
                .replace(":", "-")
                .replace("T", "_")
            ),
            "created_at": db_pred.get("db_created_at"),
            "valid_until": _valid_until.isoformat(),
            "prediction_state": "LIVE",
            "age_seconds": None,
            "seconds_remaining": _secs_remaining,
            "latency_ms": 0,
            "prediction_version": f"{sym}-{interval}-db",
            "_source": "database",
        }
    return sig, pred_meta


def _build_dashboard_response(
    sym,
    interval,
    ltp,
    signal_data,
    db_pred,
    db_opts,
    market_data_age,
    sched_status,
    system_health,
    pred_meta,
    sig,
    elapsed_ms,
    live_rec,
):
    now_iso = datetime.now().isoformat()
    quality = signal_data.get("signal_quality") or signal_data.get("quality") or {}
    entry_exit = signal_data.get("entry_exit") or {}
    mo = signal_data.get("market_overview") or {}
    regime_raw = signal_data.get("regime") or {}

    return {
        "symbol": sym,
        "interval": interval,
        "timestamp": now_iso,
        "prediction": {
            **(pred_meta or {}),
            "signal": sig.get("signal") or (db_pred or {}).get("signal", "NEUTRAL"),
            "confidence": (sig.get("confidence") or {}).get("score")
            or (db_pred or {}).get("signal_confidence", 0),
            "p_up": (db_pred or {}).get("p_up", 0),
            "p_down": (db_pred or {}).get("p_down", 0),
            "p_sideways": (db_pred or {}).get("p_sideways", 0),
            "kelly_fraction": (db_pred or {}).get("kelly_fraction", 0),
            "state": sig.get("state") or signal_data.get("state", "NO TRADE"),
            "readiness": signal_data.get("readiness", 0),
            "score": signal_data.get("score", 0),
            "allow_trade": signal_data.get("allow_trade", False),
            "entry_exit": entry_exit,
            "breakdown": sig.get("breakdown", {}),
            "conditions": quality.get("conditions", []),
        },
        "market_snapshot": {
            "ltp": ltp,
            "change_pct": mo.get("change_pct") or signal_data.get("change_pct", 0),
            "rsi": mo.get("rsi"),
            "macd": mo.get("macd"),
            "atr": mo.get("atr"),
            "ema9": mo.get("ema9"),
            "ema21": mo.get("ema21"),
            "ema50": mo.get("ema50"),
            "volume": mo.get("volume", {}),
            "candle": mo.get("candle"),
            "supertrend": mo.get("supertrend"),
            "supertrend_dir": mo.get("supertrend_dir"),
            "market_data_age": market_data_age,
            "timestamp": now_iso,
        },
        "options_summary": {
            **(db_opts or {}),
            "pcr": (signal_data.get("options") or {}).get("pcr")
            or (db_opts or {}).get("pcr"),
            "oi_score": (signal_data.get("options") or {}).get("oi_score"),
            "oi_signal": (signal_data.get("options") or {}).get("oi_signal"),
            "max_pain": (signal_data.get("options") or {}).get("max_pain"),
            "options_data_age": (db_opts or {}).get("timestamp"),
        },
        "regime": {
            "current": regime_raw.get("current_regime")
            or (db_pred or {}).get("regime", "UNKNOWN"),
            "confidence": regime_raw.get("regime_confidence"),
            "duration_bars": regime_raw.get("duration_bars"),
            "changepoint_detected": regime_raw.get("changepoint_detected", False),
            "regime_history": regime_raw.get("history", []),
        },
        "explainability": {
            "active_triggers": (signal_data.get("engine_output") or {}).get(
                "active_triggers", []
            ),
            "missing_triggers": (signal_data.get("engine_output") or {}).get(
                "reason", []
            ),
            "trigger_count": (signal_data.get("engine_output") or {}).get(
                "trigger_count", 0
            ),
            "intermarket": signal_data.get("intermarket", {}),
            "stage_contributions": [],
        },
        "confidence": {
            "score": quality.get("pct", 0),
            "grade": quality.get("grade", "—"),
            "label": quality.get("label", "—"),
            "max_score": quality.get("max_score", 100),
            "signal_quality": quality.get("conditions", []),
        },
        "system_health": {
            **system_health,
            "db_connected": pipeline_db.is_connected,
            "db_sync": "LIVE" if pipeline_db.is_connected else "OFFLINE",
        },
        "scheduler_status": sched_status,
        "live_status": {
            "prediction_generated": (pred_meta or {}).get("created_at"),
            "prediction_valid_until": (pred_meta or {}).get("valid_until"),
            "prediction_age_seconds": (pred_meta or {}).get("age_seconds"),
            "prediction_state": (pred_meta or {}).get("prediction_state", "UNKNOWN"),
            "market_data_age": market_data_age,
            "options_data_age": (db_opts or {}).get("timestamp"),
            "db_sync": "LIVE" if pipeline_db.is_connected else "OFFLINE",
            "scheduler_running": sched_status.get(
                "running", sched_status.get("is_running", False)
            ),
        },
        "performance": {
            "dashboard_latency_ms": round(elapsed_ms, 1),
            "cache_hit": live_rec is not None,
            "data_source": "prediction_store" if live_rec else "live_compute",
        },
        "chart": signal_data.get("chart", []),
        "sr_zone": signal_data.get("sr_zone", {}),
        "levels": signal_data.get("levels", {}),
        "_fast": signal_data.get("_fast", True),
    }


async def _build_dashboard(symbol: str, interval: str) -> dict:
    t0 = time.perf_counter()
    sym = symbol.upper()

    live_rec, pred_meta, signal_data = _get_signal_and_prediction(sym, interval)
    ltp = await _get_ltp_fallback(sym, signal_data)
    db_pred, db_opts, market_data_age = await _fetch_dashboard_db_metadata(sym)
    sched_status, system_health = _get_system_health()

    sig = signal_data.get("signal") or {}
    sig, pred_meta = _synthesize_prediction(sig, db_pred, pred_meta, interval, sym)

    elapsed_ms = (time.perf_counter() - t0) * 1000

    response = _build_dashboard_response(
        sym,
        interval,
        ltp,
        signal_data,
        db_pred,
        db_opts,
        market_data_age,
        sched_status,
        system_health,
        pred_meta,
        sig,
        elapsed_ms,
        live_rec,
    )

    if not live_rec:
        rec = prediction_store.lock(
            sym, interval, signal_data, elapsed_ms, namespace="signal_desk"
        )
        response["live_status"].update(rec.to_metadata())

    return response


# ── Route ─────────────────────────────────────────────────────────────────
@router.get("/{symbol}")
async def get_dashboard(
    symbol: str,
    interval: str = Query("15m", description="Bar interval: 5m, 15m, 30m, 1h"),
):
    """
    Aggregated dashboard endpoint.
    Returns prediction, market_snapshot, options_summary, regime,
    explainability, confidence, system_health, scheduler_status,
    and live_status in a single response.

    Cache strategy:
      - In-memory DashboardCache hit → ~0ms response
      - Cold cache → builds from existing TTL cache + parallel DB queries
    """
    t0 = time.perf_counter()
    sym = symbol.upper()
    cache_key = f"{sym}:{interval}"

    # ── 1. Check in-memory dashboard cache ────────────────────────────
    cached = dashboard_cache.get(cache_key)
    if cached:
        elapsed = (time.perf_counter() - t0) * 1000
        _record_latency(elapsed, cache_hit=True)
        perf = cached.setdefault("performance", {})
        perf["cache_hit"] = True
        perf["dashboard_latency_ms"] = round(elapsed, 1)
        return JSONResponse(content=cached)

    # ── 2. Build fresh dashboard ──────────────────────────────────────
    try:
        data = await _build_dashboard(sym, interval)

        # ── 3. Determine candle_ts for cache refresh logic
        chart = data.get("chart", [])
        candle_ts = chart[-1]["Datetime"] if chart else ""
        ltp = data.get("market_snapshot", {}).get("ltp", 0) or 0

        # ── 4. Store in dashboard cache ───────────────────────────────
        dashboard_cache.set(cache_key, data, candle_ts=candle_ts, ltp=ltp)

        elapsed = (time.perf_counter() - t0) * 1000
        _record_latency(elapsed, cache_hit=False)
        data["performance"]["dashboard_latency_ms"] = round(elapsed, 1)

        logger.info(
            f"[Dashboard] {sym}/{interval} | "
            f"source={data['performance']['data_source']} | "
            f"latency={elapsed:.0f}ms"
        )
        return JSONResponse(content=data)

    except Exception as e:
        import traceback

        logger.error(
            f"[Dashboard] Build failed for {sym}: {e}\n{traceback.format_exc()}"
        )
        # Return minimal error response (never crash the frontend)
        return JSONResponse(
            status_code=200,  # Return 200 with error flag so frontend doesn't show error bar
            content={
                "symbol": sym,
                "interval": interval,
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "prediction": {
                    "signal": "NEUTRAL",
                    "state": "NO TRADE",
                    "allow_trade": False,
                },
                "market_snapshot": {},
                "system_health": {"status": "DEGRADED"},
                "live_status": {"db_sync": "UNKNOWN", "scheduler_running": False},
                "performance": {"cache_hit": False, "dashboard_latency_ms": 0},
            },
        )


@router.get("/{symbol}/invalidate")
async def invalidate_dashboard_cache(symbol: str):
    """Force-invalidate dashboard cache for a symbol (admin use)."""
    dashboard_cache.invalidate(symbol.upper())
    return {"status": "invalidated", "symbol": symbol.upper()}
