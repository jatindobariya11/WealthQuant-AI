"""
WealthQuant V9.1 — Alpha Discovery Engine Orchestrator
======================================================
Coordinates data loading, automated hypothesis discovery, statistical validation,
scoring, rejection filtering, report generation, and database archiving.

Operates in complete read-only isolation from production prediction models.
"""

import logging
import time
import uuid
from dataclasses import dataclass

import pandas as pd

from .alpha_filter import AlphaFilter
from .alpha_registry import AlphaRegistry
from .alpha_reporter import AlphaReporter
from .alpha_scorer import AlphaScorer
from .alpha_validator import AlphaValidator
from .data_loader import AlphaDataLoader
from .hypothesis_generator import HypothesisGenerator

logger = logging.getLogger("alpha.engine")


@dataclass
class AlphaEngineConfig:
    symbol: str = "NIFTY"
    interval: str = "1d"
    target_horizon_days: int = 5
    max_candidates: int = 30
    min_ic_threshold: float = 0.03
    min_health_score: float = 90.0
    seed: int = 42


class AlphaEngine:
    """
    Main Orchestrator for the WealthQuant Institutional Alpha Discovery Engine.
    """

    def __init__(self, pool=None, config: AlphaEngineConfig | None = None):
        self.pool = pool
        self.config = config or AlphaEngineConfig()

        self.data_loader = AlphaDataLoader(pool)
        self.generator = HypothesisGenerator(
            min_ic_threshold=self.config.min_ic_threshold
        )
        self.validator = AlphaValidator(seed=self.config.seed)
        self.scorer = AlphaScorer()
        self.filter = AlphaFilter(min_health_score=self.config.min_health_score)
        self.registry = AlphaRegistry(pool)
        self.reporter = AlphaReporter()

    async def run_discovery_cycle(self) -> dict:
        """
        Run full automated discovery cycle:
          1. Load aligned research dataset from DB
          2. Auto-generate candidate hypotheses
          3. Validate each hypothesis statistically
          4. Score candidate alpha (6 dimensions)
          5. Apply rejection gates
          6. Archive results in PostgreSQL
          7. Generate 5 institutional markdown reports
        """
        run_id = f"RUN_{uuid.uuid4().hex[:8].upper()}"
        start_time = time.time()
        logger.info(f"[AlphaEngine] Starting discovery cycle {run_id}...")

        # 1. Load data
        datasets = await self.data_loader.build_research_dataset(
            symbol=self.config.symbol, interval=self.config.interval
        )
        features_df = datasets.get("features", pd.DataFrame())
        target_series = features_df.get(f"ret_{self.config.target_horizon_days}d")

        if features_df.empty or target_series is None or target_series.dropna().empty:
            logger.warning("[AlphaEngine] Insufficient data to run discovery cycle")
            return {
                "run_id": run_id,
                "status": "skipped",
                "reason": "insufficient_data",
                "runtime_seconds": round(time.time() - start_time, 2),
            }

        # 2. Discover Hypotheses
        candidates = self.generator.generate_all(
            features_df=features_df,
            returns_series=target_series,
            target_horizon_days=self.config.target_horizon_days,
            max_candidates=self.config.max_candidates,
        )

        validations = {}
        scores = {}
        rejections = {}
        accepted = []

        existing_accepted = await self.registry.get_accepted_alphas()

        # 3. Validate, Score, Filter & Archive each candidate
        for c in candidates:
            hid = c["hypothesis_id"]
            feat_name = c["feature_name"]

            # Save hypothesis record
            await self.registry.save_hypothesis(c, run_id=run_id)

            if feat_name in features_df.columns:
                feat_series = features_df[feat_name]
            else:
                # Try evaluating custom formula safely if present
                try:
                    feat_series = features_df.eval(c["feature_formula"])
                except Exception:
                    feat_series = features_df.iloc[:, 0]

            # Validate
            val_res = self.validator.validate(feat_series, target_series)
            validations[hid] = val_res
            await self.registry.save_validation_result(hid, val_res)

            # Score
            score_obj = self.scorer.score(hid, val_res, existing_accepted)
            scores[hid] = score_obj
            await self.registry.save_score(score_obj)

            # Filter / Gate check
            score_dict = {"research_health_score": score_obj.research_health_score}
            rej_res = self.filter.evaluate(val_res, score_dict, existing_accepted)

            if rej_res.is_rejected:
                rejections[hid] = rej_res
                await self.registry.record_rejection(hid, rej_res)
            else:
                accepted.append(c)
                await self.registry.record_acceptance(
                    hid, score_obj.composite_score, val_res
                )

        elapsed = round(time.time() - start_time, 2)
        run_stats = {
            "run_id": run_id,
            "status": "complete",
            "symbol": self.config.symbol,
            "horizon": self.config.target_horizon_days,
            "n_candidates": len(candidates),
            "n_accepted": len(accepted),
            "n_rejected": len(rejections),
            "runtime_seconds": elapsed,
        }

        # 4. Generate Reports
        reports = self.reporter.generate_all_reports(
            run_stats=run_stats,
            candidates=candidates,
            validations=validations,
            scores=scores,
            rejections=rejections,
            accepted=accepted,
        )

        logger.info(
            f"[AlphaEngine] Cycle {run_id} complete in {elapsed}s: "
            f"{len(accepted)} accepted, {len(rejections)} rejected."
        )

        return {
            "run_stats": run_stats,
            "candidates_count": len(candidates),
            "accepted_count": len(accepted),
            "rejected_count": len(rejections),
            "reports_generated": list(reports.keys()),
        }
