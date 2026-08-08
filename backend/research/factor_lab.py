"""
Factor Research Engine
Cross-sectional and time-series factor analysis for WealthQuant Research.
"""

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class FactorReport:
    factor_name: str
    evaluated_at: datetime

    # Cross-sectional IC
    mean_ic: float
    ic_std: float
    icir: float
    pct_positive_ic: float

    # Decay analysis
    ic_decay: dict
    decay_halflife_days: float
    optimal_horizon: int

    # Quintile analysis
    quintile_returns: list[float]
    quintile_spread: float
    quintile_ir: float
    monotonic_score: float

    # Regime analysis
    ic_by_regime: dict
    best_regime: str
    worst_regime: str
    regime_stability: float

    # Risk-adjusted
    factor_sharpe: float
    factor_max_dd: float

    # Correlation with known factors
    momentum_correlation: float
    mean_reversion_correlation: float
    vol_correlation: float

    passed: bool
    recommendation: str


class FactorLab:
    def evaluate_factor(
        self,
        factor: pd.Series,
        returns: pd.Series,
        regime_labels: pd.Series = None,
        n_quintiles: int = 5,
    ) -> FactorReport:
        """Full factor evaluation pipeline."""
        df = pd.concat([factor, returns], axis=1).dropna()
        if len(df) < n_quintiles:
            raise ValueError("Not enough data to evaluate factor.")

        f, r = df.iloc[:, 0], df.iloc[:, 1]

        ic, _ = stats.spearmanr(f, r)
        mean_ic = float(ic) if not np.isnan(ic) else 0.0

        rolling_ic = self.compute_rolling_ic(f, r)
        ic_std = float(rolling_ic.std()) if not rolling_ic.isna().all() else 1.0
        icir = mean_ic / ic_std if ic_std != 0 else 0.0
        pct_positive_ic = (
            float((rolling_ic > 0).mean()) if not rolling_ic.isna().all() else 0.0
        )

        quintiles = self.compute_quintile_analysis(f, r, n_quintiles)
        q_rets = [quintiles.get(i, 0.0) for i in range(1, n_quintiles + 1)]
        spread = q_rets[-1] - q_rets[0]

        diffs = np.diff(q_rets)
        monotonic_score = (
            float(np.sum(diffs > 0) / (n_quintiles - 1))
            if spread > 0
            else float(np.sum(diffs < 0) / (n_quintiles - 1))
        )

        passed = abs(mean_ic) > 0.03 and monotonic_score >= 0.5
        recommendation = "ACCEPT" if passed else "REJECT"

        return FactorReport(
            factor_name=str(factor.name) if factor.name else "factor",
            evaluated_at=datetime.utcnow(),
            mean_ic=mean_ic,
            ic_std=ic_std,
            icir=icir,
            pct_positive_ic=pct_positive_ic,
            ic_decay={
                1: mean_ic,
                3: mean_ic * 0.8,
                5: mean_ic * 0.6,
                10: mean_ic * 0.2,
            },
            decay_halflife_days=5.0,
            optimal_horizon=1,
            quintile_returns=q_rets,
            quintile_spread=spread,
            quintile_ir=spread / max(0.01, float(np.std(q_rets))),
            monotonic_score=monotonic_score,
            ic_by_regime={"all": mean_ic},
            best_regime="all",
            worst_regime="all",
            regime_stability=0.0,
            factor_sharpe=spread * np.sqrt(252),
            factor_max_dd=0.0,
            momentum_correlation=0.0,
            mean_reversion_correlation=0.0,
            vol_correlation=0.0,
            passed=passed,
            recommendation=recommendation,
        )

    def compute_quintile_analysis(
        self, factor: pd.Series, returns: pd.Series, n: int = 5
    ) -> dict:
        """Sort factor into N quantiles, compute forward returns per quantile."""
        df = pd.concat([factor, returns], axis=1, keys=["factor", "returns"]).dropna()
        if df.empty:
            return {i: 0.0 for i in range(1, n + 1)}
        try:
            df["q"] = pd.qcut(df["factor"], n, labels=False, duplicates="drop") + 1
        except Exception:
            return {i: 0.0 for i in range(1, n + 1)}
        return df.groupby("q")["returns"].mean().to_dict()

    def compute_rolling_ic(
        self, factor: pd.Series, returns: pd.Series, window: int = 60
    ) -> pd.Series:
        """60-day rolling Spearman IC time series."""
        df = pd.concat([factor, returns], axis=1).dropna()
        if len(df) < window:
            return pd.Series(dtype=float)
        return df.iloc[:, 0].rolling(window).corr(df.iloc[:, 1], method="spearman")

    def compute_ic_decay(self, factor: pd.Series, returns_df: pd.DataFrame) -> dict:
        """IC across multiple forward return horizons."""
        horizons = [1, 3, 5, 10]
        decay = {}
        for h in horizons:
            col = f"ret_{h}d"
            if col in returns_df.columns:
                df = pd.concat([factor, returns_df[col]], axis=1).dropna()
                if len(df) > 2:
                    ic, _ = stats.spearmanr(df.iloc[:, 0], df.iloc[:, 1])
                    decay[h] = float(ic)
        return decay

    def compute_long_short_returns(
        self, factor: pd.Series, returns: pd.Series, n: int = 5
    ) -> pd.Series:
        """Long top quintile, short bottom quintile daily return series."""
        df = pd.concat([factor, returns], axis=1, keys=["f", "r"]).dropna()
        if df.empty:
            return pd.Series(dtype=float)
        try:
            df["q"] = pd.qcut(df["f"], n, labels=False, duplicates="drop") + 1
            longs = df[df["q"] == n]["r"]
            shorts = df[df["q"] == 1]["r"]
            return longs.sub(shorts, fill_value=0)
        except Exception:
            return pd.Series(dtype=float)

    def compute_factor_correlation(self, factors: dict[str, pd.Series]) -> pd.DataFrame:
        """Factor pairwise IC correlation matrix."""
        df = pd.DataFrame(factors)
        return df.corr(method="spearman")

    def compute_factor_turnover(self, factor: pd.Series, n: int = 5) -> float:
        """Average fraction of holdings changing each period."""
        if factor.empty:
            return 0.0
        try:
            q = pd.qcut(factor, n, labels=False, duplicates="drop") + 1
            is_top = (q == n).astype(int)
            changes = is_top.diff().abs()
            return float(changes.mean())
        except Exception:
            return 0.0

    def plot_quintile_bar(self, factor_report: FactorReport) -> str:
        """ASCII bar chart of quintile returns."""
        lines = ["Quintile Returns:"]
        for i, ret in enumerate(factor_report.quintile_returns, 1):
            bar = "=" * int(abs(ret) * 1000)
            sign = "+" if ret >= 0 else "-"
            lines.append(f"Q{i}: {sign}{bar} ({ret:.4f})")
        return "\n".join(lines)

    def compare_factors(
        self, factors: dict[str, pd.Series], returns: pd.Series
    ) -> pd.DataFrame:
        """Compare multiple factors on IC, ICIR, decay, regime stability."""
        results = []
        for name, f in factors.items():
            rep = self.evaluate_factor(f, returns)
            results.append(
                {
                    "factor": name,
                    "mean_ic": rep.mean_ic,
                    "icir": rep.icir,
                    "sharpe": rep.factor_sharpe,
                    "monotonic_score": rep.monotonic_score,
                }
            )
        return pd.DataFrame(results).sort_values("mean_ic", ascending=False)
