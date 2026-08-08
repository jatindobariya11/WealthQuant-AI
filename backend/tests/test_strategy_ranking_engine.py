"""
WealthQuant V8.5 — Unit Test Suite for Strategy Ranking Engine & Position Sizer
Tests dynamic candidate generation, MCDA regime weights, Expected Utility,
Confidence Separation Gating (NO_TRADE fallback), and multi-factor position sizing.
"""

import unittest

import pandas as pd

from models.position_sizer import PositionSizer
from models.strategy_ranking_engine import (
    MarketRegime,
    StrategyRankingEngine,
    StrategyType,
)


class TestStrategyRankingEngine(unittest.TestCase):
    def setUp(self):
        self.engine = StrategyRankingEngine(underlying="NIFTY", capital=1_000_000.0)
        self.spot = 24000.0
        self.atm_iv = 0.15
        self.chain_df = pd.DataFrame(
            [
                {"strike": 24000.0, "option_type": "CE", "ltp": 250.0},
                {"strike": 24000.0, "option_type": "PE", "ltp": 220.0},
                {"strike": 24100.0, "option_type": "CE", "ltp": 180.0},
                {"strike": 23900.0, "option_type": "PE", "ltp": 160.0},
            ]
        )

    def test_expected_utility_calculation(self):
        u1 = self.engine.compute_expected_utility(
            ev=5000.0, sharpe=2.0, mdd=0.08, var_99=0.06, cost=150.0, liq=0.90
        )
        u2 = self.engine.compute_expected_utility(
            ev=1000.0, sharpe=0.5, mdd=0.25, var_99=0.20, cost=400.0, liq=0.40
        )

        self.assertGreater(u1, u2)

    def test_dominant_strategy_ranking(self):
        # Strong bull signal in BULL_TREND regime -> Should favor Bullish Strategy
        payload = self.engine.rank_and_gate_strategies(
            ensemble_prob=0.80,
            regime=MarketRegime.BULL_TREND,
            spot=self.spot,
            atm_iv=self.atm_iv,
            chain_df=self.chain_df,
        )

        self.assertIsNotNone(payload.top_1)
        self.assertFalse(payload.confidence_gated)
        self.assertIn(
            payload.recommended_strategy,
            [StrategyType.LONG_CALL, StrategyType.BULL_CALL_SPREAD],
        )
        self.assertGreaterEqual(payload.ranking_separation, 0.05)
        self.assertGreaterEqual(payload.ranking_confidence, 70.0)

    def test_confidence_gating_no_trade_fallback(self):
        # Neutral signal near 0.50 -> Should produce low separation and trigger NO_TRADE gate
        payload = self.engine.rank_and_gate_strategies(
            ensemble_prob=0.50,
            regime=MarketRegime.CHOPPY,
            spot=self.spot,
            atm_iv=self.atm_iv,
            chain_df=self.chain_df,
        )

        self.assertTrue(payload.confidence_gated)
        self.assertEqual(payload.recommended_strategy, StrategyType.NO_TRADE)
        self.assertEqual(payload.allocated_lots, 0)
        self.assertIsNotNone(payload.no_trade_reason)
        self.assertIn("Confidence Gating Triggered", payload.no_trade_reason)

    def test_position_sizer_gated_zero_allocation(self):
        sizer = PositionSizer(capital=1_000_000.0)

        # Test gated payload
        gated_payload = self.engine.rank_and_gate_strategies(
            ensemble_prob=0.50,
            regime=MarketRegime.CHOPPY,
            spot=self.spot,
            atm_iv=self.atm_iv,
            chain_df=self.chain_df,
        )
        res_gated = sizer.compute_position_size(gated_payload)

        self.assertTrue(res_gated.confidence_gated)
        self.assertEqual(res_gated.recommended_lots, 0)
        self.assertEqual(res_gated.allocated_fraction, 0.0)

    def test_position_sizer_valid_trade_allocation(self):
        sizer = PositionSizer(capital=1_000_000.0)

        # Test dominant payload
        active_payload = self.engine.rank_and_gate_strategies(
            ensemble_prob=0.85,
            regime=MarketRegime.BULL_TREND,
            spot=self.spot,
            atm_iv=self.atm_iv,
            chain_df=self.chain_df,
        )
        res_active = sizer.compute_position_size(active_payload)

        self.assertFalse(res_active.confidence_gated)
        self.assertGreater(res_active.recommended_lots, 0)
        self.assertLessEqual(res_active.recommended_lots, 10)
        self.assertLessEqual(res_active.max_trade_loss_inr, 1_000_000.0 * 0.02)


if __name__ == "__main__":
    unittest.main()
