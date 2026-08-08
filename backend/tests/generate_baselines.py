"""
generate_baselines.py — Generates golden reference baseline JSON files for model regression tests.
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pipeline.orchestrator import PipelineOrchestrator

BASELINES_DIR = os.path.join(os.path.dirname(__file__), "baselines")
os.makedirs(BASELINES_DIR, exist_ok=True)


async def generate_baselines():
    orchestrator = PipelineOrchestrator()
    print("Generating NIFTY 15m Golden Baseline...")
    res_nifty = await orchestrator.run("NIFTY", interval="15m", skip_llm=True)
    nifty_payload = {
        "symbol": "NIFTY",
        "interval": "15m",
        "hawkes_intensity": round(float(res_nifty.hawkes.get("intensity", 0)), 4),
        "kalman_price": round(float(res_nifty.kalman.get("price", 0)), 2),
        "regime": res_nifty.regime.current_regime,
        "signal": res_nifty.probabilities.signal,
        "signal_confidence": round(float(res_nifty.probabilities.signal_confidence), 4),
        "p_up": round(float(res_nifty.probabilities.p_up), 4),
        "p_down": round(float(res_nifty.probabilities.p_down), 4),
        "p_sideways": round(float(res_nifty.probabilities.p_sideways), 4),
        "expected_return": round(float(res_nifty.probabilities.expected_return), 4),
        "dominant_model": res_nifty.fusion.dominant_model,
    }

    nifty_path = os.path.join(BASELINES_DIR, "nifty_15m_baseline.json")
    with open(nifty_path, "w") as f:
        json.dump(nifty_payload, f, indent=2)
    print(f"Saved baseline to {nifty_path}")


if __name__ == "__main__":
    asyncio.run(generate_baselines())
