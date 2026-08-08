"""
WealthQuant V7.1 — Real NSE Options Data Collector
====================================================

Collects LIVE option chain data from NSE India and stores into the
Options Data Warehouse (4 PostgreSQL tables):
  • options_history  — daily summary per symbol per expiry
  • strike_history   — per-strike OI / IV / volume / LTP
  • wall_history     — call / put wall positions
  • pcr_history      — put-call ratio tracking

Usage:
    # As CLI
    python -m pipeline.options_collector --symbols NIFTY BANKNIFTY

    # As module
    from pipeline.options_collector import collect_and_store
    result = await collect_and_store(["NIFTY", "BANKNIFTY"])

NO synthetic / fake data is generated — every row originates from the
NSE option-chain API.
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import date

import numpy as np

# ── path bootstrap (so `pipeline.*` imports resolve when run standalone) ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

import nse_cookie_manager

load_dotenv(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
)

# Fix Windows terminal encoding (cp1252 cannot encode Unicode symbols)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline.db import pipeline_db

logger = logging.getLogger("pipeline.options_collector")

# ═══════════════════════════════════════════════════════════════════════
#  1. NSE API — session + fetch with retry
# ═══════════════════════════════════════════════════════════════════════

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
}

_NSE_BASE = "https://www.nseindia.com"
_NSE_OPTION_CHAIN_URL = (
    "https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
)

MAX_RETRIES = 3
RETRY_BACKOFF_S = 2.0


def fetch_option_chain(symbol: str) -> dict:
    """
    Fetch raw option-chain JSON from the NSE API.
    Delegates to nse_cookie_manager.
    """
    try:
        data = nse_cookie_manager.fetch_option_chain_api(symbol)
        if data and data.get("records"):
            print(
                f"[OptionsCollector] ✓ Fetched {symbol} chain using nse_cookie_manager"
            )
            return data
        else:
            raise ValueError(
                f"NSE returned empty response or no 'records' key for {symbol}"
            )
    except Exception as e:
        logger.error(
            f"[OptionsCollector] Failed to fetch option chain for {symbol}: {e}"
        )
        raise RuntimeError(f"NSE option chain unavailable for {symbol}: {e}")


# ═══════════════════════════════════════════════════════════════════════
#  2. Parse raw NSE JSON → strike rows
# ═══════════════════════════════════════════════════════════════════════


def parse_chain(
    raw_data: dict,
    expiry: str | None = None,
) -> tuple[list[dict], float, str, list[str]]:
    """
    Parse the raw NSE option-chain JSON.

    Parameters
    ----------
    raw_data : dict
        JSON returned by :func:`fetch_option_chain`.
    expiry : str, optional
        Specific expiry to filter (e.g. ``'20-Jun-2025'``).  If *None*,
        the nearest (first) expiry is used.

    Returns
    -------
    strike_rows : list[dict]
        One dict per strike with keys:
        strike, ce_oi, ce_oi_change, ce_volume, ce_iv, ce_ltp,
        pe_oi, pe_oi_change, pe_volume, pe_iv, pe_ltp.
    spot_price : float
        Underlying spot price (``underlyingValue``).
    expiry_used : str
        The expiry date string actually used (NSE format, e.g. '20-Jun-2025').
    all_expiries : list[str]
        Every available expiry date string.
    """
    records = raw_data.get("records", {})
    spot_price = float(records.get("underlyingValue", 0))
    all_expiries: list[str] = records.get("expiryDates", [])

    if not all_expiries:
        raise ValueError("No expiry dates found in NSE response")

    # Select the target expiry
    expiry_used = expiry if (expiry and expiry in all_expiries) else all_expiries[0]

    # Filter data rows for the chosen expiry
    all_data = records.get("data", [])
    strike_rows: list[dict] = []

    for row in all_data:
        expiry_key = "expiryDates" if "expiryDates" in row else "expiryDate"
        if row.get(expiry_key) != expiry_used:
            continue

        strike = float(row.get("strikePrice", 0))
        ce = row.get("CE", {})
        pe = row.get("PE", {})

        strike_rows.append(
            {
                "strike": strike,
                "ce_oi": int(ce.get("openInterest", 0)) if ce else 0,
                "ce_oi_change": int(ce.get("changeinOpenInterest", 0)) if ce else 0,
                "ce_volume": int(ce.get("totalTradedVolume", 0)) if ce else 0,
                "ce_iv": float(ce.get("impliedVolatility", 0)) if ce else 0.0,
                "ce_ltp": float(ce.get("lastPrice", 0)) if ce else 0.0,
                "pe_oi": int(pe.get("openInterest", 0)) if pe else 0,
                "pe_oi_change": int(pe.get("changeinOpenInterest", 0)) if pe else 0,
                "pe_volume": int(pe.get("totalTradedVolume", 0)) if pe else 0,
                "pe_iv": float(pe.get("impliedVolatility", 0)) if pe else 0.0,
                "pe_ltp": float(pe.get("lastPrice", 0)) if pe else 0.0,
            }
        )

    return strike_rows, spot_price, expiry_used, all_expiries


# ═══════════════════════════════════════════════════════════════════════
#  3. Max-pain calculation (vectorised with NumPy)
# ═══════════════════════════════════════════════════════════════════════


def calc_max_pain(strike_rows: list[dict]) -> float:
    """
    Calculate the max-pain strike — the settlement price at which total
    option-buyer loss is maximised (i.e. total intrinsic value of all
    open contracts is minimised for option writers).

    Uses vectorised NumPy for speed.

    Parameters
    ----------
    strike_rows : list[dict]
        Output of :func:`parse_chain`.

    Returns
    -------
    float
        The max-pain strike price.  Returns 0.0 if input is empty.
    """
    if not strike_rows:
        return 0.0

    strikes = np.array([r["strike"] for r in strike_rows], dtype=np.float64)
    ce_oi = np.array([r["ce_oi"] for r in strike_rows], dtype=np.float64)
    pe_oi = np.array([r["pe_oi"] for r in strike_rows], dtype=np.float64)

    n = len(strikes)
    total_pain = np.zeros(n, dtype=np.float64)

    for i in range(n):
        settlement = strikes[i]
        # CE buyers lose when settlement < strike (calls expire worthless above settlement)
        # Actually: CE intrinsic = max(0, settlement - strike) for each OI lot
        ce_intrinsic = np.maximum(0.0, settlement - strikes) * ce_oi
        pe_intrinsic = np.maximum(0.0, strikes - settlement) * pe_oi
        total_pain[i] = ce_intrinsic.sum() + pe_intrinsic.sum()

    # Max pain = strike with MINIMUM total intrinsic payout to buyers
    return float(strikes[np.argmin(total_pain)])


# ═══════════════════════════════════════════════════════════════════════
#  4. Main collector — fetch, compute, store
# ═══════════════════════════════════════════════════════════════════════


async def collect_and_store(
    symbols: list[str] | None = None,
) -> dict:
    """
    End-to-end collection: fetch live NSE data → compute analytics →
    upsert into the 4 options warehouse tables.

    Parameters
    ----------
    symbols : list[str], optional
        Symbols to collect.  Defaults to ``['NIFTY', 'BANKNIFTY']``.

    Returns
    -------
    dict
        Summary with per-symbol results and overall status.
    """
    if symbols is None:
        symbols = ["NIFTY", "BANKNIFTY"]

    # ── ensure DB pool is ready ──
    if not pipeline_db.is_connected:
        print("[OptionsCollector] Initialising database pool …")
        connected = await pipeline_db.init_pool()
        if not connected:
            print("[OptionsCollector] ✗ Database connection failed — aborting.")
            return {"status": "error", "reason": "db_connection_failed", "symbols": {}}

    today = date.today()
    summary: dict = {"status": "ok", "date": str(today), "symbols": {}}

    for symbol in symbols:
        sym_result: dict = {}
        try:
            print(f"\n[OptionsCollector] ── Collecting {symbol} ──")

            # 4a. Fetch ──────────────────────────────────────────────
            raw = fetch_option_chain(symbol)

            # 4b. Parse (nearest expiry) ─────────────────────────────
            strike_rows, spot_price, expiry_used, all_expiries = parse_chain(raw)

            if not strike_rows:
                print(
                    f"[OptionsCollector] ✗ No strike data for {symbol} "
                    f"expiry {expiry_used}"
                )
                sym_result = {"status": "no_data", "expiry": expiry_used}
                summary["symbols"][symbol] = sym_result
                continue

            num_strikes = len(strike_rows)
            print(
                f"[OptionsCollector]   Spot: {spot_price:,.2f}  |  "
                f"Expiry: {expiry_used}  |  Strikes: {num_strikes}"
            )

            # 4c. Aggregate metrics ──────────────────────────────────
            total_ce_oi = sum(r["ce_oi"] for r in strike_rows)
            total_pe_oi = sum(r["pe_oi"] for r in strike_rows)
            total_ce_volume = sum(r["ce_volume"] for r in strike_rows)
            total_pe_volume = sum(r["pe_volume"] for r in strike_rows)
            oi_change_ce = sum(r["ce_oi_change"] for r in strike_rows)
            oi_change_pe = sum(r["pe_oi_change"] for r in strike_rows)

            # PCR (OI-based and volume-based)
            pcr_oi = round(total_pe_oi / total_ce_oi, 4) if total_ce_oi else 0.0
            pcr_volume = (
                round(total_pe_volume / total_ce_volume, 4) if total_ce_volume else 0.0
            )
            pcr_signal = (
                "BULLISH" if pcr_oi > 1.2 else "BEARISH" if pcr_oi < 0.7 else "NEUTRAL"
            )

            # Call Wall = strike with highest CE OI
            call_wall_row = max(strike_rows, key=lambda r: r["ce_oi"])
            call_wall = call_wall_row["strike"]
            call_wall_oi = call_wall_row["ce_oi"]

            # Put Wall = strike with highest PE OI
            put_wall_row = max(strike_rows, key=lambda r: r["pe_oi"])
            put_wall = put_wall_row["strike"]
            put_wall_oi = put_wall_row["pe_oi"]

            # Wall distance from spot (%)
            call_wall_dist = (
                round((call_wall - spot_price) / spot_price * 100, 2)
                if spot_price
                else 0.0
            )
            put_wall_dist = (
                round((spot_price - put_wall) / spot_price * 100, 2)
                if spot_price
                else 0.0
            )

            # ATM strike + IV
            atm_strike = min(
                (r["strike"] for r in strike_rows),
                key=lambda s: abs(s - spot_price),
            )
            atm_row = next(r for r in strike_rows if r["strike"] == atm_strike)
            ce_iv = atm_row["ce_iv"]
            pe_iv = atm_row["pe_iv"]
            if ce_iv > 0 and pe_iv > 0:
                atm_iv = round((ce_iv + pe_iv) / 2, 2)
            else:
                atm_iv = ce_iv or pe_iv or None

            # Max Pain
            max_pain = calc_max_pain(strike_rows)

            print(
                f"[OptionsCollector]   PCR(OI): {pcr_oi:.3f}  |  "
                f"ATM IV: {atm_iv}  |  Max Pain: {max_pain:,.0f}"
            )
            print(
                f"[OptionsCollector]   Call Wall: {call_wall:,.0f} "
                f"({call_wall_oi:,} OI)  |  "
                f"Put Wall: {put_wall:,.0f} ({put_wall_oi:,} OI)"
            )

            # 4d. Database upserts ───────────────────────────────────
            async with pipeline_db.pool.acquire() as conn:
                # ① options_history
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
                        spot_price       = EXCLUDED.spot_price,
                        pcr              = EXCLUDED.pcr,
                        total_ce_oi      = EXCLUDED.total_ce_oi,
                        total_pe_oi      = EXCLUDED.total_pe_oi,
                        total_ce_volume  = EXCLUDED.total_ce_volume,
                        total_pe_volume  = EXCLUDED.total_pe_volume,
                        oi_change_ce     = EXCLUDED.oi_change_ce,
                        oi_change_pe     = EXCLUDED.oi_change_pe,
                        atm_iv           = EXCLUDED.atm_iv,
                        atm_strike       = EXCLUDED.atm_strike,
                        call_wall        = EXCLUDED.call_wall,
                        call_wall_oi     = EXCLUDED.call_wall_oi,
                        put_wall         = EXCLUDED.put_wall,
                        put_wall_oi      = EXCLUDED.put_wall_oi,
                        max_pain         = EXCLUDED.max_pain,
                        num_strikes      = EXCLUDED.num_strikes
                """,
                    symbol,
                    today,
                    spot_price,
                    expiry_used,
                    pcr_oi,
                    total_ce_oi,
                    total_pe_oi,
                    total_ce_volume,
                    total_pe_volume,
                    oi_change_ce,
                    oi_change_pe,
                    atm_iv,
                    atm_strike,
                    call_wall,
                    call_wall_oi,
                    put_wall,
                    put_wall_oi,
                    max_pain,
                    num_strikes,
                )

                # ② strike_history (batch upsert)
                strike_values = [
                    (
                        symbol,
                        today,
                        expiry_used,
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
                    strike_values,
                )

                # ③ wall_history
                await conn.execute(
                    """
                    INSERT INTO wall_history (
                        symbol, date, expiry,
                        call_wall, call_wall_oi, put_wall, put_wall_oi,
                        spot_price, call_wall_distance_pct, put_wall_distance_pct
                    ) VALUES (
                        $1, $2, $3,
                        $4, $5, $6, $7,
                        $8, $9, $10
                    )
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
                    expiry_used,
                    call_wall,
                    call_wall_oi,
                    put_wall,
                    put_wall_oi,
                    spot_price,
                    call_wall_dist,
                    put_wall_dist,
                )

                # ④ pcr_history
                await conn.execute(
                    """
                    INSERT INTO pcr_history (
                        symbol, date, expiry,
                        pcr_oi, pcr_volume,
                        total_ce_oi, total_pe_oi,
                        total_ce_volume, total_pe_volume,
                        pcr_signal
                    ) VALUES (
                        $1, $2, $3,
                        $4, $5,
                        $6, $7,
                        $8, $9,
                        $10
                    )
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
                    expiry_used,
                    pcr_oi,
                    pcr_volume,
                    total_ce_oi,
                    total_pe_oi,
                    total_ce_volume,
                    total_pe_volume,
                    pcr_signal,
                )

            print(
                f"[OptionsCollector] ✓ {symbol} → 4 tables updated "
                f"({num_strikes} strikes)"
            )

            sym_result = {
                "status": "ok",
                "spot_price": spot_price,
                "expiry": expiry_used,
                "num_strikes": num_strikes,
                "pcr_oi": pcr_oi,
                "pcr_volume": pcr_volume,
                "pcr_signal": pcr_signal,
                "atm_iv": atm_iv,
                "atm_strike": atm_strike,
                "call_wall": call_wall,
                "call_wall_oi": call_wall_oi,
                "put_wall": put_wall,
                "put_wall_oi": put_wall_oi,
                "max_pain": max_pain,
                "all_expiries": all_expiries,
            }

        except Exception as exc:
            logger.error("[OptionsCollector] %s failed: %s", symbol, exc, exc_info=True)
            print(f"[OptionsCollector] ✗ {symbol} failed: {exc}")
            sym_result = {"status": "error", "reason": str(exc)}

        summary["symbols"][symbol] = sym_result

    # ── overall status ──
    failed = [s for s, r in summary["symbols"].items() if r.get("status") != "ok"]
    if failed:
        summary["status"] = "partial" if len(failed) < len(symbols) else "error"

    return summary


# ═══════════════════════════════════════════════════════════════════════
#  5. CLI entry-point
# ═══════════════════════════════════════════════════════════════════════


def _print_summary(result: dict) -> None:
    """Pretty-print the collection summary to stdout."""
    print("\n" + "=" * 65)
    print("  WealthQuant V7.1 — Options Collection Summary")
    print("=" * 65)
    print(f"  Date   : {result.get('date', 'N/A')}")
    print(f"  Status : {result.get('status', 'unknown').upper()}")
    print("-" * 65)

    for sym, data in result.get("symbols", {}).items():
        status = data.get("status", "unknown")
        if status == "ok":
            print(f"\n  {sym}")
            print(f"    Spot Price   : {data['spot_price']:>12,.2f}")
            print(f"    Expiry       : {data['expiry']}")
            print(f"    Strikes      : {data['num_strikes']}")
            print(f"    PCR (OI)     : {data['pcr_oi']:>12.4f}  [{data['pcr_signal']}]")
            print(f"    PCR (Volume) : {data['pcr_volume']:>12.4f}")
            print(
                f"    ATM IV       : {data['atm_iv'] if data['atm_iv'] is not None else 'N/A':>12}"
            )
            print(f"    ATM Strike   : {data['atm_strike']:>12,.0f}")
            print(
                f"    Call Wall    : {data['call_wall']:>12,.0f}  "
                f"(OI: {data['call_wall_oi']:>12,})"
            )
            print(
                f"    Put Wall     : {data['put_wall']:>12,.0f}  "
                f"(OI: {data['put_wall_oi']:>12,})"
            )
            print(f"    Max Pain     : {data['max_pain']:>12,.0f}")
        else:
            reason = data.get("reason", status)
            print(f"\n  {sym}  →  FAILED ({reason})")

    print("\n" + "=" * 65)


def main() -> None:
    """CLI entry-point for the options collector."""
    parser = argparse.ArgumentParser(
        description="WealthQuant V7.1 — Real NSE Options Data Collector",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["NIFTY", "BANKNIFTY"],
        help="NSE index symbols to collect (default: NIFTY BANKNIFTY)",
    )
    args = parser.parse_args()

    print("[OptionsCollector] Starting collection …")
    print(f"[OptionsCollector] Symbols: {', '.join(args.symbols)}")
    print(f"[OptionsCollector] Date   : {date.today()}")

    result = asyncio.run(collect_and_store(args.symbols))
    _print_summary(result)


if __name__ == "__main__":
    main()
