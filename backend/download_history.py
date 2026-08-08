"""
Offline Historical Data Downloader.
Downloads 2 years of Nifty 50 + indices OHLCV and saves it to PostgreSQL.
Supports resuming and rate limiting.
"""

import argparse
import asyncio
import logging

# Configure path so we can import from backend
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pandas as pd

import yfinance as yf

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pipeline.config import DOWNLOAD_CONFIG
from pipeline.db import pipeline_db

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("download_history")

# Mapping index symbols to DB symbols
SYMBOL_CLEAN_MAP = {"^NSEI": "NIFTY", "^NSEBANK": "BANKNIFTY"}


def clean_symbol(s: str) -> str:
    s = s.upper()
    if s in SYMBOL_CLEAN_MAP:
        return SYMBOL_CLEAN_MAP[s]
    return s.replace(".NS", "")


def yf_symbol(s: str) -> str:
    s = s.upper()
    if s == "NIFTY":
        return "^NSEI"
    if s == "BANKNIFTY":
        return "^NSEBANK"
    if not s.endswith(".NS") and s not in ["^NSEI", "^NSEBANK"]:
        return s + ".NS"
    return s


async def get_latest_timestamp(symbol: str, timeframe: str) -> datetime:
    """
    Get the latest timestamp stored in the database for the given symbol and timeframe.
    """
    if not pipeline_db.pool:
        return None
    try:
        async with pipeline_db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT max(timestamp) as max_ts
                FROM ohlcv_history
                WHERE symbol = $1 AND timeframe = $2
            """,
                symbol,
                timeframe,
            )
            return row["max_ts"] if row else None
    except Exception as e:
        logger.error(f"Error fetching latest timestamp: {e}")
        return None


async def download_symbol_history(symbol: str, timeframe: str, resume: bool = False):
    """
    Download historical OHLCV data from yfinance and save to PostgreSQL.
    """
    db_symbol = clean_symbol(symbol)
    yf_sym = yf_symbol(symbol)

    # Determine period/dates
    latest_ts = None
    if resume:
        latest_ts = await get_latest_timestamp(db_symbol, timeframe)

    start_date = None
    if latest_ts:
        # Resume download from latest timestamp
        # Add 1 bar interval to avoid duplicating the last record
        if timeframe == "1d":
            start_date = (latest_ts + timedelta(days=1)).strftime("%Y-%m-%d")
        elif timeframe == "1h":
            start_date = (latest_ts + timedelta(hours=1)).strftime("%Y-%m-%d")
        else:
            start_date = (latest_ts + timedelta(minutes=15)).strftime("%Y-%m-%d")
        logger.info(f"Resuming {db_symbol} ({timeframe}) from {start_date}")

    # Determine yfinance period
    if timeframe == "15m":
        period = "60d"  # 15m is capped at 60d by yfinance
    elif timeframe == "1h":
        period = "730d"  # 1h is capped at 730d by yfinance
    else:
        period = "2y"  # 1d has full history

    try:
        logger.info(f"Downloading {yf_sym} ({timeframe}) using yfinance...")

        # Download data
        if start_date:
            df = yf.download(
                yf_sym,
                start=start_date,
                interval=timeframe,
                progress=False,
                auto_adjust=True,
            )
        else:
            df = yf.download(
                yf_sym,
                period=period,
                interval=timeframe,
                progress=False,
                auto_adjust=True,
            )

        if df.empty:
            logger.warning(f"No data returned for {yf_sym} ({timeframe})")
            return 0

        # Flatten columns if MultiIndex (yf 0.2.x fix)
        if isinstance(df.columns, pd.MultiIndex):
            for i in range(df.columns.nlevels):
                if "Close" in df.columns.get_level_values(i):
                    df.columns = df.columns.get_level_values(i)
                    break
            else:
                df.columns = df.columns.get_level_values(0)

        # Prepare records for insertion
        records = []
        for dt, row in df.iterrows():
            # Convert index to timezone-aware datetime
            if isinstance(dt, str):
                dt_obj = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
            else:
                dt_obj = dt.to_pydatetime()

            # Ensure it is timezone-aware
            if dt_obj.tzinfo is None:
                dt_obj = dt_obj.replace(tzinfo=timezone.utc)

            records.append(
                {
                    "symbol": db_symbol,
                    "timestamp": dt_obj,
                    "timeframe": timeframe,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
                }
            )

        if records:
            success = await pipeline_db.insert_ohlcv_batch(records)
            if success:
                logger.info(
                    f"Successfully inserted {len(records)} records for {db_symbol} ({timeframe})"
                )
                return len(records)
            else:
                logger.error(
                    f"Failed to insert records for {db_symbol} ({timeframe}) to database."
                )
                return 0
        return 0

    except Exception as e:
        logger.error(f"Failed to download history for {db_symbol} ({timeframe}): {e}")
        return 0


async def show_db_status():
    """
    Print summary statistics of the database table ohlcv_history.
    """
    if not pipeline_db.pool:
        return
    try:
        async with pipeline_db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT symbol, timeframe, count(*) as count, min(timestamp) as min_ts, max(timestamp) as max_ts
                FROM ohlcv_history
                GROUP BY symbol, timeframe
                ORDER BY symbol, timeframe
            """)
            print("\n" + "=" * 80)
            print(
                f"{'SYMBOL':<15} | {'TIMEFRAME':<10} | {'RECORDS':<10} | {'MIN TIMESTAMP':<25} | {'MAX TIMESTAMP':<25}"
            )
            print("=" * 80)
            for r in rows:
                min_str = (
                    r["min_ts"].strftime("%Y-%m-%d %H:%M:%S") if r["min_ts"] else "N/A"
                )
                max_str = (
                    r["max_ts"].strftime("%Y-%m-%d %H:%M:%S") if r["max_ts"] else "N/A"
                )
                print(
                    f"{r['symbol']:<15} | {r['timeframe']:<10} | {r['count']:<10} | {min_str:<25} | {max_str:<25}"
                )
            print("=" * 80 + "\n")
    except Exception as e:
        logger.error(f"Error querying DB status: {e}")


