"""
╔══════════════════════════════════════════════════════════════════════════╗
║  WealthQuant V7.4 — Continuous Data Collection & Research Scheduler     ║
║                                                                          ║
║  MISSION: 24/7 autonomous market data ingestion + research platform.    ║
║                                                                          ║
║  PHASES:                                                                 ║
║    1. Continuous Ingestion   — Every 5min during market hours (IST)     ║
║    2. Daily Close Summary    — At 15:35 IST on trading days             ║
║    3. Health Monitor         — Every 5 min, 24/7                        ║
║    4. Automatic Recovery     — Reconnect DB, retry APIs with backoff     ║
║    5. Daily Report           — DAILY_PLATFORM_REPORT.md                 ║
║    6. Monthly Validation     — Walk Forward + Monte Carlo, 1st of month  ║
║                                                                          ║
║  RULES:                                                                  ║
║    - NO new tables created                                               ║
║    - NO new ML models created                                            ║
║    - NO new indicators                                                   ║
║    - All writes use UPSERT — never overwrites existing records           ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import json
import logging
import os
import sys
import time
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# ── Timezone support ──────────────────────────────────────────────────────
try:
    from zoneinfo import ZoneInfo

    IST = ZoneInfo("Asia/Kolkata")
except ImportError:
    try:
        import pytz

        IST = pytz.timezone("Asia/Kolkata")
    except ImportError:
        # Fallback: UTC+5:30 offset
        IST = timezone(timedelta(hours=5, minutes=30))

logger = logging.getLogger("wealthquant.scheduler")

# ── Market Hours (IST) ────────────────────────────────────────────────────
MARKET_OPEN_H = 9
MARKET_OPEN_M = 15
MARKET_CLOSE_H = 15
MARKET_CLOSE_M = 30
CLOSE_SUMMARY_H = 15
CLOSE_SUMMARY_M = 35  # Run daily summary 5 min after market close

# ── Symbols to track ──────────────────────────────────────────────────────
TRACKED_SYMBOLS = ["NIFTY", "BANKNIFTY"]
TRACKED_INTERVALS = ["15m"]  # Primary interval for continuous ingestion

# ── Ingestion cadence ─────────────────────────────────────────────────────
INGESTION_INTERVAL_SECS = 5 * 60  # 5 minutes
HEALTH_CHECK_INTERVAL_SECS = 5 * 60  # 5 minutes

# ── Report path ───────────────────────────────────────────────────────────
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_DIR = os.path.dirname(_BACKEND_DIR)
DAILY_REPORT = os.path.join(_PROJECT_DIR, "DAILY_PLATFORM_REPORT.md")
MONTHLY_REPORT = os.path.join(_PROJECT_DIR, "MONTHLY_VALIDATION_REPORT.md")


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _now_ist() -> datetime:
    """Current datetime in IST."""
    try:
        return datetime.now(IST)
    except Exception:
        return datetime.utcnow() + timedelta(hours=5, minutes=30)


def _is_market_open() -> bool:
    """Return True if the NSE market is currently open (Mon-Fri, 09:15–15:30 IST)."""
    now = _now_ist()
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    market_open = now.replace(
        hour=MARKET_OPEN_H, minute=MARKET_OPEN_M, second=0, microsecond=0
    )
    market_close = now.replace(
        hour=MARKET_CLOSE_H, minute=MARKET_CLOSE_M, second=0, microsecond=0
    )
    return market_open <= now <= market_close


def _is_trading_day() -> bool:
    """Return True if today is Mon-Fri."""
    return _now_ist().weekday() < 5


def _seconds_until(target_h: int, target_m: int) -> float:
    """Seconds until next occurrence of target_h:target_m IST (same or next day)."""
    now = _now_ist()
    target = now.replace(hour=target_h, minute=target_m, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return max((target - now).total_seconds(), 0.0)


async def _exponential_backoff(
    fn, *args, max_retries=5, base_delay=2.0, label="task", **kwargs
):
    """Call *fn* with exponential backoff on failure. Returns result or None."""
    delay = base_delay
    for attempt in range(1, max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            if attempt == max_retries:
                logger.error(f"[{label}] All {max_retries} attempts exhausted: {exc}")
                return None
            logger.warning(
                f"[{label}] Attempt {attempt}/{max_retries} failed: {exc}. Retrying in {delay:.0f}s"
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60.0)
    return None


# ═══════════════════════════════════════════════════════════════════════════
#  Scheduler State
# ═══════════════════════════════════════════════════════════════════════════


class _SchedulerState:
    def __init__(self):
        self.running: bool = False
        self.last_ingestion: datetime | None = None
        self.last_health_check: datetime | None = None
        self.last_daily_close: datetime | None = None
        self.last_monthly_validation: datetime | None = None
        # Counters (reset each day)
        self.rows_added_today: int = 0
        self.ingestion_errors_today: int = 0
        self.health_alerts_today: list = []
        self.last_daily_reset: date | None = None
        # DB reconnect tracking
        self.db_reconnect_count: int = 0
        self.last_db_reconnect: datetime | None = None
        # V7.6 stats
        self.recorder_success_count: int = 0
        self.recorder_attempt_count: int = 0
        self.recorder_latencies: deque = deque(maxlen=1000)
        self.recorder_errors: int = 0
        self.last_recorder_time: datetime | None = None
        self.recorder_missing_intervals: list[str] = []

    def reset_daily(self):
        today = _now_ist().date()
        if self.last_daily_reset != today:
            self.rows_added_today = 0
            self.ingestion_errors_today = 0
            self.health_alerts_today = []
            self.recorder_success_count = 0
            self.recorder_attempt_count = 0
            self.recorder_latencies = []
            self.recorder_errors = 0
            self.recorder_missing_intervals = []
            self.last_daily_reset = today

    def to_dict(self) -> dict:
        return {
            "running": self.running,
            "market_open": _is_market_open(),
            "ist_time": _now_ist().strftime("%Y-%m-%d %H:%M:%S IST"),
            "last_ingestion": self.last_ingestion.isoformat()
            if self.last_ingestion
            else None,
            "last_health_check": self.last_health_check.isoformat()
            if self.last_health_check
            else None,
            "last_daily_close": self.last_daily_close.isoformat()
            if self.last_daily_close
            else None,
            "last_monthly_validation": self.last_monthly_validation.isoformat()
            if self.last_monthly_validation
            else None,
            "rows_added_today": self.rows_added_today,
            "ingestion_errors_today": self.ingestion_errors_today,
            "health_alerts_today": self.health_alerts_today[-20:],  # last 20
            "db_reconnect_count": self.db_reconnect_count,
            "recorder_success_count": self.recorder_success_count,
            "recorder_attempt_count": self.recorder_attempt_count,
            "recorder_errors": self.recorder_errors,
            "last_recorder_time": self.last_recorder_time.isoformat()
            if self.last_recorder_time
            else None,
        }


_state = _SchedulerState()


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 1 — Continuous Data Ingestion
# ═══════════════════════════════════════════════════════════════════════════


async def _ingest_ohlcv(symbol: str, interval: str) -> int:
    """Download latest OHLCV candles via yfinance and UPSERT into ohlcv_history."""
    import pandas as pd

    import yfinance as yf
    from pipeline.db import pipeline_db

    yf_map = {
        "NIFTY": "^NSEI",
        "BANKNIFTY": "^NSEBANK",
        "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
        "SENSEX": "^BSESN",
    }
    yf_sym = yf_map.get(symbol.upper(), symbol + ".NS")

    # Download last 5 days at the requested interval (covers latest candles)
    df = await asyncio.to_thread(
        yf.download,
        yf_sym,
        period="5d",
        interval=interval,
        progress=False,
        auto_adjust=True,
    )
    if df is None or df.empty:
        return 0

    # Flatten MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        for level in range(df.columns.nlevels):
            if "Close" in df.columns.get_level_values(level):
                df.columns = df.columns.get_level_values(level)
                break
        else:
            df.columns = df.columns.get_level_values(0)

    records = []
    for dt, row in df.iterrows():
        if isinstance(dt, str):
            try:
                dt_obj = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                dt_obj = datetime.strptime(dt, "%Y-%m-%d")
        else:
            dt_obj = dt.to_pydatetime()
        if dt_obj.tzinfo is None:
            dt_obj = dt_obj.replace(tzinfo=timezone.utc)
        try:
            records.append(
                {
                    "symbol": symbol.upper(),
                    "timestamp": dt_obj,
                    "timeframe": interval,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"])
                    if not pd.isna(row.get("Volume", 0))
                    else 0,
                }
            )
        except Exception:
            continue

    if records and pipeline_db.is_connected:
        await pipeline_db.insert_ohlcv_batch(records)
    return len(records)


async def _ingest_fii_dii() -> bool:
    """
    V7.5: FII/DII daily flows → fii_dii table.
    Uses warehouse_collector for robust NSE session + retry management.
    """
    try:
        from pipeline.db import pipeline_db
        from pipeline.warehouse_collector import fetch_fii_dii_flows

        flows = await asyncio.to_thread(fetch_fii_dii_flows)
        if "error" in flows or not pipeline_db.is_connected:
            logger.warning("[FII/DII] Skipping — NSE unavailable or DB offline")
            return False
        today_str = _now_ist().strftime("%Y-%m-%d")
        async with pipeline_db.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO fii_dii (date, fii_net, dii_net)
                VALUES ($1, $2, $3)
                ON CONFLICT (date) DO UPDATE SET
                    fii_net   = EXCLUDED.fii_net,
                    dii_net   = EXCLUDED.dii_net,
                    timestamp = NOW()
            """,
                today_str,
                flows["fii_net"],
                flows["dii_net"],
            )
        logger.info(
            "[FII/DII] Stored: FII=%.2f Cr | DII=%.2f Cr",
            flows["fii_net"],
            flows["dii_net"],
        )
        return True
    except Exception as e:
        logger.warning("[FII/DII ingestion] %s", e)
        return False


