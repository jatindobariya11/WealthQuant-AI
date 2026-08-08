"""
╔══════════════════════════════════════════════════════════════════════════╗
║  WealthQuant V7.5 — Market Data Warehouse Collector                      ║
║                                                                           ║
║  MISSION: Populate 5 PostgreSQL warehouse tables continuously:            ║
║    • options_history  — daily summary (all expiries)                     ║
║    • strike_history   — every strike for every expiry                    ║
║    • wall_history     — call/put wall positions                          ║
║    • pcr_history      — OI + volume PCR tracking                        ║
║    • fii_dii          — daily institutional flows                        ║
║                                                                           ║
║  RULES:                                                                   ║
║    - UPSERT only — never overwrites historical records                   ║
║    - Skips gracefully if NSE unavailable                                 ║
║    - Auto-retries with exponential backoff                               ║
║    - Zero new tables, zero new models, zero new indicators               ║
║    - All writes use ON CONFLICT DO UPDATE                                ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
import time
from datetime import date, datetime
from pathlib import Path

import numpy as np
import requests

logger = logging.getLogger("wealthquant.warehouse")

# ── NSE session config ─────────────────────────────────────────────────────
_NSE_BASE = "https://www.nseindia.com"
_NSE_OPT_URL = "https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
_NSE_FII_URL = "https://www.nseindia.com/api/fiidiiTradeReact"

_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# Symbols for the warehouse (options + FII/DII)
WAREHOUSE_SYMBOLS = ["NIFTY", "BANKNIFTY"]

# ── Report path ───────────────────────────────────────────────────────────
import os as _os

_BACKEND_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_PROJECT_DIR = _os.path.dirname(_BACKEND_DIR)
WAREHOUSE_REPORT = _os.path.join(_PROJECT_DIR, "MARKET_DATA_WAREHOUSE_REPORT.md")


# ═══════════════════════════════════════════════════════════════════════════
#  1. NSE Session — delegate to data_fetcher's proven session management
# ═══════════════════════════════════════════════════════════════════════════


def _nse_fetch(url: str, max_retries: int = 4, base_delay: float = 2.0) -> dict | list:
    """
    Fetch JSON from NSE. Delegates to data_fetcher._nse_get which manages
    the singleton warmed-up session (homepage + live-equity-market warmup),
    auto-refreshes on 403, and handles all retries.

    Falls back to a standalone session if data_fetcher is unavailable.
    """
    # Primary: reuse the proven data_fetcher session (already warmed up in production)
    try:
        from data_fetcher import _nse_get

        return _nse_get(url, retries=max_retries)
    except ImportError:
        pass
    except Exception as e:
        # If data_fetcher session also fails, fall through to standalone
        logger.debug(
            "[Warehouse] data_fetcher._nse_get failed (%s), trying standalone", e
        )
        raise  # propagate real errors (404, connection refused, etc.)

    # Fallback: standalone session with full two-page warmup
    last_err = None
    for attempt in range(1, max_retries + 1):
        sess = requests.Session()
        sess.headers.update(_NSE_HEADERS)
        try:
            # Two-page warmup matching data_fetcher behaviour
            try:
                sess.get(_NSE_BASE, timeout=(6.0, 8.0))
                time.sleep(1.5)
                sess.get(
                    f"{_NSE_BASE}/market-data/live-equity-market", timeout=(6.0, 8.0)
                )
                time.sleep(0.5)
            except Exception:
                pass

            resp = sess.get(url, timeout=(12.0, 15.0))
            if resp.status_code == 403:
                last_err = RuntimeError("NSE HTTP 403 — rate limited")
            elif resp.status_code == 200:
                return resp.json()
            else:
                last_err = RuntimeError(f"NSE HTTP {resp.status_code}")
        except Exception as exc:
            last_err = exc
            logger.warning(
                "[Warehouse] Standalone NSE fetch attempt %d/%d: %s",
                attempt,
                max_retries,
                exc,
            )
        finally:
            sess.close()

        if attempt < max_retries:
            delay = min(base_delay * (2 ** (attempt - 1)), 30.0)
            time.sleep(delay)

    raise RuntimeError(f"NSE unavailable after {max_retries} retries. Last: {last_err}")


# ═══════════════════════════════════════════════════════════════════════════
#  2. Options Chain: Fetch + Parse ALL expiries
# ═══════════════════════════════════════════════════════════════════════════


def fetch_option_chain_all_expiries(symbol: str) -> dict:
    """
    Fetch and parse the NSE option chain for a symbol, returning data
    keyed by expiry. This collects ALL available expiries (weekly + monthly).

    Returns
    -------
    dict with keys:
        spot_price  : float
        all_expiries: list[str]
        by_expiry   : dict[expiry_str -> list[strike_rows]]
    """
    raw = _nse_fetch(_NSE_OPT_URL.format(symbol=symbol))

    records = raw.get("records", {})
    spot_price: float = float(records.get("underlyingValue", 0.0))
    all_expiries: list[str] = records.get("expiryDates", [])

    if not all_expiries:
        raise ValueError(f"No expiry dates in NSE response for {symbol}")

    # Index raw data rows by expiry
    raw_data = records.get("data", [])
    by_expiry: dict[str, list[dict]] = {}

    for row in raw_data:
        expiry = row.get("expiryDate", "")
        if not expiry:
            continue
        if expiry not in by_expiry:
            by_expiry[expiry] = []

        strike = float(row.get("strikePrice", 0.0))
        ce = row.get("CE") or {}
        pe = row.get("PE") or {}

        by_expiry[expiry].append(
            {
                "strike": strike,
                "ce_oi": int(ce.get("openInterest", 0)),
                "ce_oi_change": int(ce.get("changeinOpenInterest", 0)),
                "ce_volume": int(ce.get("totalTradedVolume", 0)),
                "ce_iv": float(ce.get("impliedVolatility", 0.0)),
                "ce_ltp": float(ce.get("lastPrice", 0.0)),
                "pe_oi": int(pe.get("openInterest", 0)),
                "pe_oi_change": int(pe.get("changeinOpenInterest", 0)),
                "pe_volume": int(pe.get("totalTradedVolume", 0)),
                "pe_iv": float(pe.get("impliedVolatility", 0.0)),
                "pe_ltp": float(pe.get("lastPrice", 0.0)),
            }
        )

    return {
        "spot_price": spot_price,
        "all_expiries": all_expiries,
        "by_expiry": by_expiry,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  3. Analytics Engine — PCR, Walls, Max Pain, ATM IV
# ═══════════════════════════════════════════════════════════════════════════


def _calc_max_pain(strike_rows: list[dict]) -> float:
    """Max pain: strike where total option-buyer intrinsic value is minimised."""
    if not strike_rows:
        return 0.0
    strikes = np.array([r["strike"] for r in strike_rows], dtype=np.float64)
    ce_oi = np.array([r["ce_oi"] for r in strike_rows], dtype=np.float64)
    pe_oi = np.array([r["pe_oi"] for r in strike_rows], dtype=np.float64)
    n = len(strikes)
    total_pain = np.zeros(n, dtype=np.float64)
    for i in range(n):
        s = strikes[i]
        total_pain[i] = (
            np.maximum(0.0, s - strikes) * ce_oi + np.maximum(0.0, strikes - s) * pe_oi
        ).sum()
    return float(strikes[np.argmin(total_pain)])


def compute_chain_analytics(strike_rows: list[dict], spot_price: float) -> dict:
    """
    Given a list of strike rows for ONE expiry, compute all warehouse metrics.
    Returns a dict ready to UPSERT into options_history, wall_history, pcr_history.
    """
    if not strike_rows:
        return {}

    total_ce_oi = sum(r["ce_oi"] for r in strike_rows)
    total_pe_oi = sum(r["pe_oi"] for r in strike_rows)
    total_ce_volume = sum(r["ce_volume"] for r in strike_rows)
    total_pe_volume = sum(r["pe_volume"] for r in strike_rows)
    oi_change_ce = sum(r["ce_oi_change"] for r in strike_rows)
    oi_change_pe = sum(r["pe_oi_change"] for r in strike_rows)

    # PCR
    pcr_oi = round(total_pe_oi / total_ce_oi, 4) if total_ce_oi else 0.0
    pcr_volume = round(total_pe_volume / total_ce_volume, 4) if total_ce_volume else 0.0
    pcr_signal = "BULLISH" if pcr_oi > 1.2 else "BEARISH" if pcr_oi < 0.7 else "NEUTRAL"

    # Walls
    call_wall_row = max(strike_rows, key=lambda r: r["ce_oi"])
    put_wall_row = max(strike_rows, key=lambda r: r["pe_oi"])
    call_wall = call_wall_row["strike"]
    call_wall_oi = call_wall_row["ce_oi"]
    put_wall = put_wall_row["strike"]
    put_wall_oi = put_wall_row["pe_oi"]

    call_wall_dist = (
        round((call_wall - spot_price) / spot_price * 100, 2) if spot_price else 0.0
    )
    put_wall_dist = (
        round((spot_price - put_wall) / spot_price * 100, 2) if spot_price else 0.0
    )

    # ATM IV
    atm_strike = min(
        (r["strike"] for r in strike_rows), key=lambda s: abs(s - spot_price)
    )
    atm_row = next((r for r in strike_rows if r["strike"] == atm_strike), {})
    ce_iv = atm_row.get("ce_iv", 0.0)
    pe_iv = atm_row.get("pe_iv", 0.0)
    if ce_iv > 0 and pe_iv > 0:
        atm_iv = round((ce_iv + pe_iv) / 2, 2)
    else:
        atm_iv = ce_iv or pe_iv or None

    # Max Pain
    max_pain = _calc_max_pain(strike_rows)

    return {
        "total_ce_oi": total_ce_oi,
        "total_pe_oi": total_pe_oi,
        "total_ce_volume": total_ce_volume,
        "total_pe_volume": total_pe_volume,
        "oi_change_ce": oi_change_ce,
        "oi_change_pe": oi_change_pe,
        "pcr_oi": pcr_oi,
        "pcr_volume": pcr_volume,
        "pcr_signal": pcr_signal,
        "call_wall": call_wall,
        "call_wall_oi": call_wall_oi,
        "put_wall": put_wall,
        "put_wall_oi": put_wall_oi,
        "call_wall_dist": call_wall_dist,
        "put_wall_dist": put_wall_dist,
        "atm_strike": atm_strike,
        "atm_iv": atm_iv,
        "max_pain": max_pain,
        "num_strikes": len(strike_rows),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  4. FII/DII Fetcher (enhanced)
# ═══════════════════════════════════════════════════════════════════════════


def fetch_fii_dii_flows() -> dict:
    """
    Fetch today's FII + DII net flows from NSE.
    Delegates to data_fetcher.fetch_fii_dii() (proven singleton-session version).
    Returns dict with fii_net, dii_net (and error key if failed).
    """
    # Primary: reuse data_fetcher's proven session
    try:
        from data_fetcher import fetch_fii_dii

        result = fetch_fii_dii()
        if "error" not in result:
            return {
                "fii_net": result.get("fii_net", 0.0),
                "dii_net": result.get("dii_net", 0.0),
            }
    except ImportError:
        pass
    except Exception as e:
        logger.warning("[Warehouse] data_fetcher.fetch_fii_dii failed: %s", e)
        return {"error": str(e)}

    # Fallback: standalone NSE call
    try:
        raw = _nse_fetch(_NSE_FII_URL, max_retries=3, base_delay=2.0)
        if not isinstance(raw, list):
            raw = []

        def parse(v):
            try:
                return float(str(v).replace(",", "").replace(" ", "").replace("−", "-"))
            except Exception:
                return 0.0

        fii_net = dii_net = 0.0
        for row in raw:
            cat = str(row.get("category", "")).upper()
            net = parse(row.get("netValue") or row.get("netBuy") or row.get("net", 0))
            if "FII" in cat or "FPI" in cat:
                fii_net += net
            elif "DII" in cat:
                dii_net += net

        return {"fii_net": round(fii_net, 2), "dii_net": round(dii_net, 2)}
    except Exception as e:
        logger.warning("[Warehouse] FII/DII standalone fetch failed: %s", e)
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
#  5. Database Writers — all UPSERT, never DELETE
# ═══════════════════════════════════════════════════════════════════════════


async def _upsert_options_history(
    conn, symbol: str, today: date, spot: float, expiry: str, a: dict
) -> None:
    await conn.execute(
        """
        INSERT INTO options_history (
            symbol, date, spot_price, expiry, pcr,
            total_ce_oi, total_pe_oi, total_ce_volume, total_pe_volume,
            oi_change_ce, oi_change_pe,
            atm_iv, atm_strike, call_wall, call_wall_oi,
            put_wall, put_wall_oi, max_pain, num_strikes
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7, $8, $9,
            $10, $11,
            $12, $13, $14, $15,
            $16, $17, $18, $19
        )
        ON CONFLICT (symbol, date, expiry) DO UPDATE SET
            spot_price      = EXCLUDED.spot_price,
            pcr             = EXCLUDED.pcr,
            total_ce_oi     = EXCLUDED.total_ce_oi,
            total_pe_oi     = EXCLUDED.total_pe_oi,
            total_ce_volume = EXCLUDED.total_ce_volume,
            total_pe_volume = EXCLUDED.total_pe_volume,
            oi_change_ce    = EXCLUDED.oi_change_ce,
            oi_change_pe    = EXCLUDED.oi_change_pe,
            atm_iv          = EXCLUDED.atm_iv,
            atm_strike      = EXCLUDED.atm_strike,
            call_wall       = EXCLUDED.call_wall,
            call_wall_oi    = EXCLUDED.call_wall_oi,
            put_wall        = EXCLUDED.put_wall,
            put_wall_oi     = EXCLUDED.put_wall_oi,
            max_pain        = EXCLUDED.max_pain,
            num_strikes     = EXCLUDED.num_strikes
    """,
        symbol,
        today,
        spot,
        expiry,
        a["pcr_oi"],
        a["total_ce_oi"],
        a["total_pe_oi"],
        a["total_ce_volume"],
        a["total_pe_volume"],
        a["oi_change_ce"],
        a["oi_change_pe"],
        a["atm_iv"],
        a["atm_strike"],
        a["call_wall"],
        a["call_wall_oi"],
        a["put_wall"],
        a["put_wall_oi"],
        a["max_pain"],
        a["num_strikes"],
    )


async def _upsert_strike_history(
    conn, symbol: str, today: date, expiry: str, strike_rows: list[dict]
) -> None:
    values = [
        (
            symbol,
            today,
            expiry,
            r["strike"],
            r["ce_oi"],
            r["ce_oi_change"],
            r["ce_volume"],
            r["ce_iv"],
            r["ce_ltp"],
            r["pe_oi"],
            r["pe_oi_change"],
            r["pe_volume"],
            r["pe_iv"],
            r["pe_ltp"],
        )
        for r in strike_rows
    ]
    await conn.executemany(
        """
        INSERT INTO strike_history (
            symbol, date, expiry, strike,
            ce_oi, ce_oi_change, ce_volume, ce_iv, ce_ltp,
            pe_oi, pe_oi_change, pe_volume, pe_iv, pe_ltp
        ) VALUES (
            $1, $2, $3, $4,
            $5, $6, $7, $8, $9,
            $10, $11, $12, $13, $14
        )
        ON CONFLICT (symbol, date, expiry, strike) DO UPDATE SET
            ce_oi        = EXCLUDED.ce_oi,
            ce_oi_change = EXCLUDED.ce_oi_change,
            ce_volume    = EXCLUDED.ce_volume,
            ce_iv        = EXCLUDED.ce_iv,
            ce_ltp       = EXCLUDED.ce_ltp,
            pe_oi        = EXCLUDED.pe_oi,
            pe_oi_change = EXCLUDED.pe_oi_change,
            pe_volume    = EXCLUDED.pe_volume,
            pe_iv        = EXCLUDED.pe_iv,
            pe_ltp       = EXCLUDED.pe_ltp
    """,
        values,
    )


async def _upsert_wall_history(
    conn, symbol: str, today: date, spot: float, expiry: str, a: dict
) -> None:
    await conn.execute(
        """
        INSERT INTO wall_history (
            symbol, date, expiry,
            call_wall, call_wall_oi, put_wall, put_wall_oi,
            spot_price, call_wall_distance_pct, put_wall_distance_pct
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (symbol, date, expiry) DO UPDATE SET
            call_wall              = EXCLUDED.call_wall,
            call_wall_oi           = EXCLUDED.call_wall_oi,
            put_wall               = EXCLUDED.put_wall,
            put_wall_oi            = EXCLUDED.put_wall_oi,
            spot_price             = EXCLUDED.spot_price,
            call_wall_distance_pct = EXCLUDED.call_wall_distance_pct,
            put_wall_distance_pct  = EXCLUDED.put_wall_distance_pct
    """,
        symbol,
        today,
        expiry,
        a["call_wall"],
        a["call_wall_oi"],
        a["put_wall"],
        a["put_wall_oi"],
        spot,
        a["call_wall_dist"],
        a["put_wall_dist"],
    )


async def _upsert_pcr_history(
    conn, symbol: str, today: date, expiry: str, a: dict
) -> None:
    await conn.execute(
        """
        INSERT INTO pcr_history (
            symbol, date, expiry,
            pcr_oi, pcr_volume,
            total_ce_oi, total_pe_oi,
            total_ce_volume, total_pe_volume,
            pcr_signal
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (symbol, date, expiry) DO UPDATE SET
            pcr_oi          = EXCLUDED.pcr_oi,
            pcr_volume      = EXCLUDED.pcr_volume,
            total_ce_oi     = EXCLUDED.total_ce_oi,
            total_pe_oi     = EXCLUDED.total_pe_oi,
            total_ce_volume = EXCLUDED.total_ce_volume,
            total_pe_volume = EXCLUDED.total_pe_volume,
            pcr_signal      = EXCLUDED.pcr_signal
    """,
        symbol,
        today,
        expiry,
        a["pcr_oi"],
        a["pcr_volume"],
        a["total_ce_oi"],
        a["total_pe_oi"],
        a["total_ce_volume"],
        a["total_pe_volume"],
        a["pcr_signal"],
    )


async def _upsert_fii_dii(conn, today_str: str, fii_net: float, dii_net: float) -> None:
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
        fii_net,
        dii_net,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  6. Main Warehouse Collection Entry Point
# ═══════════════════════════════════════════════════════════════════════════


async def run_warehouse_collection(symbols: list | None = None) -> dict:
    """
    Full warehouse collection cycle:
    1. For each symbol: fetch ALL expiry option chains → compute analytics
       → UPSERT into options_history, strike_history, wall_history, pcr_history
    2. Fetch FII/DII flows → UPSERT into fii_dii

    Returns a summary dict with per-symbol results.
    Skips gracefully if NSE is unavailable.
    """
    from pipeline.db import pipeline_db

    if symbols is None:
        symbols = WAREHOUSE_SYMBOLS

    if not pipeline_db.is_connected:
        logger.warning("[Warehouse] DB not connected — skipping warehouse collection")
        return {"status": "error", "reason": "db_not_connected"}

    today = date.today()
    summary = {
        "status": "ok",
        "date": str(today),
        "symbols": {},
        "fii_dii": None,
    }

    # ── Options collection for all symbols ───────────────────────────────
    for symbol in symbols:
        sym_result = {
            "status": "error",
            "expiries_done": 0,
            "total_strikes": 0,
            "errors": [],
        }
        try:
            logger.info(
                "[Warehouse] Collecting option chain for %s (all expiries)…", symbol
            )
            # Fetch in thread since it's synchronous requests
            chain_data = await asyncio.to_thread(
                fetch_option_chain_all_expiries, symbol
            )

            spot_price = chain_data["spot_price"]
            all_expiries = chain_data["all_expiries"]
            by_expiry = chain_data["by_expiry"]

            expiries_done = 0
            total_strikes = 0

            async with pipeline_db.pool.acquire() as conn:
                for expiry in all_expiries:
                    strike_rows = by_expiry.get(expiry, [])
                    if not strike_rows:
                        continue
                    try:
                        analytics = compute_chain_analytics(strike_rows, spot_price)
                        if not analytics:
                            continue

                        await _upsert_options_history(
                            conn, symbol, today, spot_price, expiry, analytics
                        )
                        await _upsert_strike_history(
                            conn, symbol, today, expiry, strike_rows
                        )
                        await _upsert_wall_history(
                            conn, symbol, today, spot_price, expiry, analytics
                        )
                        await _upsert_pcr_history(
                            conn, symbol, today, expiry, analytics
                        )

                        expiries_done += 1
                        total_strikes += len(strike_rows)
                        logger.debug(
                            "[Warehouse] %s/%s: %d strikes | PCR=%.3f | CW=%.0f | PW=%.0f | MaxPain=%.0f",
                            symbol,
                            expiry,
                            len(strike_rows),
                            analytics["pcr_oi"],
                            analytics["call_wall"],
                            analytics["put_wall"],
                            analytics["max_pain"],
                        )
                    except Exception as ex:
                        sym_result["errors"].append(f"{expiry}: {ex}")
                        logger.warning(
                            "[Warehouse] %s/%s upsert failed: %s", symbol, expiry, ex
                        )

            sym_result.update(
                {
                    "status": "ok" if expiries_done > 0 else "no_data",
                    "spot_price": spot_price,
                    "expiries_done": expiries_done,
                    "total_expiries": len(all_expiries),
                    "total_strikes": total_strikes,
                }
            )
            logger.info(
                "[Warehouse] ✓ %s: %d/%d expiries | %d strikes stored",
                symbol,
                expiries_done,
                len(all_expiries),
                total_strikes,
            )

        except Exception as e:
            sym_result["errors"].append(str(e))
            logger.warning("[Warehouse] ✗ %s option chain failed: %s", symbol, e)
            if (
                "unavailable" in str(e).lower()
                or "404" in str(e)
                or "retries" in str(e).lower()
            ):
                sym_result["status"] = "nse_unavailable"
            else:
                sym_result["status"] = "error"

        summary["symbols"][symbol] = sym_result

    # ── FII/DII collection ───────────────────────────────────────────────
    try:
        logger.info("[Warehouse] Collecting FII/DII flows…")
        flows = await asyncio.to_thread(fetch_fii_dii_flows)
        if "error" not in flows and pipeline_db.is_connected:
            today_str = today.strftime("%Y-%m-%d")
            async with pipeline_db.pool.acquire() as conn:
                await _upsert_fii_dii(
                    conn, today_str, flows["fii_net"], flows["dii_net"]
                )
            summary["fii_dii"] = {
                "status": "ok",
                "fii_net": flows["fii_net"],
                "dii_net": flows["dii_net"],
            }
            logger.info(
                "[Warehouse] ✓ FII/DII: FII=%.2f Cr | DII=%.2f Cr",
                flows["fii_net"],
                flows["dii_net"],
            )
        else:
            summary["fii_dii"] = {
                "status": "error",
                "reason": flows.get("error", "unknown"),
            }
            logger.warning(
                "[Warehouse] ✗ FII/DII collection failed: %s", flows.get("error")
            )
    except Exception as e:
        summary["fii_dii"] = {"status": "error", "reason": str(e)}
        logger.warning("[Warehouse] ✗ FII/DII exception: %s", e)

    return summary


# ═══════════════════════════════════════════════════════════════════════════
#  7. Warehouse Health Report Generator
# ═══════════════════════════════════════════════════════════════════════════


async def generate_warehouse_report() -> str:
    """
    Query the 5 warehouse tables and generate MARKET_DATA_WAREHOUSE_REPORT.md.
    Returns the report as a string. Also writes it to disk.
    """
    from pipeline.db import pipeline_db

    try:
        from zoneinfo import ZoneInfo

        IST = ZoneInfo("Asia/Kolkata")
    except ImportError:
        from datetime import timedelta, timezone

        IST = timezone(timedelta(hours=5, minutes=30))

    now_ist = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    today = date.today()
    lines = [
        "# 🏭 Market Data Warehouse Report — WealthQuant V7.5",
        "",
        f"**Generated:** {now_ist}  ",
        f"**Warehouse Date:** {today}  ",
        f"**DB Status:** {'🟢 CONNECTED' if pipeline_db.is_connected else '🔴 OFFLINE'}",
        "",
        "---",
        "",
    ]

    if not pipeline_db.is_connected:
        lines.append("> ❌ Database is offline — report cannot be generated.")
        report = "\n".join(lines)
        Path(WAREHOUSE_REPORT).write_text(report, encoding="utf-8")
        return report

    try:
        async with pipeline_db.pool.acquire() as conn:
            # ── 1. Row Counts ─────────────────────────────────────────
            counts = {}
            for tbl in (
                "options_history",
                "strike_history",
                "wall_history",
                "pcr_history",
                "fii_dii",
            ):
                counts[tbl] = await conn.fetchval(f"SELECT COUNT(*) FROM {tbl}")

            lines += [
                "## 1. Row Counts",
                "",
                "| Table | Total Rows |",
                "|:---|---:|",
            ]
            for tbl, cnt in counts.items():
                icon = "✅" if cnt > 0 else "⚠️"
                lines.append(f"| `{tbl}` | {icon} {cnt:,} |")
            lines.append("")

            # ── 2. Options Coverage ────────────────────────────────────
            lines += ["## 2. Options Coverage", ""]
            for sym in WAREHOUSE_SYMBOLS:
                oh_rows = await conn.fetchval(
                    "SELECT COUNT(*) FROM options_history WHERE symbol=$1", sym
                )
                oh_days = await conn.fetchval(
                    "SELECT COUNT(DISTINCT date) FROM options_history WHERE symbol=$1",
                    sym,
                )
                oh_exp = await conn.fetchval(
                    "SELECT COUNT(DISTINCT expiry) FROM options_history WHERE symbol=$1",
                    sym,
                )
                sh_rows = await conn.fetchval(
                    "SELECT COUNT(*) FROM strike_history WHERE symbol=$1", sym
                )
                sh_today = await conn.fetchval(
                    "SELECT COUNT(*) FROM strike_history WHERE symbol=$1 AND date=$2",
                    sym,
                    today,
                )
                wh_rows = await conn.fetchval(
                    "SELECT COUNT(*) FROM wall_history WHERE symbol=$1", sym
                )
                pcr_rows = await conn.fetchval(
                    "SELECT COUNT(*) FROM pcr_history WHERE symbol=$1", sym
                )
                # Latest record
                last_opt = await conn.fetchval(
                    "SELECT MAX(date) FROM options_history WHERE symbol=$1", sym
                )
                last_pcr_oi = await conn.fetchval(
                    "SELECT pcr_oi FROM pcr_history WHERE symbol=$1 ORDER BY date DESC, id DESC LIMIT 1",
                    sym,
                )
                last_cw = await conn.fetchval(
                    "SELECT call_wall FROM wall_history WHERE symbol=$1 ORDER BY date DESC, id DESC LIMIT 1",
                    sym,
                )
                last_pw = await conn.fetchval(
                    "SELECT put_wall FROM wall_history WHERE symbol=$1 ORDER BY date DESC, id DESC LIMIT 1",
                    sym,
                )

                lines += [
                    f"### {sym}",
                    "",
                    "| Metric | Value |",
                    "|:---|---:|",
                    f"| options_history rows | {oh_rows:,} |",
                    f"| Trading days covered | {oh_days} |",
                    f"| Expiries tracked | {oh_exp} |",
                    f"| strike_history rows | {sh_rows:,} |",
                    f"| Strikes today | {sh_today:,} |",
                    f"| wall_history rows | {wh_rows:,} |",
                    f"| pcr_history rows | {pcr_rows:,} |",
                    f"| Last successful download | {last_opt or 'N/A'} |",
                    f"| Latest PCR (OI) | {round(last_pcr_oi, 3) if last_pcr_oi else 'N/A'} |",
                    f"| Latest Call Wall | {round(last_cw, 0) if last_cw else 'N/A'} |",
                    f"| Latest Put Wall | {round(last_pw, 0) if last_pw else 'N/A'} |",
                    "",
                ]

            # ── 3. PCR Coverage ────────────────────────────────────────
            lines += ["## 3. PCR Coverage (Last 5 Days)", ""]
            for sym in WAREHOUSE_SYMBOLS:
                pcr_rows = await conn.fetch(
                    """
                    SELECT date, expiry, pcr_oi, pcr_volume, pcr_signal
                    FROM pcr_history
                    WHERE symbol=$1
                    ORDER BY date DESC, id DESC
                    LIMIT 10
                """,
                    sym,
                )
                if pcr_rows:
                    lines += [
                        f"### {sym} PCR History",
                        "",
                        "| Date | Expiry | PCR OI | PCR Vol | Signal |",
                        "|:---|:---|---:|---:|:---|",
                    ]
                    for r in pcr_rows:
                        lines.append(
                            f"| {r['date']} | {r['expiry']} | "
                            f"{r['pcr_oi']:.3f} | {r['pcr_volume']:.3f} | {r['pcr_signal']} |"
                        )
                    lines.append("")
                else:
                    lines.append(f"*No PCR data yet for {sym}*\n")

            # ── 4. FII/DII Coverage ───────────────────────────────────
            lines += ["## 4. FII/DII Coverage (Last 10 Days)", ""]
            fii_rows = await conn.fetch("""
                SELECT date, fii_net, dii_net
                FROM fii_dii
                ORDER BY date DESC
                LIMIT 10
            """)
            if fii_rows:
                lines += [
                    "| Date | FII Net (Cr) | DII Net (Cr) | Net Flow |",
                    "|:---|---:|---:|---:|",
                ]
                for r in fii_rows:
                    net = (r["fii_net"] or 0) + (r["dii_net"] or 0)
                    icon = "🟢" if net > 0 else "🔴"
                    lines.append(
                        f"| {r['date']} | {r['fii_net']:,.2f} | "
                        f"{r['dii_net']:,.2f} | {icon} {net:,.2f} |"
                    )
                lines.append("")
            else:
                lines.append("*No FII/DII data yet. NSE API may be rate-limiting.*\n")

            # ── 5. Missing Days Audit ─────────────────────────────────
            lines += ["## 5. Missing Days Audit", ""]
            for sym in WAREHOUSE_SYMBOLS:
                # Find the first and last date in options_history for this symbol
                first_d = await conn.fetchval(
                    "SELECT MIN(date) FROM options_history WHERE symbol=$1", sym
                )
                last_d = await conn.fetchval(
                    "SELECT MAX(date) FROM options_history WHERE symbol=$1", sym
                )
                if first_d and last_d and first_d != last_d:
                    # Count business days between first and last
                    import numpy as _np

                    bdays = _np.busday_count(str(first_d), str(last_d))
                    actual = await conn.fetchval(
                        "SELECT COUNT(DISTINCT date) FROM options_history WHERE symbol=$1",
                        sym,
                    )
                    missing = max(0, bdays - actual)
                    lines.append(
                        f"**{sym}:** Range `{first_d}` → `{last_d}` | "
                        f"Business days: {bdays} | Actual: {actual} | "
                        f"{'✅ No gaps' if missing == 0 else f'⚠️ ~{missing} missing days'}"
                    )
                else:
                    lines.append(
                        f"**{sym}:** Insufficient history for gap analysis (need ≥2 days)"
                    )
                lines.append("")

            # ── 6. Warehouse Health Status ────────────────────────────
            total_rows = sum(counts.values())
            all_populated = all(v > 0 for v in counts.values())
            opts_today = counts["options_history"] > 0 and counts["strike_history"] > 0

            health = (
                "🟢 HEALTHY"
                if all_populated
                else ("🟡 PARTIAL" if total_rows > 0 else "🔴 EMPTY")
            )

            lines += [
                "## 6. Warehouse Health",
                "",
                "| Metric | Status |",
                "|:---|:---|",
                f"| Overall Health | {health} |",
                f"| Total Rows | {total_rows:,} |",
                f"| All Tables Populated | {'✅ YES' if all_populated else '⚠️ NO'} |",
                f"| Options Data Today | {'✅ YES' if opts_today else '⚠️ Pending market hours'} |",
                f"| FII/DII Data | {'✅ YES' if counts['fii_dii'] > 0 else '⚠️ NSE may be offline'} |",
                "",
                "---",
                "*Report auto-generated by WealthQuant V7.5 Warehouse Scheduler*",
            ]

    except Exception as e:
        lines.append(f"\n> ❌ Report generation error: {e}")
        logger.error("[Warehouse] Report generation failed: %s", e)

    report = "\n".join(lines)
    try:
        Path(WAREHOUSE_REPORT).write_text(report, encoding="utf-8")
        logger.info("[Warehouse] Report written to %s", WAREHOUSE_REPORT)
    except Exception as e:
        logger.warning("[Warehouse] Failed to write report: %s", e)

    return report
