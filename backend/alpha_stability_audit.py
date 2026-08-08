"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         WEALTHQUANT V7.2.2 — ALPHA STABILITY AUDIT                          ║
║         Mission  : Validate robustness of every feature in                   ║
║                    feature_alpha_rankings                                     ║
║         Phases   : 7  |  Output: ALPHA_STABILITY_REPORT.md                  ║
║         Note     : Audit-only. No new alpha models. No new engines.          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import mutual_info_score

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# FEATURE ALPHA RANKINGS REGISTRY
# Discovered features from: base_indicators.py, advanced_indicators.py,
#                            indicators.py, signals.py
# ─────────────────────────────────────────────────────────────────────────────

FEATURE_REGISTRY = {
    # Momentum & Oscillators
    "RSI_14": {"category": "Momentum", "lookback": 14, "priority": "HIGH"},
    "RSI_Divergence": {"category": "Momentum", "lookback": 14, "priority": "MEDIUM"},
    "StochRSI_K": {"category": "Momentum", "lookback": 14, "priority": "MEDIUM"},
    "Stoch_K": {"category": "Momentum", "lookback": 14, "priority": "MEDIUM"},
    "Stoch_D": {"category": "Momentum", "lookback": 14, "priority": "LOW"},
    # Trend & EMA
    "MACD_Line": {"category": "Trend", "lookback": 26, "priority": "HIGH"},
    "MACD_Signal": {"category": "Trend", "lookback": 26, "priority": "HIGH"},
    "MACD_Histogram": {"category": "Trend", "lookback": 26, "priority": "HIGH"},
    "MACD_Crossover": {"category": "Trend", "lookback": 26, "priority": "HIGH"},
    "EMA_9": {"category": "Trend", "lookback": 9, "priority": "HIGH"},
    "EMA_20": {"category": "Trend", "lookback": 20, "priority": "HIGH"},
    "EMA_21": {"category": "Trend", "lookback": 21, "priority": "HIGH"},
    "EMA_50": {"category": "Trend", "lookback": 50, "priority": "HIGH"},
    "EMA_200": {"category": "Trend", "lookback": 200, "priority": "MEDIUM"},
    "EMA_9_20_Cross": {"category": "Trend", "lookback": 20, "priority": "HIGH"},
    "EMA_20_50_Cross": {"category": "Trend", "lookback": 50, "priority": "HIGH"},
    "Price_vs_EMA20": {"category": "Trend", "lookback": 20, "priority": "HIGH"},
    "Price_vs_EMA50": {"category": "Trend", "lookback": 50, "priority": "MEDIUM"},
    "Supertrend": {"category": "Trend", "lookback": 10, "priority": "HIGH"},
    "Supertrend_Dir": {"category": "Trend", "lookback": 10, "priority": "HIGH"},
    # Volatility
    "ATR_14": {"category": "Volatility", "lookback": 14, "priority": "HIGH"},
    "BB_Upper": {"category": "Volatility", "lookback": 20, "priority": "MEDIUM"},
    "BB_Lower": {"category": "Volatility", "lookback": 20, "priority": "MEDIUM"},
    "BB_Width": {"category": "Volatility", "lookback": 20, "priority": "HIGH"},
    "BB_Position": {"category": "Volatility", "lookback": 20, "priority": "HIGH"},
    "BB_Squeeze": {"category": "Volatility", "lookback": 20, "priority": "HIGH"},
    # Strength
    "ADX_14": {"category": "Strength", "lookback": 14, "priority": "HIGH"},
    "DI_Plus": {"category": "Strength", "lookback": 14, "priority": "MEDIUM"},
    "DI_Minus": {"category": "Strength", "lookback": 14, "priority": "MEDIUM"},
    "ADX_Trend_Strong": {"category": "Strength", "lookback": 14, "priority": "HIGH"},
    # Volume
    "VWAP": {"category": "Volume", "lookback": 1, "priority": "HIGH"},
    "Price_vs_VWAP": {"category": "Volume", "lookback": 1, "priority": "HIGH"},
    "OBV": {"category": "Volume", "lookback": 1, "priority": "MEDIUM"},
    "OBV_Slope": {"category": "Volume", "lookback": 5, "priority": "MEDIUM"},
    "Vol_Ratio": {"category": "Volume", "lookback": 20, "priority": "HIGH"},
    "Vol_Surge": {"category": "Volume", "lookback": 20, "priority": "HIGH"},
    # Structure
    "Market_Structure": {"category": "Structure", "lookback": 30, "priority": "HIGH"},
    "HH_HL_Pattern": {"category": "Structure", "lookback": 5, "priority": "HIGH"},
    "LL_LH_Pattern": {"category": "Structure", "lookback": 5, "priority": "HIGH"},
    "SR_Support": {"category": "Structure", "lookback": 30, "priority": "HIGH"},
    "SR_Resistance": {"category": "Structure", "lookback": 30, "priority": "HIGH"},
    "Gap_Up": {"category": "Structure", "lookback": 1, "priority": "MEDIUM"},
    "Gap_Down": {"category": "Structure", "lookback": 1, "priority": "MEDIUM"},
    "Liquidity_Sweep": {"category": "Structure", "lookback": 10, "priority": "MEDIUM"},
    # Candle Patterns
    "Candle_Pattern": {"category": "Candle", "lookback": 1, "priority": "MEDIUM"},
    "Doji": {"category": "Candle", "lookback": 1, "priority": "LOW"},
    "Hammer": {"category": "Candle", "lookback": 1, "priority": "MEDIUM"},
    "Shooting_Star": {"category": "Candle", "lookback": 1, "priority": "MEDIUM"},
    "Marubozu_Bull": {"category": "Candle", "lookback": 1, "priority": "MEDIUM"},
    "Marubozu_Bear": {"category": "Candle", "lookback": 1, "priority": "MEDIUM"},
    # Composite Signals
    "Technical_Score": {"category": "Composite", "lookback": 26, "priority": "HIGH"},
    "Signal_Desk_Score": {"category": "Composite", "lookback": 26, "priority": "HIGH"},
    "Trend_Score": {"category": "Composite", "lookback": 50, "priority": "HIGH"},
    "Momentum_Rank": {"category": "Composite", "lookback": 14, "priority": "MEDIUM"},
    "Regime_Bias": {"category": "Composite", "lookback": 30, "priority": "MEDIUM"},
}

TOTAL_FEATURES = len(FEATURE_REGISTRY)


# =============================================================================
# PHASE 0 — DATA GENERATION & FEATURE COMPUTATION
# =============================================================================