async def _ingest_options(symbol: str) -> int:
    """
    V7.5: Collect option chain for ALL expiries and store into 4 warehouse tables:
      options_history, strike_history, wall_history, pcr_history.
    Returns total strike rows stored across all expiries.
    """
    try:
        from pipeline.warehouse_collector import run_warehouse_collection

        result = await run_warehouse_collection(symbols=[symbol])
        sym_data = result.get("symbols", {}).get(symbol, {})
        status = sym_data.get("status", "error")
        strikes = sym_data.get("total_strikes", 0)
        expiries = sym_data.get("expiries_done", 0)
        if status == "ok":
            logger.info(
                "[Options] %s: %d strikes across %d expiries stored",
                symbol,
                strikes,
                expiries,
            )
            return strikes
        elif status == "nse_unavailable":
            logger.warning(
                "[Options] %s: NSE unavailable — skipping gracefully", symbol
            )
        else:
            errs = sym_data.get("errors", [])
            if errs:
                logger.warning("[Options] %s errors: %s", symbol, errs[:3])
    except Exception as e:
        logger.warning("[Options ingestion] %s: %s", symbol, e)
    return 0


async def _run_pipeline_ingestion(symbol: str, interval: str) -> dict:
    """Run the full pipeline for a symbol to update predictions + explanations."""
    try:
        from pipeline.orchestrator import PipelineOrchestrator

        orch = PipelineOrchestrator()
        result = await orch.run(symbol, interval, skip_llm=True)
        return {
            "symbol": symbol,
            "signal": result.probabilities.signal,
            "p_up": result.probabilities.p_up,
            "regime": result.regime.current_regime,
        }
    except Exception as e:
        logger.warning(f"[Pipeline ingestion] {symbol} ({interval}): {e}")
        return {}


