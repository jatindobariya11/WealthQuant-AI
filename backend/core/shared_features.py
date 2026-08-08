"""
Shared technical indicators and feature calculations to ensure training-serving parity.
All calculations should be imported from this file by both training and inference pipelines.
"""

import numpy as np
import pandas as pd


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """True Wilder's smoothed RSI using Exponential Moving Average."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(com=period - 1, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(com=period - 1, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Standard Exponential Moving Average MACD."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_adx(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """True Average Directional Index (ADX) matching Wilder's smoothing."""
    up = high.diff()
    down = -low.diff()
    pos = up.where((up > down) & (up > 0), 0)
    neg = down.where((down > up) & (down > 0), 0)

    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1
    ).max(axis=1)

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    pos_di = (
        100 * pos.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
    )
    neg_di = (
        100 * neg.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
    )
    dx = (100 * (pos_di - neg_di).abs() / (pos_di + neg_di)).fillna(0)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def compute_atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """Average True Range (ATR)."""
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(period).mean()


def compute_bollinger_bands(
    close: pd.Series, period: int = 20, std_dev: int = 2
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands (Upper, Mid, Lower)."""
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower


def compute_stoch_rsi(
    close: pd.Series, period: int = 14, smooth_k: int = 3, smooth_d: int = 3
) -> tuple[pd.Series, pd.Series]:
    """StochRSI calculation (K and D lines)."""
    rsi = compute_rsi(close, period)
    rsi_min = rsi.rolling(period).min()
    rsi_max = rsi.rolling(period).max()
    stoch = (rsi - rsi_min) / (rsi_max - rsi_min).replace(0, np.nan) * 100
    k = stoch.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()
    return k, d


def compute_volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """Volume ratio relative to its rolling average."""
    vol_ma = volume.rolling(period).mean().replace(0, np.nan)
    return (volume / vol_ma).fillna(1.0)
