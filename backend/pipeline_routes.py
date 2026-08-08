"""
FastAPI Routes for Probabilistic AI Pipeline.
Defines endpoints for pipeline results, probabilities, regimes, and LLM analyst reports.
"""

import logging
import time
from enum import Enum

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response

from core.health_monitor import HealthMonitor
from core.limiter import limiter
from core.schemas import (
    AuthRefreshResponse,
    ErrorResponse,
    PipelineEmergencyResponse,
    PipelineStatusResponse,
    ProbabilityOutput,
    StandardResponse,
)
from core.security import RoleChecker, verify_token
from dashboard_cache import dashboard_cache
from pipeline.db import pipeline_db
from pipeline.orchestrator import PipelineOrchestrator
from pipeline.prediction_store import prediction_store
from pipeline.scheduler import scheduler as wq_scheduler


class IntervalEnum(str, Enum):
    MIN_1 = "1m"
    MIN_5 = "5m"
    MIN_15 = "15m"
    HOUR_1 = "1h"
    DAY_1 = "1d"


logger = logging.getLogger("pipeline.routes")
router = APIRouter(prefix="/api/pipeline", tags=["Pipeline Intelligence"])
auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@auth_router.post(
    "/refresh",
    response_model=StandardResponse[AuthRefreshResponse],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized or token missing"}
    },
    summary="Refresh Access Token",
    description="Issues a new access token if a valid HTTP-only refresh cookie is present.",
    operation_id="refresh_access_token",
)
@limiter.limit("10/minute")
async def refresh_token(
    request: Request, response: Response, refresh_token: str = Cookie(None)
):
    """
    Refresh Token Flow (FIX-005)
    """
    from core.security import create_access_token, decode_token

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    new_access_token = create_access_token(
        {"sub": payload["sub"], "roles": payload.get("roles", [])}
    )
    return StandardResponse(
        data=AuthRefreshResponse(access_token=new_access_token, token_type="bearer"),
        message="Token refreshed",
    )


# Instantiate global orchestrator
orchestrator = PipelineOrchestrator()


