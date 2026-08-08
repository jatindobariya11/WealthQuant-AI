"""
Stage 5: Regime Detection.
Classifies market states using HMM and Bayesian Online Changepoint Detection (BOCPD).
"""

import logging
import os

import joblib
import numpy as np
import pandas as pd

from core.shared_features import compute_adx, compute_rsi, compute_volume_ratio
from pipeline.base import (
    KalmanOutput,
    MarketSnapshot,
    ParticleOutput,
    PipelineStage,
    RegimeOutput,
)
from pipeline.config import REGIME_CONFIG

# Optional HMM import
try:
    from hmmlearn import hmm  # ruff: noqa: F401

    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False

logger = logging.getLogger("pipeline.regime")


class BOCPDDetector:
    """
    Bayesian Online Changepoint Detection (BOCPD).
    Computes probability of a regime change at each bar.
    """

    def __init__(self, hazard_rate=1.0 / 250.0, max_run_length=100):
        self.hazard_rate = hazard_rate
        self.max_run_length = max_run_length
        # R is run-length distribution: P(r_t | x_{1:t})
        self.R = np.zeros(max_run_length + 1)
        self.R[0] = 1.0
        self.history = []

    def update(self, x: float) -> float:
        """
        Update run-length distribution with a new observation (e.g. log return).
        Returns the changepoint probability P(r_t = 0).
        """
        self.history.append(x)
        t = len(self.history)

        if t == 1:
            return 0.0

        # Limit history to prevent memory bloat
        if len(self.history) > self.max_run_length + 10:
            self.history.pop(0)

        # Allocate new run-length distribution
        new_R = np.zeros(self.max_run_length + 1)

        # Hazard vector
        H = np.ones(self.max_run_length) * self.hazard_rate

        # Evaluate predictive probabilities: P(x_t | r_{t-1})
        # We assume a Gaussian distribution for returns with mean and variance estimated from run-lengths
        pred_probs = np.zeros(self.max_run_length)
        for r in range(min(t - 1, self.max_run_length)):
            # Segment data for this run-length
            segment = self.history[-(r + 2) : -1]
            if len(segment) >= 2:
                mu = np.mean(segment)
                sigma = max(1e-4, np.std(segment))
            else:
                mu = 0.0
                sigma = 0.01
            # Normal PDF
            pred_probs[r] = (
                1.0
                / (sigma * np.sqrt(2.0 * np.pi))
                * np.exp(-((x - mu) ** 2) / (2.0 * sigma**2))
            )

        # Growth probabilities: P(r_t = r_{t-1} + 1)
        for r in range(min(t - 1, self.max_run_length)):
            new_R[r + 1] = self.R[r] * pred_probs[r] * (1.0 - H[r])

        # Changepoint probability: P(r_t = 0)
        new_R[0] = np.sum(
            self.R[: min(t - 1, self.max_run_length)]
            * pred_probs[: min(t - 1, self.max_run_length)]
            * H[: min(t - 1, self.max_run_length)]
        )

        # Normalize R
        sum_R = np.sum(new_R)
        if sum_R > 0:
            new_R /= sum_R
        else:
            new_R[0] = 1.0

        self.R = new_R
        return float(new_R[0])


