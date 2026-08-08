"""
WealthQuant V9.1 — Alpha Discovery Engine: Rejection Engine
============================================================
Defines automatic rejection rules for candidate alpha hypotheses.

Rejection Categories:
  1. WEAK ALPHA       — Low IC (<0.05), non-significant p-value (>0.05), low MI
  2. UNSTABLE ALPHA   — High IC variance across regimes, failing Walk-Forward ICIR (<0.5), high parameter sensitivity
  3. LEAKED ALPHA     — IC_lag0 >> IC_lag1 (look-ahead bias confirmed or ratio > 2.0)
  4. OVERFIT ALPHA    — Fails Monte Carlo block permutation test or Bootstrap 95% CI contains zero
  5. DUPLICATE ALPHA  — High Spearman correlation (>0.75) with an already accepted alpha feature
"""

import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("alpha.filter")


class RejectionCategory(str, Enum):
    WEAK = "weak"
    UNSTABLE = "unstable"
    LEAKED = "leaked"
    OVERFIT = "overfit"
    DUPLICATE = "duplicate"
    NONE = "none"


@dataclass
class RejectionResult:
    is_rejected: bool
    category: RejectionCategory
    failed_gate: str
    rejection_reasons: list[str]
    metrics_summary: dict[str, float] = field(default_factory=dict)
    duplicate_of: str | None = None
    duplicate_correlation: float | None = None


