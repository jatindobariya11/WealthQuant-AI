import logging

import numpy as np

logger = logging.getLogger("backend.core.drift_monitor")


class DriftMonitor:
    # Thresholds for classifying drift
    WARNING_THRESHOLD = 2.0  # e.g., standard deviations
    CRITICAL_THRESHOLD = 3.0

    @staticmethod
    def calculate_drift(
        feature_name: str, baseline_data: list[float], recent_data: list[float]
    ) -> dict:
        """
        Calculate drift between a historical baseline and recent data.
        Returns drift score and status.
        """
        if not baseline_data or not recent_data:
            return {
                "feature_name": feature_name,
                "baseline_mean": 0.0,
                "recent_mean": 0.0,
                "drift_score": 0.0,
                "is_drifted": False,
                "status": "Unknown",
            }

        baseline_mean = float(np.mean(baseline_data))
        baseline_std = float(np.std(baseline_data))
        recent_mean = float(np.mean(recent_data))

        # Avoid division by zero
        if baseline_std < 1e-6:
            baseline_std = 1e-6

        # Z-score as a drift score
        drift_score = abs(recent_mean - baseline_mean) / baseline_std

        if drift_score >= DriftMonitor.CRITICAL_THRESHOLD:
            status = "Critical"
            is_drifted = True
        elif drift_score >= DriftMonitor.WARNING_THRESHOLD:
            status = "Warning"
            is_drifted = True
        else:
            status = "Healthy"
            is_drifted = False

        return {
            "feature_name": feature_name,
            "baseline_mean": round(baseline_mean, 4),
            "recent_mean": round(recent_mean, 4),
            "drift_score": round(drift_score, 4),
            "is_drifted": is_drifted,
            "status": status,
        }

    @staticmethod
    def evaluate_all_features(
        baseline_features: dict[str, list[float]],
        recent_features: dict[str, list[float]],
    ) -> list[dict]:
        """
        Evaluates drift for all tracked features: EMA50, VWAP, MACD, ADX, Market Structure, PCR, Options, etc.
        """
        results = []
        for feature_name in baseline_features.keys():
            if feature_name in recent_features:
                b_data = baseline_features[feature_name]
                r_data = recent_features[feature_name]
                res = DriftMonitor.calculate_drift(feature_name, b_data, r_data)
                results.append(res)
        return results
