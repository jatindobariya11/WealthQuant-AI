"""
WealthQuant Probabilistic AI Pipeline
======================================

10-stage pipeline for probabilistic stock market intelligence:

    Market Data → Hawkes Process → Kalman Filter → Particle Filter
    → Regime Detection → XGBoost Ensemble → Meta Learning
    → Bayesian Fusion → Probability Engine → LLM Analyst

Architecture: Statistical-first (NumPy/SciPy/Scikit-Learn/XGBoost).
Database: PostgreSQL for feature store, predictions, backtests.
LLM: Ollama + Qwen 7B for local analyst reports.
"""

__version__ = "1.0.0"

from pipeline.base import (
    AnalystReport,
    EnsembleOutput,
    FusionOutput,
    HawkesOutput,
    KalmanOutput,
    MarketSnapshot,
    MetaLearningOutput,
    ParticleOutput,
    PipelineResult,
    PipelineStage,
    ProbabilityOutput,
    QuantileForecast,
    RegimeOutput,
    TickEvent,
)

__all__ = [
    "PipelineStage",
    "PipelineResult",
    "MarketSnapshot",
    "TickEvent",
    "HawkesOutput",
    "KalmanOutput",
    "ParticleOutput",
    "RegimeOutput",
    "EnsembleOutput",
    "MetaLearningOutput",
    "FusionOutput",
    "ProbabilityOutput",
    "AnalystReport",
    "QuantileForecast",
]
