"""
WealthQuant V7.7 — Feature Drift Engine
========================================
Measures daily distribution drift across key indicator dimensions:
EMA50, VWAP, MACD, ADX, Market Structure, PCR, Options Wall Distance.
Classifies each feature as Healthy (Green), Warning (Yellow), or Critical (Red).
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger("pipeline.feature_drift_engine")


class FeatureDriftEngine:
    """
    Calculates distribution drift using Z-score normalized mean differences
    between a long-term baseline (e.g. last 100 bars) and a recent window (last 20 bars).
    """

    FEATURE_DIMENSIONS = [
        "EMA50",
        "VWAP",
        "MACD",
        "ADX",
        "MARKET_STRUCTURE",
        "PCR",
        "CALL_WALL_DIST",
        "PUT_WALL_DIST",
    ]

    @staticmethod
    def classify_drift(drift_score: float) -> Tuple[str, str]:
        """
        Classifies drift score into (status, color_indicator):
            < 0.10:           Healthy  (GREEN)
            0.10 <= x < 0.25: Warning  (YELLOW)
            >= 0.25:          Critical (RED)
        """
        abs_score = abs(drift_score)
        if abs_score < 0.10:
            return "Healthy", "GREEN"
        elif abs_score < 0.25:
            return "Warning", "YELLOW"
        else:
            return "Critical", "RED"

    @classmethod
    def analyze_series_drift(
        cls,
        feature_name: str,
        series: pd.Series,
        baseline_window: int = 100,
        recent_window: int = 20,
    ) -> dict:
        """
        Analyzes drift for a single numeric pandas Series.
        """
        s = series.dropna()
        if len(s) < recent_window + 10:
            return {
                "feature_name": feature_name,
                "baseline_mean": 0.0,
                "recent_mean": 0.0,
                "drift_score": 0.0,
                "status": "Healthy",
                "color": "GREEN",
                "is_drifted": False,
                "samples": len(s),
            }

        recent = s.iloc[-recent_window:]
        baseline = (
            s.iloc[-baseline_window:-recent_window]
            if len(s) >= baseline_window
            else s.iloc[:-recent_window]
        )

        base_mean = float(baseline.mean())
        base_std = float(baseline.std())
        rec_mean = float(recent.mean())

        if base_std < 1e-6:
            drift_score = 0.0
        else:
            # Normalized mean shift (Z-score magnitude)
            drift_score = float((rec_mean - base_mean) / base_std)

        status, color = cls.classify_drift(drift_score)

        return {
            "feature_name": feature_name,
            "baseline_mean": round(base_mean, 4),
            "recent_mean": round(rec_mean, 4),
            "drift_score": round(drift_score, 4),
            "status": status,
            "color": color,
            "is_drifted": status != "Healthy",
            "samples": len(s),
        }

    @classmethod
    def analyze_dataset_drift(
        cls, ohlcv_df: pd.DataFrame, options_df: pd.DataFrame = None
    ) -> list[dict]:
        """
        Computes drift across all 8 feature dimensions using OHLCV & Options dataframes.
        """
        results = []
        if ohlcv_df.empty or len(ohlcv_df) < 30:
            for feat in cls.FEATURE_DIMENSIONS:
                results.append(
                    {
                        "feature_name": feat,
                        "baseline_mean": 0.0,
                        "recent_mean": 0.0,
                        "drift_score": 0.0,
                        "status": "Healthy",
                        "color": "GREEN",
                        "is_drifted": False,
                        "samples": 0,
                    }
                )
            return results

        close = ohlcv_df["close"]
        high = ohlcv_df["high"]
        low = ohlcv_df["low"]
        volume = ohlcv_df["volume"]

        # 1. EMA50
        ema50 = close.ewm(span=min(50, len(close)), adjust=False).mean()
        ema50_dist = (close - ema50) / close
        results.append(cls.analyze_series_drift("EMA50", ema50_dist))

        # 2. VWAP
        tp = (high + low + close) / 3.0
        vwap = (tp * volume).cumsum() / (volume.cumsum() + 1e-6)
        vwap_dist = (close - vwap) / close
        results.append(cls.analyze_series_drift("VWAP", vwap_dist))

        # 3. MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = (ema12 - ema26) / close
        results.append(cls.analyze_series_drift("MACD", macd))

        # 4. ADX (Approximate trend strength via rolling range)
        tr = np.maximum(high - low, np.abs(high - close.shift(1)))
        atr14 = tr.rolling(14).mean().fillna(close * 0.01)
        adx_approx = (atr14 / close) * 100.0
        results.append(cls.analyze_series_drift("ADX", adx_approx))

        # 5. MARKET_STRUCTURE (High-Low volatility spread)
        struct_score = (high - low) / (atr14 + 1e-6)
        results.append(cls.analyze_series_drift("MARKET_STRUCTURE", struct_score))

        # Options features
        if options_df is not None and not options_df.empty:
            pcr = (
                options_df["pcr"]
                if "pcr" in options_df.columns
                else pd.Series(1.0, index=ohlcv_df.index)
            )
            cw_dist = (
                (options_df["call_wall"] - close) / close
                if "call_wall" in options_df.columns
                else pd.Series(0.0, index=ohlcv_df.index)
            )
            pw_dist = (
                (close - options_df["put_wall"]) / close
                if "put_wall" in options_df.columns
                else pd.Series(0.0, index=ohlcv_df.index)
            )
        else:
            pcr = pd.Series(1.0, index=ohlcv_df.index)
            cw_dist = pd.Series(0.0, index=ohlcv_df.index)
            pw_dist = pd.Series(0.0, index=ohlcv_df.index)

        results.append(cls.analyze_series_drift("PCR", pcr))
        results.append(cls.analyze_series_drift("CALL_WALL_DIST", cw_dist))
        results.append(cls.analyze_series_drift("PUT_WALL_DIST", pw_dist))

        return results
