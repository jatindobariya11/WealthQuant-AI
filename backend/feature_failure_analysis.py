"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         WEALTHQUANT V7.2.3 — FEATURE FAILURE ANALYSIS                       ║
║         Mission  : Forensic autopsy of every REJECTED feature from          ║
║                    V7.2.2 Alpha Stability Audit                              ║
║         Output   : FEATURE_FAILURE_REPORT.md                                ║
║         Note     : Analysis only. No new models. No new engines.            ║
╚══════════════════════════════════════════════════════════════════════════════╝

Answers per feature:
  Q1. Why was it rejected?
  Q2. Can it be repaired?
  Q3. Should it remain rejected permanently?
  Q4. Could it become regime-specific instead of global?
"""

import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# TARGET REJECTED FEATURES — from V7.2.2 Alpha Stability Audit
# ─────────────────────────────────────────────────────────────────────────────

REJECTED_FEATURES = {
    "ATR_14": {
        "category": "Volatility",
        "lookback": 14,
        "v722_score": 28.9,
        "v722_grade": "F",
        "v722_decay": "SIGNAL_REVERSAL",
        "v722_stability": "MODERATE",
        "v722_regime_var": 0.015631,
        "v722_ic": {"30d": -0.1257, "60d": 0.0034, "90d": 0.1157},
        "v722_regime_r": {
            "Bull": -0.14,
            "Bear": -0.15,
            "Sideways": -0.46,
            "HighVol": -0.23,
            "LowVol": -0.12,
        },
    },
    "BB_Width": {
        "category": "Volatility",
        "lookback": 20,
        "v722_score": 49.3,
        "v722_grade": "D",
        "v722_decay": "SIGNAL_REVERSAL",
        "v722_stability": "MODERATE",
        "v722_regime_var": 0.003203,
        "v722_ic": {"30d": -0.1012, "60d": 0.0093, "90d": 0.32},
        "v722_regime_r": {
            "Bull": -0.14,
            "Bear": -0.30,
            "Sideways": -0.17,
            "HighVol": -0.25,
            "LowVol": -0.19,
        },
    },
    "Supertrend": {
        "category": "Trend",
        "lookback": 10,
        "v722_score": 4.0,
        "v722_grade": "F",
        "v722_decay": "SIGNAL_REVERSAL",
        "v722_stability": "SIGN_FLIP",
        "v722_regime_var": None,
        "v722_ic": {"30d": -0.1152, "60d": -0.0264, "90d": 0.0196},
        "v722_regime_r": {
            "Bull": None,
            "Bear": None,
            "Sideways": None,
            "HighVol": -0.01,
            "LowVol": None,
        },
    },
    "OBV": {
        "category": "Volume",
        "lookback": 1,
        "v722_score": 15.6,
        "v722_grade": "F",
        "v722_decay": "SIGNAL_REVERSAL",
        "v722_stability": "SIGN_FLIP",
        "v722_regime_var": 0.065051,
        "v722_ic": {"30d": -0.0335, "60d": -0.035, "90d": 0.0909},
        "v722_regime_r": {
            "Bull": -0.53,
            "Bear": 0.24,
            "Sideways": 0.02,
            "HighVol": -0.12,
            "LowVol": -0.23,
        },
    },
    "RSI_Divergence": {
        "category": "Momentum",
        "lookback": 14,
        "v722_score": 17.7,
        "v722_grade": "F",
        "v722_decay": "SIGNAL_REVERSAL",
        "v722_stability": "MODERATE",
        "v722_regime_var": 0.017220,
        "v722_ic": {"30d": 0.0595, "60d": 0.0934, "90d": -0.0403},
        "v722_regime_r": {
            "Bull": 0.13,
            "Bear": -0.05,
            "Sideways": -0.17,
            "HighVol": 0.18,
            "LowVol": -0.09,
        },
    },
    "StochRSI_K": {
        "category": "Momentum",
        "lookback": 14,
        "v722_score": 7.8,
        "v722_grade": "F",
        "v722_decay": "SIGNAL_REVERSAL",
        "v722_stability": "SIGN_FLIP",
        "v722_regime_var": 0.008278,
        "v722_ic": {"30d": 0.0209, "60d": -0.0556, "90d": -0.03},
        "v722_regime_r": {
            "Bull": -0.08,
            "Bear": 0.02,
            "Sideways": 0.15,
            "HighVol": 0.11,
            "LowVol": -0.07,
        },
    },
    "Gap_Up": {
        "category": "Structure",
        "lookback": 1,
        "v722_score": 10.8,
        "v722_grade": "F",
        "v722_decay": "SIGNAL_REVERSAL",
        "v722_stability": "SIGN_FLIP",
        "v722_regime_var": 0.000757,
        "v722_ic": {"30d": -0.0564, "60d": -0.0455, "90d": 0.0282},
        "v722_regime_r": {
            "Bull": -0.02,
            "Bear": -0.04,
            "Sideways": -0.10,
            "HighVol": -0.02,
            "LowVol": -0.05,
        },
    },
    "Gap_Down": {
        "category": "Structure",
        "lookback": 1,
        "v722_score": 23.0,
        "v722_grade": "F",
        "v722_decay": "SIGNAL_REVERSAL",
        "v722_stability": "MODERATE",
        "v722_regime_var": 0.001120,
        "v722_ic": {"30d": -0.0199, "60d": 0.0119, "90d": 0.0904},
        "v722_regime_r": {
            "Bull": 0.00,
            "Bear": 0.01,
            "Sideways": -0.06,
            "HighVol": 0.02,
            "LowVol": 0.03,
        },
    },
    "Hammer": {
        "category": "Candle",
        "lookback": 1,
        "v722_score": 25.0,
        "v722_grade": "F",
        "v722_decay": "SIGNAL_REVERSAL",
        "v722_stability": "SIGN_FLIP",
        "v722_regime_var": None,
        "v722_ic": {"30d": None, "60d": None, "90d": None},
        "v722_regime_r": {
            "Bull": None,
            "Bear": None,
            "Sideways": None,
            "HighVol": None,
            "LowVol": None,
        },
    },
    "Shooting_Star": {
        "category": "Candle",
        "lookback": 1,
        "v722_score": 25.0,
        "v722_grade": "F",
        "v722_decay": "SIGNAL_REVERSAL",
        "v722_stability": "SIGN_FLIP",
        "v722_regime_var": None,
        "v722_ic": {"30d": None, "60d": None, "90d": None},
        "v722_regime_r": {
            "Bull": None,
            "Bear": None,
            "Sideways": None,
            "HighVol": None,
            "LowVol": None,
        },
    },
    "Vol_Ratio": {
        "category": "Volume",
        "lookback": 20,
        "v722_score": 9.3,
        "v722_grade": "F",
        "v722_decay": "SIGNAL_REVERSAL",
        "v722_stability": "SIGN_FLIP",
        "v722_regime_var": 0.010839,
        "v722_ic": {"30d": 0.0017, "60d": 0.0175, "90d": -0.0235},
        "v722_regime_r": {
            "Bull": 0.06,
            "Bear": -0.08,
            "Sideways": -0.24,
            "HighVol": 0.01,
            "LowVol": -0.01,
        },
    },
    "Vol_Surge": {
        "category": "Volume",
        "lookback": 20,
        "v722_score": 23.9,
        "v722_grade": "F",
        "v722_decay": "SATURATION",
        "v722_stability": "SIGN_FLIP",
        "v722_regime_var": 0.009970,
        "v722_ic": {"30d": 0.0467, "60d": 0.0337, "90d": 0.0364},
        "v722_regime_r": {
            "Bull": 0.11,
            "Bear": -0.11,
            "Sideways": -0.18,
            "HighVol": -0.06,
            "LowVol": -0.01,
        },
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# FAILURE TAXONOMY — classification codes for each dimension of rejection
# ─────────────────────────────────────────────────────────────────────────────

FAILURE_CODES = {
    "F1": "TIME_INSTABILITY",  # Correlation changes sign or magnitude across time periods
    "F2": "REGIME_COLLAPSE",  # Feature direction inverts in one or more regimes
    "F3": "ALPHA_DECAY",  # IC decreases monotonically with horizon
    "F4": "SIGNAL_REVERSAL",  # IC crosses zero at a longer horizon
    "F5": "SPARSE_SIGNAL",  # Binary feature fires rarely — insufficient sample size
    "F6": "CORRELATION_COLLAPSE",  # Absolute Pearson r < 0.05 globally
    "F7": "NaN_CONTAMINATION",  # NaN presence exceeds 30% of series
    "F8": "HORIZON_DRIFT",  # IC wanders without directional commitment
}

REPAIR_CODES = {
    "R1": "REPARABLE_CONDITIONING",  # Can be fixed by regime conditioning
    "R2": "REPARABLE_NORMALIZATION",  # ATR-normalization or z-scoring fixes
    "R3": "REPARABLE_LOOKBACK",  # Different lookback period may stabilize
    "R4": "REPARABLE_TRANSFORM",  # Log/rank transform improves signal
    "R5": "REPARABLE_SPARSE_FIX",  # Combine with other sparse signals
    "R6": "PERMANENT_REJECT",  # No viable repair path found
    "R7": "REGIME_SPECIFIC_ONLY",  # Valid in isolated regime; useless globally
}


# =============================================================================
# DATA GENERATION — identical to V7.2.2 audit (same seed, same structure)
# =============================================================================


def generate_market_data(n_bars: int = 600, seed: int = 42) -> pd.DataFrame:
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


# =============================================================================
# FEATURE COMPUTATION — all rejected features + supporting indicators
# =============================================================================


def compute_rejected_features(df: pd.DataFrame) -> pd.DataFrame:
    c = df["Close"].copy()

    # ── ATR_14 ────────────────────────────────────────────────────────────────
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["ATR_14"] = tr.rolling(14).mean().round(4)
    df["ATR_Norm"] = (df["ATR_14"] / c * 100).round(4)  # normalized version
    df["ATR_Change"] = df["ATR_14"].pct_change(5).round(4)  # rate-of-change version
    df["ATR_Rank"] = df["ATR_14"].rolling(60).rank(pct=True).round(4)  # ranked version

    # ── BB_Width ──────────────────────────────────────────────────────────────
    mid = c.rolling(20).mean()
    sd = c.rolling(20).std()
    bb_u = mid + 2 * sd
    bb_l = mid - 2 * sd
    df["BB_Width"] = ((bb_u - bb_l) / mid * 100).round(4)
    df["BB_Width_Rank"] = df["BB_Width"].rolling(60).rank(pct=True).round(4)  # ranked
    df["BB_Width_Chg"] = df["BB_Width"].diff(5).round(4)  # change (squeeze detection)
    df["BB_Width_Z"] = (
        (df["BB_Width"] - df["BB_Width"].rolling(60).mean())
        / df["BB_Width"].rolling(60).std()
    ).round(4)

    # ── Supertrend ────────────────────────────────────────────────────────────
    hl2 = (df["High"] + df["Low"]) / 2
    atr_st = tr.rolling(10).mean()
    upper = hl2 + 3 * atr_st
    lower = hl2 - 3 * atr_st
    st = pd.Series(np.nan, index=df.index)
    dir_ = pd.Series(0.0, index=df.index)
    for i in range(10, len(df)):
        if df["Close"].iloc[i] > upper.iloc[i - 1]:
            st.iloc[i] = lower.iloc[i]
            dir_.iloc[i] = 1
        elif df["Close"].iloc[i] < lower.iloc[i - 1]:
            st.iloc[i] = upper.iloc[i]
            dir_.iloc[i] = -1
        else:
            st.iloc[i] = st.iloc[i - 1]
            dir_.iloc[i] = dir_.iloc[i - 1]
    df["Supertrend"] = st.round(4)
    df["Supertrend_Dir"] = dir_
    df["ST_Dist"] = ((c - st) / c).round(6)  # normalized distance from ST line
    df["ST_Chg_Indicator"] = dir_.diff().fillna(0)  # crossover events only

    # ── OBV ───────────────────────────────────────────────────────────────────
    obv = [0]
    for i in range(1, len(df)):
        if df["Close"].iloc[i] > df["Close"].iloc[i - 1]:
            obv.append(obv[-1] + df["Volume"].iloc[i])
        elif df["Close"].iloc[i] < df["Close"].iloc[i - 1]:
            obv.append(obv[-1] - df["Volume"].iloc[i])
        else:
            obv.append(obv[-1])
    df["OBV"] = pd.Series(obv, index=df.index, dtype=float)
    df["OBV_Slope"] = df["OBV"].diff(5).round(4)
    df["OBV_EMA"] = df["OBV"].ewm(span=21, adjust=False).mean()
    df["OBV_Signal"] = (df["OBV"] - df["OBV_EMA"]).round(4)  # OBV vs its EMA
    df["OBV_Rank"] = df["OBV"].rolling(60).rank(pct=True).round(4)
    df["OBV_Accel"] = df["OBV_Slope"].diff(5).round(4)  # OBV acceleration

    # ── RSI_Divergence ────────────────────────────────────────────────────────
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
    rsi = (100 - 100 / (1 + gain / loss)).round(4)
    df["RSI_14"] = rsi
    df["RSI_Divergence"] = 0.0
    div_strength = pd.Series(0.0, index=df.index)
    for i in range(20, len(df)):
        price_new_high = c.iloc[i] > c.iloc[i - 10 : i].max()
        rsi_no_conf = rsi.iloc[i] < rsi.iloc[i - 10 : i].max()
        price_new_low = c.iloc[i] < c.iloc[i - 10 : i].min()
        rsi_no_conf_dn = rsi.iloc[i] > rsi.iloc[i - 10 : i].min()
        if price_new_high and rsi_no_conf:
            df.at[df.index[i], "RSI_Divergence"] = -1.0
            div_strength.at[df.index[i]] = rsi.iloc[i - 10 : i].max() - rsi.iloc[i]
        elif price_new_low and rsi_no_conf_dn:
            df.at[df.index[i], "RSI_Divergence"] = 1.0
            div_strength.at[df.index[i]] = rsi.iloc[i] - rsi.iloc[i - 10 : i].min()
    df["RSI_Div_Strength"] = div_strength  # magnitude of divergence

    # ── StochRSI_K ────────────────────────────────────────────────────────────
    rsi_lo = rsi.rolling(14).min()
    rsi_hi = rsi.rolling(14).max()
    srsi_k = ((rsi - rsi_lo) / (rsi_hi - rsi_lo + 1e-10) * 100).fillna(50).round(4)
    df["StochRSI_K"] = srsi_k
    df["StochRSI_K_EMA"] = srsi_k.ewm(span=3, adjust=False).mean().round(4)
    df["StochRSI_Signal"] = (srsi_k - srsi_k.shift(3)).round(4)  # momentum of srsi
    df["StochRSI_Extreme"] = ((srsi_k < 10) | (srsi_k > 90)).astype(float)

    # ── Gap features ──────────────────────────────────────────────────────────
    prev_close = df["Close"].shift(1)
    gap_pct = ((df["Open"] - prev_close) / prev_close * 100).round(4)
    df["Gap_Pct"] = gap_pct
    df["Gap_Up"] = (gap_pct > 0.3).astype(float)
    df["Gap_Down"] = (gap_pct < -0.3).astype(float)
    df["Gap_Fill"] = (  # gap filled in same session
        (df["Gap_Up"] == 1) & (df["Low"] < prev_close)
        | (df["Gap_Down"] == 1) & (df["High"] > prev_close)
    ).astype(float)
    df["Gap_Magnitude"] = gap_pct.abs()  # absolute gap size
    df["Gap_Net"] = gap_pct  # directional gap (continuous)

    # ── Hammer ────────────────────────────────────────────────────────────────
    body = (df["Close"] - df["Open"]).abs()
    rng = df["High"] - df["Low"]
    upper = df["High"] - pd.concat([df["Close"], df["Open"]], axis=1).max(axis=1)
    lower = pd.concat([df["Close"], df["Open"]], axis=1).min(axis=1) - df["Low"]
    ratio = body / (rng + 1e-10)
    df["Hammer"] = ((lower > body * 2) & (upper < body * 0.3)).astype(float)
    df["Hammer_Strength"] = (lower / (rng + 1e-10)).round(4)  # lower wick ratio
    df["Hammer_Score"] = (lower / (body + 1e-10)).round(4)  # wick-to-body ratio

    # ── Shooting_Star ─────────────────────────────────────────────────────────
    df["Shooting_Star"] = ((upper > body * 2) & (lower < body * 0.3)).astype(float)
    df["Shooting_Star_Strength"] = (upper / (rng + 1e-10)).round(4)

    # ── Vol_Ratio ─────────────────────────────────────────────────────────────
    vol_avg = df["Volume"].rolling(20).mean()
    df["Vol_Ratio"] = (df["Volume"] / vol_avg).round(4)
    df["Vol_Ratio_Rank"] = df["Vol_Ratio"].rolling(60).rank(pct=True).round(4)
    df["Vol_Ratio_Z"] = (
        (df["Vol_Ratio"] - df["Vol_Ratio"].rolling(60).mean())
        / df["Vol_Ratio"].rolling(60).std()
    ).round(4)
    df["Vol_Trend_Conf"] = (df["Vol_Ratio"] * np.sign(df["Close"].pct_change())).round(
        4
    )

    # ── Vol_Surge ─────────────────────────────────────────────────────────────
    df["Vol_Surge"] = (df["Vol_Ratio"] > 1.5).astype(float)
    df["Vol_Surge_Mag"] = (df["Vol_Ratio"] - 1.5).clip(lower=0).round(4)
    df["Vol_Surge_Dir"] = (df["Vol_Surge"] * np.sign(df["Close"].pct_change())).round(4)

    # ── Forward returns ────────────────────────────────────────────────────────
    for h in [1, 5, 10, 20, 30, 60, 90]:
        df[f"fwd_{h}d"] = df["Close"].pct_change(h).shift(-h).round(6)

    return df


# =============================================================================
# FORENSIC ANALYSIS ENGINE
# =============================================================================


def _safe_corr(x: pd.Series, y: pd.Series):
    """Return (pearson_r, pearson_p, spearman_r, spearman_p, n) or all None."""
    sub = pd.concat([x, y], axis=1).dropna()
    if len(sub) < 10:
        return None, None, None, None, len(sub)
    try:
        pr, pp = pearsonr(sub.iloc[:, 0], sub.iloc[:, 1])
        sr, sp = spearmanr(sub.iloc[:, 0], sub.iloc[:, 1])
        return round(pr, 4), round(pp, 4), round(sr, 4), round(sp, 4), len(sub)
    except Exception:
        return None, None, None, None, len(sub)


def _regime_corr_table(df: pd.DataFrame, feat: str, target: str = "fwd_5d") -> dict:
    """Per-regime Pearson r, p-value, and significance."""
    regimes = ["Bull", "Bear", "Sideways", "HighVol", "LowVol"]
    out = {}
    for reg in regimes:
        sub = df[df["Regime"] == reg][[feat, target]].dropna()
        if len(sub) < 10:
            out[reg] = {"r": None, "p": None, "n": len(sub), "sig": "INSUFFICIENT"}
            continue
        try:
            pr, pp = pearsonr(sub[feat], sub[target])
            sig = "SIGNIFICANT" if pp < 0.05 else "MARGINAL" if pp < 0.10 else "WEAK"
            out[reg] = {"r": round(pr, 4), "p": round(pp, 4), "n": len(sub), "sig": sig}
        except Exception:
            out[reg] = {"r": None, "p": None, "n": len(sub), "sig": "ERROR"}
    return out


def _time_period_corr(df: pd.DataFrame, feat: str, target: str = "fwd_5d") -> dict:
    """Pearson r in each of 3 time periods."""
    n = len(df)
    periods = {
        "Period_A": df.iloc[: n // 3],
        "Period_B": df.iloc[n // 3 : 2 * n // 3],
        "Period_C": df.iloc[2 * n // 3 :],
    }
    out = {}
    for pname, pdata in periods.items():
        sub = pdata[[feat, target]].dropna()
        if len(sub) < 15:
            out[pname] = {"r": None, "p": None, "n": len(sub)}
            continue
        try:
            pr, pp = pearsonr(sub[feat], sub[target])
            out[pname] = {"r": round(pr, 4), "p": round(pp, 4), "n": len(sub)}
        except Exception:
            out[pname] = {"r": None, "p": None, "n": len(sub)}
    return out


def _ic_across_horizons(df: pd.DataFrame, feat: str) -> dict:
    """Spearman IC at 5d, 10d, 20d, 30d, 60d, 90d horizons."""
    horizons = {
        "5d": "fwd_5d",
        "10d": "fwd_10d",
        "20d": "fwd_20d",
        "30d": "fwd_30d",
        "60d": "fwd_60d",
        "90d": "fwd_90d",
    }
    out = {}
    for hl, hc in horizons.items():
        if hc not in df.columns:
            continue
        sub = df[[feat, hc]].dropna()
        if len(sub) < 15:
            out[hl] = {"IC": None, "p": None, "n": len(sub)}
            continue
        try:
            sr, sp = spearmanr(sub[feat], sub[hc])
            out[hl] = {"IC": round(sr, 4), "p": round(sp, 4), "n": len(sub)}
        except Exception:
            out[hl] = {"IC": None, "p": None, "n": len(sub)}
    return out


def _signal_frequency(df: pd.DataFrame, feat: str) -> dict:
    """For binary features: fire rate, consecutive run stats."""
    s = df[feat].dropna()
    if s.nunique() <= 2:  # binary
        fire_rate = round(float(s.mean()), 4)
        total_fires = int(s.sum())
        return {
            "type": "BINARY",
            "fire_rate": fire_rate,
            "total_fires": total_fires,
            "n_total": len(s),
            "max_gap": int(s[s == 0].groupby((s != 0).cumsum()).count().max())
            if (s == 0).any()
            else 0,
        }
    else:
        return {
            "type": "CONTINUOUS",
            "mean": round(float(s.mean()), 4),
            "std": round(float(s.std()), 4),
            "pct_zero": round(float((s == 0).mean()), 4),
        }


def _nanrate(df: pd.DataFrame, feat: str) -> float:
    return round(float(df[feat].isna().mean()), 4) if feat in df.columns else 1.0


def _sign_consistency(corr_dict: dict) -> dict:
    """Check sign consistency across regimes or periods."""
    rs = [v.get("r") for v in corr_dict.values() if v.get("r") is not None]
    if not rs:
        return {"consistent": False, "signs": [], "flips": 0}
    signs = [1 if r > 0 else -1 if r < 0 else 0 for r in rs]
    n_positive = signs.count(1)
    n_negative = signs.count(-1)
    flips = min(n_positive, n_negative)
    return {
        "consistent": flips == 0,
        "n_positive": n_positive,
        "n_negative": n_negative,
        "flips": flips,
        "sign_values": signs,
    }


def _best_regime(regime_table: dict, mode: str = "abs") -> tuple:
    """Return the regime with the highest |r| or most significant p."""
    valid = {k: v for k, v in regime_table.items() if v.get("r") is not None}
    if not valid:
        return None, None
    if mode == "abs":
        best = max(valid, key=lambda k: abs(valid[k]["r"]))
    else:
        best = min(valid, key=lambda k: valid[k].get("p", 1))
    return best, valid[best]


def _repair_assessment(
    feat: str,
    meta: dict,
    time_analysis: dict,
    regime_analysis: dict,
    ic_analysis: dict,
    freq_info: dict,
    nan_rate: float,
) -> dict:
    """
    Determine repair potential for a rejected feature.
    Returns repair_code, repair_narrative, and regime_specific_verdict.
    """
    decay = meta.get("v722_decay", "")
    stab = meta.get("v722_stability", "")
    reg_var = meta.get("v722_regime_var") or 999
    reg_corrs = {
        k: v.get("r") for k, v in regime_analysis.items() if v.get("r") is not None
    }

    # ── regime-specific check ──────────────────────────────────────────────────
    strong_regime = {k: v for k, v in reg_corrs.items() if abs(v) >= 0.15}
    weak_regime = {k: v for k, v in reg_corrs.items() if abs(v) < 0.05}
    best_reg, best_reg_data = _best_regime(regime_analysis)

    # ── sparsity check ─────────────────────────────────────────────────────────
    is_sparse = (
        freq_info.get("type") == "BINARY" and freq_info.get("fire_rate", 1) < 0.05
    )

    # ── NaN contamination ──────────────────────────────────────────────────────
    nan_contaminated = nan_rate > 0.30

    # ── IC trajectory ─────────────────────────────────────────────────────────
    ic_vals = [v.get("IC") for v in ic_analysis.values() if v.get("IC") is not None]
    reversal_in_ic = (
        len(ic_vals) >= 2 and len({1 if x > 0 else -1 for x in ic_vals if x != 0}) > 1
    )

    # ── Repair logic ──────────────────────────────────────────────────────────
    repair_code = "R6"  # default: permanent reject
    repair_steps = []
    regime_specific_verdict = "NOT_VIABLE"

    if nan_contaminated:
        repair_code = "R6"
        repair_steps = [
            "NaN contamination too severe — feature fires too rarely to repair"
        ]
        regime_specific_verdict = "NOT_VIABLE"

    elif is_sparse:
        repair_code = "R5"
        repair_steps = [
            "Combine with confirming signal (e.g., Hammer + RSI_14 < 35)",
            "Use composite scoring instead of standalone binary signal",
            "Test on intraday data where frequency is higher",
        ]
        regime_specific_verdict = "POSSIBLY_IN_HIGH_VOL"

    elif len(strong_regime) >= 2 and not reversal_in_ic:
        repair_code = "R7"
        repair_steps = [
            f"Isolate to regimes: {list(strong_regime.keys())}",
            "Gate signal with regime classifier before applying",
            "Do not use as global signal",
        ]
        regime_specific_verdict = f"VIABLE_IN: {', '.join(strong_regime.keys())}"

    elif len(strong_regime) == 1 and not reversal_in_ic:
        repair_code = "R7"
        repair_steps = [
            f"Usable ONLY in {best_reg} regime (r={best_reg_data.get('r')})",
            "Extremely limited applicability — requires regime gate",
        ]
        regime_specific_verdict = f"VIABLE_IN: {best_reg} only"

    elif feat in ("ATR_14", "ATR_Norm"):
        repair_code = "R2"
        repair_steps = [
            "ATR normalized by price (ATR/Close*100) removes trending bias",
            "ATR-rank (rolling percentile) may stabilize directional IC",
            "Retest with ATR_Rank or ATR_Change as replacement signal",
        ]
        regime_specific_verdict = (
            "VIABLE_IN: HighVol, Sideways (as regime filter, not predictor)"
        )

    elif feat == "BB_Width":
        repair_code = "R4"
        repair_steps = [
            "BB_Width_Rank (rolling percentile rank) removes trending bias",
            "BB_Width_Z (z-score) normalizes across regimes",
            "Use squeeze/expansion rate-of-change instead of raw width",
        ]
        regime_specific_verdict = "VIABLE_IN: Bear, HighVol (expansion signals)"

    elif feat in ("OBV", "OBV_Slope"):
        repair_code = "R4"
        repair_steps = [
            "Use OBV_Signal = OBV minus OBV_EMA (removes trend drift)",
            "Rank OBV_Slope within rolling window for stationarity",
            "Test OBV divergence from price (separate from raw OBV level)",
        ]
        regime_specific_verdict = "VIABLE_IN: Bull regime (r=-0.53 in Bull)"

    elif feat == "RSI_Divergence":
        repair_code = "R3"
        repair_steps = [
            "Test divergence strength (RSI_Div_Strength) vs binary flag",
            "Condition divergence on ADX > 25 (trending market confirmation)",
            "Test at longer lookbacks (20-bar window vs current 10-bar)",
        ]
        regime_specific_verdict = "VIABLE_IN: Bull, HighVol (r=0.13, 0.18)"

    elif feat in ("StochRSI_K",):
        repair_code = "R3"
        repair_steps = [
            "Use StochRSI smoothed EMA (removes noise)",
            "Test StochRSI momentum (change in K) instead of raw K",
            "Condition on Stochastic extreme zones (K < 10 or > 90)",
        ]
        regime_specific_verdict = "VIABLE_IN: Sideways, HighVol (r=0.15, 0.11)"

    elif feat in ("Gap_Up", "Gap_Down"):
        repair_code = "R1"
        repair_steps = [
            "Use Gap_Pct (continuous) instead of binary flag",
            "Condition on gap direction + Vol_Ratio > 1.5 confirmation",
            "Test gap-fill rate as separate predictive signal",
        ]
        regime_specific_verdict = "VIABLE_IN: Sideways (r=-0.10 for Gap_Up)"

    elif reversal_in_ic:
        repair_code = "R6"
        repair_steps = [
            "IC reversal across horizons indicates structural noise, not signal",
            "Feature direction depends entirely on horizon — unpredictable",
            "No lookback or normalization fix resolves directional ambiguity",
        ]
        regime_specific_verdict = "NOT_VIABLE"

    else:
        repair_code = "R6"
        repair_steps = ["No clear repair path — insufficient predictive structure"]
        regime_specific_verdict = "NOT_VIABLE"

    return {
        "repair_code": repair_code,
        "repair_label": REPAIR_CODES.get(repair_code, "UNKNOWN"),
        "repair_steps": repair_steps,
        "regime_specific_verdict": regime_specific_verdict,
        "strong_regimes": list(strong_regime.keys()),
        "weak_regimes": list(weak_regime.keys()),
        "best_regime": best_reg,
        "is_sparse": is_sparse,
        "nan_contaminated": nan_contaminated,
        "reversal_in_ic": reversal_in_ic,
    }


def _failure_diagnosis(
    feat: str,
    meta: dict,
    time_analysis: dict,
    regime_analysis: dict,
    ic_analysis: dict,
    freq_info: dict,
    nan_rate: float,
    global_r: float,
) -> list:
    """Return list of (failure_code, description) for this feature."""
    failures = []

    # F1: Time instability
    tperiod_rs = [v.get("r") for v in time_analysis.values() if v.get("r") is not None]
    if len(tperiod_rs) >= 2:
        cstd = float(np.std(tperiod_rs))
        signs = {1 if r > 0 else -1 for r in tperiod_rs if r != 0}
        if len(signs) > 1:
            failures.append(
                (
                    "F1",
                    f"Sign flip across time periods: {[round(r, 3) for r in tperiod_rs]}",
                )
            )
        elif cstd > 0.15:
            failures.append(
                (
                    "F1",
                    f"High correlation variance across periods: std={round(cstd, 3)}",
                )
            )

    # F2: Regime collapse
    reg_rs = [v.get("r") for v in regime_analysis.values() if v.get("r") is not None]
    if reg_rs:
        signs = {1 if r > 0 else -1 for r in reg_rs if r != 0}
        if len(signs) > 1:
            regime_detail = {
                k: round(v.get("r", 0), 3)
                for k, v in regime_analysis.items()
                if v.get("r") is not None
            }
            failures.append(
                ("F2", f"Correlation sign inverts across regimes: {regime_detail}")
            )

    # F3: Alpha decay
    ic_vals = [v.get("IC") for v in ic_analysis.values() if v.get("IC") is not None]
    if len(ic_vals) >= 3:
        diffs = list(np.diff(ic_vals))
        if all(d < -0.01 for d in diffs):
            failures.append(
                ("F3", f"IC monotonically decays: {[round(v, 3) for v in ic_vals]}")
            )

    # F4: Signal reversal
    if len(ic_vals) >= 2:
        signs = {1 if v > 0 else -1 for v in ic_vals if v != 0}
        if len(signs) > 1:
            failures.append(
                (
                    "F4",
                    f"IC crosses zero at longer horizon: {[round(v, 3) for v in ic_vals]}",
                )
            )

    # F5: Sparse signal
    if freq_info.get("type") == "BINARY":
        fr = freq_info.get("fire_rate", 1)
        tf = freq_info.get("total_fires", 0)
        if fr < 0.05:
            failures.append(
                (
                    "F5",
                    f"Binary signal fires only {fr * 100:.1f}% of bars ({tf} total events)",
                )
            )
        elif fr < 0.10:
            failures.append(
                (
                    "F5",
                    f"Low frequency: {fr * 100:.1f}% fire rate ({tf} events) — statistical power limited",
                )
            )

    # F6: Correlation collapse
    if global_r is not None and abs(global_r) < 0.05:
        failures.append(
            (
                "F6",
                f"Global Pearson |r|={abs(global_r):.4f} — near-zero predictive correlation",
            )
        )

    # F7: NaN contamination
    if nan_rate > 0.30:
        failures.append(
            (
                "F7",
                f"NaN rate = {nan_rate * 100:.1f}% — insufficient valid observations",
            )
        )
    elif nan_rate > 0.10:
        failures.append(
            (
                "F7",
                f"Elevated NaN rate = {nan_rate * 100:.1f}% — reduces statistical power",
            )
        )

    # F8: Horizon drift
    if len(ic_vals) >= 3 and not any(code == "F4" for code, _ in failures):
        diffs = list(np.diff(ic_vals))
        if all(abs(d) < 0.02 for d in diffs):
            failures.append(
                ("F8", "IC near-zero across all horizons — no alpha at any horizon")
            )
        elif not all(d < 0 for d in diffs) and not all(d > 0 for d in diffs):
            failures.append(
                (
                    "F8",
                    f"IC direction drifts without commitment: {[round(v, 3) for v in ic_vals]}",
                )
            )

    return failures


# =============================================================================
# FULL FORENSIC ANALYSIS PER FEATURE
# =============================================================================


def run_feature_forensics(df: pd.DataFrame) -> dict:
    """Run complete failure analysis for every rejected feature."""
    results = {}

    for feat, meta in REJECTED_FEATURES.items():
        print(f"  Analysing: {feat}...")

        if feat not in df.columns:
            results[feat] = {"error": "FEATURE_NOT_IN_DATAFRAME"}
            continue

        # ── Core measurements ─────────────────────────────────────────────────
        nan_rate = _nanrate(df, feat)
        time_analysis = _time_period_corr(df, feat, "fwd_5d")
        regime_analysis = _regime_corr_table(df, feat, "fwd_5d")
        ic_analysis = _ic_across_horizons(df, feat)
        freq_info = _signal_frequency(df, feat)

        # Global Pearson r
        pr, pp, sr, sp, n_global = _safe_corr(df[feat], df.get("fwd_5d", pd.Series()))

        # Sign consistency
        regime_sign_check = _sign_consistency(regime_analysis)
        time_sign_check = _sign_consistency(time_analysis)

        # ── Failure diagnosis ─────────────────────────────────────────────────
        failures = _failure_diagnosis(
            feat,
            meta,
            time_analysis,
            regime_analysis,
            ic_analysis,
            freq_info,
            nan_rate,
            pr,
        )

        # ── Repair assessment ─────────────────────────────────────────────────
        repair = _repair_assessment(
            feat, meta, time_analysis, regime_analysis, ic_analysis, freq_info, nan_rate
        )

        # ── Permanent reject verdict ──────────────────────────────────────────
        permanently_rejected = (
            repair["repair_code"] == "R6"
            or nan_rate > 0.50
            or (repair["reversal_in_ic"] and not repair["strong_regimes"])
        )

        results[feat] = {
            "meta": meta,
            "nan_rate": nan_rate,
            "global_pearson_r": pr,
            "global_pearson_p": pp,
            "global_n": n_global,
            "time_analysis": time_analysis,
            "regime_analysis": regime_analysis,
            "ic_analysis": ic_analysis,
            "freq_info": freq_info,
            "regime_sign_check": regime_sign_check,
            "time_sign_check": time_sign_check,
            "failures": failures,
            "repair": repair,
            "permanently_rejected": permanently_rejected,
        }

    return results


# =============================================================================
# REPORT GENERATION — FEATURE_FAILURE_REPORT.md
# =============================================================================


def generate_failure_report(
    forensics: dict, df: pd.DataFrame, output_path: str = None
) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    L = []

    def h(text=""):
        L.append(text)

    def row(*cells):
        L.append("| " + " | ".join(str(c) for c in cells) + " |")

    def div(n):
        L.append("|" + "|".join(["---"] * n) + "|")

    def hr():
        h("\n---\n")

    # ── Header ────────────────────────────────────────────────────────────────
    h("# FEATURE FAILURE REPORT")
    h("## WealthQuant V7.2.3 — Forensic Analysis of Rejected Features")
    h("")
    h(f"**Generated:** {ts}")
    h("**Source Audit:** WealthQuant V7.2.2 Alpha Stability Audit")
    h(f"**Features Under Autopsy:** {len(forensics)}")
    h("")
    h("### Failure Taxonomy")
    h("")
    h("| Code | Name | Description |")
    div(3)
    for code, name in FAILURE_CODES.items():
        h(f"| `{code}` | {name} | *See per-feature analysis below* |")
    h("")
    h("### Repair Taxonomy")
    h("")
    h("| Code | Label |")
    div(2)
    for code, label in REPAIR_CODES.items():
        h(f"| `{code}` | {label} |")
    hr()

    # ── Executive Dashboard ────────────────────────────────────────────────────
    h("## EXECUTIVE DASHBOARD")
    h("")
    perm_reject = [f for f, d in forensics.items() if d.get("permanently_rejected")]
    reparable = [
        f
        for f, d in forensics.items()
        if not d.get("permanently_rejected")
        and d.get("repair", {}).get("repair_code") != "R6"
    ]
    regime_spec = [
        f
        for f, d in forensics.items()
        if d.get("repair", {}).get("repair_code") == "R7"
    ]

    h(
        "| Feature | Score | Decay | Stability | Primary Failure | Repair Code | Regime-Specific? | Permanent? |"
    )
    div(8)
    for feat, d in forensics.items():
        if "error" in d:
            continue
        meta = d.get("meta", {})
        fails = d.get("failures", [])
        repair = d.get("repair", {})
        pf = fails[0][0] if fails else "—"
        pf_name = FAILURE_CODES.get(pf, "—")[:18]
        perm = "YES" if d.get("permanently_rejected") else "NO"
        reg_s = "YES" if repair.get("repair_code") == "R7" else "NO"
        h(
            f"| **{feat}** | {meta.get('v722_score', '—')} | {meta.get('v722_decay', '—')} | "
            f"{meta.get('v722_stability', '—')} | `{pf}` {pf_name} | "
            f"`{repair.get('repair_code', '—')}` | {reg_s} | {perm} |"
        )

    h("")
    h(
        f"**Summary:** {len(forensics)} features analysed — "
        f"{len(perm_reject)} permanently rejected, "
        f"{len(reparable)} reparable, "
        f"{len(regime_spec)} regime-specific candidates"
    )
    hr()

    # ── Per-Feature Deep-Dives ─────────────────────────────────────────────────
    h("## PER-FEATURE FORENSIC AUTOPSY")
    h("")

    for feat, d in forensics.items():
        if "error" in d:
            h(f"### {feat}")
            h("> Feature not found in computed DataFrame.")
            hr()
            continue

        meta = d["meta"]
        fails = d["failures"]
        repair = d["repair"]
        ta = d["time_analysis"]
        ra = d["regime_analysis"]
        ic = d["ic_analysis"]
        freq = d["freq_info"]

        # ── Feature title ──────────────────────────────────────────────────────
        h(f"### {feat}")
        h(
            f"**Category:** {meta['category']} &nbsp;|&nbsp; "
            f"**V7.2.2 Score:** {meta['v722_score']}/100 &nbsp;|&nbsp; "
            f"**Grade:** {meta['v722_grade']} &nbsp;|&nbsp; "
            f"**NaN Rate:** {d['nan_rate'] * 100:.1f}%"
        )
        h("")

        # ── Q1: Why was it rejected? ───────────────────────────────────────────
        h("#### Q1: Why Was It Rejected?")
        h("")
        if fails:
            for code, desc in fails:
                h(f"- **`{code}` — {FAILURE_CODES[code]}:** {desc}")
        else:
            h(
                "- Score below approval threshold (65) with no specific pathology detected"
            )
        h("")

        # ── Time stability details ─────────────────────────────────────────────
        h("**Time Stability (Period A / B / C):**")
        h("")
        row("Period", "Pearson r", "p-value", "n")
        div(4)
        for pname, pdata in ta.items():
            r = pdata.get("r", "—")
            p = pdata.get("p", "—")
            n_ = pdata.get("n", "—")
            row(pname, r, p, n_)
        h("")

        # ── Regime stability details ───────────────────────────────────────────
        h("**Regime Stability (Pearson r vs 5d forward return):**")
        h("")
        row("Regime", "r", "p-value", "n", "Significance")
        div(5)
        for reg, rdata in ra.items():
            row(
                reg,
                rdata.get("r", "—"),
                rdata.get("p", "—"),
                rdata.get("n", "—"),
                rdata.get("sig", "—"),
            )
        h("")

        # ── IC profile ────────────────────────────────────────────────────────
        h("**Information Coefficient (IC) Across Horizons:**")
        h("")
        row("Horizon", "IC (Spearman r)", "p-value", "n")
        div(4)
        for hl, hdata in ic.items():
            row(hl, hdata.get("IC", "—"), hdata.get("p", "—"), hdata.get("n", "—"))
        h("")

        # ── Signal frequency ──────────────────────────────────────────────────
        if freq.get("type") == "BINARY":
            fr = freq.get("fire_rate", 0)
            tf = freq.get("total_fires", 0)
            h(
                f"**Signal Frequency:** BINARY — fires on {fr * 100:.1f}% of bars "
                f"({tf} events in {freq.get('n_total', 0)} bars)"
            )
        else:
            h(
                f"**Signal Distribution:** CONTINUOUS — mean={freq.get('mean', '—')}, "
                f"std={freq.get('std', '—')}, zero-pct={freq.get('pct_zero', 0) * 100:.1f}%"
            )
        h("")

        # ── Q2: Can it be repaired? ────────────────────────────────────────────
        h("#### Q2: Can It Be Repaired?")
        h("")
        rc = repair["repair_code"]
        rlabel = repair["repair_label"]
        steps = repair["repair_steps"]

        if rc == "R6":
            h(f"> **Verdict: NO — {rlabel}**")
        elif rc == "R7":
            h(f"> **Verdict: PARTIAL — {rlabel}** (regime-gated use only)")
        else:
            h(f"> **Verdict: YES — {rlabel}**")
        h("")
        if steps:
            h("**Repair Steps:**")
            for s in steps:
                h(f"- {s}")
        h("")

        # ── Q3: Permanent reject? ─────────────────────────────────────────────
        h("#### Q3: Should It Remain Rejected Permanently?")
        h("")
        perm = d["permanently_rejected"]
        if perm:
            h(
                f"> **YES — Permanently Rejected.** This feature has no viable repair path "
                f"as a global alpha signal. Primary reason: "
                f"{fails[0][1] if fails else 'insufficient alpha'}."
            )
        else:
            strong_r = repair.get("strong_regimes", [])
            h(
                f"> **NO — Conditional Reprieve.** Feature may have value in "
                f"specific contexts: {strong_r or 'with significant transformation'}. "
                f"Recommend re-audit after applying repair transformations."
            )
        h("")

        # ── Q4: Regime-specific? ──────────────────────────────────────────────
        h("#### Q4: Could It Become Regime-Specific?")
        h("")
        rv = repair["regime_specific_verdict"]
        best_r, best_data = _best_regime(ra)

        if rv == "NOT_VIABLE":
            h(
                "> **NO — Regime-specific use not viable.** Correlation sign flips or "
                "signal is near-zero in every tested regime. No isolated regime provides "
                "consistent directional edge."
            )
        else:
            h(f"> **YES — {rv}**")
            if best_r and best_data and best_data.get("r") is not None:
                h(
                    f"> Strongest regime: **{best_r}** "
                    f"(r = {best_data['r']}, p = {best_data['p']}, n = {best_data['n']})"
                )
        h("")
        hr()

    # ── Comparative Summary Table ──────────────────────────────────────────────
    h("## COMPARATIVE FAILURE MATRIX")
    h("")
    h(
        "| Feature | F1 Time | F2 Regime | F3 Decay | F4 Reversal | F5 Sparse | F6 Corr | F7 NaN | Permanent |"
    )
    div(9)

    for feat, d in forensics.items():
        if "error" in d:
            continue
        fail_codes = {fc for fc, _ in d.get("failures", [])}

        def mark(code):
            return "X" if code in fail_codes else "-"

        perm = "YES" if d.get("permanently_rejected") else "NO"
        h(
            f"| **{feat}** | {mark('F1')} | {mark('F2')} | {mark('F3')} | "
            f"{mark('F4')} | {mark('F5')} | {mark('F6')} | {mark('F7')} | {perm} |"
        )

    hr()

    # ── Repair Priority Matrix ─────────────────────────────────────────────────
    h("## REPAIR PRIORITY MATRIX")
    h("")
    h("Features ranked by repair potential (highest first):")
    h("")

    # sort by repair priority: R1/R2/R3/R4 > R7 > R5 > R6
    priority_map = {"R1": 1, "R2": 2, "R3": 3, "R4": 4, "R7": 5, "R5": 6, "R6": 7}
    sorted_feats = sorted(
        [(f, d) for f, d in forensics.items() if "error" not in d],
        key=lambda x: priority_map.get(x[1]["repair"]["repair_code"], 9),
    )

    row(
        "Rank",
        "Feature",
        "Repair Code",
        "Repair Label",
        "Regime Viable",
        "Recommended Action",
    )
    div(6)
    for rank, (feat, d) in enumerate(sorted_feats, 1):
        repair = d["repair"]
        rc = repair["repair_code"]
        rv = repair["regime_specific_verdict"]
        action = {
            "R1": "Apply regime conditioning — re-audit in V7.3",
            "R2": "Apply normalization — re-audit in V7.3",
            "R3": "Adjust lookback/parameters — re-audit in V7.3",
            "R4": "Apply transform (rank/z-score/EMA) — re-audit in V7.3",
            "R5": "Combine with other sparse signals — conditional only",
            "R7": "Gate with regime classifier — restricted use only",
            "R6": "Permanently exclude — no viable repair path",
        }.get(rc, "—")
        row(
            rank,
            f"**{feat}**",
            f"`{rc}`",
            REPAIR_CODES.get(rc, "—"),
            rv.split(":")[0],
            action,
        )

    hr()

    # ── V7.3 Disposition Summary ──────────────────────────────────────────────
    h("## V7.3 DISPOSITION SUMMARY")
    h("")
    h("### Features That Remain REJECTED for V7.3")
    h("")
    perm_feats = [
        f
        for f, d in forensics.items()
        if "error" not in d and d.get("permanently_rejected")
    ]
    for feat in perm_feats:
        d = forensics[feat]
        fails = d["failures"]
        h(f"- `{feat}` — {fails[0][1] if fails else 'no viable alpha structure'}")

    h("")
    h("### Features Eligible for Conditional Re-entry (Post-Repair)")
    h("")
    cond_feats = [
        f
        for f, d in forensics.items()
        if "error" not in d and not d.get("permanently_rejected")
    ]
    for feat in cond_feats:
        d = forensics[feat]
        repair = d["repair"]
        rv = repair["regime_specific_verdict"]
        h(f"- `{feat}` — {repair['repair_label']} | Regime: {rv}")

    h("")
    h("### Regime-Specific Candidates (Gated Use)")
    h("")
    regime_feats = [
        f
        for f, d in forensics.items()
        if "error" not in d and d.get("repair", {}).get("repair_code") == "R7"
    ]
    if regime_feats:
        for feat in regime_feats:
            d = forensics[feat]
            rv = d["repair"]["regime_specific_verdict"]
            h(f"- `{feat}` — {rv}")
    else:
        h("*No features qualify for regime-specific use.*")

    hr()

    # ── Final verdicts ─────────────────────────────────────────────────────────
    h("## FINAL VERDICT")
    h("")
    h("| Question | Answer |")
    div(2)
    h(
        "| Why rejected? | Each feature fails on signal reversal, time instability, regime collapse, or NaN contamination — documented per-feature above |"
    )
    h(
        f"| Can be repaired? | {len([f for f, d in forensics.items() if 'error' not in d and d['repair']['repair_code'] not in ('R6',)])} of {len(forensics)} features have conditional repair paths |"
    )
    h(
        f"| Permanently rejected? | {len(perm_feats)} features are permanently excluded as global signals |"
    )
    h(
        f"| Regime-specific viable? | {len(regime_feats)} features are viable when gated by regime classifier |"
    )
    h("")
    h(
        "> **RULE: None of these REJECTED features may enter V7.3 Market Structure Engine**"
    )
    h("> **without first completing their repair protocol and passing re-audit.**")
    h("")
    hr()
    h(
        "*WealthQuant V7.2.3 Feature Failure Analysis — generated by `feature_failure_analysis.py`*"
    )
    h("")

    report = "\n".join(L)
    if output_path is None:
        output_path = Path(__file__).parent / "FEATURE_FAILURE_REPORT.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n[REPORT] Written to: {output_path}")
    return report


# =============================================================================
# MAIN
# =============================================================================


def run_failure_analysis():
    print("=" * 70)
    print("  WEALTHQUANT V7.2.3 — FEATURE FAILURE ANALYSIS")
    print("=" * 70)

    print("\n[STEP 1] Reconstructing market data (600 bars, same seed as V7.2.2)...")
    df = generate_market_data(n_bars=600, seed=42)
    print(f"         Shape: {df.shape}")

    print("\n[STEP 2] Computing rejected features + repair variants...")
    df = compute_rejected_features(df)
    rejected_cols = [f for f in REJECTED_FEATURES if f in df.columns]
    print(
        f"         Computed: {len(rejected_cols)}/{len(REJECTED_FEATURES)} rejected features"
    )

    print("\n[STEP 3] Running forensic analysis on each rejected feature...")
    forensics = run_feature_forensics(df)

    print("\n[STEP 4] Generating FEATURE_FAILURE_REPORT.md...")
    generate_failure_report(forensics, df)

    # ── Console summary ────────────────────────────────────────────────────────
    perm_count = sum(
        1
        for d in forensics.values()
        if "error" not in d and d.get("permanently_rejected")
    )
    cond_count = sum(
        1
        for d in forensics.values()
        if "error" not in d and not d.get("permanently_rejected")
    )
    regime_count = sum(
        1
        for d in forensics.values()
        if "error" not in d and d.get("repair", {}).get("repair_code") == "R7"
    )

    print("\n" + "=" * 70)
    print("  FAILURE ANALYSIS COMPLETE")
    print("=" * 70)
    print(
        f"\n  Permanently Rejected : {perm_count:>2}  ->  excluded from V7.3 permanently"
    )
    print(
        f"  Conditionally Viable : {cond_count:>2}  ->  repair required before re-audit"
    )
    print(
        f"  Regime-Specific      : {regime_count:>2}  ->  usable only with regime gate"
    )
    print("\n  Output  : FEATURE_FAILURE_REPORT.md")
    print("=" * 70)

    return forensics


if __name__ == "__main__":
    results = run_failure_analysis()