@router.get("/scheduler-status")
async def get_scheduler_status():
    """
    Return the real-time status of the WealthQuant V7.4 continuous data
    collection scheduler (uptime, last ingestion, daily row counts, alerts, etc.)
    """
    try:
        return wq_scheduler.status()
    except Exception as e:
        logger.error(f"Failed to get scheduler status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/start-scheduler",
    response_model=StandardResponse[PipelineStatusResponse],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden - Admin role required"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
    },
    summary="Start Background Scheduler",
    description="Starts or restarts the background data collection scheduler.",
    operation_id="start_scheduler",
)
@limiter.limit("5/minute")
async def start_scheduler(
    request: Request, user: dict = Depends(RoleChecker(["admin"]))
):
    """
    Start or restart the background data collection scheduler. (Admin only)
    """
    try:
        logger.info(
            f"[AUDIT] User {user.get('sub')} started the scheduler from IP {request.client.host}"
        )
        await wq_scheduler.start()
        return StandardResponse(
            data=PipelineStatusResponse(
                status="SUCCESS", message="Scheduler started successfully."
            ),
            message="Operation complete",
        )
    except Exception as e:
        logger.error(f"Scheduler start failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/emergency-override",
    response_model=StandardResponse[PipelineEmergencyResponse],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {
            "model": ErrorResponse,
            "description": "Forbidden - Admin/Risk Manager role required",
        },
    },
    summary="Emergency Prediction Override",
    description="Invalidates live prediction immediately before valid_until. Used for black swan market events.",
    operation_id="emergency_override",
)
@limiter.limit("5/minute")
async def emergency_override(
    request: Request,
    symbol: str = Query("NIFTY"),
    interval: str = Query("5m"),
    reason: str = Query("CIRCUIT_BREAKER"),
    user: dict = Depends(RoleChecker(["admin", "risk_manager"])),
):
    """
    Emergency override protocol: Invalidates live prediction immediately before valid_until.
    Used for black swan market events (circuit breakers, exchange halts, extreme gap opens).
    """
    try:
        logger.info(
            f"[AUDIT] User {user.get('sub')} executed emergency override for {symbol} ({interval}). Reason: {reason}"
        )
        ok = prediction_store.expire_immediately(symbol, interval, reason)
        return StandardResponse(
            data=PipelineEmergencyResponse(
                status="SUCCESS" if ok else "NO_LIVE_PREDICTION",
                message=f"Override applied for {symbol} {interval}",
            ),
            message="Override executed",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_pipeline_status():
    """
    Get the health and status of the AI pipeline and database connection.
    """
    try:
        return orchestrator.get_status()
    except Exception as e:
        logger.error(f"Failed to get pipeline status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/db-health")
async def get_db_health():
    """
    Comprehensive database health check.
    Runs SELECT COUNT(*) on all tables and returns detailed diagnostics.
    """
    try:
        health = await pipeline_db.health_check()
        return health
    except Exception as e:
        logger.error(f"Failed to run DB health check: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system-status")
async def get_system_status():
    """
    V7.7 Institutional Prediction Calibration & Model Monitoring Dashboard
    Returns the live Health Score (0-100) and subsystem Green/Yellow/Red status.
    """
    try:
        metrics = {
            "db_connected": pipeline_db.is_connected,
            "scheduler_active": wq_scheduler.is_running()
            if hasattr(wq_scheduler, "is_running")
            else True,
        }

        # Optionally, we can fetch real drift and accuracy from DB here
        if pipeline_db.is_connected:
            async with pipeline_db.pool.acquire() as conn:
                acc_row = await conn.fetchrow(
                    "SELECT accuracy, calibration_status FROM prediction_accuracy ORDER BY id DESC LIMIT 1"
                )
                if acc_row:
                    metrics["accuracy"] = (
                        float(acc_row["accuracy"]) if acc_row["accuracy"] else 0.0
                    )
                    metrics["calibration_status"] = acc_row["calibration_status"]

                drift_row = await conn.fetchrow(
                    "SELECT is_drifted, drift_score FROM feature_drift ORDER BY updated_at DESC LIMIT 1"
                )
                if drift_row:
                    if float(drift_row["drift_score"] or 0) > 3.0:
                        metrics["drift_status"] = "Critical"
                    elif float(drift_row["drift_score"] or 0) > 2.0:
                        metrics["drift_status"] = "Warning"
                    else:
                        metrics["drift_status"] = "Healthy"

        health_data = HealthMonitor.calculate_system_status(metrics)
        return health_data
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/warehouse-health")
async def get_warehouse_health():
    """
    V7.5 Market Data Warehouse health check.
    Returns live row counts for all 5 warehouse tables + last download timestamps.
    Also triggers on-demand warehouse report generation.
    """
    if not pipeline_db.is_connected:
        return {"status": "db_not_connected", "warehouse": {}}
    try:
        async with pipeline_db.pool.acquire() as conn:
            queries = {
                "options_history": "SELECT COUNT(*) FROM options_history",
                "strike_history": "SELECT COUNT(*) FROM strike_history",
                "wall_history": "SELECT COUNT(*) FROM wall_history",
                "pcr_history": "SELECT COUNT(*) FROM pcr_history",
                "fii_dii": "SELECT COUNT(*) FROM fii_dii",
            }
            counts = {}
            for tbl, query in queries.items():
                counts[tbl] = await conn.fetchval(query)

            # Latest download per symbol for options
            last_downloads = {"NIFTY": {}, "BANKNIFTY": {}}
            for sym in last_downloads:
                last_downloads[sym] = {
                    "last_options_date": None,
                    "strikes_today": 0,
                    "latest_pcr_oi": None,
                    "latest_pcr_signal": None,
                    "latest_call_wall": None,
                    "latest_put_wall": None,
                }

            opts = await conn.fetch(
                "SELECT symbol, MAX(date) as max_date FROM options_history WHERE symbol IN ('NIFTY', 'BANKNIFTY') GROUP BY symbol"
            )
            for r in opts:
                last_downloads[r["symbol"]]["last_options_date"] = (
                    str(r["max_date"]) if r["max_date"] else None
                )

            strikes = await conn.fetch(
                "SELECT symbol, COUNT(*) as cnt FROM strike_history WHERE symbol IN ('NIFTY', 'BANKNIFTY') AND date=CURRENT_DATE GROUP BY symbol"
            )
            for r in strikes:
                last_downloads[r["symbol"]]["strikes_today"] = r["cnt"]

            pcr = await conn.fetch(
                "SELECT DISTINCT ON (symbol) symbol, pcr_oi, pcr_signal FROM pcr_history WHERE symbol IN ('NIFTY', 'BANKNIFTY') ORDER BY symbol, date DESC, id DESC"
            )
            for r in pcr:
                last_downloads[r["symbol"]]["latest_pcr_oi"] = (
                    round(float(r["pcr_oi"]), 3) if r["pcr_oi"] else None
                )
                last_downloads[r["symbol"]]["latest_pcr_signal"] = r["pcr_signal"]

            walls = await conn.fetch(
                "SELECT DISTINCT ON (symbol) symbol, call_wall, put_wall FROM wall_history WHERE symbol IN ('NIFTY', 'BANKNIFTY') ORDER BY symbol, date DESC, id DESC"
            )
            for r in walls:
                last_downloads[r["symbol"]]["latest_call_wall"] = (
                    round(float(r["call_wall"]), 0) if r["call_wall"] else None
                )
                last_downloads[r["symbol"]]["latest_put_wall"] = (
                    round(float(r["put_wall"]), 0) if r["put_wall"] else None
                )

            # FII/DII latest
            fii_latest = await conn.fetchrow(
                "SELECT date, fii_net, dii_net FROM fii_dii ORDER BY date DESC LIMIT 1"
            )

        return {
            "status": "ok",
            "warehouse_rows": counts,
            "total_warehouse_rows": sum(counts.values()),
            "symbols": last_downloads,
            "fii_dii_latest": {
                "date": str(fii_latest["date"]) if fii_latest else None,
                "fii_net": fii_latest["fii_net"] if fii_latest else None,
                "dii_net": fii_latest["dii_net"] if fii_latest else None,
            }
            if fii_latest
            else None,
            "health": "HEALTHY" if all(v > 0 for v in counts.values()) else "PARTIAL",
        }
    except (
        ValueError,
        KeyError,
        TypeError,
        ConnectionError,
        RuntimeError,
        OSError,
    ) as e:
        logger.error(f"Warehouse health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accuracy")
async def get_pipeline_accuracy():
    """
    Retrieve historical model accuracy stats from the PostgreSQL database.
    """
    if not pipeline_db.is_connected:
        return {
            "status": "db_not_connected",
            "accuracy_metrics": {
                "overall_accuracy": None,
                "precision": None,
                "recall": None,
                "f1_score": None,
                "note": "Metrics unavailable: PostgreSQL database offline",
            },
        }

    try:
        import numpy as np

        async with pipeline_db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT signal, was_correct, actual_return
                FROM predictions
                WHERE was_correct IS NOT NULL
            """)

            if not rows:
                return {
                    "status": "ok",
                    "accuracy_metrics": {
                        "overall_accuracy": None,
                        "total_predictions_evaluated": 0,
                        "correct_predictions": 0,
                        "precision": None,
                        "recall": None,
                        "f1_score": None,
                        "note": "Metrics unavailable: No evaluated predictions found in database",
                    },
                }

            total = len(rows)
            correct = sum(1 for r in rows if r["was_correct"])
            acc = correct / total

            # Map predictions to classes: +1 (Bullish), -1 (Bearish), 0 (Neutral)
            y_true = []
            y_pred = []
            for r in rows:
                sig = r["signal"]
                ret = r["actual_return"]
                if ret is None:
                    continue
                # Predicted class
                if sig in ("BUY", "STRONG_BUY"):
                    p_cls = 1
                elif sig in ("SELL", "STRONG_SELL"):
                    p_cls = -1
                else:
                    p_cls = 0

                # Actual class
                if ret > 0.005:
                    t_cls = 1
                elif ret < -0.005:
                    t_cls = -1
                else:
                    t_cls = 0

                y_true.append(t_cls)
                y_pred.append(p_cls)

            if not y_true:
                return {
                    "status": "ok",
                    "accuracy_metrics": {
                        "overall_accuracy": round(acc, 4),
                        "total_predictions_evaluated": total,
                        "correct_predictions": correct,
                        "precision": None,
                        "recall": None,
                        "f1_score": None,
                        "note": "Metrics unavailable: No evaluation returns available",
                    },
                }

            # Compute Precision, Recall per class
            precisions = []
            recalls = []
            for cls in (-1, 0, 1):
                tp = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p == cls)
                fp = sum(1 for t, p in zip(y_true, y_pred) if t != cls and p == cls)
                fn = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p != cls)

                prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0

                precisions.append(prec)
                recalls.append(rec)

            macro_precision = float(np.mean(precisions))
            macro_recall = float(np.mean(recalls))
            if macro_precision + macro_recall > 0:
                macro_f1 = float(
                    2
                    * (macro_precision * macro_recall)
                    / (macro_precision + macro_recall)
                )
            else:
                macro_f1 = 0.0

            return {
                "status": "ok",
                "accuracy_metrics": {
                    "overall_accuracy": round(acc, 4),
                    "total_predictions_evaluated": total,
                    "correct_predictions": correct,
                    "precision": round(macro_precision, 4),
                    "recall": round(macro_recall, 4),
                    "f1_score": round(macro_f1, 4),
                },
            }
    except (
        ValueError,
        KeyError,
        TypeError,
        ConnectionError,
        RuntimeError,
        OSError,
    ) as e:
        logger.error(f"Failed to query accuracy metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


import math


def sanitize_json_obj(obj):
    """Recursively convert NaN and Inf floats into None for 100% JSON compliance."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_json_obj(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_json_obj(v) for v in obj]
    return obj


@router.get(
    "/{symbol}",
    response_model=StandardResponse[dict],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {
            "model": ErrorResponse,
            "description": "Forbidden - Admin/Trader role required",
        },
        400: {"model": ErrorResponse, "description": "Bad Request"},
    },
    summary="Get Full Pipeline Output",
    description="Run the complete 10-stage AI pipeline for the given symbol and interval. Supports caching.",
    operation_id="get_full_pipeline",
)
@limiter.limit("30/minute")
async def get_full_pipeline(
    request: Request,
    symbol: str,
    interval: IntervalEnum = Query(IntervalEnum.MIN_15, description="Bar interval"),
    user: dict = Depends(RoleChecker(["admin", "trader"])),
):
    """
    Run the complete 10-stage AI pipeline for the given symbol and interval.
    Includes prediction locking: if a live prediction exists for the current
    candle, it is returned immediately without re-running the pipeline.
    """
    try:
        sym = symbol.upper()

        # ── Prediction Lock check ─────────────────────────────────────
        live_pred = prediction_store.get_live(sym, interval, namespace="pipeline")
        if live_pred:
            result_dict = sanitize_json_obj(dict(live_pred.data))
            result_dict["prediction_meta"] = live_pred.to_metadata()
            logger.debug(
                f"[Pipeline] 🔒 Lock HIT {sym}/{interval} | "
                f"id={live_pred.prediction_id[:8]} | "
                f"age={live_pred.age_seconds():.0f}s"
            )
            return result_dict

        # ── Run fresh pipeline ───────────────────────────────────────
        t0 = time.perf_counter()
        result = await orchestrator.run(sym, interval, skip_llm=False)
        latency_ms = (time.perf_counter() - t0) * 1000

        result_dict = sanitize_json_obj(result.to_dict())

        # ── Lock the prediction ───────────────────────────────────────
        locked = prediction_store.lock(
            sym, interval, result_dict, latency_ms, namespace="pipeline"
        )
        result_dict["prediction_meta"] = locked.to_metadata()

        # ── Invalidate Dashboard Cache ────────────────────────────────
        dashboard_cache.invalidate(sym)

        return result_dict
    except (
        ValueError,
        KeyError,
        TypeError,
        ConnectionError,
        RuntimeError,
        OSError,
    ) as e:
        logger.error(f"Full pipeline run failed for {symbol} ({interval}): {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline run failed: {str(e)}")