def generate_market_data(n_bars: int = 600, seed: int = 42) -> pd.DataFrame:
    """Synthetic OHLCV with labelled market regimes for audit stress-testing."""
    np.random.seed(seed)
    dates = pd.date_range(end=datetime(2026, 6, 21), periods=n_bars, freq="D")

    regime_blocks = [
        ("Bull", 120, 0.0006, 0.010),
        ("Bear", 100, -0.0005, 0.012),
        ("Sideways", 100, 0.00005, 0.006),
        ("HighVol", 120, 0.0002, 0.025),
        ("LowVol", 160, 0.0003, 0.004),
    ]
    closes = [18000.0]
    regimes = []
    for regime, length, drift, vol in regime_blocks:
        for r in np.random.normal(drift, vol, length):
            closes.append(closes[-1] * (1 + r))
        regimes.extend([regime] * length)

    closes = np.array(closes[1:][:n_bars])
    regimes = regimes[:n_bars]
    spreads = np.abs(np.random.normal(0, 0.007, n_bars))
    opens = closes * (1 + np.random.normal(0, 0.003, n_bars))
    highs = np.maximum(opens, closes) * (1 + spreads)
    lows = np.minimum(opens, closes) * (1 - spreads)
    volume = np.random.lognormal(mean=np.log(500_000), sigma=0.5, size=n_bars).astype(
        int
    )

    return pd.DataFrame(
        {
            "Open": opens.round(2),
            "High": highs.round(2),
            "Low": lows.round(2),
            "Close": closes.round(2),
            "Volume": volume,
            "Regime": regimes,
        },
        index=dates,
    )


# ── Indicator helpers ─────────────────────────────────────────────────────────


def _rsi(c: pd.Series, p: int = 14) -> pd.Series:
    d = c.diff()
    g = d.clip(lower=0).ewm(com=p - 1, min_periods=p).mean()
    l = (-d.clip(upper=0)).ewm(com=p - 1, min_periods=p).mean()
    return (100 - 100 / (1 + g / l)).round(4)


def _macd(c: pd.Series, fast=12, slow=26, sig=9):
    ef = c.ewm(span=fast, adjust=False).mean()
    es = c.ewm(span=slow, adjust=False).mean()
    m = ef - es
    s = m.ewm(span=sig, adjust=False).mean()
    return m.round(6), s.round(6), (m - s).round(6)


def _ema(c: pd.Series, p: int) -> pd.Series:
    return c.ewm(span=p, adjust=False).mean().round(4)


def _atr(df: pd.DataFrame, p: int = 14) -> pd.Series:
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(p).mean().round(4)


def _adx(df: pd.DataFrame, p: int = 14):
    up = df["High"].diff()
    dn = -df["Low"].diff()
    pos = up.where((up > dn) & (up > 0), 0)
    neg = dn.where((dn > up) & (dn > 0), 0)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    a14 = tr.ewm(alpha=1 / p, adjust=False).mean()
    pdi = (100 * pos.ewm(alpha=1 / p, adjust=False).mean() / a14).round(4)
    ndi = (100 * neg.ewm(alpha=1 / p, adjust=False).mean() / a14).round(4)
    dx = (100 * (pdi - ndi).abs() / (pdi + ndi)).fillna(0)
    return dx.ewm(alpha=1 / p, adjust=False).mean().round(4), pdi, ndi


def _bb(c: pd.Series, p: int = 20, std: int = 2):
    mid = c.rolling(p).mean()
    sd = c.rolling(p).std()
    u = (mid + std * sd).round(4)
    l = (mid - std * sd).round(4)
    return u, mid.round(4), l, ((u - l) / mid * 100).round(4)


def _stoch(df: pd.DataFrame, k: int = 14, d: int = 3):
    lo = df["Low"].rolling(k).min()
    hi = df["High"].rolling(k).max()
    k_ = ((df["Close"] - lo) / (hi - lo + 1e-10) * 100).round(4)
    return k_, k_.rolling(d).mean().round(4)


def _stoch_rsi(c: pd.Series, p: int = 14) -> pd.Series:
    rsi = _rsi(c, p)
    lo = rsi.rolling(p).min()
    hi = rsi.rolling(p).max()
    return ((rsi - lo) / (hi - lo + 1e-10) * 100).fillna(50).round(4)


def _vwap(df: pd.DataFrame) -> pd.Series:
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    return (tp * df["Volume"]).cumsum() / df["Volume"].cumsum()


def _obv(df: pd.DataFrame) -> pd.Series:
    vals = [0]
    for i in range(1, len(df)):
        if df["Close"].iloc[i] > df["Close"].iloc[i - 1]:
            vals.append(vals[-1] + df["Volume"].iloc[i])
        elif df["Close"].iloc[i] < df["Close"].iloc[i - 1]:
            vals.append(vals[-1] - df["Volume"].iloc[i])
        else:
            vals.append(vals[-1])
    return pd.Series(vals, index=df.index, dtype=float)


def _supertrend(df: pd.DataFrame, p: int = 10, m: float = 3.0):
    hl2 = (df["High"] + df["Low"]) / 2
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(p).mean()
    upper = hl2 + m * atr
    lower = hl2 - m * atr
    st = pd.Series(np.nan, index=df.index)
    dir_ = pd.Series(0.0, index=df.index)
    for i in range(p, len(df)):
        if df["Close"].iloc[i] > upper.iloc[i - 1]:
            st.iloc[i] = lower.iloc[i]
            dir_.iloc[i] = 1
        elif df["Close"].iloc[i] < lower.iloc[i - 1]:
            st.iloc[i] = upper.iloc[i]
            dir_.iloc[i] = -1
        else:
            st.iloc[i] = st.iloc[i - 1]
            dir_.iloc[i] = dir_.iloc[i - 1]
    return st.round(4), dir_


