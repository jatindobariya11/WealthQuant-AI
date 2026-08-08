"""
Pipeline base types and abstract stage class.
All inter-stage data flows through these dataclasses.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

logger = logging.getLogger("pipeline")


# ─── Tick Events ──────────────────────────────────────────────────────


@dataclass
class TickEvent:
    """A discrete market event for Hawkes Process ingestion."""

    timestamp: float  # unix epoch seconds
    event_type: str  # 'price_jump', 'volume_spike', 'oi_change', 'sweep'
    magnitude: float  # absolute magnitude of the event
    direction: int  # +1 bullish, -1 bearish, 0 neutral
    metadata: dict = field(default_factory=dict)


# ─── Market Snapshot (Stage 1 output) ────────────────────────────────


@dataclass
class MarketSnapshot:
    """Normalized market data — output of Stage 1 Market Adapter."""

    symbol: str
    timestamp: datetime
    interval: str  # '1m', '5m', '15m', '1h', '1d'
    # Core price data
    ohlcv: pd.DataFrame = None  # columns: open, high, low, close, volume
    tick_events: list = field(default_factory=list)  # list[TickEvent]
    # Pre-computed indicators from existing base_indicators.py
    indicators: dict = field(default_factory=dict)  # RSI, MACD, BB, ATR, etc.
    # Options data
    options: dict = field(default_factory=dict)  # PCR, OI, max_pain, IV
    # Institutional data
    institutional: dict = field(default_factory=dict)  # FII/DII, sweep alerts
    # Global context
    global_context: dict = field(default_factory=dict)  # VIX, global indices
    # News
    news_sentiment: dict = field(default_factory=dict)
    # Sector info for GNN / cross-stock analysis
    sector_peers: list = field(default_factory=list)


# ─── Stage 2: Hawkes Process Output ──────────────────────────────────


@dataclass
class HawkesOutput:
    """Self-exciting point process output — event clustering detection."""

    current_intensity: float = 0.0  # λ(now)
    baseline_intensity: float = 0.0  # μ
    excitation_ratio: float = 1.0  # λ(now)/μ
    branching_ratio: float = 0.0  # α/β — criticality
    is_cascade: bool = False  # branching_ratio > 0.8
    cascade_probability: float = 0.0  # P(next event within Δt)
    event_clusters: list = field(default_factory=list)
    decay_halflife_seconds: float = 0.0  # ln(2)/β
    total_events: int = 0
    timestamp: datetime = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("timestamp", None)
        return d


# ─── Stage 3: Kalman Filter Output ───────────────────────────────────


@dataclass
class KalmanOutput:
    """Linear state estimation — smoothed price + hidden states."""

    filtered_price: float = 0.0
    price_uncertainty: float = 0.0  # ±1σ
    estimated_velocity: float = 0.0  # price momentum (₹/bar)
    estimated_acceleration: float = 0.0  # momentum change rate
    estimated_volatility: float = 0.0  # hidden volatility state
    innovation: float = 0.0  # prediction error
    innovation_zscore: float = 0.0  # normalized surprise
    kalman_gain: Any = None  # np.ndarray
    state_covariance: Any = None  # np.ndarray (P matrix)
    smoothed_series: Any = None  # pd.Series
    timestamp: datetime = None

    def to_dict(self) -> dict:
        d = {
            "filtered_price": self.filtered_price,
            "price_uncertainty": self.price_uncertainty,
            "estimated_velocity": self.estimated_velocity,
            "estimated_acceleration": self.estimated_acceleration,
            "estimated_volatility": self.estimated_volatility,
            "innovation": self.innovation,
            "innovation_zscore": self.innovation_zscore,
        }
        if self.smoothed_series is not None:
            d["smoothed_prices"] = self.smoothed_series.tail(20).tolist()
        return d


# ─── Stage 4: Particle Filter Output ─────────────────────────────────


@dataclass
class ParticleOutput:
    """Non-linear state estimation — full distribution over price."""

    mean_price: float = 0.0
    median_price: float = 0.0
    std_price: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0
    percentiles: dict = field(default_factory=dict)  # {5,10,25,50,75,90,95}
    effective_sample_size: float = 0.0
    bimodality_score: float = 0.0  # 0-1
    tail_risk_left: float = 0.0  # P(crash)
    tail_risk_right: float = 0.0  # P(breakout)
    price_distribution: Any = None  # np.ndarray of particles
    weights: Any = None  # np.ndarray of weights
    timestamp: datetime = None

    def to_dict(self) -> dict:
        return {
            "mean_price": self.mean_price,
            "median_price": self.median_price,
            "std_price": self.std_price,
            "skewness": round(self.skewness, 4),
            "kurtosis": round(self.kurtosis, 4),
            "percentiles": self.percentiles,
            "effective_sample_size": round(self.effective_sample_size, 1),
            "bimodality_score": round(self.bimodality_score, 4),
            "tail_risk_left": round(self.tail_risk_left, 4),
            "tail_risk_right": round(self.tail_risk_right, 4),
        }


# ─── Stage 5: Regime Detection Output ────────────────────────────────

REGIME_TYPES = [
    "TRENDING_BULL",
    "TRENDING_BEAR",
    "MEAN_REVERTING",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "TRANSITION",
]


@dataclass
class RegimeOutput:
    """Market regime classification with transition detection."""

    current_regime: str = "TRANSITION"
    regime_probabilities: dict = field(default_factory=dict)
    regime_confidence: float = 0.0
    regime_duration_bars: int = 0
    transition_probability: float = 0.0
    transition_target: str = ""
    regime_history: list = field(default_factory=list)
    changepoint_score: float = 0.0  # BOCPD score
    features_used: dict = field(default_factory=dict)
    timestamp: datetime = None

    def to_dict(self) -> dict:
        return {
            "current_regime": self.current_regime,
            "regime_probabilities": self.regime_probabilities,
            "regime_confidence": round(self.regime_confidence, 4),
            "regime_duration_bars": self.regime_duration_bars,
            "transition_probability": round(self.transition_probability, 4),
            "transition_target": self.transition_target,
            "regime_history": self.regime_history[-10:],  # last 10
            "changepoint_score": round(self.changepoint_score, 4),
            "features_used": self.features_used,
        }


# ─── Stage 5.5: Institutional Options Intelligence Output ────────────


@dataclass
class InstitutionalOutput:
    """Institutional Options Intelligence stage output."""

    forecast: float = 0.0  # -1.0 to 1.0 (directional expected return)
    confidence: float = 0.0  # 0.0 to 1.0
    positioning_strength: float = 0.0  # 0.0 to 100.0

    # Calculated Metrics
    open_interest: float = 0.0
    oi_change: float = 0.0
    volume: float = 0.0
    volume_oi_ratio: float = 0.0
    pcr: float = 1.0
    atm_iv: float = 0.15
    oi_velocity: float = 0.0
    oi_momentum: float = 0.0
    pcr_momentum: float = 0.0
    strike_migration: float = 0.0
    volume_oi_momentum: float = 0.0
    call_wall: float = 0.0
    put_wall: float = 0.0
    support_strength: float = 0.0
    resistance_strength: float = 0.0
    gamma_pressure: float = 0.0
    dealer_pressure: float = 0.0

    # Scores (0 to 100)
    bullish_score: float = 0.0
    bearish_score: float = 0.0
    neutral_score: float = 0.0

    timestamp: datetime = None

    def to_dict(self) -> dict:
        d = {
            "forecast": round(self.forecast, 6),
            "confidence": round(self.confidence, 4),
            "positioning_strength": round(self.positioning_strength, 2),
            "open_interest": self.open_interest,
            "oi_change": self.oi_change,
            "volume": self.volume,
            "volume_oi_ratio": round(self.volume_oi_ratio, 4),
            "pcr": round(self.pcr, 4),
            "atm_iv": round(self.atm_iv, 4),
            "oi_velocity": round(self.oi_velocity, 2),
            "oi_momentum": round(self.oi_momentum, 2),
            "pcr_momentum": round(self.pcr_momentum, 4),
            "strike_migration": round(self.strike_migration, 2),
            "volume_oi_momentum": round(self.volume_oi_momentum, 4),
            "call_wall": self.call_wall,
            "put_wall": self.put_wall,
            "support_strength": self.support_strength,
            "resistance_strength": self.resistance_strength,
            "gamma_pressure": round(self.gamma_pressure, 4),
            "dealer_pressure": round(self.dealer_pressure, 4),
            "bullish_score": round(self.bullish_score, 2),
            "bearish_score": round(self.bearish_score, 2),
            "neutral_score": round(self.neutral_score, 2),
        }
        return d


# ─── Stage 6: Ensemble Predictor Output ──────────────────────────────


@dataclass
class QuantileForecast:
    """Quantile prediction for a single horizon."""

    horizon: int = 1  # bars ahead
    q10: float = 0.0
    q25: float = 0.0
    q50: float = 0.0  # median forecast
    q75: float = 0.0
    q90: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EnsembleOutput:
    """XGBoost + RF + GBM ensemble prediction output."""

    forecasts: dict = field(default_factory=dict)  # {horizon: QuantileForecast}
    feature_importance: dict = field(default_factory=dict)
    model_contributions: dict = field(default_factory=dict)  # weight per sub-model
    predicted_direction: int = 0  # +1, 0, -1
    predicted_return: float = 0.0
    prediction_interval_width: float = 0.0
    model_confidence: float = 0.0
    timestamp: datetime = None

    def to_dict(self) -> dict:
        return {
            "forecasts": {
                k: v.to_dict() if hasattr(v, "to_dict") else v
                for k, v in self.forecasts.items()
            },
            "feature_importance": dict(
                sorted(self.feature_importance.items(), key=lambda x: -x[1])[:15]
            ),
            "model_contributions": self.model_contributions,
            "predicted_direction": self.predicted_direction,
            "predicted_return": round(self.predicted_return, 6),
            "prediction_interval_width": round(self.prediction_interval_width, 6),
            "model_confidence": round(self.model_confidence, 4),
        }


# ─── Stage 7: Meta-Learning Output ───────────────────────────────────


@dataclass
class MetaLearningOutput:
    """Regime-conditioned model selection and adaptation."""

    adaptation_status: str = "STABLE"  # STABLE / ADAPTING / ADAPTED
    adaptation_progress: float = 0.0  # 0-1
    regime_model_active: str = ""  # which regime model selected
    bars_since_adaptation: int = 0
    confidence_in_adaptation: float = 0.0
    adapted_forecasts: dict = field(default_factory=dict)
    adaptation_improvement: float = 0.0  # % improvement
    selected_models: list = field(default_factory=list)
    timestamp: datetime = None

    def to_dict(self) -> dict:
        return {
            "adaptation_status": self.adaptation_status,
            "adaptation_progress": round(self.adaptation_progress, 4),
            "regime_model_active": self.regime_model_active,
            "bars_since_adaptation": self.bars_since_adaptation,
            "confidence_in_adaptation": round(self.confidence_in_adaptation, 4),
            "adaptation_improvement": round(self.adaptation_improvement, 4),
            "selected_models": self.selected_models,
        }


# ─── Stage 8: Bayesian Fusion Output ─────────────────────────────────


@dataclass
class FusionOutput:
    """Bayesian model combination — fused probability distribution."""

    fused_mean: float = 0.0
    fused_std: float = 0.0
    fused_skew: float = 0.0
    model_weights: dict = field(default_factory=dict)
    model_agreement: float = 0.0  # 0-1
    conflict_alert: bool = False
    dominant_model: str = ""
    regime_weight_profile: dict = field(default_factory=dict)
    information_ratio: float = 0.0
    historical_accuracy: dict = field(default_factory=dict)
    fused_distribution: Any = None  # np.ndarray (discretized PDF)
    return_bins: Any = None  # np.ndarray (bin edges)
    timestamp: datetime = None

    def to_dict(self) -> dict:
        d = {
            "fused_mean": round(self.fused_mean, 6),
            "fused_std": round(self.fused_std, 6),
            "fused_skew": round(self.fused_skew, 4),
            "model_weights": {k: round(v, 4) for k, v in self.model_weights.items()},
            "model_agreement": round(self.model_agreement, 4),
            "conflict_alert": self.conflict_alert,
            "dominant_model": self.dominant_model,
            "regime_weight_profile": self.regime_weight_profile,
            "information_ratio": round(self.information_ratio, 4),
        }
        # Include distribution histogram for frontend charting
        if self.fused_distribution is not None and self.return_bins is not None:
            d["distribution_histogram"] = {
                "bins": self.return_bins.tolist(),
                "density": self.fused_distribution.tolist(),
            }
        return d


# ─── Stage 9: Probability Engine Output ──────────────────────────────


@dataclass
class ProbabilityOutput:
    """Final calibrated probabilities + trading signal."""

    # Directional
    p_up: float = 0.0
    p_down: float = 0.0
    p_sideways: float = 0.0
    # Magnitude
    expected_return: float = 0.0
    expected_upside: float = 0.0
    expected_downside: float = 0.0
    expected_move_pct: float = 0.0
    # Risk
    var_95: float = 0.0  # 95% Value at Risk
    cvar_95: float = 0.0  # Conditional VaR
    max_drawdown_prob: float = 0.0
    tail_risk_score: float = 0.0  # 0-100
    # Position sizing
    kelly_fraction: float = 0.0
    suggested_position_size: float = 0.0  # half-Kelly
    # Signal
    signal: str = "NEUTRAL"
    signal_confidence: float = 0.0
    signal_edge: float = 0.0
    # Calibration
    calibration_quality: float = 0.0
    prediction_horizon: str = "1D"
    timestamp: datetime = None

    def to_dict(self) -> dict:
        return {
            "p_up": round(self.p_up, 4),
            "p_down": round(self.p_down, 4),
            "p_sideways": round(self.p_sideways, 4),
            "expected_return": round(self.expected_return, 6),
            "expected_upside": round(self.expected_upside, 6),
            "expected_downside": round(self.expected_downside, 6),
            "expected_move_pct": round(self.expected_move_pct, 4),
            "var_95": round(self.var_95, 6),
            "cvar_95": round(self.cvar_95, 6),
            "max_drawdown_prob": round(self.max_drawdown_prob, 4),
            "tail_risk_score": round(self.tail_risk_score, 2),
            "kelly_fraction": round(self.kelly_fraction, 4),
            "suggested_position_size": round(self.suggested_position_size, 4),
            "signal": self.signal,
            "signal_confidence": round(self.signal_confidence, 4),
            "signal_edge": round(self.signal_edge, 6),
            "calibration_quality": round(self.calibration_quality, 4),
            "prediction_horizon": self.prediction_horizon,
        }


# ─── Stage 10: LLM Analyst Output ────────────────────────────────────


@dataclass
class AnalystReport:
    """Structured analyst report from LLM."""

    headline: str = ""
    summary: str = ""
    conviction_level: str = "LOW"  # HIGH / MEDIUM / LOW
    thesis: str = ""
    key_drivers: list = field(default_factory=list)
    contrarian_risks: list = field(default_factory=list)
    bull_case: dict = field(default_factory=dict)
    base_case: dict = field(default_factory=dict)
    bear_case: dict = field(default_factory=dict)
    recommended_action: str = ""
    entry_zone: str = ""
    stop_loss: str = ""
    targets: list = field(default_factory=list)
    timeframe: str = ""
    position_sizing: str = ""
    risk_warnings: list = field(default_factory=list)
    confidence_caveats: list = field(default_factory=list)
    timestamp: datetime = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("timestamp", None)
        return d


# ─── Full Pipeline Result ────────────────────────────────────────────


@dataclass
class PipelineResult:
    """Complete output from the 10-stage pipeline."""

    symbol: str = ""
    timestamp: datetime = None
    interval: str = "15m"
    # Stage outputs
    hawkes: HawkesOutput = None
    kalman: KalmanOutput = None
    particle: ParticleOutput = None
    regime: RegimeOutput = None
    institutional: InstitutionalOutput = None
    ensemble: EnsembleOutput = None
    meta_learning: MetaLearningOutput = None
    fusion: FusionOutput = None
    probabilities: ProbabilityOutput = None
    analyst_report: AnalystReport = None
    # Metadata
    latency_ms: float = 0.0
    stage_latencies: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)
    pipeline_version: str = "1.0.0"

    def to_dict(self) -> dict:
        result = {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "interval": self.interval,
            "pipeline_version": self.pipeline_version,
            "latency_ms": round(self.latency_ms, 1),
            "stage_latencies": {
                k: round(v, 1) for k, v in self.stage_latencies.items()
            },
            "errors": self.errors,
            "stages": {},
        }
        for stage_name in [
            "hawkes",
            "kalman",
            "particle",
            "regime",
            "institutional",
            "ensemble",
            "meta_learning",
            "fusion",
            "probabilities",
            "analyst_report",
        ]:
            stage_obj = getattr(self, stage_name, None)
            if stage_obj is not None and hasattr(stage_obj, "to_dict"):
                result["stages"][stage_name] = stage_obj.to_dict()
            elif stage_obj is not None:
                result["stages"][stage_name] = {"status": "completed"}
            else:
                result["stages"][stage_name] = None
        return result


# ─── Abstract Pipeline Stage ─────────────────────────────────────────


class PipelineStage(ABC):
    """Abstract base class for all pipeline stages.

    Every stage must implement:
      - name: str property identifying the stage
      - process(*args, **kwargs): run the stage computation
    """

    def __init__(self):
        self._logger = logging.getLogger(f"pipeline.{self.name}")

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique stage identifier, e.g. 'hawkes', 'kalman'."""
        ...

    @abstractmethod
    def process(self, *args, **kwargs):
        """Execute the stage. Signature varies per stage."""
        ...

    def health_check(self) -> dict:
        """Return stage health status."""
        return {"stage": self.name, "status": "ok"}

    def timed_process(self, *args, **kwargs):
        """Run process() with timing instrumentation."""
        t0 = time.perf_counter()
        try:
            result = self.process(*args, **kwargs)
            elapsed = (time.perf_counter() - t0) * 1000
            self._logger.info(f"Stage [{self.name}] completed in {elapsed:.1f}ms")
            return result, elapsed
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            self._logger.error(f"Stage [{self.name}] failed after {elapsed:.1f}ms: {e}")
            raise