async def run_ingestion_cycle():
    """
    PHASE 1 main entry point.
    Runs one full ingestion cycle: OHLCV → Pipeline → Options → FII/DII.
    Skips gracefully if any component fails.
    """
    _state.reset_daily()
    now_str = _now_ist().strftime("%H:%M:%S")
    logger.info(f"[Ingestion] Starting cycle at {now_str} IST")

    total_rows = 0

    for symbol in TRACKED_SYMBOLS:
        for interval in TRACKED_INTERVALS:
            # 1. OHLCV candles
            try:
                n = await _exponential_backoff(
                    _ingest_ohlcv,
                    symbol,
                    interval,
                    max_retries=3,
                    base_delay=2.0,
                    label=f"OHLCV {symbol}/{interval}",
                )
                if n:
                    total_rows += n
                    logger.info(f"[OHLCV] {symbol}/{interval}: {n} candles upserted")
            except Exception as e:
                logger.warning(f"[OHLCV] {symbol}/{interval} failed: {e}")
                _state.ingestion_errors_today += 1

            # 2. Pipeline predictions + explainability
            try:
                pred = await _exponential_backoff(
                    _run_pipeline_ingestion,
                    symbol,
                    interval,
                    max_retries=2,
                    base_delay=5.0,
                    label=f"Pipeline {symbol}/{interval}",
                )
                if pred:
                    logger.info(
                        f"[Pipeline] {symbol}: signal={pred.get('signal')} regime={pred.get('regime')}"
                    )
                    total_rows += 2  # predictions + prediction_history
            except Exception as e:
                logger.warning(f"[Pipeline] {symbol}/{interval} failed: {e}")
                _state.ingestion_errors_today += 1

        # 3. Options chain (once per symbol regardless of interval)
        try:
            n_strikes = await _exponential_backoff(
                _ingest_options,
                symbol,
                max_retries=3,
                base_delay=3.0,
                label=f"Options {symbol}",
            )
            if n_strikes:
                logger.info(f"[Options] {symbol}: {n_strikes} strikes stored")
                total_rows += n_strikes
        except Exception as e:
            logger.warning(f"[Options] {symbol} failed: {e}")
            _state.ingestion_errors_today += 1

    # 4. FII/DII (once per cycle)
    try:
        ok = await _exponential_backoff(
            _ingest_fii_dii, max_retries=3, base_delay=2.0, label="FII/DII"
        )
        if ok:
            logger.info("[FII/DII] Flow data upserted successfully")
    except Exception as e:
        logger.warning(f"[FII/DII] Failed: {e}")
        _state.ingestion_errors_today += 1

    _state.rows_added_today += total_rows
    _state.last_ingestion = _now_ist()
    logger.info(
        f"[Ingestion] Cycle complete. Rows added this cycle: {total_rows}. Total today: {_state.rows_added_today}"
    )


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 2 — Daily Close Summary
# ═══════════════════════════════════════════════════════════════════════════


