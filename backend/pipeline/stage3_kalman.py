"""
Stage 3: Kalman Filter.
Linear state estimation for true price, velocity (momentum), acceleration, and volatility.
"""

import logging

import numpy as np
import pandas as pd

from pipeline.base import KalmanOutput, MarketSnapshot, PipelineStage
from pipeline.config import KALMAN_CONFIG

logger = logging.getLogger("pipeline.kalman")


class Stage3Kalman(PipelineStage):
    @property
    def name(self) -> str:
        return "kalman"

    def process(self, snapshot: MarketSnapshot) -> KalmanOutput:
        """
        Run predict-update loop over historical series and estimate hidden states.
        """
        df = snapshot.ohlcv
        if df is None or df.empty or len(df) < 5:
            raise ValueError("Insufficient price data in snapshot for Kalman Filter")

        close_series = df["close"].values
        n_bars = len(close_series)

        # ─── Configuration ────────────────────────────────────────────────────
        dt = KALMAN_CONFIG.get("dt", 1.0)
        rho = KALMAN_CONFIG.get("volatility_mean_reversion", 0.95)
        long_run_vol_mean = KALMAN_CONFIG.get("volatility_long_run_mean", 0.02)

        # Process noise Q for price state
        q_p = KALMAN_CONFIG.get("process_noise_price", 0.01)
        q_v = KALMAN_CONFIG.get("process_noise_velocity", 0.05)
        q_a = KALMAN_CONFIG.get("process_noise_acceleration", 0.1)
        Q_price = np.diag([q_p, q_v, q_a])

        # Process noise Q for volatility state
        Q_vol = KALMAN_CONFIG.get("process_noise_volatility", 0.02)

        # Observation noise R
        source = snapshot.indicators.get("source", "default")
        R_price = KALMAN_CONFIG.get("obs_noise", {}).get(source, 0.01)

        # ─── Stateful Caching & Incremental Update ────────────────────────────
        symbol = snapshot.symbol.upper()
        is_incremental = False
        if hasattr(self, "_last_state") and self._last_state is not None:
            ls = self._last_state
            if ls["symbol"] == symbol and n_bars == ls["last_len"] + 1:
                is_incremental = True

        # Matrices
        F_price = np.array([[1.0, dt, 0.5 * dt**2], [0.0, 1.0, dt], [0.0, 0.0, 1.0]])
        H_price = np.array([[1.0, 0.0, 0.0]])

        if is_incremental:
            ls = self._last_state
            x_price = ls["x_price"]
            P_price = ls["P_price"]
            x_vol = ls["x_vol"]
            P_vol = ls["P_vol"]
            filtered_prices = ls["filtered_prices"]
            filtered_velocities = ls["filtered_velocities"]
            filtered_accelerations = ls["filtered_accelerations"]
            filtered_volatilities = ls["filtered_volatilities"]
            innovations = ls["innovations"]
            innovation_covariances = ls["innovation_covariances"]

            z_price = close_series[-1]

            # 1. Price Predict
            x_price_pred = F_price @ x_price
            P_price_pred = F_price @ P_price @ F_price.T + Q_price

            # 2. Price Update
            innovation = z_price - (H_price @ x_price_pred)[0]
            S = (H_price @ P_price_pred @ H_price.T)[0, 0] + R_price
            K = P_price_pred @ H_price.T / S

            x_price = x_price_pred + K.flatten() * innovation
            P_price = (np.eye(3) - K @ H_price) @ P_price_pred

            # 3. Volatility Predict & Update
            ret = np.log(close_series[-1] / close_series[-2])
            z_vol = np.log(ret**2 + 1e-8) + 1.27
            R_vol = 4.93

            x_vol_pred = rho * x_vol + (1.0 - rho) * np.log(long_run_vol_mean)
            P_vol_pred = (rho**2) * P_vol + Q_vol

            S_vol = P_vol_pred[0, 0] + R_vol
            K_vol = P_vol_pred[0, 0] / S_vol
            x_vol = x_vol_pred + K_vol * (z_vol - x_vol_pred[0])
            P_vol = np.array([[(1.0 - K_vol) * P_vol_pred[0, 0]]])

            filtered_prices.append(x_price[0])
            filtered_velocities.append(x_price[1])
            filtered_accelerations.append(x_price[2])
            filtered_volatilities.append(np.exp(x_vol[0]))
            innovations.append(innovation)
            innovation_covariances.append(S)

            self._last_state = {
                "symbol": symbol,
                "last_len": n_bars,
                "x_price": x_price,
                "P_price": P_price,
                "x_vol": x_vol,
                "P_vol": P_vol,
                "filtered_prices": filtered_prices,
                "filtered_velocities": filtered_velocities,
                "filtered_accelerations": filtered_accelerations,
                "filtered_volatilities": filtered_volatilities,
                "innovations": innovations,
                "innovation_covariances": innovation_covariances,
            }
        else:
            # Price state: [price, velocity, acceleration]
            x_price = np.array([close_series[0], 0.0, 0.0])
            P_price = np.eye(3) * 1.0

            # Volatility state: log-volatility
            init_vol = (
                np.std(np.diff(close_series[: min(10, n_bars)]))
                if n_bars > 1
                else long_run_vol_mean
            )
            x_vol = np.array([np.log(max(1e-5, init_vol))])
            P_vol = np.array([[1.0]])

            # Track filtered series
            filtered_prices = []
            filtered_velocities = []
            filtered_accelerations = []
            filtered_volatilities = []
            innovations = []
            innovation_covariances = []

            # ─── Filter Loop ──────────────────────────────────────────────────────
            for t in range(n_bars):
                z_price = close_series[t]

                # 1. Price Predict
                x_price_pred = F_price @ x_price
                P_price_pred = F_price @ P_price @ F_price.T + Q_price

                # 2. Price Update
                innovation = z_price - (H_price @ x_price_pred)[0]
                S = (H_price @ P_price_pred @ H_price.T)[0, 0] + R_price
                K = P_price_pred @ H_price.T / S

                x_price = x_price_pred + K.flatten() * innovation
                P_price = (np.eye(3) - K @ H_price) @ P_price_pred

                # 3. Volatility Predict & Update
                if t > 0:
                    ret = np.log(close_series[t] / close_series[t - 1])
                    z_vol = np.log(ret**2 + 1e-8) + 1.27
                    R_vol = 4.93

                    x_vol_pred = rho * x_vol + (1.0 - rho) * np.log(long_run_vol_mean)
                    P_vol_pred = (rho**2) * P_vol + Q_vol

                    S_vol = P_vol_pred[0, 0] + R_vol
                    K_vol = P_vol_pred[0, 0] / S_vol
                    x_vol = x_vol_pred + K_vol * (z_vol - x_vol_pred[0])
                    P_vol = np.array([[(1.0 - K_vol) * P_vol_pred[0, 0]]])

                filtered_prices.append(x_price[0])
                filtered_velocities.append(x_price[1])
                filtered_accelerations.append(x_price[2])
                filtered_volatilities.append(np.exp(x_vol[0]))
                innovations.append(innovation)
                innovation_covariances.append(S)

            self._last_state = {
                "symbol": symbol,
                "last_len": n_bars,
                "x_price": x_price,
                "P_price": P_price,
                "x_vol": x_vol,
                "P_vol": P_vol,
                "filtered_prices": filtered_prices,
                "filtered_velocities": filtered_velocities,
                "filtered_accelerations": filtered_accelerations,
                "filtered_volatilities": filtered_volatilities,
                "innovations": innovations,
                "innovation_covariances": innovation_covariances,
            }

        # ─── Output ───────────────────────────────────────────────────────────
        smoothed_series = pd.Series(filtered_prices, index=df.index)

        # Last step stats
        last_innovation = innovations[-1]
        last_S = innovation_covariances[-1]
        innovation_zscore = last_innovation / np.sqrt(last_S) if last_S > 0 else 0.0

        return KalmanOutput(
            filtered_price=float(x_price[0]),
            price_uncertainty=float(np.sqrt(P_price[0, 0])),
            estimated_velocity=float(x_price[1]),
            estimated_acceleration=float(x_price[2]),
            estimated_volatility=float(filtered_volatilities[-1]),
            innovation=float(last_innovation),
            innovation_zscore=float(innovation_zscore),
            kalman_gain=K,
            state_covariance=P_price,
            smoothed_series=smoothed_series,
            timestamp=snapshot.timestamp,
        )
