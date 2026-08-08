"""
Feature Evaluation Laboratory
Evaluates any feature signal against forward returns for WealthQuant Research.
"""

from dataclasses import dataclass, field
from datetime import date, datetime

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class FeatureEvaluation:
    feature_name: str
    evaluated_at: datetime
    symbol: str
    interval: str
    data_start: date
    data_end: date
    n_observations: int

    # IC metrics
    ic_1d: float
    ic_3d: float
    ic_5d: float
    ic_10d: float
    ic_decay_halflife: float

    # Distributional metrics
    mean: float
    std: float
    skewness: float
    kurtosis: float
    min_val: float
    max_val: float
    pct_missing: float

    # Redundancy metrics
    max_correlation_with_others: float
    vif: float
    mutual_information: float

    # Drift metrics
    psi_score: float
    ks_pvalue: float
    is_drifting: bool

    # Leakage
    leakage_suspected: bool
    ic_same_day: float
    ic_next_day: float

    # Research verdict
    research_grade: str
    recommendation: str
    rejection_reasons: list[str] = field(default_factory=list)


class FeatureLab:
    def evaluate_feature(
        self,
        feature: pd.Series,
        returns_data: pd.DataFrame,
        other_features: pd.DataFrame = None,
        feature_history_baseline: pd.Series = None,
        regime_labels: pd.Series = None,
    ) -> FeatureEvaluation:
        """Full feature evaluation pipeline."""
        if not isinstance(feature.index, pd.DatetimeIndex):
            raise ValueError("Feature series must have a DatetimeIndex.")

        aligned = pd.concat([feature, returns_data], axis=1, join="inner")
        feature_aligned = aligned[feature.name]

        ic_same_day = self.compute_ic(
            feature_aligned,
            aligned.get("ret_0d", pd.Series(0, index=feature_aligned.index)),
        )
        ic_1d = self.compute_ic(
            feature_aligned,
            aligned.get("ret_1d", pd.Series(0, index=feature_aligned.index)),
        )
        ic_3d = self.compute_ic(
            feature_aligned,
            aligned.get("ret_3d", pd.Series(0, index=feature_aligned.index)),
        )
        ic_5d = self.compute_ic(
            feature_aligned,
            aligned.get("ret_5d", pd.Series(0, index=feature_aligned.index)),
        )
        ic_10d = self.compute_ic(
            feature_aligned,
            aligned.get("ret_10d", pd.Series(0, index=feature_aligned.index)),
        )

        ic_curve = {1: ic_1d, 3: ic_3d, 5: ic_5d, 10: ic_10d}
        ic_halflife = self.compute_ic_halflife(ic_curve)

        psi_score = 0.0
        is_drifting = False
        ks_pvalue = 1.0
        if feature_history_baseline is not None:
            psi_score = self.compute_feature_psi(
                feature_history_baseline, feature_aligned
            )
            is_drifting = psi_score > 0.1
            _, ks_pvalue = stats.ks_2samp(
                feature_history_baseline.dropna(), feature_aligned.dropna()
            )

        max_corr = 0.0
        vif = 1.0
        if other_features is not None:
            corrs = other_features.corrwith(feature_aligned, method="spearman")
            max_corr = float(corrs.abs().max()) if not corrs.empty else 0.0
            if max_corr > 0:
                vif = 1.0 / (1.0 - max_corr**2) if max_corr < 1.0 else float("inf")

        leakage_suspected = abs(ic_same_day) > 0.5 or abs(ic_1d) > 0.8

        eval_result = FeatureEvaluation(
            feature_name=str(feature.name),
            evaluated_at=datetime.utcnow(),
            symbol="UNKNOWN",
            interval="1d",
            data_start=feature.index.min().date()
            if not feature.empty
            else date.today(),
            data_end=feature.index.max().date() if not feature.empty else date.today(),
            n_observations=len(feature.dropna()),
            ic_1d=ic_1d,
            ic_3d=ic_3d,
            ic_5d=ic_5d,
            ic_10d=ic_10d,
            ic_decay_halflife=ic_halflife,
            mean=float(feature.mean()),
            std=float(feature.std()),
            skewness=float(feature.skew()),
            kurtosis=float(feature.kurtosis()),
            min_val=float(feature.min()),
            max_val=float(feature.max()),
            pct_missing=float(feature.isna().mean()),
            max_correlation_with_others=max_corr,
            vif=vif,
            mutual_information=0.0,
            psi_score=psi_score,
            ks_pvalue=ks_pvalue,
            is_drifting=is_drifting,
            leakage_suspected=leakage_suspected,
            ic_same_day=ic_same_day,
            ic_next_day=ic_1d,
            research_grade="",
            recommendation="",
            rejection_reasons=[],
        )

        eval_result.research_grade = self.grade_feature(eval_result)

        if eval_result.research_grade in ["A+", "A"]:
            eval_result.recommendation = "ACCEPT"
        elif eval_result.research_grade == "B":
            eval_result.recommendation = "ACCEPT"
        elif eval_result.research_grade == "C":
            eval_result.recommendation = "WATCH"
        else:
            eval_result.recommendation = "REJECT"

        return eval_result

    def compute_ic(self, feature: pd.Series, returns: pd.Series) -> float:
        """Spearman rank correlation."""
        df = pd.concat([feature, returns], axis=1).dropna()
        if len(df) < 2:
            return 0.0
        return float(stats.spearmanr(df.iloc[:, 0], df.iloc[:, 1])[0] or 0.0)

    def compute_ic_decay_curve(
        self, feature: pd.Series, returns_df: pd.DataFrame
    ) -> dict:
        """IC at horizons 1,3,5,10,20 days."""
        horizons = [1, 3, 5, 10, 20]
        curve = {}
        for h in horizons:
            ret_col = f"ret_{h}d"
            if ret_col in returns_df.columns:
                curve[h] = self.compute_ic(feature, returns_df[ret_col])
        return curve

    def compute_ic_halflife(self, ic_curve: dict) -> float:
        """Fit exponential decay to IC curve."""
        x = np.array(list(ic_curve.keys()))
        y = np.array(list(ic_curve.values()))
        y = np.abs(y)
        if len(y) < 2 or y[0] == 0:
            return 0.0
        try:
            log_y = np.log(np.maximum(y, 1e-6))
            slope, intercept, _, _, _ = stats.linregress(x, log_y)
            if slope >= 0:
                return float("inf")
            return float(-np.log(2) / slope)
        except Exception:
            return 0.0

    def grade_feature(self, eval: FeatureEvaluation) -> str:
        """Grade from A+ to F based on IC, drift, leakage, VIF."""
        if eval.ic_5d <= 0 or eval.leakage_suspected:
            return "F"
        if eval.is_drifting:
            return "D"
        if (
            eval.ic_5d > 0.12
            and not eval.leakage_suspected
            and not eval.is_drifting
            and eval.vif < 5
        ):
            return "A+"
        if eval.ic_5d > 0.08 and not eval.leakage_suspected and not eval.is_drifting:
            return "A"
        if eval.ic_5d > 0.05 and not eval.leakage_suspected:
            return "B"
        if eval.ic_5d > 0.03:
            return "C"
        return "D"

    def evaluate_feature_set(
        self,
        features: pd.DataFrame,
        returns_data: pd.DataFrame,
    ) -> pd.DataFrame:
        """Evaluate all features, return ranked DataFrame."""
        results = []
        for col in features.columns:
            feat_eval = self.evaluate_feature(
                features[col], returns_data, other_features=features.drop(columns=[col])
            )
            results.append(
                {
                    "feature": col,
                    "ic_1d": feat_eval.ic_1d,
                    "ic_5d": feat_eval.ic_5d,
                    "grade": feat_eval.research_grade,
                    "recommendation": feat_eval.recommendation,
                }
            )
        df = pd.DataFrame(results)
        if not df.empty:
            df = df.sort_values(by="ic_5d", ascending=False)
        return df

    def build_correlation_matrix(self, features: pd.DataFrame) -> pd.DataFrame:
        """Spearman correlation matrix with cluster highlighting."""
        return features.corr(method="spearman")

    def detect_redundant_features(
        self, features: pd.DataFrame, threshold: float = 0.70
    ) -> list[tuple[str, str, float]]:
        """Find feature pairs with |corr| > threshold."""
        corr = features.corr(method="spearman").abs()
        pairs = []
        for i in range(len(corr.columns)):
            for j in range(i + 1, len(corr.columns)):
                if corr.iloc[i, j] > threshold:
                    pairs.append(
                        (corr.columns[i], corr.columns[j], float(corr.iloc[i, j]))
                    )
        return pairs

    def compute_feature_psi(
        self, baseline: pd.Series, current: pd.Series, n_bins: int = 10
    ) -> float:
        """Population Stability Index."""
        baseline = baseline.dropna()
        current = current.dropna()
        if len(baseline) == 0 or len(current) == 0:
            return 0.0

        bins = np.linspace(
            min(baseline.min(), current.min()),
            max(baseline.max(), current.max()),
            n_bins + 1,
        )

        base_counts, _ = np.histogram(baseline, bins=bins)
        curr_counts, _ = np.histogram(current, bins=bins)

        base_pct = base_counts / len(baseline)
        curr_pct = curr_counts / len(current)

        base_pct = np.where(base_pct == 0, 0.0001, base_pct)
        curr_pct = np.where(curr_pct == 0, 0.0001, curr_pct)

        psi = np.sum((curr_pct - base_pct) * np.log(curr_pct / base_pct))
        return float(psi)

    def compute_feature_drift_score(
        self, feature: pd.Series, window_days: int = 30
    ) -> tuple[float, bool]:
        """Rolling PSI; returns (psi, is_drifting)."""
        if len(feature) < window_days * 2:
            return 0.0, False
        baseline = feature.iloc[:-window_days]
        current = feature.iloc[-window_days:]
        psi = self.compute_feature_psi(baseline, current)
        return psi, psi > 0.1

    def compute_information_coefficient_report(
        self,
        features: pd.DataFrame,
        returns: pd.Series,
    ) -> pd.DataFrame:
        """IC for all features, with t-stat and p-value."""
        results = []
        for col in features.columns:
            df = pd.concat([features[col], returns], axis=1).dropna()
            if len(df) > 2:
                r, p = stats.spearmanr(df.iloc[:, 0], df.iloc[:, 1])
                tstat = r * np.sqrt((len(df) - 2) / (1 - r**2)) if r**2 < 1 else np.inf
                results.append(
                    {
                        "feature": col,
                        "ic": r,
                        "tstat": tstat,
                        "pvalue": p,
                        "significant": p < 0.05,
                    }
                )
        return pd.DataFrame(results)

    async def save_evaluation(self, eval: FeatureEvaluation, db_pool) -> None:
        """Save to PostgreSQL research_feature_evaluations table."""
        query = """
            INSERT INTO research_feature_evaluations (
                feature_name, evaluated_at, symbol, interval, data_start, data_end,
                n_observations, ic_1d, ic_3d, ic_5d, ic_10d, ic_decay_halflife,
                mean, std, skewness, kurtosis, min_val, max_val, pct_missing,
                max_correlation_with_others, vif, mutual_information,
                psi_score, ks_pvalue, is_drifting, leakage_suspected,
                ic_same_day, ic_next_day, research_grade, recommendation, rejection_reasons
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
                $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31
            )
        """
        async with db_pool.acquire() as conn:
            await conn.execute(
                query,
                eval.feature_name,
                eval.evaluated_at,
                eval.symbol,
                eval.interval,
                eval.data_start,
                eval.data_end,
                eval.n_observations,
                eval.ic_1d,
                eval.ic_3d,
                eval.ic_5d,
                eval.ic_10d,
                eval.ic_decay_halflife,
                eval.mean,
                eval.std,
                eval.skewness,
                eval.kurtosis,
                eval.min_val,
                eval.max_val,
                eval.pct_missing,
                eval.max_correlation_with_others,
                eval.vif,
                eval.mutual_information,
                eval.psi_score,
                eval.ks_pvalue,
                eval.is_drifting,
                eval.leakage_suspected,
                eval.ic_same_day,
                eval.ic_next_day,
                eval.research_grade,
                eval.recommendation,
                eval.rejection_reasons,
            )