def compute_all_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute every alpha signal from feature_alpha_rankings."""
    c = df["Close"].copy()

    # ── RSI family ────────────────────────────────────────────────────────────
    df["RSI_14"] = _rsi(c, 14)
    df["StochRSI_K"] = _stoch_rsi(c, 14)

    # ── MACD family ───────────────────────────────────────────────────────────
    macd, sig, hist = _macd(c)
    df["MACD_Line"] = macd
    df["MACD_Signal"] = sig
    df["MACD_Histogram"] = hist
    df["MACD_Crossover"] = (macd > sig).astype(float) * 2 - 1  # +1 bull / -1 bear

    # ── EMA family ────────────────────────────────────────────────────────────
    for p in [9, 20, 21, 50, 200]:
        df[f"EMA_{p}"] = _ema(c, p)
    df["EMA_9_20_Cross"] = (df["EMA_9"] > df["EMA_20"]).astype(float) * 2 - 1
    df["EMA_20_50_Cross"] = (df["EMA_20"] > df["EMA_50"]).astype(float) * 2 - 1
    df["Price_vs_EMA20"] = ((c - df["EMA_20"]) / df["EMA_20"]).round(6)
    df["Price_vs_EMA50"] = ((c - df["EMA_50"]) / df["EMA_50"]).round(6)

    # ── Supertrend ────────────────────────────────────────────────────────────
    df["Supertrend"], df["Supertrend_Dir"] = _supertrend(df, 10, 3)

    # ── ATR / Bollinger ────────────────────────────────────────────────────────
    df["ATR_14"] = _atr(df, 14)
    bu, bm, bl, bw = _bb(c, 20, 2)
    df["BB_Upper"] = bu
    df["BB_Lower"] = bl
    df["BB_Width"] = bw
    df["BB_Position"] = ((c - bm) / (bu - bl + 1e-10)).round(6)
    df["BB_Squeeze"] = (bw < bw.rolling(30).mean()).astype(float)

    # ── ADX / Strength ────────────────────────────────────────────────────────
    adx, pdi, ndi = _adx(df, 14)
    df["ADX_14"] = adx
    df["DI_Plus"] = pdi
    df["DI_Minus"] = ndi
    df["ADX_Trend_Strong"] = (adx > 25).astype(float)

    # ── Stochastic ────────────────────────────────────────────────────────────
    df["Stoch_K"], df["Stoch_D"] = _stoch(df, 14, 3)

    # ── Volume ────────────────────────────────────────────────────────────────
    df["VWAP"] = _vwap(df)
    df["Price_vs_VWAP"] = ((c - df["VWAP"]) / df["VWAP"]).round(6)
    df["OBV"] = _obv(df)
    df["OBV_Slope"] = df["OBV"].diff(5).round(4)
    vol_avg = df["Volume"].rolling(20).mean()
    df["Vol_Ratio"] = (df["Volume"] / vol_avg).round(4)
    df["Vol_Surge"] = (df["Vol_Ratio"] > 1.5).astype(float)

    # ── Price Action / Structure ──────────────────────────────────────────────
    df["HH_HL_Pattern"] = (
        (df["High"] > df["High"].shift(5)) & (df["Low"] > df["Low"].shift(5))
    ).astype(float)
    df["LL_LH_Pattern"] = (
        (df["Low"] < df["Low"].shift(5)) & (df["High"] < df["High"].shift(5))
    ).astype(float)
    df["Gap_Up"] = (df["Open"] > df["Close"].shift(1) * 1.003).astype(float)
    df["Gap_Down"] = (df["Open"] < df["Close"].shift(1) * 0.997).astype(float)
    df["Market_Structure"] = (df["HH_HL_Pattern"] - df["LL_LH_Pattern"]).round(4)
    df["SR_Support"] = df["Low"].rolling(30).min()
    df["SR_Resistance"] = df["High"].rolling(30).max()
    rh = df["High"].shift(1).rolling(5).max()
    rl = df["Low"].shift(1).rolling(5).min()
    df["Liquidity_Sweep"] = (
        ((df["High"] > rh) & (df["Close"] < rh))
        | ((df["Low"] < rl) & (df["Close"] > rl))
    ).astype(float)

    # ── Candle patterns ───────────────────────────────────────────────────────
    body = (c - df["Open"]).abs()
    rng = df["High"] - df["Low"]
    upper = df["High"] - pd.concat([c, df["Open"]], axis=1).max(axis=1)
    lower = pd.concat([c, df["Open"]], axis=1).min(axis=1) - df["Low"]
    ratio = body / (rng + 1e-10)
    df["Candle_Pattern"] = (c - df["Open"]) / (rng + 1e-10)
    df["Doji"] = (ratio < 0.10).astype(float)
    df["Hammer"] = ((lower > body * 2) & (upper < body * 0.3)).astype(float)
    df["Shooting_Star"] = ((upper > body * 2) & (lower < body * 0.3)).astype(float)
    df["Marubozu_Bull"] = ((ratio > 0.80) & (c > df["Open"])).astype(float)
    df["Marubozu_Bear"] = ((ratio > 0.80) & (c < df["Open"])).astype(float)

    # ── RSI Divergence ────────────────────────────────────────────────────────
    df["RSI_Divergence"] = 0.0
    for i in range(20, len(df)):
        if (
            c.iloc[i] > c.iloc[i - 10 : i].max()
            and df["RSI_14"].iloc[i] < df["RSI_14"].iloc[i - 10 : i].max()
        ):
            df.at[df.index[i], "RSI_Divergence"] = -1.0
        elif (
            c.iloc[i] < c.iloc[i - 10 : i].min()
            and df["RSI_14"].iloc[i] > df["RSI_14"].iloc[i - 10 : i].min()
        ):
            df.at[df.index[i], "RSI_Divergence"] = 1.0

    # ── Composite signals ─────────────────────────────────────────────────────
    ts = pd.Series(0.0, index=df.index)
    ts += (df["RSI_14"] < 45).astype(float)
    ts -= (df["RSI_14"] > 65).astype(float)
    ts += df["MACD_Crossover"] + df["EMA_9_20_Cross"] + df["EMA_20_50_Cross"]
    df["Technical_Score"] = ts.round(4)
    df["Trend_Score"] = (
        df["EMA_9_20_Cross"] + df["EMA_20_50_Cross"] + df["Supertrend_Dir"]
    ).round(4)
    df["Momentum_Rank"] = df["RSI_14"].rank(pct=True).round(4)
    df["Signal_Desk_Score"] = (
        df["Technical_Score"] + df["MACD_Crossover"] + df["EMA_9_20_Cross"]
    ).round(4)
    df["Regime_Bias"] = (df["EMA_20_50_Cross"] * df["ADX_Trend_Strong"]).round(4)

    return df


def compute_forward_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Attach forward return targets at multiple horizons."""
    for h in [1, 5, 10, 20, 30, 60, 90]:
        df[f"fwd_{h}d"] = df["Close"].pct_change(h).shift(-h).round(6)
    return df


# =============================================================================
# PHASE 1 — FEATURE DISCOVERY AUDIT
# =============================================================================


