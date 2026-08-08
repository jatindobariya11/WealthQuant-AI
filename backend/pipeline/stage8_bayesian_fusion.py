"""
Stage 8: Bayesian Fusion.
Fuses predictive distributions from Hawkes, Kalman, Particle, and Ensemble/Meta stages using a Logarithmic Opinion Pool.
"""

import logging

import numpy as np
from scipy import stats

import pipeline.utils.distributions as dist_utils
from pipeline.base import (
    FusionOutput,
    HawkesOutput,
    InstitutionalOutput,
    KalmanOutput,
    MetaLearningOutput,
    ParticleOutput,
    PipelineStage,
    RegimeOutput,
)
from pipeline.config import FUSION_CONFIG

logger = logging.getLogger("pipeline.bayesian_fusion")


def safe_normalize(pdf: np.ndarray) -> np.ndarray:
    """Safely normalize a probability density function to sum to 1.0."""
    if pdf is None:
        return np.array([])
    # Handle NaNs or Infs
    if np.any(np.isnan(pdf)) or np.any(np.isinf(pdf)):
        pdf = np.nan_to_num(pdf, nan=0.0, posinf=0.0, neginf=0.0)

    s = pdf.sum()
    if s > 1e-15:
        return pdf / s
    else:
        # Uniform fallback
        return np.ones_like(pdf) / len(pdf)


