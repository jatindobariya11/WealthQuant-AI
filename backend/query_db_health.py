import asyncio
import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline.config import POSTGRES_CONFIG
from pipeline.db import pipeline_db


async def run_queries():
    connected = await pipeline_db.init_pool()
    if not connected:
        print(
            json.dumps({"connected": False, "error": "Could not connect to database"})
        )
        return

    result = {
        "connected": True,
        "connection_status": "healthy",
        "database": POSTGRES_CONFIG["database"],
        "host": POSTGRES_CONFIG["host"],
        "port": POSTGRES_CONFIG["port"],
        "tables": [],
        "total_rows": 0,
        "today_rows": 0,
        "largest_tables": [],
    }

    TABLES = [
        "predictions",
        "prediction_history",
        "prediction_results",
        "prediction_accuracy",
        "signal_explanations",
        "stage_contributions",
        "ablation_results",
        "regime_performance",
        "feature_drift",
        "alpha_leaderboard",
        "experiments",
        "walk_forward_results",
        "ohlcv_history",
        "feature_store",
        "regime_history",
        "model_accuracy",
        "backtests",
        "fii_dii",
        "options_intelligence",
        "options_history",
        "strike_history",
        "wall_history",
        "pcr_history",
        "feature_alpha_rankings",
    ]

    async with pipeline_db.pool.acquire() as conn:
        # 1. Check all tables row counts and today's new rows
        for table in TABLES:
            try:
                # Get total rows
                total = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")

                # Get today's rows
                today_count = 0

                # Determine how to filter today's rows based on table schema
                columns = [
                    r["column_name"]
                    for r in await conn.fetch(
                        """
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = $1
                """,
                        table,
                    )
                ]

                if "created_at" in columns:
                    today_count = await conn.fetchval(f"""
                        SELECT COUNT(*) FROM {table} 
                        WHERE DATE(created_at AT TIME ZONE 'Asia/Kolkata') = CURRENT_DATE
                    """)
                elif "timestamp" in columns:
                    today_count = await conn.fetchval(f"""
                        SELECT COUNT(*) FROM {table} 
                        WHERE DATE(timestamp AT TIME ZONE 'Asia/Kolkata') = CURRENT_DATE
                    """)
                elif "date" in columns:
                    # check if string or date type
                    sample_val = await conn.fetchval(
                        f"SELECT date FROM {table} LIMIT 1"
                    )
                    if isinstance(sample_val, str):
                        today_count = await conn.fetchval(f"""
                            SELECT COUNT(*) FROM {table} 
                            WHERE date = TO_CHAR(CURRENT_DATE, 'YYYY-MM-DD')
                        """)
                    else:
                        today_count = await conn.fetchval(f"""
                            SELECT COUNT(*) FROM {table} 
                            WHERE date = CURRENT_DATE
                        """)
                elif "evaluated_at" in columns:
                    today_count = await conn.fetchval(f"""
                        SELECT COUNT(*) FROM {table} 
                        WHERE DATE(evaluated_at AT TIME ZONE 'Asia/Kolkata') = CURRENT_DATE
                    """)

                result["tables"].append(
                    {"name": table, "rows": total, "added_today": today_count}
                )
                result["total_rows"] += total
                result["today_rows"] += today_count
            except Exception as e:
                # Table might not exist or failed
                result["tables"].append(
                    {"name": table, "rows": 0, "added_today": 0, "error": str(e)}
                )

        # 2. Get largest tables by disk usage
        try:
            largest = await conn.fetch("""
                SELECT relname AS table_name,
                       pg_total_relation_size(c.oid) AS total_bytes,
                       pg_size_pretty(pg_total_relation_size(c.oid)) AS pretty_size
                FROM pg_class c
                LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE nspname = 'public'
                  AND c.relkind = 'r'
                ORDER BY pg_total_relation_size(c.oid) DESC
                LIMIT 5;
            """)
            for row in largest:
                result["largest_tables"].append(
                    {
                        "table_name": row["table_name"],
                        "size_bytes": row["total_bytes"],
                        "pretty_size": row["pretty_size"],
                    }
                )
        except Exception as e:
            result["largest_tables_error"] = str(e)

    await pipeline_db.close()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(run_queries())
