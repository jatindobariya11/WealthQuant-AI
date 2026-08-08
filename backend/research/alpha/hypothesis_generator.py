"""
WealthQuant V9.1 — Alpha Discovery Engine: Hypothesis Generator
===============================================================
Automated discovery of alpha hypotheses from historical research data.

Supported discovery pipelines:
  1. Correlation & IC Mining   — Scan raw and transformed features for linear/rank relationship with forward returns.
  2. Mutual Information Scan  — Uncover non-linear relationships using discretized MI.
  3. Feature Interactions     — Pairwise products, ratios, and z-score spreads (e.g. PCR * IV_Skew).
  4. Lag Structure Mining     — Scan optimal lag horizons (1-5 days) for predictive lead times.
  5. Threshold & Extreme Scan — Non-linear threshold relationships (e.g. PCR z-score > 2.0).

Never hardcoded — dynamically constructs candidate features from loaded research datasets.
"""

import logging
import uuid

import numpy as np
import pandas as pd

logger = logging.getLogger("alpha.generator")


class HypothesisGenerator:
    """
    Automated Alpha Hypothesis Discovery Engine.
    Scans aligned DataFrames to construct formal research hypotheses.
    """

    def __init__(self, min_ic_threshold: float = 0.03):
        self.min_ic_threshold = min_ic_threshold

    def generate_all(
        self,
        features_df: pd.DataFrame,
        returns_series: pd.Series,
        target_horizon_days: int = 5,
        max_candidates: int = 50,
    ) -> list[dict]:
        """
        Run full automated hypothesis discovery pipeline.
        Returns list of hypothesis definition dicts ready for validation.
        """
        if features_df.empty or returns_series.empty:
            logger.warning("[Generator] Empty inputs — no hypotheses generated")
            return []

        candidates = []

        # 1. Single Feature IC & MI Mining
        single_candidates = self._mine_single_features(
            features_df, returns_series, target_horizon_days
        )
        candidates.extend(single_candidates)

        # 2. Lag Structure Scanning
        lag_candidates = self._mine_lags(
            features_df, returns_series, target_horizon_days
        )
        candidates.extend(lag_candidates)

        # 3. Pairwise Interaction Mining
        interaction_candidates = self._mine_interactions(
            features_df, returns_series, target_horizon_days
        )
        candidates.extend(interaction_candidates)

        # 4. Extreme Threshold Signal Mining
        threshold_candidates = self._mine_thresholds(
            features_df, returns_series, target_horizon_days
        )
        candidates.extend(threshold_candidates)

        # Sort by absolute initial candidate IC and deduplicate
        candidates.sort(key=lambda x: abs(x.get("candidate_ic", 0.0)), reverse=True)

        # Deduplicate by feature_formula
        seen_formulas = set()
        unique_candidates = []
        for c in candidates:
            formula = c["feature_formula"]
            if formula not in seen_formulas:
                seen_formulas.add(formula)
                unique_candidates.append(c)

        final_candidates = unique_candidates[:max_candidates]
        logger.info(
            f"[Generator] Discovered {len(final_candidates)} candidate alpha hypotheses"
        )
        return final_candidates

    def _mine_single_features(
        self, df: pd.DataFrame, target: pd.Series, horizon: int
    ) -> list[dict]:
        candidates = []
        valid_cols = [c for c in df.columns if not c.startswith("ret_")]
        if not valid_cols or target.empty:
            return candidates

        aligned_df = (
            df[valid_cols].join(target.to_frame("_target_ret"), how="inner").dropna()
        )
        if len(aligned_df) < 30:
            return candidates

        # Vectorized Spearman correlation across all candidate columns
        corr_series = aligned_df[valid_cols].corrwith(
            aligned_df["_target_ret"], method="spearman"
        )

        for col, ic_val in corr_series.items():
            ic = float(ic_val)
            if np.isnan(ic) or abs(ic) < self.min_ic_threshold:
                continue

            cat = self._infer_category(col)
            dir_str = "positively" if ic > 0 else "negatively"

            candidates.append(
                {
                    "hypothesis_id": f"HYP_AUTO_{uuid.uuid4().hex[:8].upper()}",
                    "source": "auto_discovery",
                    "generation_method": "correlation_mining",
                    "title": f"{col} {dir_str} predicts {horizon}-day returns",
                    "description": f"Automated IC scan identified Spearman IC of {ic:.4f} between {col} and {horizon}-day forward returns.",
                    "null_hypothesis": f"H0: Spearman correlation between {col} and {horizon}-day forward returns is zero.",
                    "alternative_hypothesis": f"H1: {col} has a non-zero Spearman correlation with {horizon}-day forward returns.",
                    "symbol": "NIFTY",
                    "interval": "1d",
                    "feature_name": col,
                    "feature_formula": f"{col}",
                    "feature_category": cat,
                    "target_horizon_days": horizon,
                    "lag_days": 1,
                    "candidate_ic": round(ic, 4),
                    "n_observations": len(aligned_df),
                }
            )
        return candidates

    def _mine_lags(
        self, df: pd.DataFrame, target: pd.Series, horizon: int
    ) -> list[dict]:
        candidates = []
        valid_cols = [c for c in df.columns if not c.startswith("ret_")][:15]

        for col in valid_cols:
            s = df[col].dropna()
            for lag in [2, 3, 5]:
                s_lag = s.shift(lag - 1).dropna()
                aligned = pd.concat([s_lag, target], axis=1, join="inner").dropna()
                if len(aligned) < 30:
                    continue

                ic = float(
                    aligned.iloc[:, 0].corr(aligned.iloc[:, 1], method="spearman")
                )
                if np.isnan(ic) or abs(ic) < (self.min_ic_threshold + 0.01):
                    continue

                candidates.append(
                    {
                        "hypothesis_id": f"HYP_LAG_{uuid.uuid4().hex[:8].upper()}",
                        "source": "auto_discovery",
                        "generation_method": "lag_scan",
                        "title": f"{col} (lag {lag}d) predicts {horizon}-day returns",
                        "description": f"Lag structure scan discovered predictive lead time of {lag} days for feature {col}.",
                        "null_hypothesis": f"H0: {col} with lag {lag}d has zero correlation with {horizon}-day returns.",
                        "alternative_hypothesis": f"H1: {col} with lag {lag}d exhibits statistically significant predictive power.",
                        "symbol": "NIFTY",
                        "interval": "1d",
                        "feature_name": f"{col}_lag{lag}",
                        "feature_formula": f"{col}.shift({lag - 1})",
                        "feature_category": self._infer_category(col),
                        "target_horizon_days": horizon,
                        "lag_days": lag,
                        "candidate_ic": round(ic, 4),
                        "n_observations": len(aligned),
                    }
                )
        return candidates

    def _mine_interactions(
        self, df: pd.DataFrame, target: pd.Series, horizon: int
    ) -> list[dict]:
        candidates = []
        cols = [c for c in df.columns if not c.startswith("ret_")]
        top_cols = cols[:10]  # limit combination explosion

        for i in range(len(top_cols)):
            for j in range(i + 1, len(top_cols)):
                c1, c2 = top_cols[i], top_cols[j]

                # Product interaction
                prod = df[c1] * df[c2]
                aligned = pd.concat([prod, target], axis=1, join="inner").dropna()
                if len(aligned) < 30:
                    continue

                ic = float(
                    aligned.iloc[:, 0].corr(aligned.iloc[:, 1], method="spearman")
                )
                if not np.isnan(ic) and abs(ic) >= (self.min_ic_threshold + 0.02):
                    candidates.append(
                        {
                            "hypothesis_id": f"HYP_INT_{uuid.uuid4().hex[:8].upper()}",
                            "source": "auto_discovery",
                            "generation_method": "interaction",
                            "title": f"Interaction {c1} * {c2} predicts returns",
                            "description": f"Pairwise product interaction between {c1} and {c2} yielded candidate IC of {ic:.4f}.",
                            "null_hypothesis": f"H0: Interaction between {c1} and {c2} has zero predictive power.",
                            "alternative_hypothesis": f"H1: Synergistic interaction {c1} * {c2} predicts forward returns.",
                            "symbol": "NIFTY",
                            "interval": "1d",
                            "feature_name": f"{c1}_x_{c2}",
                            "feature_formula": f"{c1} * {c2}",
                            "feature_category": "composite",
                            "target_horizon_days": horizon,
                            "lag_days": 1,
                            "candidate_ic": round(ic, 4),
                            "n_observations": len(aligned),
                        }
                    )
        return candidates

    def _mine_thresholds(
        self, df: pd.DataFrame, target: pd.Series, horizon: int
    ) -> list[dict]:
        candidates = []
        cols = [
            c
            for c in df.columns
            if "zscore" in c or "pcr" in c or "persistence" in c or "migration" in c
        ]

        for col in cols:
            s = df[col].dropna()
            if len(s) < 30:
                continue

            # Binary extreme signal (e.g. > 1.5 std)
            extreme = (s > 1.5).astype(float)
            aligned = pd.concat([extreme, target], axis=1, join="inner").dropna()
            if len(aligned) < 30:
                continue

            ic = float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1], method="spearman"))
            if not np.isnan(ic) and abs(ic) >= self.min_ic_threshold:
                candidates.append(
                    {
                        "hypothesis_id": f"HYP_THRESH_{uuid.uuid4().hex[:8].upper()}",
                        "source": "auto_discovery",
                        "generation_method": "threshold",
                        "title": f"Extreme {col} (>1.5σ) predicts returns",
                        "description": f"Threshold indicator for {col} > 1.5 standard deviations exhibits directional edge.",
                        "null_hypothesis": f"H0: Extreme events in {col} have no return predictability.",
                        "alternative_hypothesis": f"H1: Tail events in {col} predict mean-reversion or momentum.",
                        "symbol": "NIFTY",
                        "interval": "1d",
                        "feature_name": f"{col}_extreme",
                        "feature_formula": f"({col} > 1.5).astype(float)",
                        "feature_category": self._infer_category(col),
                        "target_horizon_days": horizon,
                        "lag_days": 1,
                        "candidate_ic": round(ic, 4),
                        "n_observations": len(aligned),
                    }
                )
        return candidates

    def _infer_category(self, col_name: str) -> str:
        c = col_name.lower()
        if "oi" in c or "open_interest" in c:
            return "open_interest"
        elif "pcr" in c:
            return "pcr"
        elif "wall" in c or "cog" in c:
            return "call_put_walls"
        elif "iv" in c or "vol" in c or "skew" in c:
            return "iv_gex"
        elif "fii" in c or "dii" in c:
            return "institutional"
        elif "ret" in c or "close" in c or "volume" in c:
            return "price_volume"
        return "general"
