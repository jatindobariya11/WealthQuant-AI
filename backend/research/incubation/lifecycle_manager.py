"""
WealthQuant V9.2 — Alpha Lifecycle Manager
===========================================
Defines the strict 10-Stage Alpha Incubation Lifecycle and governance approval state machine:

10-STAGE LIFECYCLE:
  1. DISCOVERED            — Initial alpha discovery from Alpha Engine
  2. UNDER_REVIEW          — Pre-screening and hypothesis audit
  3. BACKTESTED            — Full in-sample/out-of-sample backtest completed
  4. WALK_FORWARD_VERIFIED — Purged Walk-Forward ICIR & fold verification
  5. MONTE_CARLO_VERIFIED  — Block permutation p-value < 0.05 verified
  6. BOOTSTRAP_VERIFIED    — Circular block bootstrap 95% CI excludes zero
  7. PAPER_TRADE           — Simulated execution on forward market data (30 days min)
  8. SHADOW_MODE           — Live parallel execution without capital deployment (60 days min)
  9. PRODUCTION_CANDIDATE  — All statistical & tracking error gates passed
 10. APPROVED / REJECTED   — Final sign-off for IPS inclusion or termination
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

logger = logging.getLogger("incubation.lifecycle")


class AlphaLifecycleStage(str, Enum):
    DISCOVERED = "DISCOVERED"
    UNDER_REVIEW = "UNDER_REVIEW"
    BACKTESTED = "BACKTESTED"
    WALK_FORWARD_VERIFIED = "WALK_FORWARD_VERIFIED"
    MONTE_CARLO_VERIFIED = "MONTE_CARLO_VERIFIED"
    BOOTSTRAP_VERIFIED = "BOOTSTRAP_VERIFIED"
    PAPER_TRADE = "PAPER_TRADE"
    SHADOW_MODE = "SHADOW_MODE"
    PRODUCTION_CANDIDATE = "PRODUCTION_CANDIDATE"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ON_HOLD = "ON_HOLD"


STAGE_ORDER = [
    AlphaLifecycleStage.DISCOVERED,
    AlphaLifecycleStage.UNDER_REVIEW,
    AlphaLifecycleStage.BACKTESTED,
    AlphaLifecycleStage.WALK_FORWARD_VERIFIED,
    AlphaLifecycleStage.MONTE_CARLO_VERIFIED,
    AlphaLifecycleStage.BOOTSTRAP_VERIFIED,
    AlphaLifecycleStage.PAPER_TRADE,
    AlphaLifecycleStage.SHADOW_MODE,
    AlphaLifecycleStage.PRODUCTION_CANDIDATE,
    AlphaLifecycleStage.APPROVED,
]


@dataclass
class IncubationRecord:
    incubation_id: str
    alpha_id: str
    hypothesis_title: str
    author: str = "quant_research_team"
    discovery_date: str = field(default_factory=lambda: date.today().isoformat())

    current_stage: AlphaLifecycleStage = AlphaLifecycleStage.DISCOVERED
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    production_status: str = "NOT_DEPLOYED"

    sample_size: int = 0
    research_health_score: float = 0.0
    information_coefficient: float = 0.0
    sharpe_contribution: float = 0.0
    drawdown_impact: float = 0.0
    regime_stability: float = 0.0
    calibration_score: float = 0.0

    validation_checklist: dict[str, bool] = field(default_factory=dict)
    failure_modes: list[str] = field(default_factory=list)
    supporting_features: list[str] = field(default_factory=list)


class LifecycleManager:
    """
    State machine enforcing sequential progression through the 10 lifecycle stages.
    """

    def __init__(self, pool=None):
        self.pool = pool

    def evaluate_stage_transition(
        self, record: IncubationRecord, target_stage: AlphaLifecycleStage, metrics: dict
    ) -> tuple[bool, list[str]]:
        """
        Check if an incubated alpha meets all criteria to advance to target_stage.
        Returns (can_advance, reasons_if_blocked).
        """
        reasons = []

        # Check stage order
        curr_idx = (
            STAGE_ORDER.index(record.current_stage)
            if record.current_stage in STAGE_ORDER
            else -1
        )
        targ_idx = (
            STAGE_ORDER.index(target_stage) if target_stage in STAGE_ORDER else -1
        )

        if target_stage == AlphaLifecycleStage.REJECTED:
            return True, ["Target stage is REJECTED"]

        if targ_idx != curr_idx + 1:
            reasons.append(
                f"Cannot skip stages: Current = {record.current_stage.value}, Target = {target_stage.value}"
            )
            return False, reasons

        # Stage-specific hard gates
        if target_stage == AlphaLifecycleStage.UNDER_REVIEW:
            if metrics.get("sample_size", 0) < 30:
                reasons.append("Insufficient sample size (<30 observations)")

        elif target_stage == AlphaLifecycleStage.BACKTESTED:
            if abs(metrics.get("ic", 0.0)) < 0.05:
                reasons.append("IC below backtest minimum (0.05)")

        elif target_stage == AlphaLifecycleStage.WALK_FORWARD_VERIFIED:
            if metrics.get("wf_icir", 0.0) < 0.5:
                reasons.append("Walk-Forward ICIR < 0.5")
            if metrics.get("wf_pct_positive", 0.0) < 0.60:
                reasons.append("Walk-Forward positive folds < 60%")

        elif target_stage == AlphaLifecycleStage.MONTE_CARLO_VERIFIED:
            if metrics.get("mc_pvalue", 1.0) >= 0.05:
                reasons.append("Monte Carlo permutation p-value >= 0.05")

        elif target_stage == AlphaLifecycleStage.BOOTSTRAP_VERIFIED:
            if metrics.get("boot_ic_lower", -1.0) <= 0:
                reasons.append("Bootstrap 95% CI includes zero")

        elif target_stage == AlphaLifecycleStage.PAPER_TRADE:
            if metrics.get("health_score", 0.0) < 90.0:
                reasons.append("Research Health Score < 90/100")
            if metrics.get("leakage_status") != "CLEAN":
                reasons.append("Data leakage not confirmed CLEAN")

        elif target_stage == AlphaLifecycleStage.SHADOW_MODE:
            if metrics.get("paper_trade_days", 0) < 30:
                reasons.append("Paper trading duration < 30 days required")

        elif target_stage == AlphaLifecycleStage.PRODUCTION_CANDIDATE:
            if metrics.get("shadow_mode_days", 0) < 60:
                reasons.append("Shadow mode duration < 60 days required")
            if metrics.get("shadow_tracking_error", 1.0) > 0.15:
                reasons.append("Shadow mode tracking error > 15%")

        elif target_stage == AlphaLifecycleStage.APPROVED:
            if not metrics.get("sharpe_improved", False) and not metrics.get(
                "dd_reduced", False
            ):
                reasons.append("Must improve Sharpe OR reduce drawdown")
            if metrics.get("health_score", 0.0) < 90.0:
                reasons.append("Final approval requires Research Health Score >= 90")

        can_advance = len(reasons) == 0
        return can_advance, reasons
