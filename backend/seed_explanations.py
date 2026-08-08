import asyncio
import os
import sys
from datetime import datetime, timedelta

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ["PG_HOST"] = "127.0.0.1"
from pipeline.db import pipeline_db


async def seed():
    await pipeline_db.init_pool()
    if not pipeline_db.pool:
        print("DB pool connection failed")
        return

    np.random.seed(42)
    symbols = ["NIFTY", "BANKNIFTY"]

    async with pipeline_db.pool.acquire() as conn:
        for symbol in symbols:
            now = datetime.now()
            for i in range(50):
                ts = now - timedelta(minutes=15 * (50 - i))
                spot = 24400.0 if symbol == "NIFTY" else 51200.0
                p_up = float(np.clip(np.random.normal(0.5, 0.15), 0.1, 0.9))
                p_down = float(
                    np.clip(1.0 - p_up - np.random.uniform(0.05, 0.15), 0.05, 0.8)
                )
                actual_ret = float(
                    np.random.normal(0.001 if p_up > 0.5 else -0.001, 0.008)
                )
                correct = (
                    (p_up > 0.5 and actual_ret > 0.005)
                    or (p_down > 0.5 and actual_ret < -0.005)
                    or (abs(actual_ret) <= 0.005)
                )

                await conn.execute(
                    """
                    INSERT INTO signal_explanations (
                        symbol, timestamp, spot_price, hawkes_score, kalman_velocity,
                        particle_mean, regime_state, ensemble_prediction, meta_learning_weight,
                        fusion_mean, p_up, p_down, expected_return, kelly_fraction, signal,
                        signal_confidence, actual_return, correct
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18
                    ) ON CONFLICT (symbol, timestamp) DO UPDATE SET
                        actual_return = EXCLUDED.actual_return,
                        correct = EXCLUDED.correct,
                        p_up = EXCLUDED.p_up,
                        p_down = EXCLUDED.p_down
                """,
                    symbol,
                    ts,
                    spot,
                    0.1,
                    0.05,
                    spot,
                    "TRANSITION",
                    0.002 if p_up > 0.5 else -0.002,
                    0.8,
                    0.001,
                    p_up,
                    p_down,
                    actual_ret,
                    0.05,
                    "BUY" if p_up > 0.5 else "NEUTRAL",
                    0.8,
                    actual_ret,
                    correct,
                )

    print("Successfully seeded 50 calibration records for NIFTY and BANKNIFTY.")
    await pipeline_db.close()


if __name__ == "__main__":
    asyncio.run(seed())
