"""
WealthQuant V7.7 — Confidence Validation & Decile Analysis
===========================================================
Measures whether 90% confidence actually wins 90% historically.
Displays predicted confidence, historical accuracy, calibration gap, and confidence bias.
"""

import logging

import numpy as np

logger = logging.getLogger("pipeline.confidence_validator")


class ConfidenceValidator:
    """
    Validates confidence levels against empirical win rates across confidence deciles.
    """

    CONFIDENCE_DECILES = [
        (0.50, 0.60, "50-60%"),
        (0.60, 0.70, "60-70%"),
        (0.70, 0.80, "70-80%"),
        (0.80, 0.90, "80-90%"),
        (0.90, 1.00, "90-100%"),
    ]

    @classmethod
    def validate_deciles(
        cls, predictions: list[float], outcomes: list[float]
    ) -> list[dict]:
        """
        Evaluates performance across standard confidence deciles.
        Computes Calibration Gap (Actual Win Rate - Predicted Confidence)
        and Confidence Bias (Overconfident, Underconfident, Well-Calibrated).
        """
        if not predictions or len(predictions) != len(outcomes):
            return []

        preds = np.clip(np.array(predictions), 0.0, 1.0)
        outs = np.clip(np.array(outcomes), 0.0, 1.0)

        decile_results = []
        for low, high, label in cls.CONFIDENCE_DECILES:
            if high == 1.0:
                mask = (preds >= low) & (preds <= high)
            else:
                mask = (preds >= low) & (preds < high)

            count = int(np.sum(mask))
            if count > 0:
                avg_pred_conf = float(np.mean(preds[mask]))
                actual_acc = float(np.mean(outs[mask]))
                gap = (
                    actual_acc - avg_pred_conf
                )  # positive = underconfident, negative = overconfident

                if gap > 0.05:
                    bias = "Underconfident"
                elif gap < -0.05:
                    bias = "Overconfident"
                else:
                    bias = "Well-Calibrated"
            else:
                avg_pred_conf = (low + high) / 2.0
                actual_acc = 0.0
                gap = 0.0
                bias = "Insufficient Data"

            decile_results.append(
                {
                    "decile_label": label,
                    "range_min": low,
                    "range_max": high,
                    "sample_count": count,
                    "predicted_confidence": round(avg_pred_conf, 4),
                    "historical_accuracy": round(actual_acc, 4),
                    "calibration_gap": round(gap, 4),
                    "confidence_bias": bias,
                }
            )

        return decile_results

    @classmethod
    def get_historical_accuracy_for_confidence(
        cls,
        target_conf: float,
        predictions: list[float],
        outcomes: list[float],
        window_width: float = 0.05,
    ) -> dict:
        """
        Finds historical win rate for predictions near target_conf +/- window_width.
        """
        if not predictions or len(predictions) != len(outcomes):
            return {
                "target_confidence": target_conf,
                "historical_accuracy": target_conf,
                "matching_samples": 0,
                "calibration_gap": 0.0,
                "bias": "Insufficient Data",
            }

        preds = np.clip(np.array(predictions), 0.0, 1.0)
        outs = np.clip(np.array(outcomes), 0.0, 1.0)

        low = max(0.0, target_conf - window_width)
        high = min(1.0, target_conf + window_width)
        mask = (preds >= low) & (preds <= high)

        count = int(np.sum(mask))
        if count >= 3:
            actual_acc = float(np.mean(outs[mask]))
            gap = actual_acc - target_conf
            bias = (
                "Well-Calibrated"
                if abs(gap) <= 0.05
                else ("Underconfident" if gap > 0.05 else "Overconfident")
            )
        else:
            actual_acc = target_conf  # fallback to target
            gap = 0.0
            bias = "Learning"

        return {
            "target_confidence": round(target_conf, 4),
            "historical_accuracy": round(actual_acc, 4),
            "matching_samples": count,
            "calibration_gap": round(gap, 4),
            "bias": bias,
        }
