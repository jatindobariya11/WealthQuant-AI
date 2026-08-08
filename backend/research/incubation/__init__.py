"""
WealthQuant V9.2 — Alpha Validation & Incubation Platform
==========================================================
Package: backend/research/incubation/

Sub-package of the Research Laboratory. Completely isolated from production.
Manages alpha lifecycle, governance, paper trading simulation, shadow mode monitoring,
decay detection, and production candidate sign-offs.

DO NOT MODIFY: Bayesian Fusion, Ensemble, Stage 5 HMM, prediction engine, production APIs.
"""

from .decay_detector import DecayAlert, DecayDetector
from .incubation_db import IncubationDB
from .incubation_engine import IncubationEngine
from .lifecycle_manager import AlphaLifecycleStage, ApprovalStatus, LifecycleManager
from .shadow_monitor import ShadowMonitor, ShadowPerformanceReport

__version__ = "9.2.0"
__all__ = [
    "IncubationEngine",
    "LifecycleManager",
    "AlphaLifecycleStage",
    "ApprovalStatus",
    "ShadowMonitor",
    "ShadowPerformanceReport",
    "DecayDetector",
    "DecayAlert",
    "IncubationDB",
]