class AlphaFilter:
    """
    Evaluates candidate alpha against hard statistical acceptance gates.
    All criteria are strictly enforced without exception.
    """

    def __init__(
        self,
        min_ic: float = 0.05,
        min_wf_icir: float = 0.5,
        min_wf_positive_pct: float = 0.60,
        max_mc_pvalue: float = 0.05,
        max_leakage_ratio: float = 2.0,
        max_duplicate_corr: float = 0.75,
        min_health_score: float = 90.0,
    ):
        self.min_ic = min_ic
        self.min_wf_icir = min_wf_icir
        self.min_wf_positive_pct = min_wf_positive_pct
        self.max_mc_pvalue = max_mc_pvalue
        self.max_leakage_ratio = max_leakage_ratio
        self.max_duplicate_corr = max_duplicate_corr
        self.min_health_score = min_health_score

    def evaluate(
        self, val_result: dict, score_result: dict, accepted_alphas: list[dict] = None
    ) -> RejectionResult:
        """
        Run full gate checks on a validated hypothesis.
        Order of evaluation:
          1. Leakage (Leaked Alpha)
          2. Significance & Overfitting (Overfit Alpha)
          3. Predictive Power (Weak Alpha)
          4. Stability (Unstable Alpha)
          5. Duplicate Check (Duplicate Alpha)
          6. Research Health Score
        """
        reasons = []
        metrics = {}

        # Extract metrics safely
        ic_5d = val_result.get("ic_5d", 0.0) or 0.0
        ic_same_day = val_result.get("ic_same_day", 0.0) or 0.0
        ic_next_day = val_result.get("ic_next_day", 0.0) or 0.0
        leakage_ratio = val_result.get("leakage_ratio", 0.0) or 0.0
        leakage_status = val_result.get("leakage_status", "CLEAN")

        wf_icir = val_result.get("wf_icir", 0.0) or 0.0
        wf_pct_pos = val_result.get("wf_pct_positive", 0.0) or 0.0
        mc_pvalue = val_result.get("mc_pvalue", 1.0) or 1.0
        boot_lower = val_result.get("boot_ic_lower", -1.0) or -1.0
        boot_upper = val_result.get("boot_ic_upper", -1.0) or -1.0

        health_score = score_result.get("research_health_score", 0.0) or 0.0

        metrics = {
            "ic_5d": ic_5d,
            "wf_icir": wf_icir,
            "mc_pvalue": mc_pvalue,
            "boot_ic_lower": boot_lower,
            "leakage_ratio": leakage_ratio,
            "health_score": health_score,
        }

        # 1. LEAKED ALPHA GATE
        if leakage_status == "CONFIRMED" or leakage_ratio > self.max_leakage_ratio:
            reasons.append(
                f"Data leakage detected (Ratio {leakage_ratio:.2f} > {self.max_leakage_ratio})"
            )
            return RejectionResult(
                is_rejected=True,
                category=RejectionCategory.LEAKED,
                failed_gate="G1_LEAKAGE",
                rejection_reasons=reasons,
                metrics_summary=metrics,
            )

        # 2. OVERFIT ALPHA GATE (Monte Carlo & Bootstrap)
        if mc_pvalue >= self.max_mc_pvalue:
            reasons.append(
                f"Monte Carlo permutation p-value non-significant ({mc_pvalue:.4f} >= {self.max_mc_pvalue})"
            )
            return RejectionResult(
                is_rejected=True,
                category=RejectionCategory.OVERFIT,
                failed_gate="G4_MONTE_CARLO",
                rejection_reasons=reasons,
                metrics_summary=metrics,
            )

        if boot_lower <= 0:
            reasons.append(
                f"Bootstrap 95% CI lower bound includes zero ({boot_lower:.4f} <= 0)"
            )
            return RejectionResult(
                is_rejected=True,
                category=RejectionCategory.OVERFIT,
                failed_gate="G5_BOOTSTRAP",
                rejection_reasons=reasons,
                metrics_summary=metrics,
            )

        # 3. WEAK ALPHA GATE (IC & Statistical Significance)
        if abs(ic_5d) < self.min_ic:
            reasons.append(
                f"5-day Information Coefficient too weak (|{ic_5d:.4f}| < {self.min_ic})"
            )
            return RejectionResult(
                is_rejected=True,
                category=RejectionCategory.WEAK,
                failed_gate="G7_IC_THRESHOLD",
                rejection_reasons=reasons,
                metrics_summary=metrics,
            )

        # 4. UNSTABLE ALPHA GATE (Walk-Forward & Regime Stability)
        if wf_pct_pos < self.min_wf_positive_pct:
            reasons.append(
                f"Walk-Forward positive fold ratio too low ({wf_pct_pos * 100:.1f}% < {self.min_wf_positive_pct * 100:.1f}%)"
            )
            return RejectionResult(
                is_rejected=True,
                category=RejectionCategory.UNSTABLE,
                failed_gate="G2_WALK_FORWARD_PCT",
                rejection_reasons=reasons,
                metrics_summary=metrics,
            )

        if wf_icir < self.min_wf_icir:
            reasons.append(
                f"Walk-Forward ICIR too low ({wf_icir:.2f} < {self.min_wf_icir})"
            )
            return RejectionResult(
                is_rejected=True,
                category=RejectionCategory.UNSTABLE,
                failed_gate="G3_WALK_FORWARD_ICIR",
                rejection_reasons=reasons,
                metrics_summary=metrics,
            )

        # 5. DUPLICATE ALPHA GATE
        if accepted_alphas:
            feature_series = val_result.get("feature_values")
            if feature_series is not None:
                for existing in accepted_alphas:
                    ex_series = existing.get("feature_values")
                    ex_id = existing.get("hypothesis_id", "unknown")
                    if ex_series is not None and len(ex_series) == len(feature_series):
                        corr = feature_series.corr(ex_series, method="spearman")
                        if abs(corr) >= self.max_duplicate_corr:
                            reasons.append(
                                f"Duplicate of accepted alpha {ex_id} (Spearman corr {corr:.3f} >= {self.max_duplicate_corr})"
                            )
                            return RejectionResult(
                                is_rejected=True,
                                category=RejectionCategory.DUPLICATE,
                                failed_gate="G10_DUPLICATE_CHECK",
                                rejection_reasons=reasons,
                                metrics_summary=metrics,
                                duplicate_of=ex_id,
                                duplicate_correlation=float(corr),
                            )

        # 6. RESEARCH HEALTH SCORE GATE
        if health_score < self.min_health_score:
            reasons.append(
                f"Research Health Score insufficient ({health_score:.1f} < {self.min_health_score})"
            )
            return RejectionResult(
                is_rejected=True,
                category=RejectionCategory.WEAK,
                failed_gate="G9_HEALTH_SCORE",
                rejection_reasons=reasons,
                metrics_summary=metrics,
            )

        # PASSED ALL GATES
        return RejectionResult(
            is_rejected=False,
            category=RejectionCategory.NONE,
            failed_gate="NONE",
            rejection_reasons=[],
            metrics_summary=metrics,
        )
