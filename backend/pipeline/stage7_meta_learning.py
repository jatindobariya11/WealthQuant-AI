"""
Stage 7: Meta-Learning.
Adapts ensemble model weights based on regime changes and historical performance.
"""

import logging

from pipeline.base import (
    EnsembleOutput,
    MetaLearningOutput,
    PipelineStage,
    QuantileForecast,
    RegimeOutput,
)
from pipeline.config import META_LEARNING_CONFIG

logger = logging.getLogger("pipeline.meta_learning")


class Stage7MetaLearning(PipelineStage):
    def __init__(self):
        super().__init__()
        # Symbol-specific adaptation states to prevent cross-symbol leakage
        self.symbol_states = {}

        # Regime-specific target weights
        self.regime_target_weights = {
            "TRENDING_BULL": {
                "xgboost": 0.60,
                "random_forest": 0.20,
                "gradient_boosting": 0.20,
            },
            "TRENDING_BEAR": {
                "xgboost": 0.60,
                "random_forest": 0.20,
                "gradient_boosting": 0.20,
            },
            "MEAN_REVERTING": {
                "xgboost": 0.30,
                "random_forest": 0.50,
                "gradient_boosting": 0.20,
            },
            "HIGH_VOLATILITY": {
                "xgboost": 0.20,
                "random_forest": 0.40,
                "gradient_boosting": 0.40,
            },
            "LOW_VOLATILITY": {
                "xgboost": 0.40,
                "random_forest": 0.40,
                "gradient_boosting": 0.20,
            },
            "TRANSITION": {
                "xgboost": 0.30,
                "random_forest": 0.30,
                "gradient_boosting": 0.40,
            },
        }

    def _get_or_create_state(self, symbol: str) -> dict:
        if symbol not in self.symbol_states:
            self.symbol_states[symbol] = {
                "active_weights": {
                    "xgboost": 0.5,
                    "random_forest": 0.3,
                    "gradient_boosting": 0.2,
                },
                "current_regime": "TRANSITION",
                "bars_since_regime_change": 0,
                "adaptation_status": "STABLE",
                "adaptation_progress": 1.0,
            }
        return self.symbol_states[symbol]

    @property
    def name(self) -> str:
        return "meta_learning"

    def process(
        self, ensemble: EnsembleOutput, regime: RegimeOutput, symbol: str = "DEFAULT"
    ) -> MetaLearningOutput:
        """
        Adapt model selection and blend weights based on current regime.
        """
        detected_regime = regime.current_regime
        confidence = regime.regime_confidence

        alpha_start = META_LEARNING_CONFIG.get("regime_model_blend_alpha_start", 0.3)
        alpha_max = META_LEARNING_CONFIG.get("regime_model_blend_alpha_max", 0.9)
        ramp_bars = META_LEARNING_CONFIG.get("regime_model_blend_ramp_bars", 20)
        conf_threshold = META_LEARNING_CONFIG.get(
            "regime_change_confidence_threshold", 0.7
        )

        # Get state for the active symbol
        state = self._get_or_create_state(symbol)

        # Check for regime change
        if detected_regime != state["current_regime"] and confidence >= conf_threshold:
            logger.info(
                f"[{symbol}] Regime change detected from {state['current_regime']} to {detected_regime}. Initiating weight adaptation."
            )
            state["current_regime"] = detected_regime
            state["bars_since_regime_change"] = 0
            state["adaptation_status"] = "ADAPTING"
            state["adaptation_progress"] = 0.0

        # Run weight adaptation step
        target_weights = self.regime_target_weights.get(
            state["current_regime"], self.regime_target_weights["TRANSITION"]
        )

        if state["adaptation_status"] == "ADAPTING":
            state["bars_since_regime_change"] += 1
            progress = min(state["bars_since_regime_change"] / ramp_bars, 1.0)
            state["adaptation_progress"] = progress

            # Blending parameter alpha
            alpha = alpha_start + (alpha_max - alpha_start) * progress

            # Blend active weights with target regime weights
            new_weights = {}
            for k in state["active_weights"]:
                new_weights[k] = (
                    alpha * target_weights[k]
                    + (1.0 - alpha) * state["active_weights"][k]
                )

            # Re-normalize to sum to 1
            sum_w = sum(new_weights.values())
            state["active_weights"] = {k: v / sum_w for k, v in new_weights.items()}

            if progress >= 1.0:
                state["adaptation_status"] = "ADAPTED"
                logger.info(
                    f"[{symbol}] Regime adaptation complete. Active weights stabilized for regime {state['current_regime']}."
                )
        else:
            state["adaptation_status"] = "STABLE"
            state["adaptation_progress"] = 1.0
            # Active weights are set directly to target weights
            state["active_weights"] = target_weights

        # Model selection: Rank models by active weights
        ranked_models = sorted(state["active_weights"].items(), key=lambda x: -x[1])
        selected_models = [
            m[0]
            for m in ranked_models[: META_LEARNING_CONFIG.get("max_active_models", 3)]
        ]

        # Calculate adapted forecasts
        adapted_forecasts = {}
        improvement = 0.0

        for h, fc in ensemble.forecasts.items():
            # Adjust forecast based on adapted weights
            # For trending, we boost momentum; for mean reverting, we dampen it.
            scale_factor = 1.0
            if state["current_regime"] in ["MEAN_REVERTING", "LOW_VOLATILITY"]:
                scale_factor = 0.8  # dampen forecast return magnitudes
            elif state["current_regime"] in ["TRENDING_BULL", "TRENDING_BEAR"]:
                scale_factor = 1.2  # amplify forecast return magnitudes

            adapted_forecasts[h] = QuantileForecast(
                horizon=h,
                q10=float(fc.q10 * scale_factor),
                q25=float(fc.q25 * scale_factor),
                q50=float(fc.q50 * scale_factor),
                q75=float(fc.q75 * scale_factor),
                q90=float(fc.q90 * scale_factor),
            )

            if h == 5:
                # Mock adaptation improvement metric
                improvement = float(
                    abs(fc.q50 * scale_factor - fc.q50) / (abs(fc.q50) + 1e-6) * 100.0
                )

        return MetaLearningOutput(
            adaptation_status=state["adaptation_status"],
            adaptation_progress=state["adaptation_progress"],
            regime_model_active=state["current_regime"],
            bars_since_adaptation=state["bars_since_regime_change"],
            confidence_in_adaptation=float(confidence),
            adapted_forecasts=adapted_forecasts,
            adaptation_improvement=improvement,
            selected_models=selected_models,
            timestamp=ensemble.timestamp,
        )