@router.get(
    "/probability/{symbol}",
    response_model=StandardResponse[ProbabilityOutput],
    responses={401: {"model": ErrorResponse, "description": "Unauthorized"}},
    summary="Get Pipeline Probability (Fast)",
    description="Fast prediction endpoint: runs stages 1-9 (skips the LLM analyst report stage). Returns probability matrix.",
    operation_id="get_pipeline_probability",
)
@limiter.limit("60/minute")
async def get_pipeline_probability(
    request: Request,
    symbol: str,
    interval: IntervalEnum = Query(IntervalEnum.MIN_15, description="Bar interval"),
    user: dict = Depends(verify_token),
):
    """
    Fast prediction endpoint: runs stages 1-9 (skips the LLM analyst report stage).
    """
    try:
        sym = symbol.upper()
        # ── Inference Cache check ─────────────────────────────────────
        live_pred = prediction_store.get_live(sym, interval, namespace="pipeline_prob")
        if live_pred:
            result_dict = sanitize_json_obj(dict(live_pred.data))
            result_dict["prediction_meta"] = live_pred.to_metadata()
            result_dict["cached"] = True
            return result_dict

        # ── Run fresh pipeline ───────────────────────────────────────
        t0 = time.perf_counter()
        result = await orchestrator.run(sym, interval, skip_llm=True)
        latency_ms = (time.perf_counter() - t0) * 1000

        prob_dict = result.probabilities.to_dict()
        prob_dict["latency_ms"] = round(latency_ms, 2)
        prob_dict["stage_latencies"] = {
            k: round(v, 2) for k, v in result.stage_latencies.items()
        }
        prob_dict["cached"] = False

        result_dict = sanitize_json_obj(prob_dict)

        # ── Lock the prediction ───────────────────────────────────────
        t_pers = time.perf_counter()
        locked = prediction_store.lock(
            sym, interval, result_dict, latency_ms, namespace="pipeline_prob"
        )
        result_dict["prediction_meta"] = locked.to_metadata()
        result_dict["stage_latencies"]["persistence"] = round(
            (time.perf_counter() - t_pers) * 1000, 2
        )
        result_dict["latency_ms"] = round(
            latency_ms + result_dict["stage_latencies"]["persistence"], 2
        )

        return StandardResponse(
            data=ProbabilityOutput(**result_dict),
            message="Probability fetched successfully",
        )
    except Exception as e:
        logger.error(
            f"Probability endpoint error for {symbol}: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/regime/{symbol}")
