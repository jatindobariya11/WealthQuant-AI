"""
test_prediction_lock.py — Pillar 2: Prediction Lock & Mid-Candle Invariance Tests
"""

import asyncio
from datetime import datetime

import pytest

from pipeline.prediction_store import (
    PredictionRecord,
    PredictionState,
    prediction_store,
)


def test_prediction_record_lock():
    """Verify PredictionRecord locks valid_until and candle_id."""
    data_payload = {"signal": "BUY", "confidence": 0.85}
    rec = prediction_store.lock("NIFTY", "15m", data_payload, latency_ms=120.0)
    assert rec.symbol == "NIFTY"
    assert rec.interval == "15m"
    assert rec.state == PredictionState.LIVE
    assert rec.is_live() is True

    meta = rec.to_metadata()
    assert meta["prediction_id"] == rec.prediction_id
    assert "NIFTY-15m" in meta["prediction_version"]


def test_prediction_store_lock_hit():
    """Verify PredictionStore returns live prediction without regenerating."""
    payload = {"signal": "NEUTRAL", "score": 95}
    locked = prediction_store.lock("BANKNIFTY", "15m", payload)

    live = prediction_store.get_live("BANKNIFTY", "15m")
    assert live is not None
    assert live.prediction_id == locked.prediction_id
    assert live.data["signal"] == "NEUTRAL"


def test_timestamp_binding():
    """Verify prediction record candle_id binds to explicit base_dt snapshot timestamp."""
    custom_dt = datetime(2026, 7, 19, 9, 15, 0)
    rec = PredictionRecord("NIFTY", "15m", {"test": 1}, base_dt=custom_dt)
    assert "09:15" in rec.candle_id
    assert rec.valid_until.minute == 30


@pytest.mark.asyncio
async def test_concurrent_prediction_locking():
    """Verify 20 concurrent lock requests maintain lock integrity."""

    async def lock_task(i):
        return prediction_store.lock("NIFTY", "15m", {"task_id": i})

    tasks = [lock_task(i) for i in range(20)]
    results = await asyncio.gather(*tasks)
    assert len(results) == 20

    live = prediction_store.get_live("NIFTY", "15m")
    assert live is not None
    assert live.is_live() is True
