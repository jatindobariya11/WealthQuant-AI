"""
Stage 9: Probability Engine.
Converts the fused return distribution into calibrated directional trading probabilities and position sizing.
"""

import logging

import numpy as np

from pipeline.base import FusionOutput, PipelineStage, ProbabilityOutput, RegimeOutput
from pipeline.config import PROBABILITY_CONFIG
from pipeline.db import pipeline_db
from pipeline.utils.distributions import PlattCalibrator

logger = logging.getLogger("pipeline.probability_engine")


class Stage9ProbabilityEngine(PipelineStage):
    def __init__(self):
        super().__init__()
        # Store Platt Calibrators per symbol and direction
        self.calibrators = {}

    @property
    def name(self) -> str:
        return "probability_engine"

    def _get_calibrator(self, symbol: str, direction: str) -> PlattCalibrator:
        key = (symbol.upper(), direction)
        if key not in self.calibrators:
            self.calibrators[key] = PlattCalibrator()
        return self.calibrators[key]

    async def fit_calibrators(self, symbol: str):
        """
        Fetch prediction-outcome pairs for the symbol, populate and fit Platt Calibrators.
        """
        limit = PROBABILITY_CONFIG.get("calibration_window", 100)

        # Fetch calibration data from PostgreSQL using pipeline_db
        calibration_data = await pipeline_db.get_calibration_data(
            symbol.upper(), "5", limit=500
        )
        if not calibration_data:
            logger.info(f"No calibration data found in database for symbol {symbol}.")
            return

        min_samples = PROBABILITY_CONFIG.get("min_calibration_samples", 20)
        if len(calibration_data) < min_samples:
            logger.info(
                f"Insufficient calibration data for {symbol} ({len(calibration_data)} < {min_samples}). Skipping fitting."
            )
            return

        up_thresh = PROBABILITY_CONFIG.get("up_threshold", 0.005)
        down_thresh = PROBABILITY_CONFIG.get("down_threshold", -0.005)

        calib_up = self._get_calibrator(symbol, "up")
        calib_down = self._get_calibrator(symbol, "down")

        # Populate history and fit
        calib_up._predictions = [float(row["p_up"]) for row in calibration_data]
        calib_up._outcomes = [
            float(row["actual_return"] > up_thresh) for row in calibration_data
        ]

        calib_down._predictions = [float(row["p_down"]) for row in calibration_data]
        calib_down._outcomes = [
            float(row["actual_return"] < down_thresh) for row in calibration_data
        ]

        calib_up._fit()
        calib_down._fit()

        logger.info(
            f"Successfully fit Platt calibrators for {symbol} with {len(calibration_data)} samples. "
            f"Up calibrator (a={calib_up.a:.4f}, b={calib_up.b:.4f}, fitted={calib_up.is_fitted}). "
            f"Down calibrator (a={calib_down.a:.4f}, b={calib_down.b:.4f}, fitted={calib_down.is_fitted})."
        )

    def process(
        self, symbol: str, fusion: FusionOutput, regime: RegimeOutput
    ) -> ProbabilityOutput:
        """
        Extract calibrated probabilities and calculate risk/sizing metrics from distribution.
        """
        pdf = fusion.fused_distribution
        bins = fusion.return_bins

        if pdf is None or bins is None:
            raise ValueError(
                "Fused distribution is missing from Bayesian Fusion output"
            )

        # ─── 1. Directional Probabilities ─────────────────────────────────────
        up_thresh = PROBABILITY_CONFIG.get("up_threshold", 0.005)
        down_thresh = PROBABILITY_CONFIG.get("down_threshold", -0.005)

        idx_up = bins >= up_thresh
        idx_down = bins <= down_thresh
        idx_side = (bins > down_thresh) & (bins < up_thresh)

        p_up_raw = float(np.sum(pdf[idx_up]))
        p_down_raw = float(np.sum(pdf[idx_down]))

        # Calibrate raw probabilities using Platt scaling
        calib_up = self._get_calibrator(symbol, "up")
        calib_down = self._get_calibrator(symbol, "down")

        p_up = calib_up.calibrate(p_up_raw)
        p_down = calib_down.calibrate(p_down_raw)

        # Re-normalize with sideways
        p_sum = p_up + p_down
        if p_sum > 0.999:
            p_up = p_up / p_sum * 0.99
            p_down = p_down / p_sum * 0.99

        p_sideways = 1.0 - p_up - p_down

        # ─── 2. Expected Values ───────────────────────────────────────────────
        expected_return = float(np.sum(bins * pdf))

        up_pdf_sum = np.sum(pdf[bins > 0.0])
        expected_upside = (
            float(np.sum(bins[bins > 0.0] * pdf[bins > 0.0]) / up_pdf_sum)
            if up_pdf_sum > 0
            else 0.005
        )

        down_pdf_sum = np.sum(pdf[bins < 0.0])
        expected_downside = (
            float(np.sum(bins[bins < 0.0] * pdf[bins < 0.0]) / down_pdf_sum)
            if down_pdf_sum > 0
            else -0.005
        )

        expected_move = float(np.sum(np.abs(bins) * pdf))

        # ─── 3. Risk Metrics ──────────────────────────────────────────────────
        # Cumulative distribution function
        cdf = np.cumsum(pdf)

        # Value at Risk 95% (5th percentile)
        idx_var = np.searchsorted(cdf, 0.05)
        idx_var = min(idx_var, len(bins) - 1)
        var_95 = float(bins[idx_var])

        # Conditional Value at Risk 95%
        sum_var_pdf = np.sum(pdf[: idx_var + 1])
        cvar_95 = (
            float(np.sum(bins[: idx_var + 1] * pdf[: idx_var + 1]) / sum_var_pdf)
            if sum_var_pdf > 0
            else var_95
        )

        # Drawdown probability (return < -3%)
        max_drawdown_prob = float(np.sum(pdf[bins < -0.03]))

        # Crash tail risk (return < -5%)
        crash_prob = float(np.sum(pdf[bins < -0.05]))

        # Tail risk score (0 to 100)
        tail_risk_score = 100.0 * (max_drawdown_prob + crash_prob) / 2.0
        tail_risk_score = float(np.clip(tail_risk_score, 0.0, 100.0))

        # ─── 4. Kelly Criterion position sizing ───────────────────────────────
        # Directional Kelly sizing to handle both long (BUY) and short (SELL) positions correctly.
        if p_up >= p_down:
            win = expected_upside
            loss = abs(expected_downside)
            edge = p_up * win - p_down * loss
            odds = win / loss if loss > 0 else 1.0
            kelly = edge / win if win > 0 and edge > 0 else 0.0
        else:
            win = abs(expected_downside)
            loss = expected_upside
            edge = p_down * win - p_up * loss
            odds = win / loss if loss > 0 else 1.0
            kelly = edge / win if win > 0 and edge > 0 else 0.0

        kelly_cap = PROBABILITY_CONFIG.get("kelly_cap", 0.25)
        kelly_fraction = float(np.clip(kelly, 0.0, kelly_cap))

        # Suggested position size
        use_half_kelly = PROBABILITY_CONFIG.get("use_half_kelly", True)
        suggested_size = kelly_fraction * 0.5 if use_half_kelly else kelly_fraction

        # ─── 5. Trading Signal Generation ─────────────────────────────────────
        s_buy_t = PROBABILITY_CONFIG.get("strong_buy_threshold", 0.65)
        buy_t = PROBABILITY_CONFIG.get("buy_threshold", 0.55)
        s_sell_t = PROBABILITY_CONFIG.get("strong_sell_threshold", 0.65)
        sell_t = PROBABILITY_CONFIG.get("sell_threshold", 0.55)

        if p_up > s_buy_t and kelly_fraction > 0.05:
            signal = "STRONG_BUY"
            confidence = p_up
        elif p_up > buy_t:
            signal = "BUY"
            confidence = p_up
        elif p_down > s_sell_t and kelly_fraction > 0.05:
            signal = "STRONG_SELL"
            confidence = p_down
        elif p_down > sell_t:
            signal = "SELL"
            confidence = p_down
        else:
            signal = "NEUTRAL"
            confidence = p_sideways

        # Calibration quality score (mock or based on fitted calibrators)
        calib_quality = 1.0 if (calib_up.is_fitted or calib_down.is_fitted) else 0.0

        return ProbabilityOutput(
            p_up=float(p_up),
            p_down=float(p_down),
            p_sideways=float(p_sideways),
            expected_return=float(expected_return),
            expected_upside=float(expected_upside),
            expected_downside=float(expected_downside),
            expected_move_pct=float(expected_move),
            var_95=float(var_95),
            cvar_95=float(cvar_95),
            max_drawdown_prob=float(max_drawdown_prob),
            tail_risk_score=float(tail_risk_score),
            kelly_fraction=float(kelly_fraction),
            suggested_position_size=float(suggested_size),
            signal=signal,
            signal_confidence=float(confidence),
            signal_edge=float(edge),
            calibration_quality=float(calib_quality),
            prediction_horizon="1D",
            timestamp=fusion.timestamp,
        )
