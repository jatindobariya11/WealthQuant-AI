"""
Probability distribution helper functions.
Used by Particle Filter, Bayesian Fusion, and Probability Engine.
"""

import numpy as np
from scipy import stats
from scipy.special import expit  # sigmoid


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    """Weighted mean of values."""
    w = weights / weights.sum()
    return float(np.dot(w, values))


def weighted_std(values: np.ndarray, weights: np.ndarray) -> float:
    """Weighted standard deviation."""
    w = weights / weights.sum()
    mu = np.dot(w, values)
    return float(np.sqrt(np.dot(w, (values - mu) ** 2)))


def weighted_percentile(
    values: np.ndarray, weights: np.ndarray, percentiles: list[float]
) -> dict[float, float]:
    """Weighted percentiles using interpolation."""
    idx = np.argsort(values)
    sorted_vals = values[idx]
    sorted_weights = weights[idx]
    cum_weights = np.cumsum(sorted_weights)
    cum_weights /= cum_weights[-1]  # normalize to [0, 1]

    result = {}
    for p in percentiles:
        q = p / 100.0 if p > 1 else p
        i = np.searchsorted(cum_weights, q)
        i = min(i, len(sorted_vals) - 1)
        result[p] = float(sorted_vals[i])
    return result


def weighted_skewness(values: np.ndarray, weights: np.ndarray) -> float:
    """Weighted Fisher skewness."""
    w = weights / weights.sum()
    mu = np.dot(w, values)
    sigma = np.sqrt(np.dot(w, (values - mu) ** 2))
    if sigma < 1e-12:
        return 0.0
    m3 = np.dot(w, ((values - mu) / sigma) ** 3)
    return float(m3)


def weighted_kurtosis(values: np.ndarray, weights: np.ndarray) -> float:
    """Weighted excess kurtosis."""
    w = weights / weights.sum()
    mu = np.dot(w, values)
    sigma = np.sqrt(np.dot(w, (values - mu) ** 2))
    if sigma < 1e-12:
        return 0.0
    m4 = np.dot(w, ((values - mu) / sigma) ** 4)
    return float(m4 - 3.0)  # excess kurtosis


def effective_sample_size(weights: np.ndarray) -> float:
    """Effective sample size (ESS) of weighted particles.
    ESS = 1 / Σ(w_i²) where w_i are normalized weights.
    ESS close to N means diverse particles; ESS close to 1 means degeneracy.
    """
    w = weights / weights.sum()
    return float(1.0 / np.sum(w**2))


def kde_density(
    values: np.ndarray,
    weights: np.ndarray,
    bins: np.ndarray,
    bandwidth: str = "silverman",
) -> np.ndarray:
    """Weighted Kernel Density Estimation on given bin points.

    Uses Gaussian KDE with Scott/Silverman bandwidth selection.
    Returns density values at each bin point.
    """
    if len(values) < 5:
        # Too few points — return uniform
        return np.ones_like(bins) / len(bins)

    try:
        # Standard deviation of values
        w = weights / (weights.sum() + 1e-30)
        mu = np.dot(w, values)
        std = np.sqrt(np.dot(w, (values - mu) ** 2))
        std = max(std, 1e-6)

        # Silverman's / Scott's rule of thumb for bandwidth
        n = len(values)
        if bandwidth == "silverman":
            h = std * (4.0 * (std**5) / (3.0 * n)) ** 0.2
        else:  # Scott's rule
            h = std * n ** (-0.2)

        h = max(h, 1e-5)

        # Vectorized evaluation: (n_bins, n_values)
        diff = (bins[:, None] - values[None, :]) / h
        kernels = np.exp(-0.5 * diff**2) / (h * np.sqrt(2.0 * np.pi))

        # Weighted sum over values axis (axis=1)
        density = np.dot(kernels, weights)

        # Normalize to sum to 1 (approximate integral)
        bin_width = bins[1] - bins[0] if len(bins) > 1 else 1.0
        density = density / (density.sum() * bin_width + 1e-12)
        return density
    except Exception:
        # Fallback: histogram
        counts, _ = np.histogram(values, bins=len(bins), weights=weights, density=True)
        if len(counts) == len(bins) - 1:
            counts = np.append(counts, counts[-1])
        return counts


