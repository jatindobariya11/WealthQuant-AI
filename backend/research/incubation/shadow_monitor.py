"""
WealthQuant V9.2 — Shadow Mode & Paper Trade Monitor
=====================================================
Tracks live/simulated performance of incubated alpha in Paper Trade and Shadow Mode.
Compares shadow mode tracking error against historical backtest expectations.
"""

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger("incubation.shadow")


@dataclass
class ShadowPerformanceReport:
    alpha_id: str
    mode: str  # PAPER_TRADE | SHADOW_MODE
    n_days: int
    n_signals: int
    simulated_sharpe: float
    realized_sharpe: float
    tracking_error: float  # Std dev of (realized_pnl - expected_pnl)
    win_rate: float
    max_drawdown: float
    matches_expectations: bool
    notes: list[str] = field(default_factory=list)


class ShadowMonitor:
    """
    Monitors parallel execution of incubated alpha without affecting production.
    """

    def __init__(self, max_tracking_error: float = 0.15):
        self.max_tracking_error = max_tracking_error

    def evaluate_shadow_performance(
        self,
        alpha_id: str,
        shadow_logs: list[dict],
        expected_sharpe: float = 1.5,
        mode: str = "SHADOW_MODE",
    ) -> ShadowPerformanceReport:
        """
        Evaluate tracking error between simulated/shadow signals and historical expectations.
        """
        if not shadow_logs:
            return ShadowPerformanceReport(
                alpha_id=alpha_id,
                mode=mode,
                n_days=0,
                n_signals=0,
                simulated_sharpe=0.0,
                realized_sharpe=0.0,
                tracking_error=0.0,
                win_rate=0.0,
                max_drawdown=0.0,
                matches_expectations=False,
                notes=["No shadow logs recorded"],
            )

        pnls = [
            log.get("realized_pnl", 0.0)
            for log in shadow_logs
            if log.get("realized_pnl") is not None
        ]
        expected_pnls = [
            log.get("expected_pnl", 0.0)
            for log in shadow_logs
            if log.get("expected_pnl") is not None
        ]

        n_signals = len(pnls)
        if n_signals < 5:
            return ShadowPerformanceReport(
                alpha_id=alpha_id,
                mode=mode,
                n_days=len(shadow_logs),
                n_signals=n_signals,
                simulated_sharpe=expected_sharpe,
                realized_sharpe=0.0,
                tracking_error=0.0,
                win_rate=0.0,
                max_drawdown=0.0,
                matches_expectations=False,
                notes=["Insufficient shadow trades (<5)"],
            )

        pnl_arr = np.array(pnls)
        exp_arr = (
            np.array(expected_pnls) if len(expected_pnls) == n_signals else pnl_arr
        )

        # Calculations
        mean_pnl = np.mean(pnl_arr)
        std_pnl = np.std(pnl_arr) + 1e-6
        realized_sharpe = float((mean_pnl / std_pnl) * np.sqrt(252))

        diffs = pnl_arr - exp_arr
        tracking_error = float(np.std(diffs))

        wins = np.sum(pnl_arr > 0)
        win_rate = float(wins / n_signals)

        # Drawdown
        cum_pnl = np.cumsum(pnl_arr)
        peak = np.maximum.accumulate(cum_pnl)
        dd = peak - cum_pnl
        max_dd = float(np.max(dd)) if len(dd) > 0 else 0.0

        matches = (tracking_error <= self.max_tracking_error) and (
            realized_sharpe >= expected_sharpe * 0.70
        )

        notes = []
        if tracking_error > self.max_tracking_error:
            notes.append(
                f"Tracking error high ({tracking_error:.3f} > {self.max_tracking_error})"
            )
        if realized_sharpe < expected_sharpe * 0.70:
            notes.append(
                f"Realized Sharpe degraded ({realized_sharpe:.2f} vs expected {expected_sharpe:.2f})"
            )
        if matches:
            notes.append("Shadow performance closely matches backtest expectations")

        return ShadowPerformanceReport(
            alpha_id=alpha_id,
            mode=mode,
            n_days=len(shadow_logs),
            n_signals=n_signals,
            simulated_sharpe=expected_sharpe,
            realized_sharpe=round(realized_sharpe, 2),
            tracking_error=round(tracking_error, 4),
            win_rate=round(win_rate, 4),
            max_drawdown=round(max_dd, 4),
            matches_expectations=matches,
            notes=notes,
        )