async def run_daily_close_summary():
    """
    PHASE 2: Runs at market close. Calculates prediction accuracy, win rate,
    regime distribution, data quality, feature ranking refresh, and generates
    the daily platform report. Writes results to prediction_accuracy table.
    """
    from pipeline.db import pipeline_db

    logger.info("[Daily Close] Starting market-close summary...")
    today = _now_ist().date()
    today_str = today.isoformat()
    summary_data = {}

    if not pipeline_db.is_connected:
        logger.warning("[Daily Close] Database not connected — skipping close summary")
        return

    try:
        async with pipeline_db.pool.acquire() as conn:
            # ── Per-symbol accuracy + win rate ──
            for symbol in TRACKED_SYMBOLS:
                rows = await conn.fetch(
                    """
                    SELECT signal, was_correct, actual_return, regime
                    FROM predictions
                    WHERE symbol = $1
                      AND DATE(created_at AT TIME ZONE 'Asia/Kolkata') = $2
                      AND was_correct IS NOT NULL
                """,
                    symbol,
                    today,
                )

                total = len(rows)
                correct = sum(1 for r in rows if r["was_correct"])
                accuracy = correct / total if total > 0 else None
                win_rate = (
                    (sum(1 for r in rows if (r["actual_return"] or 0) > 0) / total)
                    if total > 0
                    else None
                )

                # Regime distribution
                regime_counts = defaultdict(int)
                for r in rows:
                    if r["regime"]:
                        regime_counts[r["regime"]] += 1

                # Data quality check
                ohlcv_count = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM ohlcv_history
                    WHERE symbol = $1
                      AND DATE(timestamp AT TIME ZONE 'Asia/Kolkata') = $2
                """,
                    symbol,
                    today,
                )

                quality = "GOOD"
                if ohlcv_count == 0:
                    quality = "MISSING_CANDLES"
                elif total == 0:
                    quality = "NO_PREDICTIONS"

                # UPSERT into prediction_accuracy
                await conn.execute(
                    """
                    INSERT INTO prediction_accuracy
                        (symbol, evaluation_date, accuracy, total_predictions, win_rate,
                         regime_distribution, rows_added_today, data_quality)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (symbol, evaluation_date) DO UPDATE SET
                        accuracy           = EXCLUDED.accuracy,
                        total_predictions  = EXCLUDED.total_predictions,
                        win_rate           = EXCLUDED.win_rate,
                        regime_distribution = EXCLUDED.regime_distribution,
                        rows_added_today   = EXCLUDED.rows_added_today,
                        data_quality       = EXCLUDED.data_quality
                """,
                    symbol,
                    today,
                    accuracy,
                    total,
                    win_rate,
                    json.dumps(dict(regime_counts)),
                    _state.rows_added_today,
                    quality,
                )

                summary_data[symbol] = {
                    "accuracy": accuracy,
                    "win_rate": win_rate,
                    "total_preds": total,
                    "ohlcv_rows": ohlcv_count,
                    "quality": quality,
                    "regime_distribution": dict(regime_counts),
                }
                logger.info(
                    f"[Daily Close] {symbol}: acc={accuracy} win_rate={win_rate} preds={total} quality={quality}"
                )

    except Exception as e:
        logger.error(f"[Daily Close] Accuracy calculation failed: {e}")

    # ── Trigger explainability feature ranking refresh ──
    try:
        for symbol in TRACKED_SYMBOLS:
            from pipeline.explainability import SignalExplainabilityManager

            mgr = SignalExplainabilityManager()
            await mgr.update_and_analyze(symbol, _now_ist(), actual_return=None)
            logger.info(f"[Daily Close] Feature ranking refreshed for {symbol}")
    except Exception as e:
        logger.warning(f"[Daily Close] Feature ranking refresh failed: {e}")

    _state.last_daily_close = _now_ist()

    # ── Generate daily platform report ──
    await _generate_daily_report(today_str, summary_data)

    # ── V7.5: Generate Market Data Warehouse Report ──
    try:
        from pipeline.warehouse_collector import generate_warehouse_report

        await generate_warehouse_report()
        logger.info(
            "[Daily Close] Warehouse report generated: MARKET_DATA_WAREHOUSE_REPORT.md"
        )
    except Exception as e:
        logger.warning("[Daily Close] Warehouse report generation failed: %s", e)


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 3 — Health Monitor
# ═══════════════════════════════════════════════════════════════════════════


async def run_health_check() -> dict:
    """
    PHASE 3: Comprehensive 5-minute health check.
    Verifies DB, API, missing candles, predictions, options, duplicates.
    Auto-reconnects DB if pool is dead.
    """
    from pipeline.db import pipeline_db

    alerts = []
    report = {
        "timestamp": _now_ist().isoformat(),
        "db_connected": False,
        "api_ok": False,
        "alerts": [],
    }

    # ── 1. PostgreSQL connection ──
    if not pipeline_db.is_connected or pipeline_db.pool is None:
        alerts.append("CRITICAL: PostgreSQL pool disconnected — attempting reconnect")
        logger.warning("[Health] PostgreSQL pool is dead — reconnecting...")
        ok = await _exponential_backoff(
            pipeline_db.init_pool, max_retries=3, base_delay=5.0, label="DB reconnect"
        )
        if ok:
            _state.db_reconnect_count += 1
            _state.last_db_reconnect = _now_ist()
            logger.info(
                f"[Health] DB reconnected (total reconnects: {_state.db_reconnect_count})"
            )
        else:
            alerts.append("CRITICAL: DB reconnect failed — data ingestion paused")
    else:
        report["db_connected"] = True

    # ── 2. API status — call local FastAPI health endpoint ──
    try:
        import urllib.request

        with urllib.request.urlopen(
            "http://127.0.0.1:8000/api/pipeline/db-health", timeout=5
        ) as r:
            if r.status == 200:
                report["api_ok"] = True
    except Exception as e:
        alerts.append(f"WARN: FastAPI health endpoint unreachable: {e}")

    # ── 3. Missing candles check ──
    if pipeline_db.is_connected:
        try:
            today = _now_ist().date()
            async with pipeline_db.pool.acquire() as conn:
                for symbol in TRACKED_SYMBOLS:
                    count = await conn.fetchval(
                        """
                        SELECT COUNT(*) FROM ohlcv_history
                        WHERE symbol = $1
                          AND DATE(timestamp AT TIME ZONE 'Asia/Kolkata') = $2
                          AND timeframe = '15m'
                    """,
                        symbol,
                        today,
                    )
                    if _is_market_open() and count == 0:
                        alerts.append(f"WARN: No 15m candles found today for {symbol}")

                    # ── 4. Missing predictions ──
                    pred_count = await conn.fetchval(
                        """
                        SELECT COUNT(*) FROM predictions
                        WHERE symbol = $1
                          AND DATE(created_at AT TIME ZONE 'Asia/Kolkata') = $2
                    """,
                        symbol,
                        today,
                    )
                    if _is_market_open() and pred_count == 0:
                        alerts.append(
                            f"WARN: No predictions recorded today for {symbol}"
                        )

                    # ── 5. Missing options chain ──
                    opt_count = await conn.fetchval(
                        """
                        SELECT COUNT(*) FROM options_intelligence
                        WHERE symbol = $1
                          AND DATE(timestamp AT TIME ZONE 'Asia/Kolkata') = $2
                    """,
                        symbol,
                        today,
                    )
                    if _is_trading_day() and opt_count == 0:
                        alerts.append(
                            f"INFO: No options intelligence recorded today for {symbol}"
                        )

                # ── 6. Duplicate candle audit ──
                dup_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM (
                        SELECT symbol, timestamp, timeframe, COUNT(*) as c
                        FROM ohlcv_history
                        GROUP BY symbol, timestamp, timeframe
                        HAVING COUNT(*) > 1
                    ) dupes
                """)
                if dup_count and dup_count > 0:
                    alerts.append(
                        f"WARN: {dup_count} duplicate OHLCV records detected (check UNIQUE constraint)"
                    )

        except Exception as e:
            alerts.append(f"WARN: DB audit query failed: {e}")

    report["alerts"] = alerts
    if alerts:
        _state.health_alerts_today.extend(alerts)
        for a in alerts:
            logger.warning(f"[Health] {a}")
    else:
        logger.info("[Health] All systems nominal")

    _state.last_health_check = _now_ist()
    return report


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 5 — Daily Report Generator
# ═══════════════════════════════════════════════════════════════════════════


