"""
WealthQuant V9.1 — Alpha Discovery Engine: FastAPI Router
=========================================================
Exposes isolated endpoints for triggering discovery cycles, querying candidate alpha,
retrieving leaderboard entries, and inspecting rejection logs.

Mounts at /api/alpha/* — completely separate from main production prediction endpoints.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from pipeline.db import pipeline_db

from .alpha_engine import AlphaEngine, AlphaEngineConfig
from .db_schema import create_alpha_tables, get_alpha_db_stats

router = APIRouter(prefix="/api/alpha", tags=["Alpha Discovery Engine"])


class TriggerDiscoveryRequest(BaseModel):
    symbol: str = "NIFTY"
    interval: str = "1d"
    target_horizon_days: int = 5
    max_candidates: int = 30
    min_health_score: float = 90.0


@router.on_event("startup")
async def _startup_alpha():
    """Ensure PostgreSQL alpha tables exist on startup."""
    if pipeline_db.pool is not None:
        try:
            await create_alpha_tables(pipeline_db.pool)
        except Exception as e:
            print(f"[AlphaAPI] Table setup warning: {e}")


@router.get("/health")
async def get_alpha_health():
    """Check Alpha Engine database and system health."""
    stats = (
        await get_alpha_db_stats(pipeline_db.pool)
        if pipeline_db.pool
        else {"status": "offline"}
    )
    return {"status": "online", "engine_version": "9.1.0", "database": stats}


@router.post("/run")
async def trigger_alpha_discovery(
    req: TriggerDiscoveryRequest, background_tasks: BackgroundTasks
):
    """Trigger an asynchronous alpha discovery run."""
    config = AlphaEngineConfig(
        symbol=req.symbol,
        interval=req.interval,
        target_horizon_days=req.target_horizon_days,
        max_candidates=req.max_candidates,
        min_health_score=req.min_health_score,
    )
    engine = AlphaEngine(pool=pipeline_db.pool, config=config)

    # Execute discovery
    background_tasks.add_task(engine.run_discovery_cycle)

    return {
        "status": "started",
        "message": f"Alpha discovery cycle initiated for {req.symbol} ({req.target_horizon_days}d horizon)",
        "config": req.dict(),
    }


@router.get("/leaderboard")
async def get_alpha_leaderboard():
    """Get accepted alpha features ranked by composite score."""
    if pipeline_db.pool is None:
        return {"leaderboard": [], "status": "db_offline"}

    query = """
        SELECT h.hypothesis_id, h.title, h.feature_name, h.feature_category,
               l.composite_score, l.ic_5d, l.icir, l.mc_pvalue, l.boot_ic_lower,
               l.leakage_status, l.accepted_at
        FROM alpha_leaderboard l
        JOIN alpha_hypotheses h ON l.hypothesis_id = h.hypothesis_id
        ORDER BY l.composite_score DESC;
    """
    try:
        async with pipeline_db.pool.acquire() as conn:
            rows = await conn.fetch(query)
        return {"leaderboard": [dict(r) for r in rows], "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rejected")
async def get_rejected_alpha(limit: int = 50):
    """Get rejected hypotheses audit log with rejection categories."""
    if pipeline_db.pool is None:
        return {"rejected": [], "status": "db_offline"}

    query = """
        SELECT r.*, h.title, h.feature_name, h.feature_category
        FROM alpha_rejected r
        JOIN alpha_hypotheses h ON r.hypothesis_id = h.hypothesis_id
        ORDER BY r.rejected_at DESC
        LIMIT $1;
    """
    try:
        async with pipeline_db.pool.acquire() as conn:
            rows = await conn.fetch(query, limit)
        return {"rejected": [dict(r) for r in rows], "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