async def main():
    parser = argparse.ArgumentParser(
        description="WealthQuant historical data downloader."
    )
    parser.add_argument(
        "--symbols", nargs="+", help="Specific symbols to download (e.g. RELIANCE TCS)"
    )
    parser.add_argument(
        "--timeframe",
        choices=["15m", "1h", "1d"],
        help="Specific timeframe to download",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume downloads from latest database records",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show database record summary status and exit",
    )

    args = parser.parse_args()

    # 1. Initialize DB pool
    logger.info("Initializing database connection pool...")
    connected = await pipeline_db.init_pool()
    if not connected:
        logger.error("Database initialization failed. Exiting.")
        sys.exit(1)

    if args.status:
        await show_db_status()
        await pipeline_db.close()
        return

    # Determine symbols list
    symbols = args.symbols
    if not symbols:
        # Load Nifty 50 + indices from config
        symbols = DOWNLOAD_CONFIG.get("symbols_nifty50", []) + DOWNLOAD_CONFIG.get(
            "indices", []
        )

    # Determine timeframes
    timeframes = (
        [args.timeframe]
        if args.timeframe
        else DOWNLOAD_CONFIG.get("timeframes", ["1d", "1h", "15m"])
    )

    logger.info(
        f"Starting historical download for {len(symbols)} symbols across {timeframes} timeframes..."
    )
    t0 = time.time()

    total_inserted = 0

    for timeframe in timeframes:
        logger.info(f"Downloading timeframe: {timeframe}")
        for symbol in symbols:
            # Skip empty symbol strings
            if not symbol:
                continue

            inserted = await download_symbol_history(
                symbol, timeframe, resume=args.resume
            )
            total_inserted += inserted
            # Rate limiting delay
            time.sleep(1.0)

    logger.info(
        f"Historical download completed. Total records inserted: {total_inserted}. Time elapsed: {time.time() - t0:.1f}s"
    )

    # Show status summary
    await show_db_status()

    # Close pool
    await pipeline_db.close()


if __name__ == "__main__":
    # Use standard selector event loop on Windows to avoid issues with asyncpg
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
