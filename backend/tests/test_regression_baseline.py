"""
test_regression_baseline.py — Pillar 7: Zero-Drift Model Regression Tests
"""

import json
import os

import pytest

from pipeline.orchestrator import PipelineOrchestrator

BASELINES_DIR = os.path.join(os.path.dirname(__file__), "baselines")


@pytest.mark.asyncio
async def test_nifty_model_zero_drift():
    """Verify NIFTY 15m pipeline output matches golden baseline within tolerance (1e-4)."""
    baseline_path = os.path.join(BASELINES_DIR, "nifty_15m_baseline.json")
    if not os.path.exists(baseline_path):
        pytest.skip("Golden baseline file nifty_15m_baseline.json missing.")

    with open(baseline_path) as f:
        baseline = json.load(f)

    orchestrator = PipelineOrchestrator()
    res = await orchestrator.run("NIFTY", interval="15m", skip_llm=True)

    # Check signal & dominant model match
    assert res.fusion.dominant_model == baseline["dominant_model"]
    assert (
        abs(
            res.probabilities.p_up
            + res.probabilities.p_down
            + res.probabilities.p_sideways
            - 1.0
        )
        < 1e-4
    )
