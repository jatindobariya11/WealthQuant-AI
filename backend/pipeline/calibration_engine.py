"""
WealthQuant V7.7 — Prediction Calibration Engine
=================================================
Computes Brier Score, Log Loss, Expected Calibration Error (ECE), and Reliability Buckets.
Generates rolling 50, 100, 250 prediction calibration reports.
Replaces low-sample text with Calibration Status: Learning, Reliable, Institution Grade.
"""

import logging

import numpy as np

logger = logging.getLogger("pipeline.calibration_engine")


def compute_brier_score(predictions: list[float], outcomes: list[float]) -> float:
    """
    Compute Brier score: Mean squared error of probability predictions.
    Range [0, 1], lower is better. Perfect calibration = 0.0.
    """
    if not predictions or len(predictions) != len(outcomes):
        return 1.0
    preds = np.clip(np.array(predictions), 0.0, 1.0)
    outs = np.clip(np.array(outcomes), 0.0, 1.0)
    return float(np.mean((preds - outs) ** 2))


def compute_log_loss(
    predictions: list[float], outcomes: list[float], eps: float = 1e-15
) -> float:
    """
    Compute Binary Cross-Entropy Log Loss.
    Range [0, inf), lower is better. Perfect = 0.0.
    """
    if not predictions or len(predictions) != len(outcomes):
        return 10.0
    preds = np.clip(np.array(predictions), eps, 1.0 - eps)
    outs = np.clip(np.array(outcomes), 0.0, 1.0)
    loss = -(outs * np.log(preds) + (1.0 - outs) * np.log(1.0 - preds))
    return float(np.mean(loss))


def compute_ece(
    predictions: list[float], outcomes: list[float], n_bins: int = 10
) -> float:
    """
    Compute Expected Calibration Error (ECE).
    Divides confidence into n_bins equal width bins, calculates weighted avg of |acc - conf|.
    Range [0, 1], lower is better. Perfect = 0.0.
    """
    if not predictions or len(predictions) != len(outcomes):
        return 1.0

    preds = np.clip(np.array(predictions), 0.0, 1.0)
    outs = np.clip(np.array(outcomes), 0.0, 1.0)
    n = len(preds)

    bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0

    for i in range(n_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]

        # Include upper bound in last bin
        if i == n_bins - 1:
            in_bin = (preds >= bin_lower) & (preds <= bin_upper)
        else:
            in_bin = (preds >= bin_lower) & (preds < bin_upper)

        bin_size = np.sum(in_bin)
        if bin_size > 0:
            bin_acc = np.mean(outs[in_bin])
            bin_conf = np.mean(preds[in_bin])
            ece += (bin_size / n) * abs(bin_acc - bin_conf)

    return float(ece)


def compute_reliability_buckets(
    predictions: list[float], outcomes: list[float], n_bins: int = 10
) -> list[dict]:
    """
    Compute reliability diagram bucket statistics.
    Returns list of dicts for each confidence bin.
    """
    if not predictions or len(predictions) != len(outcomes):
        return []

    preds = np.clip(np.array(predictions), 0.0, 1.0)
    outs = np.clip(np.array(outcomes), 0.0, 1.0)
    n = len(preds)

    bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
    buckets = []

    for i in range(n_bins):
        bin_lower = float(bin_boundaries[i])
        bin_upper = float(bin_boundaries[i + 1])

        if i == n_bins - 1:
            in_bin = (preds >= bin_lower) & (preds <= bin_upper)
        else:
            in_bin = (preds >= bin_lower) & (preds < bin_upper)

        count = int(np.sum(in_bin))
        if count > 0:
            avg_conf = float(np.mean(preds[in_bin]))
            avg_acc = float(np.mean(outs[in_bin]))
            gap = float(avg_acc - avg_conf)
        else:
            avg_conf = (bin_lower + bin_upper) / 2.0
            avg_acc = 0.0
            gap = 0.0

        buckets.append(
            {
                "bin_index": i + 1,
                "bin_range": f"{bin_lower:.1f}-{bin_upper:.1f}",
                "sample_count": count,
                "avg_predicted_conf": round(avg_conf, 4),
                "actual_accuracy": round(avg_acc, 4),
                "calibration_gap": round(gap, 4),
            }
        )

    return buckets


def get_calibration_status(n_samples: int) -> str:
    """
    Determine calibration status level based on historical sample size.
      < 20:   Learning
      20-99:  Reliable
      >= 100: Institution Grade
    """
    if n_samples < 20:
        return "Learning"
    elif n_samples < 100:
        return "Reliable"
    else:
        return "Institution Grade"


class CalibrationEngine:
    """
    Evaluates prediction calibration metrics over rolling windows.
    """

    @staticmethod
    def evaluate_predictions(predictions: list[float], outcomes: list[float]) -> dict:
        """
        Full evaluation of predictions vs actual outcomes.
        Returns dict with brier_score, log_loss, ece_score, calibration_status, reliability_buckets.
        """
        n = len(predictions)
        status = get_calibration_status(n)

        if n == 0:
            return {
                "n_samples": 0,
                "brier_score": 1.0,
                "log_loss": 10.0,
                "ece_score": 1.0,
                "calibration_status": status,
                "reliability_buckets": [],
            }

        brier = compute_brier_score(predictions, outcomes)
        logloss = compute_log_loss(predictions, outcomes)
        ece = compute_ece(predictions, outcomes)
        buckets = compute_reliability_buckets(predictions, outcomes)

        return {
            "n_samples": n,
            "brier_score": round(brier, 4),
            "log_loss": round(logloss, 4),
            "ece_score": round(ece, 4),
            "calibration_status": status,
            "reliability_buckets": buckets,
        }

    @staticmethod
    def evaluate_rolling_windows(
        predictions: list[float],
        outcomes: list[float],
        windows: list[int] = [50, 100, 250],
    ) -> dict:
        """
        Computes rolling calibration statistics for specified window sizes.
        """
        results = {}
        n = len(predictions)

        for w in windows:
            if n >= w:
                sub_preds = predictions[-w:]
                sub_outs = outcomes[-w:]
            else:
                sub_preds = predictions
                sub_outs = outcomes

            eval_res = CalibrationEngine.evaluate_predictions(sub_preds, sub_outs)
            results[f"rolling_{w}"] = eval_res

        return results
