import asyncio
import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline.db import pipeline_db


async def run_quality_check():
    connected = await pipeline_db.init_pool()
    if not connected:
        print(
            json.dumps({"connected": False, "error": "Could not connect to database"})
        )
        return

    result = {
        "missing_candles": {},
        "duplicate_rows": {},
        "null_values": {},
        "broken_fks": {},
        "prediction_sync": {},
        "scheduler_latency_ms": 0,
        "database_size": "Unknown",
    }

    async with pipeline_db.pool.acquire() as conn:
        # 1. Missing candles (ohlcv_history gaps)
        for symbol in ["NIFTY", "BANKNIFTY"]:
            try:
                # Get consecutive timestamps to check for gaps
                rows = await conn.fetch(
                    """
                    SELECT timestamp FROM ohlcv_history 
                    WHERE symbol = $1 AND timeframe = '15m'
                    ORDER BY timestamp ASC
                """,
                    symbol,
                )
                if len(rows) > 1:
                    gaps = 0
                    for i in range(len(rows) - 1):
                        diff = rows[i + 1]["timestamp"] - rows[i]["timestamp"]
                        # During market hours, candles should be 15 mins apart.
                        # We ignore overnight/weekend gaps by checking if diff > 16 hours
                        if (
                            diff.total_seconds() > 900 and diff.total_seconds() < 57600
                        ):  # between 15 min and 16 hours
                            gaps += 1
                    result["missing_candles"][symbol] = gaps
                else:
                    result["missing_candles"][symbol] = 0
            except Exception as e:
                result["missing_candles"][symbol + "_error"] = str(e)

        # 2. Duplicate rows
        tables_to_check = [
            "ohlcv_history",
            "predictions",
            "prediction_history",
            "regime_history",
        ]
        for table in tables_to_check:
            try:
                if table == "ohlcv_history":
                    dupes = await conn.fetchval("""
                        SELECT COUNT(*) FROM (
                            SELECT symbol, timestamp, timeframe, COUNT(*) 
                            FROM ohlcv_history 
                            GROUP BY symbol, timestamp, timeframe 
                            HAVING COUNT(*) > 1
                        ) AS sub
                    """)
                elif table == "predictions":
                    dupes = await conn.fetchval("""
                        SELECT COUNT(*) FROM (
                            SELECT symbol, timestamp, horizon, COUNT(*) 
                            FROM predictions 
                            GROUP BY symbol, timestamp, horizon 
                            HAVING COUNT(*) > 1
                        ) AS sub
                    """)
                else:
                    col = "start_time" if table == "regime_history" else "timestamp"
                    dupes = await conn.fetchval(f"""
                        SELECT COUNT(*) FROM (
                            SELECT symbol, {col}, COUNT(*) 
                            FROM {table} 
                            GROUP BY symbol, {col} 
                            HAVING COUNT(*) > 1
                        ) AS sub
                    """)
                result["duplicate_rows"][table] = dupes if dupes else 0
            except Exception as e:
                result["duplicate_rows"][table + "_error"] = str(e)

        # 3. NULL values in critical fields
        try:
            null_preds = await conn.fetchval("""
                SELECT COUNT(*) FROM predictions 
                WHERE symbol IS NULL OR timestamp IS NULL OR horizon IS NULL OR signal IS NULL
            """)
            result["null_values"]["predictions"] = null_preds

            null_ohlcv = await conn.fetchval("""
                SELECT COUNT(*) FROM ohlcv_history 
                WHERE symbol IS NULL OR timestamp IS NULL OR timeframe IS NULL OR close IS NULL
            """)
            result["null_values"]["ohlcv_history"] = null_ohlcv
        except Exception as e:
            result["null_values_error"] = str(e)

        # 4. Broken foreign keys
        try:
            # check if prediction_results has prediction_id that does not exist in prediction_history
            broken_results = await conn.fetchval("""
                SELECT COUNT(*) FROM prediction_results r
                LEFT JOIN prediction_history h ON r.prediction_id = h.id
                WHERE h.id IS NULL
            """)
            result["broken_fks"]["prediction_results_to_history"] = broken_results
        except Exception as e:
            result["broken_fks_error"] = str(e)

        # 5. Prediction synchronization
        try:
            # Check if count of predictions matches count of prediction_history for NIFTY
            pred_count = await conn.fetchval(
                "SELECT COUNT(*) FROM predictions WHERE symbol='NIFTY'"
            )
            hist_count = await conn.fetchval(
                "SELECT COUNT(*) FROM prediction_history WHERE symbol='NIFTY'"
            )
            result["prediction_sync"] = {
                "predictions_count": pred_count,
                "prediction_history_count": hist_count,
                "synchronized": pred_count == hist_count,
            }
        except Exception as e:
            result["prediction_sync_error"] = str(e)

        # 6. Database size
        try:
            db_size = await conn.fetchval(
                "SELECT pg_size_pretty(pg_database_size(current_database()))"
            )
            result["database_size"] = db_size
        except Exception as e:
            result["database_size_error"] = str(e)

    # 7. Scheduler latency
    try:
        import json as _json
        import urllib.request

        resp = urllib.request.urlopen(
            "http://127.0.0.1:8000/api/pipeline/scheduler-status", timeout=5
        )
        sched_status = _json.loads(resp.read().decode())
        # Average latency
        result["scheduler_latency_ms"] = sched_status.get("recorder_latencies", [0.0])
    except Exception:
        pass

    await pipeline_db.close()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(run_quality_check())
