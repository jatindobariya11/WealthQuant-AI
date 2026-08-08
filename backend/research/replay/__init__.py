"""
WealthQuant V10.0 — Deterministic Market Replay & Simulation Engine
===================================================================
Package: backend/research/replay/

Completely isolated from production. Reconstructs historical market sessions
step-by-step with strict point-in-time temporal isolation (zero look-ahead bias).

Supported Timeframes: 5m, 15m, 30m, 1h, 1d
Performance Target: 1 trading day < 30 seconds, 1 month < 10 minutes
Determinism: 100% repeatable given identical random seeds.

DO NOT MODIFY: Bayesian Fusion, Ensemble, Stage 5 HMM, prediction pipeline, or production APIs.
"""

from .replay_db import ReplayDB
from .replay_engine import MarketReplayEngine, ReplayConfig, ReplaySessionResult
from .replay_reporter import ReplayReportGenerator
from .temporal_buffer import PointInTimeBuffer

__version__ = "10.0.0"
__all__ = [
    "MarketReplayEngine",
    "ReplayConfig",
    "ReplaySessionResult",
    "PointInTimeBuffer",
    "ReplayReportGenerator",
    "ReplayDB",
]
