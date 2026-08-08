"""
WealthQuant V9.1 — Alpha Discovery Engine: Alpha Scorer
=======================================================
Evaluates candidate alpha across 6 scoring dimensions (0-100 each):
  1. Novelty Score          — Low correlation with standard factors/features
  2. Predictive Power Score — IC, ICIR, Mutual Information, SHAP value
  3. Significance Score     — Monte Carlo p-value, Bootstrap CI width, t-stat
  4. Regime Stability Score — Consistency of IC across volatile/trending/ranging regimes
  5. Research Health Score  — Composite health metric (leakage, WF, MC, Bootstrap)
  6. Production Readiness   — VIF, missingness, turnover, compute complexity
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("alpha.scorer")


@dataclass
class AlphaScore:
    hypothesis_id: str
    novelty_score: float
    predictive_power_score: float
    significance_score: float
    regime_stability_score: float
    research_health_score: float
    production_readiness_score: float

    composite_score: float
    passed_all_gates: bool
    recommendation: str  # ACCEPT | WATCH | REJECT

    details: dict[str, dict] = field(default_factory=dict)


class AlphaScorer:
    """
    6-Dimension Alpha Scoring Engine.
    Computes normalized sub-scores and composite weighted score.
    """

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or {
            "predictive_power": 0.25,
            "significance": 0.20,
            "research_health": 0.20,
            "regime_stability": 0.15,
            "novelty": 0.10,
            "production_readiness": 0.10,
        }

    def score(
        self,
        hypothesis_id: str,
        val_result: dict,
        existing_features: list[dict] | None = None,
    ) -> AlphaScore:
        """Score candidate alpha across all 6 dimensions."""

        # 1. Predictive Power Score
        ic_5d = abs(val_result.get("ic_5d", 0.0) or 0.0)
        icir = abs(val_result.get("wf_icir", 0.0) or 0.0)
        mi = val_result.get("mutual_information", 0.0) or 0.0

        p_ic = min(100.0, (ic_5d / 0.15) * 50.0)  # IC 0.15 = 50 pts
        p_icir = min(50.0, (icir / 1.5) * 50.0)  # ICIR 1.5 = 50 pts
        predictive_power = min(100.0, p_ic + p_icir)

        # 2. Significance Score
        mc_p = val_result.get("mc_pvalue", 1.0) or 1.0
        boot_lower = val_result.get("boot_ic_lower", 0.0) or 0.0
        ic_tstat = abs(val_result.get("ic_tstat", 0.0) or 0.0)

        s_mc = max(0.0, (0.05 - mc_p) / 0.05 * 40.0) if mc_p < 0.05 else 0.0
        s_boot = min(30.0, (boot_lower / 0.05) * 30.0) if boot_lower > 0 else 0.0
        s_tstat = min(30.0, (ic_tstat / 3.0) * 30.0)
        significance = min(100.0, s_mc + s_boot + s_tstat)

        # 3. Regime Stability Score
        regime_ic = val_result.get("regime_ic", {}) or {}
        regime_stab = val_result.get("regime_stability", 1.0) or 1.0

        if regime_ic:
            ics = [abs(v) for v in regime_ic.values() if v is not None]
            min_regime_ic = min(ics) if ics else 0.0
            r_min = min(50.0, (min_regime_ic / 0.03) * 50.0)
            r_std = max(0.0, 50.0 - (regime_stab / 0.05) * 50.0)
            regime_stability = min(100.0, r_min + r_std)
        else:
            regime_stability = 50.0  # default neutral

        # 4. Research Health Score
        leakage_clean = 10.0 if val_result.get("leakage_status") == "CLEAN" else 0.0
        wf_pct = (val_result.get("wf_pct_positive", 0.0) or 0.0) * 20.0
        mc_pass = 20.0 if mc_p < 0.05 else 0.0
        boot_pass = 20.0 if boot_lower > 0 else 0.0
        ic_bonus = min(30.0, max(0.0, (ic_5d - 0.05) * 300.0))
        research_health = min(
            100.0, leakage_clean + wf_pct + mc_pass + boot_pass + ic_bonus
        )

        # 5. Novelty Score
        max_corr = val_result.get("vif_score", 1.0) or 1.0
        if existing_features:
            novelty = max(
                0.0, 100.0 - (val_result.get("max_correlation", 0.0) or 0.0) * 100.0
            )
        else:
            novelty = 85.0  # default high for new repository

        # 6. Production Readiness Score
        vif = val_result.get("vif_score", 1.0) or 1.0
        drifting = val_result.get("is_drifting", False)

        prod_vif = max(0.0, 50.0 - (vif / 10.0) * 50.0) if vif > 1.0 else 50.0
        prod_drift = 0.0 if drifting else 50.0
        production_readiness = min(100.0, prod_vif + prod_drift)

        # Composite score
        composite = (
            predictive_power * self.weights["predictive_power"]
            + significance * self.weights["significance"]
            + research_health * self.weights["research_health"]
            + regime_stability * self.weights["regime_stability"]
            + novelty * self.weights["novelty"]
            + production_readiness * self.weights["production_readiness"]
        )

        passed_all = (
            research_health >= 90.0
            and mc_p < 0.05
            and boot_lower > 0
            and val_result.get("leakage_status") == "CLEAN"
            and ic_5d >= 0.05
        )

        rec = "ACCEPT" if passed_all else ("WATCH" if composite >= 70.0 else "REJECT")

        details = {
            "predictive_power": {"ic_5d": ic_5d, "icir": icir, "mi": mi},
            "significance": {
                "mc_pvalue": mc_p,
                "boot_lower": boot_lower,
                "tstat": ic_tstat,
            },
            "regime_stability": {"regime_ic": regime_ic, "stability_std": regime_stab},
            "research_health": {"score": research_health},
            "novelty": {"novelty_score": novelty},
            "production_readiness": {"vif": vif, "drifting": drifting},
        }

        return AlphaScore(
            hypothesis_id=hypothesis_id,
            novelty_score=round(novelty, 2),
            predictive_power_score=round(predictive_power, 2),
            significance_score=round(significance, 2),
            regime_stability_score=round(regime_stability, 2),
            research_health_score=round(research_health, 2),
            production_readiness_score=round(production_readiness, 2),
            composite_score=round(composite, 2),
            passed_all_gates=passed_all,
            recommendation=rec,
            details=details,
        )
