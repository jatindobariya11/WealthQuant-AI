import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from core.shared_features import *

from .config import *


def _supertrend(df: pd.DataFrame, period=10, mult=3):
    """Returns (supertrend_value, direction) Series. direction: 1=bullish, -1=bearish."""
    # Dedup the entire input DataFrame index first to prevent "cannot reindex" errors
    if df.index.duplicated().any():
        df = df[~df.index.duplicated(keep="last")]
    df = df.sort_index()

    high = df["High"].squeeze()
    low = df["Low"].squeeze()
    close = df["Close"].squeeze()

    hl2 = (high + low) / 2
    atr = compute_atr(high, low, close, period)

    upper = hl2 + mult * atr
    lower = hl2 - mult * atr

    st = pd.Series(np.nan, index=df.index)
    dire = pd.Series(1, index=df.index)

    # Find the first index where ATR is not NaN
    first_valid = atr.first_valid_index()
    if first_valid is None:
        return st, dire

    first_idx = df.index.get_loc(first_valid)

    # Initialize for the first valid index
    st.iloc[first_idx] = (
        lower.iloc[first_idx]
        if close.iloc[first_idx] >= hl2.iloc[first_idx]
        else upper.iloc[first_idx]
    )
    dire.iloc[first_idx] = 1 if close.iloc[first_idx] >= hl2.iloc[first_idx] else -1

    for i in range(first_idx + 1, len(df)):
        prev_upper = upper.iloc[i - 1]
        prev_lower = lower.iloc[i - 1]
        prev_close = close.iloc[i - 1]

        # Upper band adjustment
        if (
            np.isnan(prev_upper)
            or upper.iloc[i] < prev_upper
            or prev_close > prev_upper
        ):
            upper.iloc[i] = upper.iloc[i]
        else:
            upper.iloc[i] = prev_upper

        # Lower band adjustment
        if (
            np.isnan(prev_lower)
            or lower.iloc[i] > prev_lower
            or prev_close < prev_lower
        ):
            lower.iloc[i] = lower.iloc[i]
        else:
            lower.iloc[i] = prev_lower

        # Direction
        if dire.iloc[i - 1] == 1 and close.iloc[i] < lower.iloc[i]:
            dire.iloc[i] = -1
        elif dire.iloc[i - 1] == -1 and close.iloc[i] > upper.iloc[i]:
            dire.iloc[i] = 1
        else:
            dire.iloc[i] = dire.iloc[i - 1]

        st.iloc[i] = lower.iloc[i] if dire.iloc[i] == 1 else upper.iloc[i]

    return st, dire


def _safe(val):
    """Convert numpy float to Python float, return None if NaN."""
    try:
        v = float(val)
        return None if np.isnan(v) or np.isinf(v) else round(v, 4)
    except Exception:
        return None


def _generate_fallback_df(symbol: str, interval: str) -> pd.DataFrame:
    base_price = 51200.0 if "BANK" in symbol.upper() else 24400.0
    freq_str = (
        "15min"
        if "15m" in interval
        else ("1h" if "1h" in interval else ("1D" if "1d" in interval else "5min"))
    )
    dates = pd.date_range(end=datetime.now(), periods=100, freq=freq_str)
    np.random.seed(abs(hash(symbol.upper())) % 10000)
    returns = np.random.normal(0.0001, 0.0015, 100)
    prices = base_price * np.exp(np.cumsum(returns))

    df = pd.DataFrame(
        {
            "Open": prices * (1 - 0.001 * np.random.rand(100)),
            "High": prices * (1 + 0.002 * np.random.rand(100)),
            "Low": prices * (1 - 0.002 * np.random.rand(100)),
            "Close": prices,
            "Volume": np.random.randint(1000, 50000, 100),
        },
        index=dates,
    )
    return df


def refresh_nse_session():
    """Warms up the session and ensures cookies are set."""
    try:
        NSE_SESSION.get("https://www.nseindia.com", timeout=10)
        time.sleep(0.3)  # Small delay for cookie stability
    except Exception as e:
        print(f"[NSE] Session refresh failed: {e}")


def map_confidence(score: int) -> dict:
    """Map a numeric confidence score (0-100) to a labelled dict."""
    label = "HIGH" if score >= 70 else "MEDIUM" if score >= 40 else "LOW"
    return {"label": label, "score": score}


class FetchedAt:
    """Track when each data source was last fetched (UTC)."""

    def __init__(self):
        self._t = {}

    def mark(self, key):
        self._t[key] = datetime.now(timezone.utc)

    def to_dict(self):
        return {k: v.isoformat() for k, v in self._t.items()}
