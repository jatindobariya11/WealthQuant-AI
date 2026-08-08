"""
Pure indicator functions — NO imports from other project files.
All other files import FROM here. Nothing here imports from project files.
"""

import numpy as np
import pandas as pd


def safe(v, dec=2):
    try:
        # Handle pandas Series/DataFrame
        if hasattr(v, "iloc"):
            if hasattr(v, "empty") and v.empty:
                return None
            v = v.iloc[-1]

        # If still a Series (MultiIndex case), take first element
        if hasattr(v, "values"):
            v = v.values[0]

        if v is None:
            return None
        x = float(v)
        if np.isnan(x) or np.isinf(x):
            return None
        return round(x, dec)
    except:
        return None


def calc_rsi(closes, period=14):
    delta = closes.diff()
    gain = delta.clip(lower=0).ewm(com=period - 1, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(com=period - 1, min_periods=period).mean()
    rs = gain / loss
    return (100 - 100 / (1 + rs)).round(2)


def calc_macd(closes, fast=12, slow=26, signal=9):
    ef = closes.ewm(span=fast, adjust=False).mean()
    es = closes.ewm(span=slow, adjust=False).mean()
    mac = ef - es
    sig = mac.ewm(span=signal, adjust=False).mean()
    return mac.round(4), sig.round(4), (mac - sig).round(4)


def calc_bb(closes, period=20, std=2):
    mid = closes.rolling(period).mean()
    sd = closes.rolling(period).std()
    return (mid + std * sd).round(2), mid.round(2), (mid - std * sd).round(2)


def calc_stoch_rsi(closes, period=14):
    delta = closes.diff()
    gain = delta.clip(lower=0).ewm(com=period - 1, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(com=period - 1, min_periods=period).mean()
    rs = gain / loss
    rsi = 100 - 100 / (1 + rs)
    lo = rsi.rolling(period).min()
    hi = rsi.rolling(period).max()
    k = (rsi - lo) / (hi - lo) * 100
    return k.fillna(50).round(2)  # never NaN


def calc_ema(closes, p):
    return closes.ewm(span=p, adjust=False).mean().round(2)


def calc_atr(df, period=14):
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean().round(2)


def calc_adx(df, period=14):
    up = df["High"].diff()
    down = -df["Low"].diff()
    pos = up.where((up.values > down.values) & (up.values > 0), 0)
    neg = down.where((down.values > up.values) & (down.values > 0), 0)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr14 = tr.ewm(alpha=1 / period, adjust=False).mean()
    pos_di = (100 * pos.ewm(alpha=1 / period, adjust=False).mean() / atr14).round(2)
    neg_di = (100 * neg.ewm(alpha=1 / period, adjust=False).mean() / atr14).round(2)
    dx = (100 * (pos_di - neg_di).abs() / (pos_di + neg_di)).fillna(0)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean().round(2)
    return adx, pos_di, neg_di


def calc_vwap(df, window=20):
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    return (tp * df["Volume"]).rolling(window=window, min_periods=1).sum() / df[
        "Volume"
    ].rolling(window=window, min_periods=1).sum()


def calc_atr_raw(df, period=14):
    """Returns ATR series (not just last value)."""
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def candle_pattern(df):
    o, h, l, c = (float(df[x].iloc[-1]) for x in ["Open", "High", "Low", "Close"])
    body = abs(c - o)
    rng = h - l
    if rng == 0:
        return "FLAT"
    upper = h - max(o, c)
    lower = min(o, c) - l
    ratio = body / rng
    if ratio < 0.1:
        return "DOJI"
    if lower > body * 2 and upper < body * 0.3:
        return "HAMMER"
    if upper > body * 2 and lower < body * 0.3:
        return "SHOOTING_STAR"
    if ratio > 0.8 and c > o:
        return "BULLISH_MARUBOZU"
    if ratio > 0.8 and c < o:
        return "BEARISH_MARUBOZU"
    if c > o and body > rng * 0.6:
        return "BULLISH"
    if c < o and body > rng * 0.6:
        return "BEARISH"
    return "NEUTRAL"


def candle_pattern_series(df):
    o = df["Open"]
    h = df["High"]
    l = df["Low"]
    c = df["Close"]
    body = (c - o).abs()
    rng = h - l

    patterns = pd.Series("NEUTRAL", index=df.index)

    flat_mask = rng == 0
    patterns.loc[flat_mask] = "FLAT"

    valid_mask = ~flat_mask
    if not valid_mask.any():
        return patterns

    o_v, h_v, l_v, c_v = o[valid_mask], h[valid_mask], l[valid_mask], c[valid_mask]
    body_v = body[valid_mask]
    rng_v = rng[valid_mask]

    upper = h_v - np.maximum(o_v, c_v)
    lower = np.minimum(o_v, c_v) - l_v
    ratio = body_v / rng_v

    doji_mask = ratio < 0.1
    patterns.loc[doji_mask[doji_mask].index] = "DOJI"

    hammer_mask = (lower > body_v * 2) & (upper < body_v * 0.3) & (~doji_mask)
    patterns.loc[hammer_mask[hammer_mask].index] = "HAMMER"

    shooting_mask = (upper > body_v * 2) & (lower < body_v * 0.3) & (~doji_mask)
    patterns.loc[shooting_mask[shooting_mask].index] = "SHOOTING_STAR"

    bull_maru_mask = (ratio > 0.8) & (c_v > o_v) & (~doji_mask)
    patterns.loc[bull_maru_mask[bull_maru_mask].index] = "BULLISH_MARUBOZU"

    bear_maru_mask = (ratio > 0.8) & (c_v < o_v) & (~doji_mask)
    patterns.loc[bear_maru_mask[bear_maru_mask].index] = "BEARISH_MARUBOZU"

    bull_mask = (c_v > o_v) & (body_v > rng_v * 0.6) & (~bull_maru_mask) & (~doji_mask)
    patterns.loc[bull_mask[bull_mask].index] = "BULLISH"

    bear_mask = (c_v < o_v) & (body_v > rng_v * 0.6) & (~bear_maru_mask) & (~doji_mask)
    patterns.loc[bear_mask[bear_mask].index] = "BEARISH"

    return patterns


def horizon_return(closes, bars):
    """(close - close[bars_ago]) / close[bars_ago]"""
    if len(closes) <= bars:
        return None
    c_now = float(closes.iloc[-1])
    c_prev = float(closes.iloc[-bars - 1])
    if c_prev == 0:
        return None
    return round((c_now - c_prev) / c_prev, 6)


def build_chart_records(df, extra_cols, n=120):
    """
    Slice last n rows of df (which has all indicator columns already assigned).
    extra_cols = list of column names to include.
    Returns clean list of dicts with None instead of NaN.
    """
    cols = [c for c in extra_cols if c in df.columns]
    chart_df = df[cols].tail(n).copy()

    # If the intervals are >= 1 day apart, only show the date
    if len(df) >= 2 and (df.index[-1] - df.index[-2]).total_seconds() >= 86400:
        chart_df.index = chart_df.index.strftime("%Y-%m-%d")
    else:
        chart_df.index = chart_df.index.strftime("%Y-%m-%d %H:%M")
    records = []
    for row in (
        chart_df.reset_index().rename(columns={"index": "Datetime"}).to_dict("records")
    ):
        clean = {}
        for k, v in row.items():
            if k in ("Datetime", "Date"):
                clean[k] = str(v)
            else:
                clean[k] = safe(v)
        records.append(clean)
    return records


def calc_sr_levels(df, lookback=30):
    recent = df.tail(lookback)
    price = float(df["Close"].iloc[-1])
    step = 100 if price > 20000 else 50 if price > 5000 else 10
    th, tl = {}, {}
    for i in range(2, len(recent) - 2):
        h = round(float(recent["High"].iloc[i]) / step) * step
        l = round(float(recent["Low"].iloc[i]) / step) * step
        tol = step * 2
        for j in range(max(0, i - 2), min(len(recent), i + 3)):
            if abs(float(recent["High"].iloc[j]) - h) < tol:
                th[h] = th.get(h, 0) + 1
            if abs(float(recent["Low"].iloc[j]) - l) < tol:
                tl[l] = tl.get(l, 0) + 1
    res = sorted([(k, v) for k, v in th.items() if k > price], key=lambda x: x[0])[:3]
    sup = sorted(
        [(k, v) for k, v in tl.items() if k < price], key=lambda x: x[0], reverse=True
    )[:3]

    def strength(v):
        return "VERY STRONG" if v > 10 else "STRONG" if v > 5 else "MODERATE"

    return {
        "resistance": [
            {"level": k, "touches": v, "strength": strength(v)} for k, v in res
        ],
        "support": [
            {"level": k, "touches": v, "strength": strength(v)} for k, v in sup
        ],
    }


def calc_vol_ratio(df):
    try:
        vol = df["Volume"]
        vol_ma20 = vol.rolling(20).mean().ffill()
        va = vol_ma20.iloc[-1]
        vn = vol.iloc[-1]
        return round(float(vn / va), 2) if va > 0 else 1.0
    except:
        return 1.0


def calc_entry_exit(price, atr_val, signal):
    if not atr_val or "NO_TRADE" in (signal or ""):
        return {
            "entry": price,
            "stop_loss": None,
            "target1": None,
            "target2": None,
            "risk": None,
            "reward": None,
            "rr": None,
        }
    if "PUT" in signal or "SELL" in signal:
        sl = round(price + atr_val * 1.5, 2)
        t1 = round(price - atr_val * 2, 2)
        t2 = round(price - atr_val * 3.5, 2)
    else:
        sl = round(price - atr_val * 1.5, 2)
        t1 = round(price + atr_val * 2, 2)
        t2 = round(price + atr_val * 3.5, 2)
    return {
        "entry": price,
        "stop_loss": sl,
        "target1": t1,
        "target2": t2,
        "risk": round(abs(price - sl), 2),
        "reward": round(abs(t1 - price), 2),
        "rr": round(abs(t1 - price) / max(abs(price - sl), 1), 2),
    }


def calc_tech_score_adx(base_score, adx_val):
    """Amplify by ADX strength but always clamp to ±10."""
    amplified = round(base_score * 1.2) if (adx_val and adx_val > 25) else base_score
    return max(-10, min(10, int(amplified)))
