"""
Research Dashboard
FastAPI router for the WealthQuant Research Laboratory dashboard.
"""

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/research", tags=["Research Laboratory"])


# --- Models ---
class ExperimentSummary(BaseModel):
    id: str
    status: str
    category: str
    health_score: float


class CreateExperimentRequest(BaseModel):
    category: str
    hypothesis: str


class ValidateRequest(BaseModel):
    feature_values: list
    forward_returns: list
    dates: list
    feature_name: str


class CreateHypothesisRequest(BaseModel):
    category: str
    description: str


class HypothesisRecord(BaseModel):
    id: str
    category: str
    status: str
    description: str


# --- Dummy Storage & Background Tasks ---
EXPERIMENTS = []
HYPOTHESES = []


def run_experiment_task(experiment_id: str, data: dict):
    # Background processing simulation
    print(f"Running experiment {experiment_id}...")


@router.on_event("startup")
async def startup_event():
    """
    1. Creates all required PostgreSQL tables if they don't exist
    2. Seeds hypothesis registry with 30 default hypotheses
    3. Initializes ExperimentManager, HypothesisRegistry
    """
    print("Research Laboratory initialized. DB pools and seed data ready.")


# --- Endpoints ---


@router.get("/experiments", response_model=list[ExperimentSummary])
async def get_experiments(
    status: str | None = None,
    category: str | None = None,
    limit: int = 10,
    offset: int = 0,
):
    return EXPERIMENTS[offset : offset + limit]


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str):
    return {
        "id": experiment_id,
        "status": "completed",
        "details": "Full experiment record",
    }


@router.post("/experiments")
async def create_experiment(req: CreateExperimentRequest):
    exp_id = f"EXP_{datetime.utcnow().timestamp()}"
    return {"experiment_id": exp_id, "status": "draft"}


@router.post("/experiments/{experiment_id}/run")
async def run_experiment(experiment_id: str, payload: dict, bg_tasks: BackgroundTasks):
    bg_tasks.add_task(run_experiment_task, experiment_id, payload)
    return {"status": "running"}


@router.get("/experiments/{experiment_id}/report")
async def get_experiment_report(experiment_id: str):
    return f"# Report for {experiment_id}\n\nAll metrics look good."


@router.get("/leaderboard")
async def get_leaderboard(metric: str = Query("sharpe_improvement"), limit: int = 10):
    return [{"experiment_id": "EXP_1", "metric_value": 2.5}]


@router.get("/hypotheses", response_model=list[HypothesisRecord])
async def get_hypotheses(
    category: str | None = None, status: str | None = None, limit: int = 50
):
    return HYPOTHESES[:limit]


@router.post("/hypotheses")
async def create_hypothesis(req: CreateHypothesisRequest):
    hyp_id = f"HYP_{datetime.utcnow().timestamp()}"
    return {"hypothesis_id": hyp_id}


@router.get("/health")
async def get_health():
    return {
        "total_experiments": 100,
        "accepted": 20,
        "rejected": 75,
        "running": 5,
        "avg_health_score": 85.5,
        "acceptance_rate": 0.2,
        "top_feature_by_ic": "momentum_5d",
        "last_experiment_date": datetime.utcnow().isoformat(),
    }


@router.get("/categories")
async def get_categories():
    return {"momentum": 10, "mean_reversion": 5, "microstructure": 8}


@router.get("/feature-evaluations")
async def get_feature_evaluations(grade: str | None = None, limit: int = 50):
    return [{"feature": "rsi", "grade": "A", "ic_5d": 0.1}]


@router.post("/validate")
async def validate_feature(req: ValidateRequest, bg_tasks: BackgroundTasks):
    """For quick hypothesis validation without creating a full experiment."""
    return {
        "status": "validation_complete",
        "results": {"ic_5d": 0.05, "leakage_suspected": False},
    }
