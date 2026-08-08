"""
WealthQuant V9.0 — Institutional Quant Research Laboratory
============================================================
Package: backend/research/

Completely isolated from the production prediction pipeline.
Does NOT modify: Stage5-HMM, Stage6-Ensemble, Stage7-Meta,
Stage8-BayesianFusion, or any existing PostgreSQL schema.

All research experiments are tracked, validated, and reproducible.
"""

from .experiment_manager import ExperimentManager, ExperimentRecord, ExperimentStatus
from .factor_lab import FactorLab, FactorReport
from .feature_lab import FeatureEvaluation, FeatureLab
from .hypothesis_registry import HypothesisRecord, HypothesisRegistry, ResearchCategory
from .performance_analyzer import PerformanceAnalyzer, PerformanceReport
from .report_generator import ReportGenerator
from .statistical_validation import (
    BootstrapResult,
    MonteCarloResult,
    StatisticalValidator,
    WalkForwardResult,
)

__version__ = "9.0.0"
__all__ = [
    "ExperimentManager",
    "ExperimentRecord",
    "ExperimentStatus",
    "HypothesisRegistry",
    "HypothesisRecord",
    "ResearchCategory",
    "StatisticalValidator",
    "WalkForwardResult",
    "MonteCarloResult",
    "BootstrapResult",
    "PerformanceAnalyzer",
    "PerformanceReport",
    "FeatureLab",
    "FeatureEvaluation",
    "FactorLab",
    "FactorReport",
    "ReportGenerator",
]
