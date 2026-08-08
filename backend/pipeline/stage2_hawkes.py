"""
Stage 2: Hawkes Process.
Self-exciting point process to detect event clustering and cascade probabilities.
"""

import logging
from datetime import datetime

import numpy as np
from scipy.optimize import minimize

from pipeline.base import HawkesOutput, MarketSnapshot, PipelineStage
from pipeline.config import HAWKES_CONFIG

logger = logging.getLogger("pipeline.hawkes")


class Stage2Hawkes(PipelineStage):
    @property
    def name(self) -> str:
        return "hawkes"

    def process(self, snapshot: MarketSnapshot) -> HawkesOutput:
        """
        Estimate Hawkes process parameters and detect cascade probability.
        """
        events = snapshot.tick_events
        num_events = len(events)

        min_events = HAWKES_CONFIG.get("min_events", 10)
        max_events = HAWKES_CONFIG.get("max_events", 500)

        # Limit events to fit on last max_events
        if num_events > max_events:
            events = events[-max_events:]
            num_events = len(events)

        now_ts = snapshot.timestamp.timestamp()

        # If too few events, return baseline default
        if num_events < min_events:
            logger.info(
                f"Too few tick events ({num_events} < {min_events}) for Hawkes MLE estimation. Returning default."
            )
            # Default fallback values
            default_mu = 0.01  # events per second
            default_alpha = 0.005
            default_beta = 0.02

            # Compute default intensity
            t_events = np.array([e.timestamp for e in events])
            intensity = default_mu
            if num_events > 0:
                intensity += np.sum(
                    default_alpha * np.exp(-default_beta * (now_ts - t_events))
                )

            return HawkesOutput(
                current_intensity=float(intensity),
                baseline_intensity=float(default_mu),
                excitation_ratio=float(intensity / default_mu),
                branching_ratio=float(default_alpha / default_beta),
                is_cascade=False,
                cascade_probability=float(
                    1.0
                    - np.exp(
                        -intensity * HAWKES_CONFIG.get("forecast_window_seconds", 300)
                    )
                ),
                event_clusters=[],
                decay_halflife_seconds=float(np.log(2) / default_beta),
                total_events=num_events,
                timestamp=snapshot.timestamp,
            )

        # Timestamps relative to the first event
        t_start = events[0].timestamp
        t = np.array([e.timestamp - t_start for e in events])
        T = now_ts - t_start

        # Ensure T is slightly greater than the last event
        if T <= t[-1]:
            T = t[-1] + 1.0

        # Negative log-likelihood function
        def neg_log_likelihood(params):
            mu, alpha, beta = params
            if mu <= 0 or alpha < 0 or beta <= 0:
                return 1e12

            # Recursive calculation of sum_{j<i} exp(-beta*(t_i - t_j))
            A = np.zeros(num_events)
            for i in range(1, num_events):
                A[i] = (A[i - 1] + 1.0) * np.exp(-beta * (t[i] - t[i - 1]))

            intensities = mu + alpha * A
            # Log intensities with a safety floor
            log_int = np.log(np.maximum(intensities, 1e-12))

            # Integral part
            integral = mu * T + (alpha / beta) * np.sum(1.0 - np.exp(-beta * (T - t)))

            return -(np.sum(log_int) - integral)

        # Fit parameters using MLE with lazy caching (refit every 20 bars)
        if not hasattr(self, "_cached_params"):
            self._cached_params = None
            self._bars_since_fit = 999

        if self._cached_params is not None and self._bars_since_fit < 20:
            self._bars_since_fit += 1
            mu, alpha, beta = self._cached_params
        else:
            # Initial guess: [baseline, alpha, beta]
            init_mu = max(0.0001, num_events / T)
            init_beta = HAWKES_CONFIG.get("decay_prior_beta", 0.1)
            init_alpha = init_beta * 0.4  # start with branching ratio 0.4

            initial_guess = [init_mu, init_alpha, init_beta]
            bounds = [(1e-6, 10.0), (0.0, 10.0), (1e-5, 20.0)]

            try:
                res = minimize(
                    neg_log_likelihood, initial_guess, bounds=bounds, method="L-BFGS-B"
                )
                if res.success:
                    mu, alpha, beta = res.x
                    self._cached_params = (mu, alpha, beta)
                    self._bars_since_fit = 0
                else:
                    mu, alpha, beta = initial_guess
            except Exception as err:
                logger.error(f"Hawkes MLE optimization failed: {err}")
                mu, alpha, beta = initial_guess

        # Compute current intensity at snapshot timestamp
        time_offsets = now_ts - np.array([e.timestamp for e in events])
        current_intensity = mu + np.sum(alpha * np.exp(-beta * time_offsets))
        excitation_ratio = current_intensity / mu if mu > 0 else 1.0
        branching_ratio = alpha / beta if beta > 0 else 0.0

        cascade_threshold = HAWKES_CONFIG.get("cascade_threshold", 0.8)
        is_cascade = branching_ratio > cascade_threshold

        forecast_window = HAWKES_CONFIG.get("forecast_window_seconds", 300)
        cascade_probability = float(1.0 - np.exp(-current_intensity * forecast_window))

        # Event cluster detection
        # Group events within decay_halflife of each other
        decay_halflife = np.log(2) / beta if beta > 0 else 1.0
        clusters = []
        if num_events > 0:
            current_cluster = [events[0]]
            for i in range(1, num_events):
                if events[i].timestamp - current_cluster[-1].timestamp < decay_halflife:
                    current_cluster.append(events[i])
                else:
                    if len(current_cluster) >= 3:  # minimum cluster size
                        clusters.append(
                            {
                                "start": datetime.fromtimestamp(
                                    current_cluster[0].timestamp
                                ).isoformat(),
                                "end": datetime.fromtimestamp(
                                    current_cluster[-1].timestamp
                                ).isoformat(),
                                "size": len(current_cluster),
                                "types": list(
                                    set(e.event_type for e in current_cluster)
                                ),
                            }
                        )
                    current_cluster = [events[i]]
            # Add final cluster
            if len(current_cluster) >= 3:
                clusters.append(
                    {
                        "start": datetime.fromtimestamp(
                            current_cluster[0].timestamp
                        ).isoformat(),
                        "end": datetime.fromtimestamp(
                            current_cluster[-1].timestamp
                        ).isoformat(),
                        "size": len(current_cluster),
                        "types": list(set(e.event_type for e in current_cluster)),
                    }
                )

        return HawkesOutput(
            current_intensity=float(current_intensity),
            baseline_intensity=float(mu),
            excitation_ratio=float(excitation_ratio),
            branching_ratio=float(branching_ratio),
            is_cascade=bool(is_cascade),
            cascade_probability=float(cascade_probability),
            event_clusters=clusters,
            decay_halflife_seconds=float(decay_halflife),
            total_events=num_events,
            timestamp=snapshot.timestamp,
        )
