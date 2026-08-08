"""
WealthQuant V9.1 — Alpha Discovery Engine
==========================================
Package: backend/research/alpha/

Sub-package of the Research Laboratory. Completely isolated from production.
Automatically discovers, tests, validates, scores, and archives alpha.

Architecture:
  data_loader.py          → Load all historical inputs from PostgreSQL
  hypothesis_generator.py → Automated hypothesis discovery (not hardcoded)
  alpha_validator.py      → Full statistical validation pipeline
  alpha_scorer.py         → 6-dimension alpha scoring (0-100)
  alpha_filter.py         → Automatic rejection logic
  alpha_registry.py       → PostgreSQL persistence and querying
  alpha_reporter.py       → Auto-generate 5 research reports
  alpha_engine.py         → Main orchestrator
  alpha_routes.py         → FastAPI /api/alpha/* endpoints
  db_schema.py            → PostgreSQL table creation

DO NOT MODIFY: Bayesian Fusion, Ensemble, HMM, prediction pipeline.
"""

from .alpha_engine import AlphaEngine, AlphaEngineConfig
from .alpha_filter import AlphaFilter, RejectionCategory, RejectionResult
from .alpha_registry import AlphaRecord, AlphaRegistry, AlphaStatus
from .alpha_scorer import AlphaScore, AlphaScorer

__version__ = "9.1.0"
__all__ = [
    "AlphaEngine",
    "AlphaEngineConfig",
    "AlphaRegistry",
    "AlphaRecord",
    "AlphaStatus",
    "AlphaScorer",
    "AlphaScore",
    "AlphaFilter",
    "RejectionResult",
    "RejectionCategory",
]
