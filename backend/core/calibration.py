import logging

import numpy as np
import pandas as pd

logger = logging.getLogger("backend.core.calibration")


class CalibrationEngine:
    @staticmethod
    def compute_brier_score(predictions: list[float], outcomes: list[int]) -> float:
        """
        Compute Brier Score: (1/N) * sum((p - o)^2)
        """
        if not predictions or len(predictions) != len(outcomes):
            return 0.0
        return float(np.mean((np.array(predictions) - np.array(outcomes)) ** 2))

    @staticmethod
    def compute_log_loss(
        predictions: list[float], outcomes: list[int], eps: float = 1e-15
    ) -> float:
        """
        Compute Log Loss
        """
        if not predictions or len(predictions) != len(outcomes):
            return 0.0
        p = np.clip(predictions, eps, 1 - eps)
        o = np.array(outcomes)
        return float(-np.mean(o * np.log(p) + (1 - o) * np.log(1 - p)))

    @staticmethod
    def compute_ece_and_buckets(
        predictions: list[float], outcomes: list[int], n_bins: int = 10
    ) -> tuple[float, list[dict]]:
        """
        Compute Expected Calibration Error (ECE) and Reliability Buckets.
        """
        if not predictions or not outcomes:
            return 0.0, []

        df = pd.DataFrame({"p": predictions, "o": outcomes})
        df["bin"] = pd.cut(
            df["p"], bins=np.linspace(0, 1, n_bins + 1), include_lowest=True
        )

        ece = 0.0
        reliability_buckets = []
        n_total = len(df)

        for bin_interval, group in df.groupby("bin", observed=False):
            n_bin = len(group)
            if n_bin > 0:
                acc = group["o"].mean()
                conf = group["p"].mean()
                weight = n_bin / n_total
                ece += weight * np.abs(acc - conf)

                reliability_buckets.append(
                    {
                        "bin_start": float(bin_interval.left),
                        "bin_end": float(bin_interval.right),
                        "count": int(n_bin),
                        "mean_confidence": float(conf),
                        "accuracy": float(acc),
                    }
                )

        return float(ece), reliability_buckets

    @staticmethod
    def determine_calibration_status(sample_size: int) -> str:
        """
        Return calibration status based on sample size.
        """
        if sample_size < 50:
            return "Learning"
        elif sample_size <= 250:
            return "Reliable"
        else:
            return "Institution Grade"

    @staticmethod
    def validate_confidence(buckets: list[dict], target_conf: float = 0.90) -> dict:
        """
        Measure whether a target confidence (e.g., 90%) actually wins historically.
        Finds the closest bucket or aggregates buckets >= target_conf.
        """
        if not buckets:
            return {
                "predicted_confidence": target_conf,
                "historical_accuracy": 0.0,
                "calibration_gap": 0.0,
                "confidence_bias": "Unknown",
            }

        relevant = [b for b in buckets if b["mean_confidence"] >= target_conf - 0.05]
        if not relevant:
            return {
                "predicted_confidence": target_conf,
                "historical_accuracy": 0.0,
                "calibration_gap": 0.0,
                "confidence_bias": "Unknown",
            }

        total_count = sum(b["count"] for b in relevant)
        if total_count == 0:
            return {
                "predicted_confidence": target_conf,
                "historical_accuracy": 0.0,
                "calibration_gap": 0.0,
                "confidence_bias": "Unknown",
            }

        avg_acc = sum(b["accuracy"] * b["count"] for b in relevant) / total_count
        avg_conf = (
            sum(b["mean_confidence"] * b["count"] for b in relevant) / total_count
        )

        gap = avg_acc - avg_conf
        bias = (
            "Overconfident"
            if gap < -0.05
            else ("Underconfident" if gap > 0.05 else "Calibrated")
        )

        return {
            "predicted_confidence": round(avg_conf, 4),
            "historical_accuracy": round(avg_acc, 4),
            "calibration_gap": round(gap, 4),
            "confidence_bias": bias,
        }
