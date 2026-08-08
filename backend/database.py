import json
import logging
import os

from pipeline.db import pipeline_db

logger = logging.getLogger("backend.database")

# Path to local cache file for offline fallback
FII_CACHE_PATH = os.path.join(os.path.dirname(__file__), "fii_cache.json")


def init_db():
    """
    No-op: tables are automatically initialized via pipeline_db in FastAPI lifespan.
    """
    logger.info(
        "[Database] Unification: schema is initialized via PostgreSQL / PipelineDB."
    )
    print("[Database] Schema initialized via PostgreSQL / PipelineDB.")


async def save_fii_dii_async(date_str: str, fii: float, dii: float) -> bool:
    """
    Asynchronously saves or updates FII/DII data in PostgreSQL.
    Falls back to writing to fii_cache.json if PostgreSQL is offline.
    """
    # 1. Try PostgreSQL if connected
    if pipeline_db.is_connected and pipeline_db.pool:
        try:
            async with pipeline_db.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO fii_dii (date, fii_net, dii_net)
                    VALUES ($1, $2, $3)
                    ON CONFLICT(date) DO UPDATE SET
                        fii_net = EXCLUDED.fii_net,
                        dii_net = EXCLUDED.dii_net,
                        timestamp = NOW()
                """,
                    date_str,
                    fii,
                    dii,
                )
            logger.info(
                f"[Database] Successfully saved FII/DII to PostgreSQL for {date_str}"
            )
            return True
        except Exception as e:
            logger.error(
                f"[Database] PostgreSQL error saving FII/DII: {e}. Falling back to cache file."
            )

    # 2. Fallback: Save to JSON file
    return _save_to_local_cache(date_str, fii, dii)


def save_fii_dii(date_str: str, fii: float, dii: float) -> bool:
    """
    Synchronous fallback wrapper.
    Only saves to local cache. Use save_fii_dii_async for database persistence.
    """
    return _save_to_local_cache(date_str, fii, dii)


async def get_fii_history_async(limit: int = 100) -> list[dict]:
    """
    Asynchronously fetches FII/DII history.
    Falls back to reading from fii_cache.json if PostgreSQL is offline.
    """
    if pipeline_db.is_connected and pipeline_db.pool:
        try:
            async with pipeline_db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT date, fii_net, dii_net
                    FROM fii_dii
                    ORDER BY date DESC
                    LIMIT $1
                """,
                    limit,
                )
            # Map database rows to list of dicts with chronological ordering (oldest first)
            # which matches expected prediction engine pattern
            result = [
                {"date": r["date"], "fii_net": r["fii_net"], "dii_net": r["dii_net"]}
                for r in rows
            ]
            return result[::-1]
        except Exception as e:
            logger.error(
                f"[Database] PostgreSQL error fetching history: {e}. Falling back to cache file."
            )

    # Fallback to local cache file
    return _read_from_local_cache(limit)


def get_fii_history(limit: int = 100) -> list[dict]:
    """
    Synchronous fallback wrapper.
    Only reads from local cache. Use get_fii_history_async for database reads.
    """
    return _read_from_local_cache(limit)


def get_fii_stats(days: int = 30) -> dict | None:
    """
    Calculates aggregate stats for the last N records.
    """
    history = get_fii_history(days)
    if not history:
        return None

    fii_sum = sum(row["fii_net"] for row in history)
    dii_sum = sum(row["dii_net"] for row in history)
    return {
        "days": len(history),
        "fii_total": round(fii_sum, 2),
        "dii_total": round(dii_sum, 2),
        "fii_avg": round(fii_sum / len(history), 2),
        "dii_avg": round(dii_sum / len(history), 2),
    }


# ────────── Helper Functions for Local JSON Cache ──────────


def _save_to_local_cache(date_str: str, fii: float, dii: float) -> bool:
    try:
        cache_data = []
        if os.path.exists(FII_CACHE_PATH):
            try:
                with open(FII_CACHE_PATH) as f:
                    cache_data = json.load(f)
            except (json.JSONDecodeError, OSError, ValueError) as e:
                logger.debug(
                    f"[Database] Local FII cache read failed, starting fresh: {e}"
                )
                cache_data = []

        # Remove existing record with the same date to avoid duplicates
        cache_data = [item for item in cache_data if item.get("date") != date_str]

        # Append new record (keep format consistent with existing cache files)
        cache_data.append({"date": date_str, "fii": fii, "dii": dii})

        # Keep only the last 200 records
        cache_data = cache_data[-200:]

        with open(FII_CACHE_PATH, "w") as f:
            json.dump(cache_data, f)
        logger.debug(f"[Database] Saved FII/DII to local cache for {date_str}")
        return True
    except Exception as e:
        logger.error(f"[Database] Error writing to local FII cache: {e}")
        return False


def _read_from_local_cache(limit: int) -> list[dict]:
    try:
        if not os.path.exists(FII_CACHE_PATH):
            return []

        with open(FII_CACHE_PATH) as f:
            data = json.load(f)

        # Map local cache format ("fii", "dii") to SQLite/PostgreSQL schema ("fii_net", "dii_net")
        result = []
        for item in data[-limit:]:
            result.append(
                {
                    "date": item.get("date"),
                    "fii_net": item.get("fii", 0.0),
                    "dii_net": item.get("dii", 0.0),
                }
            )
        return result
    except Exception as e:
        logger.error(f"[Database] Error reading local FII cache: {e}")
        return []
