import uuid
from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: int = Field(..., description="HTTP Status Code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Any] = Field(
        None, description="Additional context or validation errors"
    )


class ErrorResponse(BaseModel):
    success: bool = Field(False, description="Always false for errors")
    error: ErrorDetail
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class StandardResponse(BaseModel, Generic[T]):
    success: bool = Field(True, description="Always true for successful requests")
    data: T
    message: str = Field("", description="Optional success message")
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


# Pipeline Specific Response Models


class PipelineStatusResponse(BaseModel):
    status: str
    message: str


class PipelineEmergencyResponse(BaseModel):
    status: str
    message: str


class ProbabilityOutput(BaseModel):
    p_up: float
    p_down: float
    p_sideways: float
    expected_return: float
    expected_upside: float
    expected_downside: float
    expected_move_pct: float
    var_95: float
    cvar_95: float
    max_drawdown_prob: float
    tail_risk_score: float
    kelly_fraction: float
    suggested_position_size: float
    signal: str
    signal_confidence: float
    signal_edge: float
    calibration_quality: float
    prediction_horizon: str
    latency_ms: float
    stage_latencies: dict
    cached: bool = False
    prediction_meta: Optional[dict] = None


class AuthRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
