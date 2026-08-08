"""
WealthQuant V9.2 — Incubation Platform FastAPI Router
======================================================
Exposes endpoints for querying incubation pipeline, advancing lifecycle stages,
inspecting decay alerts, and fetching governance reports.

Mounts at /api/incubation/* — completely isolated from production prediction endpoints.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from pipeline.db import pipeline_db

from .incubation_db import IncubationDB
from .incubation_engine import IncubationEngine
from .lifecycle_manager import AlphaLifecycleStage

router = APIRouter(prefix="/api/incubation", tags=["Alpha Incubation Platform"])


class AdvanceStageRequest(BaseModel):
    alpha_id: str
    target_stage: str
    metrics: dict[str, float] = {}


@router.on_event("startup")
async def _startup_incubation():
    if pipeline_db.pool is not None:
        try:
            db = IncubationDB(pipeline_db.pool)
            await db.create_tables()
        except Exception as e:
            print(f"[IncubationAPI] Table setup warning: {e}")


@router.get("/health")
async def get_incubation_health():
    """Check incubation platform status."""
    return {
        "status": "online",
        "platform_version": "9.2.0",
        "database": "connected" if pipeline_db.pool else "offline",
    }


@router.get("/pipeline")
async def list_incubation_pipeline():
    """List all active incubated alphas and their current lifecycle stage."""
    engine = IncubationEngine(pool=pipeline_db.pool)
    alphas = await engine.list_incubated_alphas()
    return {"incubated_alphas": alphas, "count": len(alphas)}


@router.post("/advance")
async def advance_alpha_stage(req: AdvanceStageRequest):
    """Attempt to advance an incubated alpha to the next lifecycle stage."""
    engine = IncubationEngine(pool=pipeline_db.pool)
    try:
        stage = AlphaLifecycleStage(req.target_stage)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Invalid lifecycle stage: {req.target_stage}"
        )

    success, reasons = await engine.advance_stage(req.alpha_id, stage, req.metrics)
    if not success:
        raise HTTPException(
            status_code=422,
            detail={"message": "Stage transition blocked", "reasons": reasons},
        )

    return {
        "status": "success",
        "alpha_id": req.alpha_id,
        "new_stage": req.target_stage,
    }


@router.post("/governance-cycle")
async def trigger_governance_cycle(background_tasks: BackgroundTasks):
    """Trigger a periodic governance audit and decay check cycle."""
    engine = IncubationEngine(pool=pipeline_db.pool)
    background_tasks.add_task(engine.run_governance_cycle)
    return {
        "status": "initiated",
        "message": "Governance audit cycle running in background",
    }