class Stage5Regime(PipelineStage):
    def __init__(self):
        super().__init__()
        self._hmm_cache = {}
        self._bocpd_detectors = {}

    @property
    def name(self) -> str:
        return "regime"

    def process(
        self, snapshot: MarketSnapshot, kalman: KalmanOutput, particle: ParticleOutput
    ) -> RegimeOutput:
        """
        Classify current market regime and detect changepoint probabilities.
        """
        df = snapshot.ohlcv
        if df is None or df.empty or len(df) < 5:
            raise ValueError("Insufficient price data in snapshot for Regime Detection")

        close_series = df["close"].values
        volume_series = df["volume"].values

        # 1. Feature Engineering for current step
        # 5-d return
        ret_5d = (
            float((close_series[-1] - close_series[-5]) / close_series[-5])
            if len(close_series) >= 5
            else 0.0
        )
        # 20-d volatility
        returns_1d = (
            np.diff(close_series) / close_series[:-1]
            if len(close_series) > 1
            else np.array([0.0])
        )
        vol_20d = float(np.std(returns_1d[-20:])) if len(returns_1d) >= 20 else 0.01
        # Volume ratio
        vol_20_avg = np.mean(volume_series[-20:]) if len(volume_series) >= 20 else 1.0
        vol_ratio = float(volume_series[-1] / vol_20_avg) if vol_20_avg > 0 else 1.0

        # ADX & RSI
        rsi_14 = float(snapshot.indicators.get("rsi", 50.0) or 50.0)
        adx = float(snapshot.indicators.get("adx", 20.0) or 20.0)

        # BB width
        bb_upper = snapshot.indicators.get("bb_upper")
        bb_lower = snapshot.indicators.get("bb_lower")
        bb_mid = snapshot.indicators.get("bb_mid")
        if bb_upper and bb_lower and bb_mid and bb_mid > 0:
            bb_width = float((bb_upper - bb_lower) / bb_mid)
        else:
            bb_width = 0.02

        features_dict = {
            "returns_5d": ret_5d,
            "volatility_20d": vol_20d,
            "volume_ratio": vol_ratio,
            "adx": adx,
            "rsi_14": rsi_14,
            "bb_width": bb_width,
        }

        # 2. Rule-based heuristic regime classification (fallback)
        current_regime = "TRANSITION"
        regime_probs = {r: 0.0 for r in REGIME_CONFIG["regime_names"]}
        regime_confidence = 0.5

        # Heuristic rules
        vix = snapshot.global_context.get("vix", 15.0) or 15.0

        if vix > 22.0 or vol_20d > 0.025:
            current_regime = "HIGH_VOLATILITY"
            regime_probs["HIGH_VOLATILITY"] = 0.7
            regime_probs["TRANSITION"] = 0.3
        elif vix < 11.0 and bb_width < 0.015:
            current_regime = "LOW_VOLATILITY"
            regime_probs["LOW_VOLATILITY"] = 0.7
            regime_probs["MEAN_REVERTING"] = 0.3
        elif adx > 25.0:
            # Trending
            if ret_5d > 0.01 or kalman.estimated_velocity > 0:
                current_regime = "TRENDING_BULL"
                regime_probs["TRENDING_BULL"] = 0.7
                regime_probs["HIGH_VOLATILITY"] = 0.2
                regime_probs["TRANSITION"] = 0.1
            else:
                current_regime = "TRENDING_BEAR"
                regime_probs["TRENDING_BEAR"] = 0.7
                regime_probs["HIGH_VOLATILITY"] = 0.2
                regime_probs["TRANSITION"] = 0.1
        elif adx < 18.0:
            current_regime = "MEAN_REVERTING"
            regime_probs["MEAN_REVERTING"] = 0.7
            regime_probs["LOW_VOLATILITY"] = 0.2
            regime_probs["TRANSITION"] = 0.1
        else:
            current_regime = "TRANSITION"
            regime_probs["TRANSITION"] = 0.6
            regime_probs["MEAN_REVERTING"] = 0.2
            regime_probs["HIGH_VOLATILITY"] = 0.2

        # 3. Optional Machine Learning HMM classification
        # If hmmlearn is installed and we have enough data (e.g., length of Close series > 40)
        if HMM_AVAILABLE and len(close_series) >= 40:
            try:
                # Ensure cache exists
                if not hasattr(self, "_features_cache"):
                    self._features_cache = {}

                symbol = snapshot.symbol.upper()
                if symbol not in self._features_cache:
                    # Prepare historical feature matrix
                    hist_close = df["close"].values
                    h_ret_5d = pd.Series(hist_close).pct_change(5).fillna(0.0).values
                    pct_change_1d = pd.Series(hist_close).pct_change().fillna(0.0)
                    h_vol_20d = pct_change_1d.rolling(20).std().fillna(0.01).values
                    h_vol_ratio = compute_volume_ratio(df["volume"]).values
                    h_rsi = compute_rsi(df["close"]).fillna(50.0).values
                    h_adx = (
                        compute_adx(df["high"], df["low"], df["close"])
                        .fillna(20.0)
                        .values
                    )
                    X = np.column_stack(
                        [h_ret_5d, h_vol_20d, h_vol_ratio, h_adx, h_rsi]
                    )
                    self._features_cache[symbol] = X
                else:
                    # Only compute features for the last bar
                    ret_5d = (
                        float((close_series[-1] - close_series[-6]) / close_series[-6])
                        if len(close_series) >= 6
                        else 0.0
                    )
                    returns_1d = (
                        np.diff(close_series[-21:]) / close_series[-21:-1]
                        if len(close_series) > 1
                        else np.array([0.0])
                    )
                    vol_20d = (
                        float(np.std(returns_1d[-20:]))
                        if len(returns_1d) >= 20
                        else 0.01
                    )
                    vol_ratio = float(
                        snapshot.indicators.get("volume_ratio", 1.0) or 1.0
                    )
                    rsi = float(snapshot.indicators.get("rsi", 50.0) or 50.0)
                    adx = float(snapshot.indicators.get("adx", 20.0) or 20.0)
                    new_row = np.array([[ret_5d, vol_20d, vol_ratio, adx, rsi]])

                    # If length mismatch, rebuild cache
                    if len(self._features_cache[symbol]) != len(close_series) - 1:
                        hist_close = df["close"].values
                        h_ret_5d = (
                            pd.Series(hist_close).pct_change(5).fillna(0.0).values
                        )
                        pct_change_1d = pd.Series(hist_close).pct_change().fillna(0.0)
                        h_vol_20d = pct_change_1d.rolling(20).std().fillna(0.01).values
                        h_vol_ratio = compute_volume_ratio(df["volume"]).values
                        h_rsi = compute_rsi(df["close"]).fillna(50.0).values
                        h_adx = (
                            compute_adx(df["high"], df["low"], df["close"])
                            .fillna(20.0)
                            .values
                        )
                        X = np.column_stack(
                            [h_ret_5d, h_vol_20d, h_vol_ratio, h_adx, h_rsi]
                        )
                        self._features_cache[symbol] = X
                    else:
                        self._features_cache[symbol] = np.vstack(
                            [self._features_cache[symbol], new_row]
                        )
                        X = self._features_cache[symbol]

                model_path = f"pipeline/models/{snapshot.symbol.upper()}_hmm.joblib"

                # Ensure cache exists
                if not hasattr(self, "_hmm_cache"):
                    self._hmm_cache = {}

                cache_key = snapshot.symbol.upper()
                if cache_key in self._hmm_cache:
                    model = self._hmm_cache[cache_key]
                else:
                    if not os.path.exists(model_path):
                        raise FileNotFoundError(
                            f"Pre-trained HMM model not found at {model_path}"
                        )
                    model = joblib.load(model_path)
                    self._hmm_cache[cache_key] = model

                # Predict current state
                state_seq = model.predict(X)
                prob_states = model.predict_proba(X[-1:])[0]

                last_state = state_seq[-1]
                regime_confidence = float(prob_states[last_state])

                # Map hidden states to our semantic regimes based on mean returns and variances
                means = model.means_
                state_mapping = {}
                for s in range(len(means)):
                    m_ret = means[s][0]  # mean return
                    m_vol = means[s][1]  # mean vol

                    if m_vol > np.median(means[:, 1]) * 1.5:
                        state_mapping[s] = "HIGH_VOLATILITY"
                    elif m_vol < np.median(means[:, 1]) * 0.7:
                        state_mapping[s] = "LOW_VOLATILITY"
                    elif m_ret > 0.002:
                        state_mapping[s] = "TRENDING_BULL"
                    elif m_ret < -0.002:
                        state_mapping[s] = "TRENDING_BEAR"
                    else:
                        state_mapping[s] = "MEAN_REVERTING"

                mapped_regime = state_mapping.get(last_state, "TRANSITION")

                # Update probabilities with HMM outputs
                new_probs = {r: 0.0 for r in REGIME_CONFIG["regime_names"]}
                for s, prob in enumerate(prob_states):
                    mapped_r = state_mapping.get(s, "TRANSITION")
                    if mapped_r in new_probs:
                        new_probs[mapped_r] += float(prob)

                current_regime = mapped_regime
                regime_probs = new_probs

            except Exception as hmm_err:
                logger.info(
                    f"HMM load/prediction bypassed (using heuristics fallback): {hmm_err}"
                )

        # 4. BOCPD for changepoint score
        symbol = snapshot.symbol.upper()
        if not hasattr(self, "_bocpd_detectors"):
            self._bocpd_detectors = {}

        if symbol not in self._bocpd_detectors:
            self._bocpd_detectors[symbol] = BOCPDDetector(
                hazard_rate=REGIME_CONFIG.get("changepoint_hazard", 1.0 / 250.0),
                max_run_length=REGIME_CONFIG.get("bocpd_lookback", 100),
            )
            # Warm up with historical returns except the last one
            log_rets = (
                np.log(close_series[1:] / close_series[:-1])
                if len(close_series) > 1
                else np.array([0.0])
            )
            for ret in log_rets[:-1]:
                self._bocpd_detectors[symbol].update(ret)

        # Update with only the last return
        ret = (
            np.log(close_series[-1] / close_series[-2])
            if len(close_series) > 1
            else 0.0
        )
        changepoint_score = self._bocpd_detectors[symbol].update(ret)

        # Transition target & probability
        transition_prob = changepoint_score
        sorted_probs = sorted(regime_probs.items(), key=lambda x: -x[1])
        transition_target = (
            sorted_probs[1][0]
            if sorted_probs[0][0] == current_regime
            else sorted_probs[0][0]
        )

        # Simulated regime history for timeline
        regime_history = []
        mean_target = np.mean(close_series)
        # Let's generate a mock sequence based on past returns to populate the timeline
        segment_size = max(5, len(close_series) // 10)
        for i in range(10):
            idx = max(0, len(close_series) - (10 - i) * segment_size)
            close_val = close_series[idx]
            vol_val = volume_series[idx]
            # Simple rule mapping for past steps
            if vol_val > vol_20_avg * 1.5:
                reg = "HIGH_VOLATILITY"
            elif close_val > mean_target * 1.02:
                reg = "TRENDING_BULL"
            elif close_val < mean_target * 0.98:
                reg = "TRENDING_BEAR"
            else:
                reg = "MEAN_REVERTING"
            regime_history.append({"regime": reg, "bars": segment_size})

        # Calculate duration of current regime
        # Look back from the end and count how many steps have similar regime conditions
        duration = 1
        for i in range(len(close_series) - 2, 0, -1):
            # If price change is within range, assume regime persists
            if abs(close_series[i] - close_series[-1]) / close_series[-1] < 0.02:
                duration += 1
            else:
                break

        return RegimeOutput(
            current_regime=current_regime,
            regime_probabilities={k: float(v) for k, v in regime_probs.items()},
            regime_confidence=float(regime_probs[current_regime]),
            regime_duration_bars=duration,
            transition_probability=float(transition_prob),
            transition_target=transition_target,
            regime_history=regime_history,
            changepoint_score=float(changepoint_score),
            features_used=features_dict,
            timestamp=snapshot.timestamp,
        )
