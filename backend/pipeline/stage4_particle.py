"""
Stage 4: Particle Filter (Sequential Monte Carlo).
Non-linear state estimation using a mixture of market dynamics and Student-t likelihood.
"""

import logging

import numpy as np

import pipeline.utils.distributions as dist_utils
from pipeline.base import MarketSnapshot, ParticleOutput, PipelineStage
from pipeline.config import PARTICLE_CONFIG

logger = logging.getLogger("pipeline.particle")


class Stage4Particle(PipelineStage):
    @property
    def name(self) -> str:
        return "particle"

    def process(self, snapshot: MarketSnapshot) -> ParticleOutput:
        """
        Run Sequential Monte Carlo estimation over the price series.
        """
        df = snapshot.ohlcv
        if df is None or df.empty or len(df) < 5:
            raise ValueError("Insufficient price data in snapshot for Particle Filter")

        close_series = df["close"].values
        n_bars = len(close_series)

        # ─── Configuration ────────────────────────────────────────────────────
        N = PARTICLE_CONFIG.get("n_particles", 1000)
        resample_threshold = PARTICLE_CONFIG.get("resample_threshold", 0.5)
        decay = PARTICLE_CONFIG.get("trend_momentum_decay", 0.95)
        theta = PARTICLE_CONFIG.get("mean_reversion_theta", 0.1)
        jump_prob = PARTICLE_CONFIG.get("jump_probability", 0.01)
        jump_mean = PARTICLE_CONFIG.get("jump_mean", 0.0)
        jump_std = PARTICLE_CONFIG.get("jump_std", 0.02)
        obs_df = PARTICLE_CONFIG.get("obs_df", 5)
        # Estimate parameters from data
        returns = np.diff(close_series)
        historical_std = np.std(returns) if len(returns) > 0 else 0.01

        # Scale observation noise to the actual volatility
        obs_scale = max(historical_std, 0.1)

        # Scaling noise parameters to historical volatility
        std_trend = max(1e-4, historical_std * 0.8)
        std_mom = max(1e-5, std_trend * 0.1)
        std_mr = max(1e-4, historical_std * 0.8)
        std_vol = max(1e-4, historical_std * 1.5)

        # Mean reversion target
        mean_target = np.mean(close_series)

        # ─── Stateful Caching & Incremental Update ────────────────────────────
        symbol = snapshot.symbol.upper()
        is_incremental = False
        if hasattr(self, "_last_state") and self._last_state is not None:
            ls = self._last_state
            if ls["symbol"] == symbol and n_bars == ls["last_len"] + 1:
                is_incremental = True

        if is_incremental:
            ls = self._last_state
            prices = ls["prices"]
            momenta = ls["momenta"]
            weights = ls["weights"]
            mean_target = ls["mean_target"]
            obs_scale = ls["obs_scale"]
            std_trend = ls["std_trend"]
            std_mom = ls["std_mom"]
            std_mr = ls["std_mr"]
            std_vol = ls["std_vol"]

            # Predict and update for the single new bar (close_series[-1])
            z = close_series[-1]

            # 1. Predict
            rand = np.random.rand(N)
            choices = np.zeros(N, dtype=int)
            choices[(rand >= 0.4) & (rand < 0.8)] = 1
            choices[rand >= 0.8] = 2

            idx_trend = choices == 0
            n_trend = np.sum(idx_trend)
            if n_trend > 0:
                prices[idx_trend] += momenta[idx_trend] + np.random.normal(
                    0.0, std_trend, size=n_trend
                )
                momenta[idx_trend] = decay * momenta[idx_trend] + np.random.normal(
                    0.0, std_mom, size=n_trend
                )

            idx_mr = choices == 1
            n_mr = np.sum(idx_mr)
            if n_mr > 0:
                prices[idx_mr] += theta * (
                    mean_target - prices[idx_mr]
                ) + np.random.normal(0.0, std_mr, size=n_mr)
                momenta[idx_mr] = 0.0

            idx_vol = choices == 2
            n_vol = np.sum(idx_vol)
            if n_vol > 0:
                prices[idx_vol] += np.random.normal(0.0, std_vol, size=n_vol)
                momenta[idx_vol] = 0.0
                jumps = np.random.rand(n_vol) < jump_prob
                if np.sum(jumps) > 0:
                    prices[idx_vol][jumps] += np.random.normal(
                        jump_mean, jump_std, size=np.sum(jumps)
                    )

            # 2. Update
            likelihoods = (1.0 + ((z - prices) / obs_scale) ** 2 / obs_df) ** (
                -(obs_df + 1) / 2
            )
            weights *= likelihoods
            sum_weights = np.sum(weights)
            if sum_weights < 1e-15:
                weights = np.ones(N) / N
            else:
                weights /= sum_weights

            # 3. Resample
            ess = dist_utils.effective_sample_size(weights)
            if ess < resample_threshold * N:
                cum_w = np.cumsum(weights)
                u = (np.arange(N) + np.random.rand()) / N
                idx = np.searchsorted(cum_w, u)
                prices = prices[idx]
                momenta = momenta[idx]
                weights = np.ones(N) / N

            # Update cache
            self._last_state = {
                "symbol": symbol,
                "last_len": n_bars,
                "prices": prices,
                "momenta": momenta,
                "weights": weights,
                "mean_target": mean_target,
                "obs_scale": obs_scale,
                "std_trend": std_trend,
                "std_mom": std_mom,
                "std_mr": std_mr,
                "std_vol": std_vol,
            }
        else:
            # Run the filter loop from scratch
            prices = np.random.normal(close_series[0], obs_scale, N)
            momenta = np.random.normal(0.0, obs_scale * 0.1, N)
            weights = np.ones(N) / N

            for t in range(n_bars):
                z = close_series[t]

                rand = np.random.rand(N)
                choices = np.zeros(N, dtype=int)
                choices[(rand >= 0.4) & (rand < 0.8)] = 1
                choices[rand >= 0.8] = 2

                idx_trend = choices == 0
                n_trend = np.sum(idx_trend)
                if n_trend > 0:
                    prices[idx_trend] += momenta[idx_trend] + np.random.normal(
                        0.0, std_trend, size=n_trend
                    )
                    momenta[idx_trend] = decay * momenta[idx_trend] + np.random.normal(
                        0.0, std_mom, size=n_trend
                    )

                idx_mr = choices == 1
                n_mr = np.sum(idx_mr)
                if n_mr > 0:
                    prices[idx_mr] += theta * (
                        mean_target - prices[idx_mr]
                    ) + np.random.normal(0.0, std_mr, size=n_mr)
                    momenta[idx_mr] = 0.0

                idx_vol = choices == 2
                n_vol = np.sum(idx_vol)
                if n_vol > 0:
                    prices[idx_vol] += np.random.normal(0.0, std_vol, size=n_vol)
                    momenta[idx_vol] = 0.0
                    jumps = np.random.rand(n_vol) < jump_prob
                    if np.sum(jumps) > 0:
                        prices[idx_vol][jumps] += np.random.normal(
                            jump_mean, jump_std, size=np.sum(jumps)
                        )

                likelihoods = (1.0 + ((z - prices) / obs_scale) ** 2 / obs_df) ** (
                    -(obs_df + 1) / 2
                )
                weights *= likelihoods
                sum_weights = np.sum(weights)

                if sum_weights < 1e-15:
                    weights = np.ones(N) / N
                else:
                    weights /= sum_weights

                ess = dist_utils.effective_sample_size(weights)
                if ess < resample_threshold * N:
                    cum_w = np.cumsum(weights)
                    u = (np.arange(N) + np.random.rand()) / N
                    idx = np.searchsorted(cum_w, u)

                    prices = prices[idx]
                    momenta = momenta[idx]
                    weights = np.ones(N) / N

            # Save state cache
            self._last_state = {
                "symbol": symbol,
                "last_len": n_bars,
                "prices": prices,
                "momenta": momenta,
                "weights": weights,
                "mean_target": mean_target,
                "obs_scale": obs_scale,
                "std_trend": std_trend,
                "std_mom": std_mom,
                "std_mr": std_mr,
                "std_vol": std_vol,
            }

        # ─── Compute Output Statistics ────────────────────────────────────────
        mean_p = dist_utils.weighted_mean(prices, weights)
        std_p = dist_utils.weighted_std(prices, weights)
        skew = dist_utils.weighted_skewness(prices, weights)
        kurt = dist_utils.weighted_kurtosis(prices, weights)

        pct_levels = [5.0, 10.0, 25.0, 50.0, 75.0, 90.0, 95.0]
        pcts = dist_utils.weighted_percentile(prices, weights, pct_levels)

        # Calculate tail risks based on z-score distance of the current observation
        tail_risk_left = float(np.sum(weights[prices < mean_p - 2.0 * std_p]))
        tail_risk_right = float(np.sum(weights[prices > mean_p + 2.0 * std_p]))

        bimodality = dist_utils.bimodality_coefficient(prices, weights)

        return ParticleOutput(
            mean_price=float(mean_p),
            median_price=float(pcts[50.0]),
            std_price=float(std_p),
            skewness=float(skew),
            kurtosis=float(kurt),
            percentiles={str(int(k)): float(v) for k, v in pcts.items()},
            effective_sample_size=float(ess),
            bimodality_score=float(bimodality),
            tail_risk_left=float(tail_risk_left),
            tail_risk_right=float(tail_risk_right),
            price_distribution=prices,
            weights=weights,
            timestamp=snapshot.timestamp,
        )