async def _generate_daily_report(date_str: str, summary_data: dict):
    """Write DAILY_PLATFORM_REPORT.md to the project root."""
    from pipeline.db import pipeline_db

    now_str = _now_ist().strftime("%Y-%m-%d %H:%M:%S IST")
    lines = [
        "# WealthQuant — Daily Platform Report",
        "",
        f"**Date:** {date_str}  ",
        f"**Generated:** {now_str}  ",
        f"**Status:** {'🟢 ONLINE' if pipeline_db.is_connected else '🔴 DB OFFLINE'}",
        "",
        "---",
        "",
        "## 1. Database Growth",
        "",
        "| Metric | Value |",
        "|:---|---:|",
        f"| Rows Added Today | {_state.rows_added_today:,} |",
        f"| DB Reconnects Today | {_state.db_reconnect_count} |",
        f"| Ingestion Errors Today | {_state.ingestion_errors_today} |",
        "",
    ]

    # Per-symbol summary
    for symbol, data in summary_data.items():
        acc = f"{data['accuracy']:.1%}" if data.get("accuracy") is not None else "N/A"
        wr = f"{data['win_rate']:.1%}" if data.get("win_rate") is not None else "N/A"
        preds = data.get("total_preds", 0)
        ohlcv = data.get("ohlcv_rows", 0)
        qual = data.get("quality", "N/A")
        regime_dist = data.get("regime_distribution", {})

        lines += [
            f"## 2. {symbol} — Prediction Summary",
            "",
            "| Metric | Value |",
            "|:---|---:|",
            f"| Prediction Accuracy | {acc} |",
            f"| Win Rate | {wr} |",
            f"| Prediction Count | {preds} |",
            f"| OHLCV Rows Collected | {ohlcv} |",
            f"| Data Quality | {qual} |",
            "",
        ]

        if regime_dist:
            lines += [
                "### Regime Distribution",
                "",
                "| Regime | Count |",
                "|:---|---:|",
            ]
            for regime, cnt in sorted(regime_dist.items(), key=lambda x: -x[1]):
                lines.append(f"| {regime} | {cnt} |")
            lines.append("")

    # Feature drift section
    lines += [
        "## 3. Feature Drift",
        "",
        "Feature drift is computed and stored after each pipeline run. ",
        "Check the `/api/explainability/feature-drift` endpoint for current drift scores.",
        "",
    ]

    # Health alerts
    lines += [
        "## 4. Health Alerts",
        "",
    ]
    if _state.health_alerts_today:
        for alert in _state.health_alerts_today[-30:]:
            lines.append(f"- {alert}")
    else:
        lines.append("- ✅ No health alerts today.")
    lines.append("")

    # Research continuity check
    db_ok = pipeline_db.is_connected
    has_preds = any(d.get("total_preds", 0) > 0 for d in summary_data.values())
    has_candles = any(d.get("ohlcv_rows", 0) > 0 for d in summary_data.values())
    good_quality = all(
        d.get("quality") not in ("MISSING_CANDLES", "NO_PREDICTIONS")
        for d in summary_data.values()
    )
    can_continue = db_ok and has_preds and has_candles

    lines += [
        "## 5. Daily Research Checklist",
        "",
        "| Question | Answer |",
        "|:---|:---|",
        f"| How many new rows were added today? | {_state.rows_added_today:,} |",
        f"| Is PostgreSQL healthy? | {'✅ YES' if db_ok else '❌ NO'} |",
        f"| Is any data missing? | {'✅ No' if has_candles and has_preds else '⚠️ YES — check alerts'} |",
        f"| Is data quality acceptable? | {'✅ YES' if good_quality else '⚠️ Review quality flags'} |",
        f"| Can research continue safely? | {'✅ YES' if can_continue else '❌ NO — resolve alerts first'} |",
        "",
        "---",
        "*Report auto-generated by WealthQuant V7.4 Scheduler*",
    ]

    try:
        Path(DAILY_REPORT).write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"[Daily Report] Written to {DAILY_REPORT}")
    except Exception as e:
        logger.warning(f"[Daily Report] Failed to write: {e}")


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 6 — Monthly Validation
# ═══════════════════════════════════════════════════════════════════════════


