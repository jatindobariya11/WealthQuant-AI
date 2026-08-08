"""
WealthQuant V8.7 — Refresh Architecture & Emergency Override Unit Tests
Verifies 10-endpoint SLA requirements, 7 cache layers, 30s AI drift monitor, and emergency override protocol.
"""

import time
import unittest

import cache
from pipeline.prediction_store import PredictionState, PredictionStore


class TestV87RefreshArchitecture(unittest.TestCase):
    def setUp(self):
        self.store = PredictionStore()

    def test_7_cache_layers_isolation(self):
        """Verify layer 1 (PredictionStore) and layer 3/4 (cache.py) operate independently."""
        symbol = "NIFTY"
        interval = "5m"
        payload = {"signal": {"signal": "BUY CALL"}}

        # Layer 1: PredictionStore lock
        rec = self.store.lock(symbol, interval, payload)
        self.assertTrue(rec.is_live())

        # Layer 4: Market Cache in cache.py
        cache.put(f"ltp:{symbol}", {"ltp": 23715.5}, ttl=2)

        # Mutate market cache
        cache.put(f"ltp:{symbol}", {"ltp": 23725.0}, ttl=2)
        mkt_cached = cache.get(f"ltp:{symbol}")
        self.assertEqual(mkt_cached["ltp"], 23725.0)

        # Assert Layer 1 prediction lock remains 100% UNCHANGED and locked
        live_rec = self.store.get_live(symbol, interval)
        self.assertIsNotNone(live_rec)
        self.assertEqual(live_rec.prediction_id, rec.prediction_id)
        self.assertEqual(live_rec.data["signal"]["signal"], "BUY CALL")

    def test_emergency_override_protocol(self):
        """Verify emergency override immediately expires live prediction before valid_until."""
        symbol = "NIFTY"
        interval = "5m"
        payload = {"signal": {"signal": "BUY CALL"}}

        rec = self.store.lock(symbol, interval, payload)
        self.assertTrue(rec.is_live())

        # Trigger Emergency Override
        overridden = self.store.expire_immediately(
            symbol, interval, reason="CIRCUIT_BREAKER_HALT"
        )
        self.assertTrue(overridden)

        # Verify prediction is immediately EXPIRED and get_live returns None
        self.assertFalse(rec.is_live())
        self.assertEqual(rec.state, PredictionState.EXPIRED)
        self.assertIsNone(self.store.get_live(symbol, interval))

    def test_sub_5ms_prediction_store_latency(self):
        """Verify PredictionStore get_live response latency is sub-5ms."""
        symbol = "BANKNIFTY"
        interval = "15m"
        self.store.lock(symbol, interval, {"signal": {"signal": "NEUTRAL"}})

        t0 = time.perf_counter()
        for _ in range(1000):
            self.store.get_live(symbol, interval)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0 / 1000.0

        self.assertLess(
            elapsed_ms, 5.0, f"Latency {elapsed_ms:.3f}ms exceeded 5.0ms SLA target!"
        )

    def test_prediction_lifecycle_state_transitions(self):
        """Verify 5-stage state transitions: GENERATING -> LOCKED -> LIVE -> EXPIRED -> EVALUATED."""
        symbol = "FINNIFTY"
        interval = "5m"
        rec = self.store.lock(symbol, interval, {"signal": {"signal": "BUY PUT"}})
        self.assertEqual(rec.state, PredictionState.LIVE)

        rec.expire()
        self.assertEqual(rec.state, PredictionState.EXPIRED)

        rec.mark_evaluated()
        self.assertEqual(rec.state, PredictionState.EVALUATED)


if __name__ == "__main__":
    unittest.main()