async def get_pipeline_regime(
    symbol: str,
    interval: str = Query("15m", description="Bar interval: 5m, 15m, 1h, 1d"),
):
    """
    Regime-only endpoint: returns regime HMM predictions and changepoint details.
    """
    try:
        result = await orchestrator.run(symbol, interval, skip_llm=True)
        return sanitize_json_obj(result.regime.to_dict())
    except Exception as e:
        logger.error(
            f"Pipeline regime prediction failed for {symbol} ({interval}): {e}"
        )
        raise HTTPException(status_code=500, detail=f"Regime run failed: {str(e)}")


@router.get("/llm-analysis/{symbol}")
async def get_pipeline_llm_analysis(
    symbol: str,
    interval: str = Query("15m", description="Bar interval: 5m, 15m, 1h, 1d"),
):
    """
    LLM report endpoint: runs the full pipeline and extracts only the text report.
    """
    try:
        result = await orchestrator.run(symbol, interval, skip_llm=False)
        if result.analyst_report:
            return sanitize_json_obj(result.analyst_report.to_dict())
        else:
            return {"error": "LLM Analyst report generation failed."}
    except Exception as e:
        logger.error(f"Pipeline LLM report failed for {symbol} ({interval}): {e}")
        raise HTTPException(status_code=500, detail=f"LLM analyst run failed: {str(e)}")


