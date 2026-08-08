"""
WealthQuant V8.6 — Prediction Stability & Lock Validation Unit Tests
Verifies that locked predictions remain 100% stable across consecutive refreshes.
"""

import unittest
from datetime import datetime, timedelta

from pipeline.prediction_store import (
    PredictionState,
    PredictionStore,
    _next_candle_close,
    _now_ist,
)


class TestPredictionStability(unittest.TestCase):
    def setUp(self):
        self.store = PredictionStore()

    def test_candle_close_boundary_calculation(self):
        """Verify candle close boundary calculation for various intervals."""
        now = datetime(2026, 7, 24, 9, 17, 30)
        close_5m = _next_candle_close("5m", base_dt=now)
        self.assertEqual(close_5m, datetime(2026, 7, 24, 9, 20, 0))

        close_15m = _next_candle_close("15m", base_dt=now)
        self.assertEqual(close_15m, datetime(2026, 7, 24, 9, 30, 0))

        close_1h = _next_candle_close("1h", base_dt=now)
        self.assertEqual(close_1h, datetime(2026, 7, 24, 10, 0, 0))

    def test_100_consecutive_refreshes_stability(self):
        """Verify 100 consecutive queries return 100% identical prediction_id and signal data."""
        symbol = "NIFTY"
        interval = "5m"
        sample_payload = {
            "signal": {
                "signal": "BUY CALL",
                "confidence": {"score": 78.5},
                "entry": 23700.0,
                "stop_loss": 23650.0,
                "target1": 23800.0,
            },
            "quality": {"pct": 78.5, "grade": "Good Trade"},
            "regime": {"current": "TRENDING_BULL"},
        }

        # Lock prediction
        rec_initial = self.store.lock(symbol, interval, sample_payload)
        initial_id = rec_initial.prediction_id
        initial_valid_until = rec_initial.valid_until

        # Issue 100 consecutive reads
        for i in range(100):
            live_rec = self.store.get_live(symbol, interval)
            self.assertIsNotNone(live_rec, f"Refresh {i}: live_rec was None!")
            self.assertEqual(
                live_rec.prediction_id,
                initial_id,
                f"Refresh {i}: prediction_id changed!",
            )
            self.assertEqual(live_rec.valid_until, initial_valid_until)
            self.assertEqual(live_rec.data["signal"]["signal"], "BUY CALL")
            self.assertEqual(live_rec.data["signal"]["entry"], 23700.0)
            self.assertEqual(live_rec.data["signal"]["stop_loss"], 23650.0)
            self.assertEqual(live_rec.data["signal"]["target1"], 23800.0)

    def test_candle_expiration_transition(self):
        """Verify that crossing valid_until expires the prediction record."""
        symbol = "BANKNIFTY"
        interval = "5m"
        sample_payload = {"signal": {"signal": "BUY PUT"}}

        rec = self.store.lock(symbol, interval, sample_payload)
        self.assertTrue(rec.is_live())

        # Manually set valid_until to 1 second in the past (offset-aware IST)
        rec.valid_until = _now_ist() - timedelta(seconds=1)
        self.assertFalse(rec.is_live())

        # Query store again — should return None and expire record
        live_rec = self.store.get_live(symbol, interval)
        self.assertIsNone(live_rec)
        self.assertEqual(rec.state, PredictionState.EXPIRED)

    def test_store_statistics_tracking(self):
        """Verify hit ratio and statistics tracking in PredictionStore."""
        symbol = "FINNIFTY"
        interval = "15m"
        self.store.lock(symbol, interval, {"signal": {"signal": "NEUTRAL"}})

        # 5 hits
        for _ in range(5):
            self.store.get_live(symbol, interval)

        # 1 miss (different interval)
        self.store.get_live(symbol, "1h")

        stats = self.store.stats()
        self.assertEqual(stats["cache_hits"], 5)
        self.assertEqual(stats["cache_misses"], 1)
        self.assertGreater(stats["hit_ratio"], 0.8)


if __name__ == "__main__":
    unittest.main()