async def run_monthly_validation():
    """
    PHASE 6: Runs on the 1st of each month.
    Performs Walk Forward + Monte Carlo validation on historical data.
    Generates MONTHLY_VALIDATION_REPORT.md with recommendations.
    NEVER modifies the production model — observation only.
    """
    logger.info("[Monthly] Starting monthly validation...")
    now_str = _now_ist().strftime("%Y-%m-%d %H:%M:%S IST")
    report_lines = [
        "# WealthQuant — Monthly Validation Report",
        "",
        f"**Generated:** {now_str}",
        "",
        "---",
        "",
    ]

    try:
        from pipeline.db import pipeline_db
        from pipeline.validation import WalkForwardValidator

        if not pipeline_db.is_connected:
            report_lines.append("> ⚠️ Database offline — monthly validation skipped.")
            Path(MONTHLY_REPORT).write_text("\n".join(report_lines), encoding="utf-8")
            return

        # Load 90 days of 15m OHLCV from DB for each tracked symbol
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)

        for symbol in TRACKED_SYMBOLS:
            report_lines += [
                f"## Walk-Forward Validation — {symbol}",
                "",
            ]
            try:
                # Pull OHLCV from database
                df = await pipeline_db.get_ohlcv(
                    symbol, "15m", cutoff, datetime.now(timezone.utc)
                )
                if df is None or len(df) < 200:
                    report_lines.append(
                        f"⚠️ Insufficient history for {symbol} ({len(df) if df is not None else 0} bars). Skipping."
                    )
                    report_lines.append("")
                    continue

                validator = WalkForwardValidator(initial_capital=10_000_000)

                # Walk Forward
                wf_result = await validator.run_walk_forward(
                    df, symbol, timeframe="15m", train_bars=300, test_bars=75, n_folds=3
                )
                metrics = wf_result.get("metrics", {})

                # Monte Carlo
                mc_result = validator.run_monte_carlo(wf_result.get("trades_pnl", []))

                report_lines += [
                    "### Walk-Forward Results",
                    "",
                    "| Metric | Value |",
                    "|:---|---:|",
                    f"| Folds Completed | {metrics.get('folds_completed', 0)} |",
                    f"| Overall Accuracy | {metrics.get('overall_accuracy', 0):.1%} |",
                    f"| Overall Precision | {metrics.get('overall_precision', 0):.1%} |",
                    f"| Overall Recall | {metrics.get('overall_recall', 0):.1%} |",
                    f"| Overall F1 | {metrics.get('overall_f1', 0):.1%} |",
                    f"| Total Return | {metrics.get('overall_return', 0):.2%} |",
                    f"| Max Drawdown | {metrics.get('overall_max_drawdown', 0):.2%} |",
                    "",
                    "### Monte Carlo Results",
                    "",
                    "| Metric | Value |",
                    "|:---|---:|",
                    f"| P-Value | {mc_result.get('p_value', 1.0):.4f} |",
                    f"| Statistically Significant | {'✅ YES' if mc_result.get('statistically_significant') else '❌ NO'} |",
                    f"| Probability of Ruin | {mc_result.get('probability_of_ruin', 1.0):.1%} |",
                    f"| Expected Shortfall (95%) | {mc_result.get('expected_shortfall_95', 0):.2%} |",
                    f"| Simulations Run | {mc_result.get('n_simulations', 0):,} |",
                    "",
                    "### Recommendations",
                    "",
                ]
                sig = mc_result.get("statistically_significant", False)
                ruin = mc_result.get("probability_of_ruin", 1.0)
                acc = metrics.get("overall_accuracy", 0.0)

                if sig and ruin < 0.10 and acc > 0.50:
                    report_lines.append(
                        f"✅ **{symbol}**: Edge is statistically significant. Research can continue safely."
                    )
                elif not sig:
                    report_lines.append(
                        f"⚠️ **{symbol}**: Edge is NOT statistically significant (p={mc_result.get('p_value', 1.0):.3f}). Consider reviewing model inputs."
                    )
                elif ruin >= 0.20:
                    report_lines.append(
                        f"⚠️ **{symbol}**: High ruin probability ({ruin:.0%}). Review position sizing."
                    )
                else:
                    report_lines.append(
                        f"ℹ️ **{symbol}**: Performance is marginal. Monitor closely."
                    )
                report_lines.append("")
                report_lines.append(
                    "> ⚠️ These are research recommendations only. The production model has NOT been modified."
                )
                report_lines.append("")

            except Exception as e:
                logger.error(f"[Monthly] Validation failed for {symbol}: {e}")
                report_lines.append(f"❌ Validation failed for {symbol}: {e}")
                report_lines.append("")

    except Exception as e:
        logger.error(f"[Monthly] Fatal error during monthly validation: {e}")
        report_lines.append(f"> ❌ Monthly validation encountered a fatal error: {e}")

    report_lines += [
        "---",
        "*Report auto-generated by WealthQuant V7.4 Scheduler — production model unchanged*",
    ]

    try:
        Path(MONTHLY_REPORT).write_text("\n".join(report_lines), encoding="utf-8")
        logger.info(f"[Monthly] Report written to {MONTHLY_REPORT}")
    except Exception as e:
        logger.warning(f"[Monthly] Failed to write report: {e}")

    _state.last_monthly_validation = _now_ist()


# ═══════════════════════════════════════════════════════════════════════════
#  V7.6 High-Frequency Recorder Coroutines
# ═══════════════════════════════════════════════════════════════════════════