# ─── EXPLAINABILITY & ALPHA DISCOVERY API ROUTER ───

explainability_router = APIRouter(
    prefix="/api/explainability", tags=["Explainability & Alpha Discovery"]
)

_cache = {}
CACHE_TTL = 15.0  # seconds


def get_cached(key: str):
    if key in _cache:
        t, val = _cache[key]
        if time.time() - t < CACHE_TTL:
            return val
    return None


def set_cached(key: str, val):
    _cache[key] = (time.time(), val)


@explainability_router.get("/stage-contributions")
async def get_stage_contributions(
    symbol: str | None = Query(None, description="Filter by stock symbol"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
):
    cache_key = f"stage_contribs_{symbol}_{page}_{limit}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        data = await pipeline_db.get_stage_contributions(
            symbol=symbol, page=page, limit=limit
        )
        set_cached(cache_key, data)
        return data
    except Exception as e:
        logger.error(f"Error in GET /api/explainability/stage-contributions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@explainability_router.get("/ablation-results")
async def get_ablation_results(
    symbol: str | None = Query(None, description="Filter by stock symbol"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
):
    cache_key = f"ablation_results_{symbol}_{page}_{limit}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        data = await pipeline_db.get_ablation_results(
            symbol=symbol, page=page, limit=limit
        )
        set_cached(cache_key, data)
        return data
    except Exception as e:
        logger.error(f"Error in GET /api/explainability/ablation-results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@explainability_router.get("/regime-performance")
async def get_regime_performance(
    symbol: str | None = Query(None, description="Filter by stock symbol"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
):
    cache_key = f"regime_perf_{symbol}_{page}_{limit}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        data = await pipeline_db.get_regime_performance(
            symbol=symbol, page=page, limit=limit
        )
        set_cached(cache_key, data)
        return data
    except Exception as e:
        logger.error(f"Error in GET /api/explainability/regime-performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@explainability_router.get("/feature-drift")
async def get_feature_drift(
    symbol: str | None = Query(None, description="Filter by stock symbol"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
):
    cache_key = f"feat_drift_{symbol}_{page}_{limit}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        data = await pipeline_db.get_feature_drift(
            symbol=symbol, page=page, limit=limit
        )
        set_cached(cache_key, data)
        return data
    except Exception as e:
        logger.error(f"Error in GET /api/explainability/feature-drift: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@explainability_router.get("/signal-explanations")
async def get_signal_explanations(
    symbol: str | None = Query(None, description="Filter by stock symbol"),
    start_date: str | None = Query(
        None, description="Filter from start date (ISO format)"
    ),
    end_date: str | None = Query(None, description="Filter to end date (ISO format)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
):
    cache_key = f"sig_exps_{symbol}_{start_date}_{end_date}_{page}_{limit}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        start_dt, end_dt = None, None
        if start_date:
            try:
                from dateutil import parser

                start_dt = parser.parse(start_date)
            except Exception:
                raise HTTPException(
                    status_code=400, detail="Invalid start_date format. Use ISO format."
                )
        if end_date:
            try:
                from dateutil import parser

                end_dt = parser.parse(end_date)
            except Exception:
                raise HTTPException(
                    status_code=400, detail="Invalid end_date format. Use ISO format."
                )

        data = await pipeline_db.get_signal_explanations(
            symbol=symbol, start_date=start_dt, end_date=end_dt, page=page, limit=limit
        )
        set_cached(cache_key, data)
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in GET /api/explainability/signal-explanations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@explainability_router.get("/alpha-leaderboard")
async def get_alpha_leaderboard(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
):
    cache_key = f"alpha_lead_{page}_{limit}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        data = await pipeline_db.get_alpha_leaderboard(page=page, limit=limit)
        set_cached(cache_key, data)
        return data
    except Exception as e:
        logger.error(f"Error in GET /api/explainability/alpha-leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@explainability_router.get("/research-summary")
async def get_research_summary(
    symbol: str | None = Query(None, description="Filter by stock symbol"),
):
    cache_key = f"res_sum_{symbol}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        data = await pipeline_db.get_research_summary(symbol=symbol)
        set_cached(cache_key, data)
        return data
    except Exception as e:
        logger.error(f"Error in GET /api/explainability/research-summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