class Stage8BayesianFusion(PipelineStage):
    @property
    def name(self) -> str:
        return "bayesian_fusion"

    def process(
        self,
        snapshot_price: float,
        hawkes: HawkesOutput,
        kalman: KalmanOutput,
        particle: ParticleOutput,
        meta_learning: MetaLearningOutput,
        regime: RegimeOutput,
        institutional: InstitutionalOutput = None,
    ) -> FusionOutput:
        """
        Combine upstream stage forecasts into a single coherent probability distribution.
        """
        if institutional is None:
            institutional = InstitutionalOutput()

        n_bins = FUSION_CONFIG.get("n_bins", 200)
        ret_range = FUSION_CONFIG.get("return_range", (-0.10, 0.10))
        bins = np.linspace(ret_range[0], ret_range[1], n_bins)

        # Current price to normalize inputs
        price = max(1.0, snapshot_price)

        # ─── 1. Build Discretized PDFs for each Model ────────────────────────
        distributions = []

        # A. Hawkes (Volatility/Excitation scaling)
        # Hawkes doesn't predict directional mean, but models tail fatness from intensity
        h_mean = 0.0
        h_std = max(0.005, 0.01 * hawkes.excitation_ratio)
        h_pdf = stats.norm.pdf(bins, loc=h_mean, scale=h_std)
        h_pdf = safe_normalize(h_pdf)
        distributions.append(h_pdf)

        # B. Kalman Filter (Gaussian Return Forecast)
        # Kalman mean for 5-bar horizon: estimated velocity * 5 / current price
        k_mean = (kalman.estimated_velocity * 5.0) / price
        k_std = max(0.001, (kalman.price_uncertainty * np.sqrt(5.0)) / price)
        k_pdf = stats.norm.pdf(bins, loc=k_mean, scale=k_std)
        k_pdf = safe_normalize(k_pdf)
        distributions.append(k_pdf)

        # C. Particle Filter (Non-linear Return Forecast)
        if particle.price_distribution is not None and particle.weights is not None:
            # Convert particle prices to returns
            p_returns = (particle.price_distribution - price) / price
            p_pdf = dist_utils.kde_density(p_returns, particle.weights, bins)
            p_pdf = safe_normalize(p_pdf)
        else:
            p_mean = (particle.mean_price - price) / price
            p_std = max(0.001, particle.std_price / price)
            p_pdf = stats.norm.pdf(bins, loc=p_mean, scale=p_std)
            p_pdf = safe_normalize(p_pdf)
        distributions.append(p_pdf)

        # D. Ensemble / Meta (Quantile Forecasts Return)
        # Use default horizon 5 forecast
        fc = meta_learning.adapted_forecasts.get(5)
        if fc:
            e_mean = fc.q50
            # For a normal distribution, q90 - q10 is approx 2.56 * std
            e_std = max(0.001, (fc.q90 - fc.q10) / 2.56)
            e_pdf = stats.norm.pdf(bins, loc=e_mean, scale=e_std)
            e_pdf = safe_normalize(e_pdf)
        else:
            e_pdf = k_pdf  # fallback
        distributions.append(e_pdf)

        # E. Institutional Positioning (Gaussian Return Forecast)
        i_mean = institutional.forecast
        # Standard deviation scales inversely to confidence
        i_std = max(0.001, 0.015 * (1.0 - institutional.confidence))
        i_pdf = stats.norm.pdf(bins, loc=i_mean, scale=i_std)
        i_pdf = safe_normalize(i_pdf)
        distributions.append(i_pdf)

        # ─── 2. Retrieve Bayesian Fusion Weights ──────────────────────────────
        current_regime = regime.current_regime
        regime_weights = FUSION_CONFIG.get("regime_weights", {}).get(
            current_regime, FUSION_CONFIG["initial_weights"]
        )

        # Build weights list aligned with distributions
        weights = [
            regime_weights.get("hawkes", 0.10),
            regime_weights.get("kalman", 0.15),
            regime_weights.get("particle", 0.15),
            regime_weights.get("ensemble", 0.60),  # ensemble + meta combined
            regime_weights.get("institutional", 0.0),  # default is 0.0 (disabled)
        ]

        # Normalize weights
        w_sum = sum(weights)
        weights = [w / w_sum for w in weights]

        # ─── 3. Logarithmic Opinion Pool Fusion ──────────────────────────────
        fused_pdf = dist_utils.combine_distributions_log_pool(distributions, weights)

        # ─── 4. Compute Agreement & Conflict Metrics ──────────────────────────
        # Each model votes direction based on its mean return
        votes = [
            0,  # Hawkes is neutral
            1 if k_mean > 0.0005 else -1 if k_mean < -0.0005 else 0,
            1
            if (particle.mean_price - price) > 0.0005 * price
            else -1
            if (particle.mean_price - price) < -0.0005 * price
            else 0,
            1
            if (fc.q50 if fc else 0) > 0.0005
            else -1
            if (fc.q50 if fc else 0) < -0.0005
            else 0,
            1 if i_mean > 0.0005 else -1 if i_mean < -0.0005 else 0,
        ]

        # Remove neutral votes for agreement calculation
        active_votes = [v for v in votes if v != 0]
        if active_votes:
            pos_votes = sum(1 for v in active_votes if v > 0)
            neg_votes = sum(1 for v in active_votes if v < 0)
            agreement = max(pos_votes, neg_votes) / len(active_votes)
        else:
            agreement = 1.0

        threshold = FUSION_CONFIG.get("agreement_threshold", 0.6)
        conflict_alert = agreement < threshold

        # Determine dominant model
        weights_dict = {
            "hawkes": weights[0],
            "kalman": weights[1],
            "particle": weights[2],
            "ensemble": weights[3],
            "institutional": weights[4],
        }
        dominant_model = max(weights_dict, key=weights_dict.get)

        # ─── 5. Fused Distribution Statistics ─────────────────────────────────
        fused_mean = float(np.sum(bins * fused_pdf))
        fused_std = float(np.sqrt(np.sum(((bins - fused_mean) ** 2) * fused_pdf)))
        fused_skew = float(
            np.sum(((bins - fused_mean) ** 3) * fused_pdf) / (fused_std**3 + 1e-12)
        )

        # Information ratio of fused signal
        info_ratio = fused_mean / fused_std if fused_std > 0 else 0.0

        return FusionOutput(
            fused_mean=float(fused_mean),
            fused_std=float(fused_std),
            fused_skew=float(fused_skew),
            model_weights=weights_dict,
            model_agreement=float(agreement),
            conflict_alert=bool(conflict_alert),
            dominant_model=dominant_model,
            regime_weight_profile=regime_weights,
            information_ratio=float(info_ratio),
            historical_accuracy={},
            fused_distribution=fused_pdf,
            return_bins=bins,
            timestamp=regime.timestamp,
        )