def bimodality_coefficient(values: np.ndarray, weights: np.ndarray = None) -> float:
    """Sarle's bimodality coefficient.

    BC = (γ² + 1) / (κ + 3 · (n-1)²/((n-2)(n-3)))

    BC > 0.555 suggests bimodality (multi-modal distribution).
    Returns value in [0, 1].
    """
    n = len(values)
    if n < 4:
        return 0.0

    if weights is not None:
        skew = weighted_skewness(values, weights)
        kurt = weighted_kurtosis(values, weights)
    else:
        skew = float(stats.skew(values))
        kurt = float(stats.kurtosis(values))  # excess

    numerator = skew**2 + 1
    denominator = kurt + 3 * ((n - 1) ** 2) / ((n - 2) * (n - 3))

    if abs(denominator) < 1e-12:
        return 0.0

    bc = numerator / denominator
    return float(np.clip(bc, 0.0, 1.0))


def discretize_distribution(
    values: np.ndarray,
    weights: np.ndarray,
    n_bins: int = 200,
    range_pct: tuple = (-0.10, 0.10),
) -> tuple[np.ndarray, np.ndarray]:
    """Convert weighted particles into a discretized PDF.

    Returns:
        bins: bin centers (return values)
        density: probability density at each bin
    """
    bins = np.linspace(range_pct[0], range_pct[1], n_bins)
    density = kde_density(values, weights, bins)
    return bins, density


def combine_distributions_log_pool(
    distributions: list[np.ndarray],
    weights: list[float],
) -> np.ndarray:
    """Logarithmic Opinion Pool — combine distributions via weighted log.

    log p_fused(y) = Σ w_m · log p_m(y) - log Z

    Args:
        distributions: list of density arrays (same shape)
        weights: model weights (sum to 1)

    Returns:
        fused density array (normalized)
    """
    if not distributions:
        return np.array([])

    weights = np.array(weights)
    weights = weights / weights.sum()

    # Work in log space for numerical stability
    log_densities = []
    for d in distributions:
        d_safe = np.maximum(d, 1e-30)  # avoid log(0)
        log_densities.append(np.log(d_safe))

    log_fused = np.zeros_like(log_densities[0])
    for w, logd in zip(weights, log_densities):
        log_fused += w * logd

    # Normalize
    log_fused -= log_fused.max()  # numerical stability
    fused = np.exp(log_fused)
    fused = fused / (fused.sum() + 1e-30)

    return fused


class PlattCalibrator:
    """Platt scaling for probability calibration.

    Fits sigmoid: P_calibrated = sigmoid(a * P_raw + b)
    using historical predicted vs actual outcomes.
    """

    def __init__(self):
        self.a = 1.0
        self.b = 0.0
        self.is_fitted = False
        self._predictions = []
        self._outcomes = []

    def update(self, predicted_prob: float, actual_outcome: bool):
        """Add a prediction-outcome pair."""
        self._predictions.append(predicted_prob)
        self._outcomes.append(float(actual_outcome))

        # Re-fit periodically
        if len(self._predictions) >= 20 and len(self._predictions) % 10 == 0:
            self._fit()

    def _to_log_odds(self, p_array: np.ndarray) -> np.ndarray:
        p_clipped = np.clip(p_array, 1e-12, 1.0 - 1e-12)
        return np.log(p_clipped / (1.0 - p_clipped))

    def _fit(self):
        """Fit Platt scaling parameters via logistic regression."""
        preds = np.array(self._predictions[-200:])  # use last 200
        outcomes = np.array(self._outcomes[-200:])

        if len(np.unique(outcomes)) < 2:
            return  # need both classes

        # Convert predictions to log-odds
        preds_log_odds = self._to_log_odds(preds)

        # Simple grid search for a, b (avoid scipy dependency for this)
        best_loss = float("inf")
        best_a, best_b = 1.0, 0.0

        for a in np.linspace(0.5, 3.0, 20):
            for b in np.linspace(-1.0, 1.0, 20):
                calibrated = expit(a * preds_log_odds + b)
                # Binary cross-entropy loss
                loss = -np.mean(
                    outcomes * np.log(calibrated + 1e-10)
                    + (1 - outcomes) * np.log(1 - calibrated + 1e-10)
                )
                if loss < best_loss:
                    best_loss = loss
                    best_a, best_b = a, b

        self.a = best_a
        self.b = best_b
        self.is_fitted = True

    def calibrate(self, raw_prob: float) -> float:
        """Apply Platt scaling to a raw probability."""
        if not self.is_fitted:
            return raw_prob

        p_clipped = max(1e-12, min(1.0 - 1e-12, raw_prob))
        log_odds = float(np.log(p_clipped / (1.0 - p_clipped)))
        return float(expit(self.a * log_odds + self.b))

    @property
    def n_samples(self) -> int:
        return len(self._predictions)