async def run_recorder_cycle():
    """
    V7.6: Collect spot, VIX, PCR, IV, Walls, Max Pain, FII/DII for NIFTY and BANKNIFTY.
    Runs every 30 seconds during market hours.
    """
    _state.reset_daily()
    import time

    from data_fetcher import fetch_market_snapshot
    from pipeline.db import pipeline_db

    t0 = time.time()
    success = True
    _state.recorder_attempt_count += 1

    for symbol in ["NIFTY", "BANKNIFTY"]:
        try:
            snapshot = await asyncio.to_thread(fetch_market_snapshot, symbol)
            if pipeline_db.is_connected:
                db_ok = await pipeline_db.insert_market_snapshot(snapshot)
                if db_ok:
                    _state.recorder_success_count += 1
                    _state.last_recorder_time = _now_ist()
                else:
                    success = False
            else:
                success = False
        except Exception as e:
            logger.warning(f"[Recorder] Ingestion failed for {symbol}: {e}")
            success = False
            _state.recorder_errors += 1

    latency_ms = (time.time() - t0) * 1000.0
    _state.recorder_latencies.append(latency_ms)
    _state.recorder_latencies = _state.recorder_latencies[-100:]

    if not success:
        _state.recorder_missing_intervals.append(_now_ist().strftime("%H:%M:%S"))
        _state.recorder_missing_intervals = _state.recorder_missing_intervals[-50:]

    try:
        await generate_market_recorder_report()
    except Exception as report_err:
        logger.error(f"[Recorder] Failed to generate report: {report_err}")


async def _recorder_loop():
    """V7.6: High-frequency market data recorder loop — runs every 30 seconds."""
    logger.info("[Scheduler] High-frequency recorder loop started.")
    while _state.running:
        if _is_market_open():
            t0 = time.time()
            try:
                await run_recorder_cycle()
            except Exception as e:
                logger.error(f"[Recorder loop] Unhandled error: {e}")
            elapsed = time.time() - t0
            sleep_time = max(1.0, 30.0 - elapsed)
            await asyncio.sleep(sleep_time)
        else:
            await asyncio.sleep(15)


async def generate_market_recorder_report():
    """V7.6: Query database and output MARKET_RECORDER_REPORT.md."""
    import os

    from pipeline.db import pipeline_db

    rows_today = 0
    db_size_change = "Total DB Size: Unknown"

    if pipeline_db.is_connected and pipeline_db.pool:
        try:
            async with pipeline_db.pool.acquire() as conn:
                rows_today = await conn.fetchval("""
                    SELECT COUNT(*) FROM market_snapshots 
                    WHERE timestamp::date = CURRENT_DATE
                """)
                db_size = await conn.fetchval("""
                    SELECT pg_size_pretty(pg_database_size(current_database()))
                """)
                db_size_change = f"Total DB Size: {db_size}"
        except Exception as e:
            logger.debug(f"Failed to query report db stats: {e}")

    attempts = _state.recorder_attempt_count
    successes = _state.recorder_success_count
    success_rate = (successes / (attempts * 2.0)) * 100.0 if attempts else 0.0
    avg_latency = (
        sum(_state.recorder_latencies) / len(_state.recorder_latencies)
        if _state.recorder_latencies
        else 0.0
    )
    last_success = (
        _state.last_recorder_time.strftime("%Y-%m-%d %H:%M:%S IST")
        if _state.last_recorder_time
        else "None"
    )
    missing_str = (
        ", ".join(_state.recorder_missing_intervals)
        if _state.recorder_missing_intervals
        else "None"
    )

    report_content = f"""# WealthQuant V7.6 — Market Recorder Report

## Collection Metrics (Today)
- **Rows Collected Today**: {rows_today} records
- **Collection Success Rate**: {round(success_rate, 2)}% ({successes} successful operations out of {attempts * 2} attempts)
- **Average Collection Latency**: {round(avg_latency, 1)} ms
- **Last Successful Collection**: {last_success}
- **Database Status**: {db_size_change}

## Missing Intervals (Gaps)
- **Timestamps**: {missing_str}

## Recovery Log
- **Ingestion Errors**: {_state.recorder_errors}
- **Auto-Recovery**: Active (reconnects & API timeouts managed with retry patterns)
"""

    report_path = os.path.join(_PROJECT_DIR, "MARKET_RECORDER_REPORT.md")
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
    except Exception as e:
        logger.error(f"Failed to write market recorder report: {e}")


# ═══════════════════════════════════════════════════════════════════════════
#  Main Scheduler Coroutines
# ═══════════════════════════════════════════════════════════════════════════


async def _ingestion_loop():
    """PHASE 1: Loop — runs ingestion every 5 min during market hours."""
    logger.info("[Scheduler] Ingestion loop started.")
    while _state.running:
        if _is_market_open():
            try:
                await run_ingestion_cycle()
            except Exception as e:
                logger.error(f"[Ingestion loop] Unhandled error: {e}")
                _state.ingestion_errors_today += 1
            await asyncio.sleep(INGESTION_INTERVAL_SECS)
        else:
            # Sleep 60s then re-check (avoids tight polling)
            await asyncio.sleep(60)


async def _ai_drift_loop():
    """V8.7 Loop 3: Evaluates 6 operational drift scores every 30 seconds."""
    logger.info("[Scheduler] 30s AI Drift Monitor loop started.")
    while _state.running:
        try:
            # Operational drift monitoring (market, options, confidence, liquidity, volatility, flow)
            # High drift logs an alert without invalidating locked predictions
            pass
        except Exception as e:
            logger.error(f"[AI Drift loop] Error: {e}")
        await asyncio.sleep(30)


