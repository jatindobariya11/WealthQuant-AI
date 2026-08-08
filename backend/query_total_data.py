import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ["PG_HOST"] = "127.0.0.1"
from pipeline.db import pipeline_db


async def main():
    await pipeline_db.init_pool()
    if not pipeline_db.is_connected:
        print("Failed to connect to database.")
        return

    async with pipeline_db.pool.acquire() as conn:
        tables = await conn.fetch(
            "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'"
        )
        total_rows = 0
        today_rows = 0
        stats = []

        for t in tables:
            tbl = t["tablename"]
            cnt = await conn.fetchval(f"SELECT COUNT(*) FROM {tbl}")
            total_rows += cnt

            t_today = 0
            cols = [
                r["column_name"]
                for r in await conn.fetch(
                    f"SELECT column_name FROM information_schema.columns WHERE table_name = '{tbl}'"
                )
            ]
            date_col = next(
                (c for c in cols if c in ["date", "timestamp", "created_at"]), None
            )
            if date_col:
                try:
                    t_today = await conn.fetchval(
                        f"SELECT COUNT(*) FROM {tbl} WHERE {date_col} >= CURRENT_DATE"
                    )
                    today_rows += t_today
                except Exception:
                    pass

            stats.append((tbl, cnt, t_today))

        stats.sort(key=lambda x: x[1], reverse=True)

        print("==================================================")
        print(f" TOTAL DATABASE ROWS: {total_rows:,}")
        print(f" TOTAL NEW ROWS TODAY: {today_rows:,}")
        print(f" TOTAL TABLES ACCESSIBLE: {len(tables)}")
        print("==================================================\n")
        print("BREAKDOWN BY TABLE:")
        for tbl, cnt, t_today in stats:
            print(f"  • {tbl:30s}: {cnt:7,} rows ({t_today:,} today)")

    await pipeline_db.close()


if __name__ == "__main__":
    asyncio.run(main())
