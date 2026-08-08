# models/position_sizer.py
"""
WealthQuant V8.5 — Institutional Position Sizing Model
NSE India Edition: NIFTY / BANKNIFTY / FINNIFTY / MIDCPNIFTY

Implements multi-factor risk allocation:
F_Alloc = f_Kelly * C_Pred * (H_Score/100) * (1 - DD_Current) * M_Regime * (sigma_Target/sigma_Current) * U_Scale * I_Gated

Includes hard risk limits:
- Confidence Gate fallback (I_Gated = 0 for NO_TRADE)
- Maximum 10 lots per trade
- Maximum 2.0% portfolio capital loss per trade
"""

import logging
from dataclasses import dataclass

import numpy as np

from models.strategy_ranking_engine import (
    MarketRegime,
    RankedStrategyPayload,
    StrategyType,
)

logger = logging.getLogger(__name__)


@dataclass
class SizingResult:
    """Complete output specification for multi-factor position sizing."""

    allocated_fraction: float  # F_Alloc (0.0 to 0.25)
    target_capital_inr: float  # F_Alloc * Total_Capital
    recommended_lots: int  # Final lot count
    raw_lots: int  # Unconstrained lot count
    confidence_gated: bool  # True if NO_TRADE
    max_loss_per_lot: float  # Maximum risk per lot
    max_trade_loss_inr: float  # Max potential loss in ₹
    factor_breakdown: dict[str, float]


class PositionSizer:
    """
    Multi-Factor Position Sizing Engine for WealthQuant V8.5.
    """

    KELLY_FRACTION = 0.25  # 25% Fractional Kelly baseline
    MAX_CAPITAL_LOSS_PCT = 0.02  # 2.0% maximum portfolio risk per trade
    HARD_LOT_CAP = 10  # Maximum 10 lots per position
    TARGET_VOLATILITY = 0.15  # 15% target annual volatility

    def __init__(self, capital: float = 1_000_000.0):
        self.capital = capital

    def compute_position_size(
        self,
        payload: RankedStrategyPayload,
        current_drawdown: float = 0.0,
        current_volatility: float = 0.15,
    ) -> SizingResult:
        """
        Calculates risk-budgeted lot sizing using 9 multi-factor multipliers.
        """
        # Confidence Gate Check
        if (
            payload.confidence_gated
            or payload.recommended_strategy == StrategyType.NO_TRADE
        ):
            return SizingResult(
                allocated_fraction=0.0,
                target_capital_inr=0.0,
                recommended_lots=0,
                raw_lots=0,
                confidence_gated=True,
                max_loss_per_lot=0.0,
                max_trade_loss_inr=0.0,
                factor_breakdown={"I_Gated": 0.0},
            )

        top_1 = payload.top_1

        # Factor 1: Fractional Kelly (25% Kelly)
        f_kelly = (
            min(top_1.kelly_score * self.KELLY_FRACTION, 0.25)
            if top_1.kelly_score > 0
            else 0.05
        )

        # Factor 2: Prediction Confidence
        c_pred = payload.feature_attributions.get("Ensemble_Conviction", 0.60)

        # Factor 3: Research Health Score Index
        h_score = top_1.health_score / 100.0

        # Factor 4: Active Portfolio Drawdown Adjustment
        dd_factor = max(0.0, 1.0 - current_drawdown)

        # Factor 5: Market Regime Multiplier
        regime_mults = {
            MarketRegime.BULL_TREND: 1.00,
            MarketRegime.BEAR_TREND: 1.00,
            MarketRegime.CHOPPY: 0.50,
            MarketRegime.HIGH_VOLATILITY: 0.30,
            MarketRegime.LOW_VOLATILITY: 0.90,
            MarketRegime.TRANSITION: 0.40,
        }
        m_regime = regime_mults.get(payload.active_regime, 0.50)

        # Factor 6: Volatility Scaling
        vol_ratio = self.TARGET_VOLATILITY / max(current_volatility, 0.05)

        # Factor 7: Expected Utility Scale
        u_scale = np.clip(0.5 + top_1.expected_utility * 0.1, 0.5, 1.2)

        # Factor 8: Confidence Gate Indicator
        i_gated = 1.0

        # Multiplicative Capital Allocation Fraction
        f_alloc = float(
            f_kelly
            * c_pred
            * h_score
            * dd_factor
            * m_regime
            * vol_ratio
            * u_scale
            * i_gated
        )
        f_alloc = float(np.clip(f_alloc, 0.0, 0.25))

        target_cap = self.capital * f_alloc

        # Lot Calculation
        max_loss_per_lot = (
            top_1.capital_required if top_1.capital_required > 0 else 10000.0
        )
        raw_lots = int(target_cap / max_loss_per_lot) if max_loss_per_lot > 0 else 0

        # Hard Risk Caps
        max_loss_cap = self.capital * self.MAX_CAPITAL_LOSS_PCT
        cap_lots = int(max_loss_cap / max_loss_per_lot) if max_loss_per_lot > 0 else 0

        # If even 1 lot exceeds the 2.0% risk cap, set lots to 0 (Risk Budget Violation)
        if cap_lots == 0:
            final_lots = 0
            f_alloc = 0.0
            gated = True
        else:
            final_lots = int(min(raw_lots, cap_lots, self.HARD_LOT_CAP))
            final_lots = max(0, final_lots)
            gated = False

        max_trade_loss = final_lots * max_loss_per_lot

        factor_breakdown = {
            "f_kelly": round(f_kelly, 4),
            "c_pred": round(c_pred, 4),
            "h_score": round(h_score, 4),
            "dd_factor": round(dd_factor, 4),
            "m_regime": round(m_regime, 4),
            "vol_ratio": round(vol_ratio, 4),
            "u_scale": round(u_scale, 4),
            "i_gated": round(i_gated, 4),
            "f_alloc": round(f_alloc, 4),
        }

        return SizingResult(
            allocated_fraction=round(f_alloc, 4),
            target_capital_inr=round(target_cap, 2),
            recommended_lots=final_lots,
            raw_lots=raw_lots,
            confidence_gated=False,
            max_loss_per_lot=round(max_loss_per_lot, 2),
            max_trade_loss_inr=round(max_trade_loss, 2),
            factor_breakdown=factor_breakdown,
        )
