import asyncio
import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline.db import pipeline_db


async def run_audit():
    connected = await pipeline_db.init_pool()
    if not connected:
        print(
            json.dumps({"connected": False, "error": "Could not connect to database"})
        )
        return

    report = {}
    tables = [
        "options_intelligence",
        "options_history",
        "strike_history",
        "wall_history",
        "pcr_history",
    ]

    async with pipeline_db.pool.acquire() as conn:
        for table in tables:
            table_stats = {
                "rows_today": 0,
                "duplicates": 0,
                "gaps": [],
                "missing_timestamps": 0,
            }

            # 1. Count rows today
            try:
                if table == "options_intelligence":
                    table_stats["rows_today"] = await conn.fetchval(f"""
                        SELECT COUNT(*) FROM {table} 
                        WHERE DATE(timestamp AT TIME ZONE 'Asia/Kolkata') = CURRENT_DATE
                    """)
                else:
                    table_stats["rows_today"] = await conn.fetchval(f"""
                        SELECT COUNT(*) FROM {table} 
                        WHERE date = CURRENT_DATE
                    """)
            except Exception as e:
                table_stats["rows_today_error"] = str(e)

            # 2. Count duplicates
            try:
                if table == "options_intelligence":
                    dup_count = await conn.fetchval(f"""
                        SELECT COUNT(*) FROM (
                            SELECT symbol, timestamp, COUNT(*) 
                            FROM {table} 
                            GROUP BY symbol, timestamp 
                            HAVING COUNT(*) > 1
                        ) AS sub
                    """)
                else:
                    dup_count = await conn.fetchval(f"""
                        SELECT COUNT(*) FROM (
                            SELECT symbol, date, expiry, COUNT(*) 
                            FROM {table} 
                            GROUP BY symbol, date, expiry 
                            HAVING COUNT(*) > 1
                        ) AS sub
                    """)
                table_stats["duplicates"] = dup_count if dup_count else 0
            except Exception as e:
                table_stats["duplicates_error"] = str(e)

            # 3. Detect gaps / missing timestamps
            try:
                if table == "options_intelligence":
                    # For options_intelligence, it updates frequently. Let's get timestamps for NIFTY
                    timestamps = await conn.fetch("""
                        SELECT timestamp FROM options_intelligence 
                        WHERE symbol = 'NIFTY' 
                        ORDER BY timestamp ASC
                    """)
                    if len(timestamps) > 1:
                        gaps = []
                        for i in range(len(timestamps) - 1):
                            diff = (
                                timestamps[i + 1]["timestamp"]
                                - timestamps[i]["timestamp"]
                            )
                            # If diff is greater than 10 minutes (600s), we consider it a gap
                            if diff.total_seconds() > 600:
                                gaps.append(
                                    {
                                        "after": timestamps[i]["timestamp"].isoformat(),
                                        "before": timestamps[i + 1][
                                            "timestamp"
                                        ].isoformat(),
                                        "duration_min": round(
                                            diff.total_seconds() / 60.0, 1
                                        ),
                                    }
                                )
                        table_stats["gaps"] = gaps[:5]  # show first 5 gaps
                        table_stats["missing_timestamps"] = len(gaps)
                else:
                    # Daily tables
                    dates = await conn.fetch(
                        f"SELECT DISTINCT date FROM {table} ORDER BY date ASC"
                    )
                    if len(dates) > 1:
                        gaps = []
                        for i in range(len(dates) - 1):
                            diff = dates[i + 1]["date"] - dates[i]["date"]
                            if diff.days > 1:
                                gaps.append(
                                    {
                                        "after": dates[i]["date"].isoformat(),
                                        "before": dates[i + 1]["date"].isoformat(),
                                        "duration_days": diff.days - 1,
                                    }
                                )
                        table_stats["gaps"] = gaps[:5]
                        table_stats["missing_timestamps"] = len(gaps)
            except Exception as e:
                table_stats["gaps_error"] = str(e)

            report[table] = table_stats

    await pipeline_db.close()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(run_audit())
