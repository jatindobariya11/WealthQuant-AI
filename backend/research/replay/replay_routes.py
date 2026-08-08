"""
WealthQuant V10.0 — Replay Engine FastAPI Router
=================================================
Exposes endpoints for running deterministic market replays and inspecting session reports.
Mounts at /api/replay/* — completely isolated from production endpoints.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from pipeline.db import pipeline_db

from .replay_db import ReplayDB
from .replay_engine import MarketReplayEngine, ReplayConfig

router = APIRouter(prefix="/api/replay", tags=["Deterministic Market Replay Engine"])


class RunReplayRequest(BaseModel):
    symbol: str = "NIFTY"
    timeframe: str = "5m"  # 5m, 15m, 30m, 1h, 1d
    start_date: str = "2026-07-01"
    end_date: str = "2026-07-24"


@router.on_event("startup")
async def _startup_replay():
    if pipeline_db.pool is not None:
        try:
            db = ReplayDB(pipeline_db.pool)
            await db.create_tables()
        except Exception as e:
            print(f"[ReplayAPI] Table setup warning: {e}")


@router.get("/health")
async def get_replay_health():
    return {
        "status": "online",
        "engine_version": "10.0.0",
        "database": "connected" if pipeline_db.pool else "offline",
    }


@router.post("/run")
async def run_replay_session(req: RunReplayRequest):
    """Run a deterministic market replay session synchronously or as a task."""
    config = ReplayConfig(
        symbol=req.symbol,
        timeframe=req.timeframe,
        start_date=req.start_date,
        end_date=req.end_date,
    )
    engine = MarketReplayEngine(pool=pipeline_db.pool, config=config)
    res = await engine.run_replay_session()

    return {
        "status": "complete",
        "session_id": res.session_id,
        "symbol": res.symbol,
        "timeframe": res.timeframe,
        "candles_processed": res.processed_candles,
        "runtime_seconds": res.runtime_seconds,
        "is_deterministic": res.is_deterministic,
        "reports_generated": res.reports_generated,
    }
