"""
Stage 6: Ensemble Predictor.
Ensemble model (XGBoost, RandomForest, GradientBoosting) to predict future returns over multiple horizons.
"""

import logging
import os

import numpy as np
import pandas as pd

from core.shared_features import compute_adx, compute_rsi, compute_volume_ratio
from pipeline.base import (
    EnsembleOutput,
    HawkesOutput,
    KalmanOutput,
    MarketSnapshot,
    ParticleOutput,
    PipelineStage,
    QuantileForecast,
    RegimeOutput,
)
from pipeline.config import ENSEMBLE_CONFIG

# Optional model imports
try:
    import joblib
    from sklearn.ensemble import (  # ruff: noqa: F401
        GradientBoostingRegressor,
        RandomForestRegressor,
    )
    from xgboost import XGBRegressor

    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False

logger = logging.getLogger("pipeline.ensemble")


class Stage6Ensemble(PipelineStage):
    def __init__(self):
        super().__init__()
        self._models_cache = {}

    @property
    def name(self) -> str:
        return "ensemble"

    def _extract_features_row(
        self,
        snapshot: MarketSnapshot,
        hawkes: HawkesOutput,
        kalman: KalmanOutput,
        particle: ParticleOutput,
        regime: RegimeOutput,
    ) -> dict:
        """
        Extract a single row of features for prediction.
        """
        df = snapshot.ohlcv
        close_series = df["close"].values
        volume_series = df["volume"].values

        features = {}

        # 1. Price features
        for h in [1, 3, 5, 10, 20]:
            if len(close_series) >= h + 1:
                features[f"return_{h}d"] = float(
                    (close_series[-1] - close_series[-h - 1]) / close_series[-h - 1]
                )
            else:
                features[f"return_{h}d"] = 0.0

        # Momentum
        if len(close_series) >= 10:
            features["momentum"] = float(close_series[-1] - close_series[-10])
        else:
            features["momentum"] = 0.0

        # 2. Volatility features
        features["volatility_kalman"] = kalman.estimated_volatility
        features["volatility_particle"] = particle.std_price
        features["bb_width"] = regime.features_used.get("bb_width", 0.02)
        atr_val = snapshot.indicators.get("atr")
        if atr_val is None:
            atr_val = 0.0
        features["atr_pct"] = (
            float(atr_val / close_series[-1]) if close_series[-1] > 0 else 0.01
        )

        # 3. Volume features
        features["volume_ratio"] = regime.features_used.get("volume_ratio", 1.0)

        # 4. Technical indicator features
        features["rsi"] = regime.features_used.get("rsi_14", 50.0)
        features["adx"] = regime.features_used.get("adx", 20.0)

        # 5. Upstream stage outputs
        features["hawkes_intensity_ratio"] = hawkes.excitation_ratio
        features["hawkes_branching_ratio"] = hawkes.branching_ratio
        features["hawkes_is_cascade"] = float(hawkes.is_cascade)

        features["kalman_velocity"] = kalman.estimated_velocity
        features["kalman_acceleration"] = kalman.estimated_acceleration
        features["kalman_innovation_z"] = kalman.innovation_zscore

        features["particle_skewness"] = particle.skewness
        features["particle_kurtosis"] = particle.kurtosis
        features["particle_bimodality"] = particle.bimodality_score
        features["particle_tail_left"] = particle.tail_risk_left
        features["particle_tail_right"] = particle.tail_risk_right

        # 6. Regime features (One-hot encoding)
        for r_name in ENSEMBLE_CONFIG.get(
            "regime_names",
            [
                "TRENDING_BULL",
                "TRENDING_BEAR",
                "MEAN_REVERTING",
                "HIGH_VOLATILITY",
                "LOW_VOLATILITY",
                "TRANSITION",
            ],
        ):
            features[f"regime_{r_name}"] = (
                1.0 if regime.current_regime == r_name else 0.0
            )
        features["regime_transition_prob"] = regime.transition_probability

        # 7. Options features
        features["options_pcr"] = snapshot.options.get("pcr", 1.0)
        features["options_oi_score"] = snapshot.options.get("oi_score", 0.0)
        features["options_atm_iv"] = snapshot.options.get("atm_iv", 0.15) or 0.15

        # 8. Calendar features
        now = snapshot.timestamp
        features["calendar_day_of_week"] = float(now.weekday())
        features["calendar_month"] = float(now.month)

        # Sector returns (mock or calculated from sector peers if available)
        features["sector_avg_return"] = 0.0  # default

        return features

    def process(
        self,
        snapshot: MarketSnapshot,
        hawkes: HawkesOutput,
        kalman: KalmanOutput,
        particle: ParticleOutput,
        regime: RegimeOutput,
    ) -> EnsembleOutput:
        """
        Run the ensemble regression to get quantile forecasts.
        """
        horizons = ENSEMBLE_CONFIG.get("forecast_horizons", [1, 3, 5, 10])
        quantiles = ENSEMBLE_CONFIG.get("quantiles", [0.1, 0.25, 0.5, 0.75, 0.9])

        # Build features dict
        feat_dict = self._extract_features_row(
            snapshot, hawkes, kalman, particle, regime
        )

        model_dir = ENSEMBLE_CONFIG.get("model_dir", "pipeline/models")
        symbol = snapshot.symbol.upper()

        forecasts = {}
        models_loaded = False

        if MODELS_AVAILABLE:
            try:
                # Try to load models for each horizon
                # Features list matching model's expected features
                feature_names = sorted(feat_dict.keys())
                X_pred = pd.DataFrame([feat_dict])[feature_names]

                # Ensure cache exists
                if not hasattr(self, "_models_cache"):
                    self._models_cache = {}

                for h in horizons:
                    cache_key = f"{symbol}_horizon_{h}"
                    if cache_key in self._models_cache:
                        h_models = self._models_cache[cache_key]
                    else:
                        model_path = os.path.join(
                            model_dir, f"{symbol}_horizon_{h}.joblib"
                        )
                        if os.path.exists(model_path):
                            h_models = joblib.load(model_path)
                            self._models_cache[cache_key] = h_models
                        else:
                            h_models = None

                    if h_models is not None:
                        # Predictions for each quantile
                        q_preds = {}
                        for q in quantiles:
                            q_model = h_models[f"xgb_q_{q}"]
                            q_preds[f"q{int(q * 100)}"] = float(
                                q_model.predict(X_pred)[0]
                            )

                        forecasts[h] = QuantileForecast(
                            horizon=h,
                            q10=q_preds["q10"],
                            q25=q_preds["q25"],
                            q50=q_preds["q50"],
                            q75=q_preds["q75"],
                            q90=q_preds["q90"],
                        )
                        models_loaded = True
            except Exception as load_err:
                logger.error(
                    f"Ensemble load/prediction failed, using rules: {load_err}"
                )
                models_loaded = False

        # Fallback if models are not trained/loaded
        if not models_loaded:
            # Generate predictions using statistical rules
            # Expected return = kalman velocity * horizon
            for h in horizons:
                pred_mean = kalman.estimated_velocity * h
                pred_std = (
                    kalman.price_uncertainty
                    / snapshot.ohlcv["close"].values[-1]
                    * np.sqrt(h)
                )

                # Assume Gaussian for quantiles fallback
                forecasts[h] = QuantileForecast(
                    horizon=h,
                    q10=float(pred_mean - 1.28 * pred_std),
                    q25=float(pred_mean - 0.67 * pred_std),
                    q50=float(pred_mean),
                    q75=float(pred_mean + 0.67 * pred_std),
                    q90=float(pred_mean + 1.28 * pred_std),
                )

        # Calculate final metrics from 5-step forecast (or the first available)
        default_h = horizons[1] if len(horizons) > 1 else horizons[0]
        f_def = forecasts[default_h]

        predicted_return = f_def.q50
        predicted_direction = (
            1 if predicted_return > 0.001 else -1 if predicted_return < -0.001 else 0
        )

        interval_width = f_def.q90 - f_def.q10
        model_confidence = 1.0 / (1.0 + interval_width * 100.0)

        # Feature importance list (mock when using rules, real when loaded)
        feat_importance = {k: 1.0 / len(feat_dict) for k in feat_dict.keys()}

        return EnsembleOutput(
            forecasts=forecasts,
            feature_importance=feat_importance,
            model_contributions=ENSEMBLE_CONFIG.get("initial_weights", {}),
            predicted_direction=predicted_direction,
            predicted_return=float(predicted_return),
            prediction_interval_width=float(interval_width),
            model_confidence=float(model_confidence),
            timestamp=snapshot.timestamp,
        )

    def train(self, df_history: pd.DataFrame, symbol: str):
        """
        Offline training method called by training scripts or download_history.py.
        """
        if not MODELS_AVAILABLE:
            raise RuntimeError(
                "scikit-learn and xgboost must be installed for training."
            )

        logger.info(f"Training Stage 6 Ensemble models for {symbol}")

        horizons = ENSEMBLE_CONFIG.get("forecast_horizons", [1, 3, 5, 10])
        # Clear cache for the symbol being trained to avoid stale models
        if hasattr(self, "_models_cache"):
            for h in horizons:
                cache_key = f"{symbol}_horizon_{h}"
                if cache_key in self._models_cache:
                    del self._models_cache[cache_key]

        close_series = df_history["close"].values
        volume_series = df_history["volume"].values
        n_bars = len(df_history)

        if n_bars < 50:
            raise ValueError(
                f"Insufficient historical data ({n_bars} < 50) for training"
            )

        quantiles = ENSEMBLE_CONFIG.get("quantiles", [0.1, 0.25, 0.5, 0.75, 0.9])
        model_dir = ENSEMBLE_CONFIG.get("model_dir", "pipeline/models")
        os.makedirs(model_dir, exist_ok=True)

        # Construct historical feature matrix
        # For simplicity, we compute technical indicators and rolling stats over the history
        df_feats = pd.DataFrame(index=df_history.index)

        # Simple technical indicators
        df_feats["rsi"] = (
            compute_rsi(
                df_history["close"]
                if "close" in df_history.columns
                else df_history["Close"]
            )
            .fillna(50.0)
            .values
        )
        high_s = (
            df_history["high"] if "high" in df_history.columns else df_history["High"]
        )
        low_s = df_history["low"] if "low" in df_history.columns else df_history["Low"]
        close_s = (
            df_history["close"]
            if "close" in df_history.columns
            else df_history["Close"]
        )
        df_feats["adx"] = compute_adx(high_s, low_s, close_s).fillna(20.0).values
        df_feats["volume_ratio"] = compute_volume_ratio(
            df_history["volume"]
            if "volume" in df_history.columns
            else df_history["Volume"]
        ).values

        # Returns
        for h in [1, 3, 5, 10, 20]:
            df_feats[f"return_{h}d"] = df_history["close"].pct_change(h).fillna(0.0)

        # Momentum
        df_feats["momentum"] = df_history["close"].diff(10).fillna(0.0)

        # Volatility features
        df_feats["volatility_kalman"] = 0.01
        df_feats["volatility_particle"] = 0.01

        # Bollinger Band Width
        std_20 = close_s.rolling(20).std().fillna(close_s * 0.01)
        mean_20 = close_s.rolling(20).mean().fillna(close_s)
        df_feats["bb_width"] = (4.0 * std_20 / mean_20).fillna(0.02)

        # ATR percentage
        tr = pd.concat(
            [
                high_s - low_s,
                (high_s - close_s.shift()).abs(),
                (low_s - close_s.shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(14).mean().fillna(close_s * 0.01)
        df_feats["atr_pct"] = (atr / close_s).fillna(0.01)

        # Set other missing features to 0.0
        df_feats["hawkes_intensity_ratio"] = 1.0
        df_feats["hawkes_branching_ratio"] = 0.4
        df_feats["hawkes_is_cascade"] = 0.0
        df_feats["kalman_velocity"] = df_history["close"].diff().fillna(0.0)
        df_feats["kalman_acceleration"] = df_history["close"].diff().diff().fillna(0.0)
        df_feats["kalman_innovation_z"] = 0.0
        df_feats["particle_skewness"] = 0.0
        df_feats["particle_kurtosis"] = 0.0
        df_feats["particle_bimodality"] = 0.0
        df_feats["particle_tail_left"] = 0.05
        df_feats["particle_tail_right"] = 0.05
        df_feats["options_pcr"] = 1.0
        df_feats["options_oi_score"] = 0.0
        df_feats["options_atm_iv"] = 0.15
        df_feats["calendar_day_of_week"] = (
            pd.Series(df_history.index)
            .apply(lambda x: float(x.weekday()) if hasattr(x, "weekday") else 0.0)
            .values
        )
        df_feats["calendar_month"] = (
            pd.Series(df_history.index)
            .apply(lambda x: float(x.month) if hasattr(x, "month") else 1.0)
            .values
        )

        # Regime encoding
        for r_name in [
            "TRENDING_BULL",
            "TRENDING_BEAR",
            "MEAN_REVERTING",
            "HIGH_VOLATILITY",
            "LOW_VOLATILITY",
            "TRANSITION",
        ]:
            df_feats[f"regime_{r_name}"] = 0.0
        df_feats["regime_MEAN_REVERTING"] = 1.0
        df_feats["regime_transition_prob"] = 0.0
        df_feats["sector_avg_return"] = 0.0

        # Sort columns to ensure consistent feature order
        feature_names = sorted(df_feats.columns)
        X = df_feats[feature_names].values

        # Train models for each horizon
        for h in horizons:
            # Target is the N-bar forward return
            y = df_history["close"].pct_change(h).shift(-h).fillna(0.0).values

            # Align target and features (remove last h steps where target is NaN)
            X_train = X[:-h]
            y_train = y[:-h]

            # Fit quantile models
            h_models = {}
            for q in quantiles:
                model_name = f"xgb_q_{q}"
                xgb = XGBRegressor(
                    n_estimators=100,
                    max_depth=4,
                    learning_rate=0.1,
                    objective="reg:quantileerror",  # Quantile loss in newer XGBoost
                    quantile_alpha=q,
                    random_state=42,
                )

                try:
                    xgb.fit(X_train, y_train)
                except Exception:
                    # Fallback for older XGBoost versions that don't support reg:quantileerror
                    xgb = XGBRegressor(
                        n_estimators=100,
                        max_depth=4,
                        learning_rate=0.1,
                        objective="reg:squarederror",
                        random_state=42,
                    )
                    xgb.fit(X_train, y_train)

                h_models[model_name] = xgb

            # Save models dictionary using joblib
            model_path = os.path.join(model_dir, f"{symbol}_horizon_{h}.joblib")
            joblib.dump(h_models, model_path)
            logger.info(
                f"Saved trained models for {symbol} horizon {h} to {model_path}"
            )