def phase1_feature_discovery(df: pd.DataFrame) -> dict:
    """Audit coverage, NaN rate, signal variance for every registered feature."""
    results = {}
    for feat, meta in FEATURE_REGISTRY.items():
        if feat not in df.columns:
            results[feat] = {
                "status": "MISSING",
                "nan_rate": 1.0,
                "coverage": 0.0,
                "signal_std": 0.0,
                "unique_vals": 0,
                "meta": meta,
            }
            continue
        s = df[feat].dropna()
        nan_rate = float(df[feat].isna().mean())
        results[feat] = {
            "status": "DISCOVERED",
            "nan_rate": round(nan_rate, 4),
            "coverage": round(1 - nan_rate, 4),
            "signal_std": round(float(s.std()) if len(s) > 1 else 0.0, 6),
            "unique_vals": int(s.nunique()),
            "meta": meta,
        }
    return results


# =============================================================================
# PHASE 2 — TIME STABILITY
# Period A | Period B | Period C
# =============================================================================


def phase2_time_stability(df: pd.DataFrame, target: str = "fwd_5d") -> dict:
    """
    Correlation, Information, Rank, and p-value stability across 3 equal time periods.
    """
    n = len(df)
    periods = {
        "Period_A": df.iloc[: n // 3],
        "Period_B": df.iloc[n // 3 : 2 * n // 3],
        "Period_C": df.iloc[2 * n // 3 :],
    }
    results = {}
    for feat in FEATURE_REGISTRY:
        if feat not in df.columns or target not in df.columns:
            results[feat] = {"stability": "N/A", "period_details": {}}
            continue

        pstats = {}
        corrs = []
        spearmans = []
        pvals = []
        for pname, pdata in periods.items():
            sub = pdata[[feat, target]].dropna()
            if len(sub) < 20:
                pstats[pname] = {
                    "pearson_r": None,
                    "spearman_r": None,
                    "p_value": None,
                    "n": len(sub),
                }
                continue
            try:
                pr, pp = pearsonr(sub[feat], sub[target])
                sr, _ = spearmanr(sub[feat], sub[target])
                pstats[pname] = {
                    "pearson_r": round(pr, 4),
                    "spearman_r": round(sr, 4),
                    "p_value": round(pp, 4),
                    "n": len(sub),
                }
                corrs.append(pr)
                spearmans.append(sr)
                pvals.append(pp)
            except Exception:
                pstats[pname] = {
                    "pearson_r": None,
                    "spearman_r": None,
                    "p_value": None,
                    "n": len(sub),
                }

        if len(corrs) >= 2:
            cstd = float(np.std(corrs))
            sign_flip = len({np.sign(c) for c in corrs if c != 0}) > 1
            pval_max = float(np.max(pvals))
            rstd = float(np.std(spearmans))
            if cstd < 0.08 and not sign_flip and pval_max < 0.10:
                stab = "STABLE"
            elif cstd < 0.18 and not sign_flip:
                stab = "MODERATE"
            elif sign_flip:
                stab = "SIGN_FLIP"
            else:
                stab = "UNSTABLE"
        else:
            cstd = sign_flip = pval_max = rstd = None
            stab = "INSUFFICIENT_DATA"

        results[feat] = {
            "stability": stab,
            "corr_std": round(cstd, 4) if cstd is not None else None,
            "sign_flip": sign_flip,
            "pval_max": round(pval_max, 4) if pval_max is not None else None,
            "rank_corr_std": round(rstd, 4) if rstd is not None else None,
            "correlations": {k: v.get("pearson_r") for k, v in pstats.items()},
            "spearman": {k: v.get("spearman_r") for k, v in pstats.items()},
            "period_details": pstats,
        }
    return results


# =============================================================================
# PHASE 3 — REGIME STABILITY
# Bull | Bear | Sideways | HighVol | LowVol
# =============================================================================


def phase3_regime_stability(df: pd.DataFrame, target: str = "fwd_5d") -> dict:
    """
    Evaluate each feature inside each market regime.
    Reports: avg correlation, worst correlation, regime variance.
    """
    regimes = ["Bull", "Bear", "Sideways", "HighVol", "LowVol"]
    results = {}
    for feat in FEATURE_REGISTRY:
        if feat not in df.columns or target not in df.columns:
            results[feat] = {"regime_variance": None, "regimes": {}}
            continue

        rc = {}
        cl = []
        for regime in regimes:
            sub = df[df["Regime"] == regime][[feat, target]].dropna()
            if len(sub) < 15:
                rc[regime] = {
                    "n": len(sub),
                    "pearson_r": None,
                    "spearman_r": None,
                    "p_value": None,
                    "significance": "INSUFFICIENT",
                }
                continue
            try:
                pr, pp = pearsonr(sub[feat], sub[target])
                sr, _ = spearmanr(sub[feat], sub[target])
                sig = (
                    "SIGNIFICANT"
                    if pp < 0.05
                    else "MARGINAL"
                    if pp < 0.10
                    else "NOT_SIGNIFICANT"
                )
                rc[regime] = {
                    "n": len(sub),
                    "pearson_r": round(pr, 4),
                    "spearman_r": round(sr, 4),
                    "p_value": round(pp, 4),
                    "significance": sig,
                }
                cl.append(pr)
            except Exception:
                rc[regime] = {
                    "n": len(sub),
                    "pearson_r": None,
                    "spearman_r": None,
                    "p_value": None,
                    "significance": "ERROR",
                }

        vc = [v for v in cl if v is not None]
        results[feat] = {
            "avg_correlation": round(float(np.mean(vc)), 4) if vc else None,
            "worst_correlation": round(float(np.min(np.abs(vc))), 4) if vc else None,
            "best_correlation": round(float(np.max(np.abs(vc))), 4) if vc else None,
            "regime_variance": round(float(np.var(vc)), 6) if len(vc) >= 2 else None,
            "n_regimes_tested": len(vc),
            "regimes": rc,
        }
    return results


# =============================================================================
# PHASE 4 — FEATURE DECAY TEST
# Horizons: 30d | 60d | 90d
# Detect: Alpha Decay | Signal Saturation | Signal Reversal
# =============================================================================


def phase4_decay_test(df: pd.DataFrame) -> dict:
    """Measure IC (Spearman) at 30/60/90-day horizons and classify decay type."""
    horizons = {"30d": "fwd_20d", "60d": "fwd_30d", "90d": "fwd_60d"}
    results = {}
    for feat in FEATURE_REGISTRY:
        if feat not in df.columns:
            results[feat] = {"decay_type": "N/A"}
            continue

        hstats = {}
        icv = []
        for hl, hc in horizons.items():
            if hc not in df.columns:
                continue
            sub = df[[feat, hc]].dropna()
            if len(sub) < 20:
                hstats[hl] = {"IC": None, "p_value": None, "n": len(sub)}
                continue
            try:
                sr, sp = spearmanr(sub[feat], sub[hc])
                hstats[hl] = {
                    "IC": round(sr, 4),
                    "p_value": round(sp, 4),
                    "n": len(sub),
                }
                icv.append(sr)
            except Exception:
                hstats[hl] = {"IC": None, "p_value": None, "n": len(sub)}

        if len(icv) >= 2:
            ia = np.array(icv)
            idd = np.diff(ia)
            if all(d < -0.01 for d in idd):
                dtype = "ALPHA_DECAY"
            elif len({np.sign(x) for x in ia if x != 0}) > 1:
                dtype = "SIGNAL_REVERSAL"
            elif all(abs(d) < 0.02 for d in idd):
                dtype = "SATURATION"
            elif all(d > 0 for d in idd):
                dtype = "IMPROVING"
            else:
                dtype = "MIXED"
        else:
            dtype = "INSUFFICIENT_DATA"

        results[feat] = {
            "decay_type": dtype,
            "ic_30d": hstats.get("30d", {}).get("IC"),
            "ic_60d": hstats.get("60d", {}).get("IC"),
            "ic_90d": hstats.get("90d", {}).get("IC"),
            "ic_trajectory": icv,
            "horizon_stats": hstats,
        }
    return results


# =============================================================================
# PHASE 5 — FEATURE QUALITY SCORE (0–100)
# =============================================================================


def _mi_score(x: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    """Binned mutual information between two continuous series."""
    try:
        xb = pd.cut(pd.Series(x).rank(pct=True), bins=bins, labels=False)
        yb = pd.cut(pd.Series(y).rank(pct=True), bins=bins, labels=False)
        return float(mutual_info_score(xb.fillna(0), yb.fillna(0)))
    except Exception:
        return 0.0


def phase5_quality_score(
    df: pd.DataFrame,
    p1: dict,
    p2: dict,
    p3: dict,
    p4: dict,
    target: str = "fwd_5d",
) -> dict:
    """
    feature_quality_score (0-100) based on:
      Correlation (20) | Mutual Information (15) | p-value (15) |
      Sample Size (10) | Time Stability (20)      | Regime Stability (20)
    """
    results = {}
    for feat in FEATURE_REGISTRY:
        sc = 0.0
        parts = {}
        notes = []
        if feat not in df.columns or target not in df.columns:
            results[feat] = {
                "feature_quality_score": 0,
                "grade": "F",
                "parts": {},
                "notes": ["FEATURE MISSING"],
            }
            continue

        sub = df[[feat, target]].dropna()
        n = len(sub)

        # 1. Pearson Correlation → max 20 pts
        try:
            pr, pp = pearsonr(sub[feat], sub[target])
            c_pts = min(20.0, abs(pr) * 100)
        except Exception:
            pr, pp, c_pts = 0.0, 1.0, 0.0
            notes.append("Pearson computation failed")
        sc += c_pts
        parts["correlation"] = round(c_pts, 2)

        # 2. Mutual Information → max 15 pts
        mi = _mi_score(sub[feat].values, sub[target].values)
        m_pts = min(15.0, mi * 30)
        sc += m_pts
        parts["mutual_info"] = round(m_pts, 2)

        # 3. p-value → max 15 pts
        p_pts = 15.0 if pp < 0.01 else 10.0 if pp < 0.05 else 5.0 if pp < 0.10 else 0.0
        sc += p_pts
        parts["p_value"] = round(p_pts, 2)

        # 4. Sample size → max 10 pts
        s_pts = (
            10.0
            if n >= 400
            else 7.0
            if n >= 200
            else 4.0
            if n >= 100
            else 2.0
            if n >= 50
            else 0.0
        )
        sc += s_pts
        parts["sample_size"] = round(s_pts, 2)

        # 5. Time Stability → max 20 pts
        tl = p2.get(feat, {}).get("stability", "N/A")
        t_pts = (
            20.0
            if tl == "STABLE"
            else 12.0
            if tl == "MODERATE"
            else 0.0
            if tl == "SIGN_FLIP"
            else 4.0
        )
        if tl == "SIGN_FLIP":
            notes.append("Sign flip detected across time periods")
        sc += t_pts
        parts["time_stability"] = round(t_pts, 2)

        # 6. Regime Stability → max 20 pts
        rv = p3.get(feat, {}).get("regime_variance")
        rc = p3.get(feat, {}).get("avg_correlation")
        if rv is not None and rc is not None:
            var_penalty = min(10.0, rv * 1000)
            r_pts = max(0.0, 20.0 - var_penalty - (5.0 if abs(rc) < 0.05 else 0.0))
        else:
            r_pts = 0.0
            notes.append("Regime data insufficient")
        sc += r_pts
        parts["regime_stability"] = round(r_pts, 2)

        # Decay penalties
        dt = p4.get(feat, {}).get("decay_type", "")
        if dt == "SIGNAL_REVERSAL":
            sc = max(0, sc - 15)
            notes.append("Penalty -15: signal reversal")
        elif dt == "ALPHA_DECAY":
            sc = max(0, sc - 8)
            notes.append("Penalty -8: alpha decay")

        fs = round(min(100.0, max(0.0, sc)), 1)
        gr = (
            "A"
            if fs >= 80
            else "B"
            if fs >= 65
            else "C"
            if fs >= 50
            else "D"
            if fs >= 35
            else "F"
        )

        results[feat] = {
            "feature_quality_score": fs,
            "grade": gr,
            "pearson_r": round(pr, 4),
            "p_value": round(pp, 4),
            "n": n,
            "decay_type": dt,
            "parts": parts,
            "notes": notes,
        }
    return results


# =============================================================================
# PHASE 6 — CLASSIFICATION
# REJECT | WATCHLIST | PROMISING | APPROVED
# =============================================================================


def phase6_classify(p5: dict, p2: dict, p4: dict) -> dict:
    """Classify every feature into REJECT / WATCHLIST / PROMISING / APPROVED."""
    results = {}
    for feat, qd in p5.items():
        sc = qd.get("feature_quality_score", 0)
        dt = qd.get("decay_type", "")
        ts = p2.get(feat, {}).get("stability", "UNKNOWN")

        if dt == "SIGNAL_REVERSAL":
            cls = "REJECT"
            rsn = "Signal reversal — direction inverts at longer horizons"
        elif sc >= 65 and ts in ("STABLE", "MODERATE"):
            cls = "APPROVED"
            rsn = f"Score {sc}/100, time-stable [{ts}], passes V7.3 criteria"
        elif sc >= 65:
            cls = "PROMISING"
            rsn = f"Score {sc}/100 but time stability [{ts}] — needs monitoring"
        elif sc >= 45:
            cls = "PROMISING"
            rsn = f"Score {sc}/100 — shows alpha potential, more validation needed"
        elif sc >= 25:
            cls = "WATCHLIST"
            rsn = f"Score {sc}/100 — weak alpha, keep under observation"
        else:
            cls = "REJECT"
            rsn = f"Score {sc}/100 — insufficient predictive power"

        results[feat] = {
            "classification": cls,
            "feature_quality_score": sc,
            "grade": qd.get("grade"),
            "time_stability": ts,
            "decay_type": dt,
            "reason": rsn,
            "category": FEATURE_REGISTRY[feat]["category"],
            "priority": FEATURE_REGISTRY[feat]["priority"],
            "v73_eligible": cls == "APPROVED",
        }
    return results


# =============================================================================
# PHASE 7 — ALPHA_STABILITY_REPORT.md GENERATION
# =============================================================================


def phase7_generate_report(
    p6: dict,
    p2: dict,
    p3: dict,
    p4: dict,
    p5: dict,
    output_path: str = None,
) -> str:
    """Build and write the full ALPHA_STABILITY_REPORT.md."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    by_class = {"APPROVED": [], "PROMISING": [], "WATCHLIST": [], "REJECT": []}
    for feat, d in p6.items():
        by_class[d["classification"]].append(feat)

    approved = sorted(by_class["APPROVED"])
    promising = sorted(by_class["PROMISING"])
    watchlist = sorted(by_class["WATCHLIST"])
    rejected = sorted(by_class["REJECT"])
    total = len(p6)

    cat_summary = {}
    for feat, d in p6.items():
        cat = d["category"]
        cat_summary.setdefault(
            cat, {"APPROVED": 0, "PROMISING": 0, "WATCHLIST": 0, "REJECT": 0}
        )
        cat_summary[cat][d["classification"]] += 1

    regime_robust = [
        f for f in approved if (p3.get(f, {}).get("regime_variance") or 999) < 0.005
    ]

    # ─────────────────────────────────────────────────────────────────────────
    L = []

    def h(text):
        L.append(text)

    def row(*cells):
        L.append("| " + " | ".join(str(c) for c in cells) + " |")

    def divider(n):
        L.append("|" + "|".join(["---"] * n) + "|")

    h("# ALPHA STABILITY REPORT")
    h("## WealthQuant V7.2.2 — Feature Alpha Rankings Audit")
    h("")
    h(f"**Generated:** {ts}")
    h(
        f"**Scope:** {total} features across {len(FEATURE_REGISTRY)} registered alpha signals"
    )
    h(
        "**Data:** 600 synthetic daily bars · 5 labelled regimes (Bull / Bear / Sideways / HighVol / LowVol)"
    )
    h("**Target:** 5-Day Forward Return (fwd_5d)")
    h("")
    h("---")
    h("")
    h("## EXECUTIVE SUMMARY")
    h("")
    row("Classification", "Count", "% of Total")
    divider(3)
    row("APPROVED", len(approved), f"{len(approved) / total * 100:.1f}%")
    row("PROMISING", len(promising), f"{len(promising) / total * 100:.1f}%")
    row("WATCHLIST", len(watchlist), f"{len(watchlist) / total * 100:.1f}%")
    row("REJECT", len(rejected), f"{len(rejected) / total * 100:.1f}%")
    row("**TOTAL**", f"**{total}**", "**100%**")
    h("")
    h("---")
    h("")

    # ── Phase 1 ────────────────────────────────────────────────────────────────
    h("## PHASE 1 — FEATURE DISCOVERY")
    h("")
    cats = {}
    for feat, meta in FEATURE_REGISTRY.items():
        cats[meta["category"]] = cats.get(meta["category"], 0) + 1
    row("Category", "Feature Count")
    divider(2)
    for cat, cnt in sorted(cats.items()):
        row(cat, cnt)
    h("")
    h(
        f"**{TOTAL_FEATURES} features registered and discovered** across 7 indicator families."
    )
    h("")
    h("---")
    h("")

    # ── Phase 2 ────────────────────────────────────────────────────────────────
    h("## PHASE 2 — TIME STABILITY (Period A | B | C)")
    h("")
    h("*History split into 3 equal periods of ~200 bars each.*")
    h("")
    row("Feature", "Per-A r", "Per-B r", "Per-C r", "Corr Std", "Stability")
    divider(6)
    for feat in sorted(FEATURE_REGISTRY):
        t = p2.get(feat, {})
        corrs = t.get("correlations", {})
        a = corrs.get("Period_A", "—")
        b = corrs.get("Period_B", "—")
        c_ = corrs.get("Period_C", "—")
        std = t.get("corr_std", "—")
        stab = t.get("stability", "—")
        row(feat, a, b, c_, std, stab)
    h("")
    stab_counts = {}
    for v in p2.values():
        k = v.get("stability", "?")
        stab_counts[k] = stab_counts.get(k, 0) + 1
    h(f"**Stability summary:** {stab_counts}")
    h("")
    h("---")
    h("")

    # ── Phase 3 ────────────────────────────────────────────────────────────────
    h("## PHASE 3 — REGIME STABILITY")
    h("")
    h("*Pearson r against 5d forward return within each market regime.*")
    h("")
    row("Feature", "Bull", "Bear", "Sideways", "HighVol", "LowVol", "AvgCorr", "RegVar")
    divider(8)
    for feat in sorted(FEATURE_REGISTRY):
        r = p3.get(feat, {})
        rg = r.get("regimes", {})
        row(
            feat,
            rg.get("Bull", {}).get("pearson_r", "—"),
            rg.get("Bear", {}).get("pearson_r", "—"),
            rg.get("Sideways", {}).get("pearson_r", "—"),
            rg.get("HighVol", {}).get("pearson_r", "—"),
            rg.get("LowVol", {}).get("pearson_r", "—"),
            r.get("avg_correlation", "—"),
            r.get("regime_variance", "—"),
        )
    h("")
    h("---")
    h("")

    # ── Phase 4 ────────────────────────────────────────────────────────────────
    h("## PHASE 4 — FEATURE DECAY TEST (30d / 60d / 90d)")
    h("")
    h(
        "*Information Coefficient (Spearman rank correlation) at increasing forward horizons.*"
    )
    h("")
    row("Feature", "IC-30d", "IC-60d", "IC-90d", "Decay Type")
    divider(5)
    for feat in sorted(FEATURE_REGISTRY):
        d = p4.get(feat, {})
        row(
            feat,
            d.get("ic_30d", "—"),
            d.get("ic_60d", "—"),
            d.get("ic_90d", "—"),
            d.get("decay_type", "—"),
        )
    h("")
    dc = {}
    for v in p4.values():
        k = v.get("decay_type", "?")
        dc[k] = dc.get(k, 0) + 1
    h(f"**Decay profile:** {dc}")
    h("")
    h("---")
    h("")

    # ── Phase 5 ────────────────────────────────────────────────────────────────
    h("## PHASE 5 — FEATURE QUALITY SCORES (0–100)")
    h("")
    h(
        "**Scoring:** Correlation (20) + Mutual Information (15) + p-value (15) + Sample Size (10) + Time Stability (20) + Regime Stability (20) = 100"
    )
    h("")
    row("Feature", "Score", "Grade", "Corr", "MI", "p-val", "Sample", "TStab", "RStab")
    divider(9)
    for feat in sorted(FEATURE_REGISTRY):
        q = p5.get(feat, {})
        pts = q.get("parts", {})
        row(
            feat,
            q.get("feature_quality_score", 0),
            q.get("grade", "F"),
            pts.get("correlation", "—"),
            pts.get("mutual_info", "—"),
            pts.get("p_value", "—"),
            pts.get("sample_size", "—"),
            pts.get("time_stability", "—"),
            pts.get("regime_stability", "—"),
        )
    avg_sc = float(np.mean([v["feature_quality_score"] for v in p5.values()]))
    h("")
    h(f"**Portfolio Average Quality Score: {avg_sc:.1f} / 100**")
    h("")
    h("---")
    h("")

    # ── Phase 6 ────────────────────────────────────────────────────────────────
    h("## PHASE 6 — CLASSIFICATION")
    h("")
    h("### APPROVED — Cleared for V7.3 Market Structure Engine")
    h("")
    if approved:
        for feat in approved:
            d = p6[feat]
            h(
                f"- **{feat}** | Score: {d['feature_quality_score']} | Grade: {d['grade']} | {d['reason']}"
            )
    else:
        h("*No features approved in this audit cycle.*")

    h("")
    h("### PROMISING — Monitor and Re-evaluate")
    h("")
    if promising:
        for feat in promising:
            d = p6[feat]
            h(
                f"- **{feat}** | Score: {d['feature_quality_score']} | Grade: {d['grade']} | {d['reason']}"
            )
    else:
        h("*No promising features identified.*")

    h("")
    h("### WATCHLIST — Weak signal, keep monitoring")
    h("")
    if watchlist:
        for feat in watchlist:
            d = p6[feat]
            h(
                f"- **{feat}** | Score: {d['feature_quality_score']} | Grade: {d['grade']} | {d['reason']}"
            )
    else:
        h("*No features on watchlist.*")

    h("")
    h("### REJECT — Excluded from V7.3")
    h("")
    if rejected:
        for feat in rejected:
            d = p6[feat]
            h(
                f"- **{feat}** | Score: {d['feature_quality_score']} | Grade: {d['grade']} | {d['reason']}"
            )
    else:
        h("*No features rejected.*")

    h("")
    h("---")
    h("")

    # ── Phase 7 ────────────────────────────────────────────────────────────────
    h("## PHASE 7 — V7.3 INTEGRATION ELIGIBILITY")
    h("")

    h("### Q1: Which features survive?")
    h("")
    survivors = approved + promising
    h(f"**{len(survivors)} features survive the audit** (APPROVED + PROMISING):")
    h("")
    for feat in sorted(survivors):
        d = p6[feat]
        h(
            f"- `{feat}` [{d['classification']}] · Score: {d['feature_quality_score']} · Category: {d['category']}"
        )
    h("")

    h("### Q2: Which features collapse?")
    h("")
    collapsed = rejected
    h(f"**{len(collapsed)} features collapse** (REJECT):")
    h("")
    for feat in sorted(collapsed):
        d = p6[feat]
        d4 = p4.get(feat, {})
        h(
            f"- `{feat}` · Score: {d['feature_quality_score']} · Decay: {d4.get('decay_type', '—')} · Reason: {d['reason']}"
        )
    h("")

    h("### Q3: Which features remain robust across regimes?")
    h("")
    if regime_robust:
        h(
            f"**{len(regime_robust)} features demonstrate cross-regime robustness** (regime variance < 0.005):"
        )
        h("")
        for feat in sorted(regime_robust):
            r = p3.get(feat, {})
            h(
                f"- `{feat}` · Avg Corr: {r.get('avg_correlation')} · Regime Var: {r.get('regime_variance')}"
            )
    else:
        h(
            "No features met the strict regime robustness threshold (var < 0.005) in this cycle."
        )
        h("")
        h("**Nearest candidates by lowest regime variance:**")
        h("")
        ranked = sorted(
            [(f, p3.get(f, {}).get("regime_variance") or 999) for f in approved],
            key=lambda x: x[1],
        )[:5]
        for feat, rv in ranked:
            h(f"- `{feat}` · Regime Variance: {rv}")
    h("")

    h("### Q4: Which features qualify for V7.3 integration?")
    h("")
    v73 = [f for f, d in p6.items() if d["v73_eligible"]]
    if v73:
        h(f"**{len(v73)} features qualify for V7.3 Market Structure Engine:**")
        h("")
        row("Feature", "Quality Score", "Category", "Time Stability", "Decay Type")
        divider(5)
        for feat in sorted(v73):
            d = p6[feat]
            d4 = p4.get(feat, {})
            row(
                f"`{feat}`",
                d["feature_quality_score"],
                d["category"],
                d["time_stability"],
                d4.get("decay_type", "—"),
            )
    else:
        h("**No features qualify for V7.3 in this audit cycle.**")
        h("")
        h(
            "> Recommendation: Expand data history beyond 600 bars (target 2,000+), then re-run audit."
        )
    h("")
    h("---")
    h("")

    # ── Category analysis ───────────────────────────────────────────────────────
    h("## CATEGORY-LEVEL AUDIT RESULTS")
    h("")
    row(
        "Category", "Total", "APPROVED", "PROMISING", "WATCHLIST", "REJECT", "Pass Rate"
    )
    divider(7)
    for cat, cnts in sorted(cat_summary.items()):
        tot = sum(cnts.values())
        passes = cnts["APPROVED"] + cnts["PROMISING"]
        rate = f"{passes / tot * 100:.0f}%" if tot > 0 else "—"
        row(
            cat,
            tot,
            cnts["APPROVED"],
            cnts["PROMISING"],
            cnts["WATCHLIST"],
            cnts["REJECT"],
            rate,
        )
    h("")
    h("---")
    h("")

    # ── Conclusion ─────────────────────────────────────────────────────────────
    h("## AUDIT CONCLUSION")
    h("")
    h("| Metric | Value |")
    divider(2)
    row("Total Features Audited", total)
    row("V7.3 Eligible (APPROVED)", len(approved))
    row("Pipeline (PROMISING)", len(promising))
    row("Under Watch (WATCHLIST)", len(watchlist))
    row("Eliminated (REJECT)", len(rejected))
    row("Average Quality Score", f"{avg_sc:.1f}/100")
    row("Cross-Regime Robust", len(regime_robust))
    h("")
    h("> **RULE: ONLY APPROVED features may enter the V7.3 Market Structure Engine.**")
    h("")

    if len(approved) > 0:
        h(
            f"The audit has identified **{len(approved)} APPROVED** features ready for V7.3 integration."
        )
        h("These features have demonstrated stable correlations across time periods,")
        h("acceptable regime variance, and no signal reversal. They form the approved")
        h("foundation of the V7.3 Market Structure Engine.")
    else:
        h("**No features have been APPROVED in this audit cycle.**")
        h("")
        h("Root causes:")
        h(
            "- Synthetic dataset of 600 bars provides limited statistical power for STABLE classification"
        )
        h(
            "- Features showing PROMISING status should be re-evaluated on live market data"
        )
        h(
            "- Expand history to 1,000–2,000+ bars and re-run audit before V7.3 integration"
        )

    h("")
    h("---")
    h("")
    h(
        "*WealthQuant V7.2.2 Alpha Stability Audit — generated by `alpha_stability_audit.py`*"
    )
    h("")

    # ── Write file ─────────────────────────────────────────────────────────────
    report = "\n".join(L)
    if output_path is None:
        output_path = Path(__file__).parent / "ALPHA_STABILITY_REPORT.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n[REPORT] Written to: {output_path}")
    return report


# =============================================================================
# MAIN AUDIT PIPELINE
# =============================================================================


def run_audit() -> dict:
    """Execute all 7 audit phases and generate the report."""
    print("=" * 70)
    print("  WEALTHQUANT V7.2.2 — ALPHA STABILITY AUDIT")
    print("=" * 70)

    # ── Phase 0: Data & Features ───────────────────────────────────────────────
    print("\n[PHASE 0] Generating 600-bar synthetic OHLCV with 5 regimes...")
    df = generate_market_data(n_bars=600)
    print(f"          Shape: {df.shape} | Regimes: {list(df['Regime'].unique())}")

    print(
        f"\n[PHASE 0] Computing all {TOTAL_FEATURES} alpha features from feature_alpha_rankings..."
    )
    df = compute_all_features(df)
    df = compute_forward_returns(df)
    print(f"          Total columns: {len(df.columns)}")

    # ── Phase 1 ───────────────────────────────────────────────────────────────
    print(
        f"\n[PHASE 1] Feature discovery audit ({TOTAL_FEATURES} registered features)..."
    )
    p1 = phase1_feature_discovery(df)
    disc = sum(1 for v in p1.values() if v["status"] == "DISCOVERED")
    print(f"          Discovered: {disc}/{TOTAL_FEATURES}")

    # ── Phase 2 ───────────────────────────────────────────────────────────────
    print("\n[PHASE 2] Time stability analysis (Period A / B / C)...")
    p2 = phase2_time_stability(df, target="fwd_5d")
    sc = {
        k: sum(1 for v in p2.values() if v.get("stability") == k)
        for k in ["STABLE", "MODERATE", "UNSTABLE", "SIGN_FLIP", "INSUFFICIENT_DATA"]
    }
    print(f"          {sc}")

    # ── Phase 3 ───────────────────────────────────────────────────────────────
    print(
        "\n[PHASE 3] Regime stability analysis (Bull/Bear/Sideways/HighVol/LowVol)..."
    )
    p3 = phase3_regime_stability(df, target="fwd_5d")
    print(f"          Regime analysis complete for {len(p3)} features")

    # ── Phase 4 ───────────────────────────────────────────────────────────────
    print("\n[PHASE 4] Feature decay test (30d / 60d / 90d)...")
    p4 = phase4_decay_test(df)
    dc: dict = {}
    for v in p4.values():
        t_ = v.get("decay_type", "?")
        dc[t_] = dc.get(t_, 0) + 1
    print(f"          Decay profile: {dc}")

    # ── Phase 5 ───────────────────────────────────────────────────────────────
    print("\n[PHASE 5] Computing feature quality scores (0–100)...")
    p5 = phase5_quality_score(df, p1, p2, p3, p4, target="fwd_5d")
    avg = float(np.mean([v["feature_quality_score"] for v in p5.values()]))
    print(f"          Portfolio average: {avg:.1f}/100")

    # ── Phase 6 ───────────────────────────────────────────────────────────────
    print("\n[PHASE 6] Classifying features...")
    p6 = phase6_classify(p5, p2, p4)
    bc: dict = {}
    for v in p6.values():
        c_ = v["classification"]
        bc[c_] = bc.get(c_, 0) + 1
    print(f"          {bc}")

    # ── Phase 7 ───────────────────────────────────────────────────────────────
    print("\n[PHASE 7] Generating ALPHA_STABILITY_REPORT.md...")
    phase7_generate_report(p6, p2, p3, p4, p5)

    # ── Final summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  AUDIT COMPLETE")
    print("=" * 70)
    print(
        f"\n  APPROVED    : {bc.get('APPROVED', 0):>3}  ->  eligible for V7.3 Market Structure Engine"
    )
    print(
        f"  PROMISING   : {bc.get('PROMISING', 0):>3}  ->  pipeline candidates, re-evaluate"
    )
    print(
        f"  WATCHLIST   : {bc.get('WATCHLIST', 0):>3}  ->  weak alpha, keep monitoring"
    )
    print(f"  REJECT      : {bc.get('REJECT', 0):>3}  ->  excluded from V7.3")
    print("\n  Output      : ALPHA_STABILITY_REPORT.md")
    print("=" * 70)

    return {
        "phase1": p1,
        "phase2": p2,
        "phase3": p3,
        "phase4": p4,
        "phase5": p5,
        "phase6": p6,
    }


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    results = run_audit()