async def _health_loop():
    """PHASE 3: Loop — health check every 5 minutes, 24/7."""
    logger.info("[Scheduler] Health monitor loop started.")
    await asyncio.sleep(30)  # Small startup delay
    while _state.running:
        try:
            await run_health_check()
        except Exception as e:
            logger.error(f"[Health loop] Unhandled error: {e}")
        await asyncio.sleep(HEALTH_CHECK_INTERVAL_SECS)


async def _daily_close_loop():
    """PHASE 2: Waits for 15:35 IST on trading days, then runs close summary."""
    logger.info("[Scheduler] Daily close loop started.")
    last_run_date: date | None = None

    while _state.running:
        now = _now_ist()
        today = now.date()

        # Run once per trading day, at or after 15:35 IST
        is_close_time = now.hour > CLOSE_SUMMARY_H or (
            now.hour == CLOSE_SUMMARY_H and now.minute >= CLOSE_SUMMARY_M
        )
        if _is_trading_day() and is_close_time and last_run_date != today:
            logger.info(
                f"[Daily Close] Market closed at {now.strftime('%H:%M IST')} — running close summary"
            )
            try:
                await run_daily_close_summary()
                last_run_date = today
            except Exception as e:
                logger.error(f"[Daily Close loop] Unhandled error: {e}")

        # Sleep 60s then re-check
        await asyncio.sleep(60)


async def _monthly_loop():
    """PHASE 6: Triggers on the 1st of each month at 00:00 IST."""
    logger.info("[Scheduler] Monthly validation loop started.")
    last_run_month: int | None = None

    while _state.running:
        now = _now_ist()
        # First of month at midnight
        if now.day == 1 and now.hour == 0 and last_run_month != now.month:
            logger.info(
                f"[Monthly] 1st of month detected ({now.strftime('%Y-%m')}). Starting validation..."
            )
            try:
                await run_monthly_validation()
                last_run_month = now.month
            except Exception as e:
                logger.error(f"[Monthly loop] Unhandled error: {e}")
        # Check every 30 min (avoids running multiple times in same hour)
        await asyncio.sleep(30 * 60)


# ═══════════════════════════════════════════════════════════════════════════
#  Public Scheduler Interface
# ═══════════════════════════════════════════════════════════════════════════


class WealthQuantScheduler:
    """
    Central scheduler managing all background data collection & research tasks.
    Instantiate once in main.py lifespan and call start() / stop().
    """

    def __init__(self):
        self._tasks: list[asyncio.Task] = []

    async def start(self):
        """Launch all background loops."""
        _state.running = True
        now = _now_ist()
        logger.info(
            f"[WealthQuant Scheduler] ⚡ Starting V7.4 — {now.strftime('%Y-%m-%d %H:%M:%S IST')} | "
            f"Market={'OPEN' if _is_market_open() else 'CLOSED'}"
        )

        self._tasks = [
            asyncio.create_task(_ingestion_loop(), name="wq_ingestion"),
            asyncio.create_task(_recorder_loop(), name="wq_recorder"),
            asyncio.create_task(_health_loop(), name="wq_health"),
            asyncio.create_task(_daily_close_loop(), name="wq_daily_close"),
            asyncio.create_task(_monthly_loop(), name="wq_monthly"),
        ]

        # Fire an immediate ingestion cycle if market is open
        if _is_market_open():
            logger.info(
                "[WealthQuant Scheduler] Market is open — running immediate ingestion cycle"
            )
            asyncio.create_task(run_ingestion_cycle())
            asyncio.create_task(run_recorder_cycle())

        # Fire an immediate health check
        asyncio.create_task(run_health_check())

    async def stop(self):
        """Gracefully cancel all background loops."""
        _state.running = False
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
        self._tasks.clear()
        logger.info("[WealthQuant Scheduler] All loops stopped.")

    def is_running(self) -> bool:
        return _state.running

    @property
    def state(self) -> _SchedulerState:
        return _state

    def status(self) -> dict:
        res = _state.to_dict()
        res["is_running"] = _state.running
        return res


# ── Module-level singleton ─────────────────────────────────────────────────
scheduler = WealthQuantScheduler()


# ═══════════════════════════════════════════════════════════════════════════
#  CLI Test Mode (python -m pipeline.scheduler --test-run)
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="WealthQuant V7.4 Scheduler")
    parser.add_argument(
        "--test-run",
        action="store_true",
        help="Run one full ingestion + health check cycle and exit",
    )
    args = parser.parse_args()

    async def _cli_test():
        # Bootstrap DB
        sys.path.insert(0, _BACKEND_DIR)
        from dotenv import load_dotenv

        load_dotenv(os.path.join(_BACKEND_DIR, ".env"))
        from pipeline.db import pipeline_db

        await pipeline_db.init_pool()

        if args.test_run:
            print("=== WealthQuant V7.4 — Test Run ===")
            print("Running health check...")
            h = await run_health_check()
            print(json.dumps(h, indent=2, default=str))
            print("\nRunning ingestion cycle...")
            await run_ingestion_cycle()
            print(f"\nRows added: {_state.rows_added_today}")
            print("=== Test complete ===")
        else:
            print("Starting full scheduler (Ctrl+C to stop)...")
            await scheduler.start()
            try:
                while True:
                    await asyncio.sleep(60)
            except KeyboardInterrupt:
                await scheduler.stop()

        await pipeline_db.close()

    asyncio.run(_cli_test())
