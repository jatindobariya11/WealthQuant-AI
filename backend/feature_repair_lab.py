"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         WEALTHQUANT V7.2.4 — FEATURE REPAIR LAB                             ║
║         Mission  : Implement & validate repair protocols for every           ║
║                    repairable feature from V7.2.3 Failure Analysis           ║
║         Phases   : 5  |  Output: FEATURE_REPAIR_REPORT.md                  ║
║         Scope    : Research only. No Ensemble. No Meta-Learning.            ║
╚══════════════════════════════════════════════════════════════════════════════╝

Repair Queue:
  ATR_14          ->  ATR_Normalized
  BB_Width        ->  ZScore_BB_Width
  OBV             ->  Regime_OBV
  RSI_Divergence  ->  RSI_Div_ADX
  Hammer          ->  Hammer_RSI35
  Shooting_Star   ->  Star_RSI65
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
# REPAIR REGISTRY
# Maps original rejected feature → repaired variant + repair protocol
# ─────────────────────────────────────────────────────────────────────────────

REPAIR_REGISTRY = {
    "ATR_14": {
        "repaired_name": "ATR_Normalized",
        "repair_code": "R2",
        "repair_protocol": "ATR / Close * 100  →  removes absolute-price trending bias",
        "v722_score": 28.9,
        "v722_failure": "SIGNAL_REVERSAL — IC flips positive at 60d+ horizon",
        "category": "Volatility",
    },
    "BB_Width": {
        "repaired_name": "ZScore_BB_Width",
        "repair_code": "R4",
        "repair_protocol": "Rolling 60-bar z-score of BB_Width  →  makes stationary, removes drift",
        "v722_score": 49.3,
        "v722_failure": "SIGNAL_REVERSAL — IC goes from -0.10 to +0.32 at 90d",
        "category": "Volatility",
    },
    "OBV": {
        "repaired_name": "Regime_OBV",
        "repair_code": "R4",
        "repair_protocol": "OBV_Signal = (OBV - EMA21_OBV) / ATR_proxy  →  detrended, normalized",
        "v722_score": 15.6,
        "v722_failure": "SIGN_FLIP — Bull r=-0.53 vs Bear r=+0.24",
        "category": "Volume",
    },
    "RSI_Divergence": {
        "repaired_name": "RSI_Div_ADX",
        "repair_code": "R3",
        "repair_protocol": "RSI_Divergence AND ADX > 25  →  gates divergence to confirmed trends only",
        "v722_score": 17.7,
        "v722_failure": "REGIME_COLLAPSE — direction flips in Sideways regime",
        "category": "Momentum",
    },
    "Hammer": {
        "repaired_name": "Hammer_RSI35",
        "repair_code": "R5",
        "repair_protocol": "Hammer AND RSI_14 < 35  →  gates to oversold reversals only",
        "v722_score": 25.0,
        "v722_failure": "SPARSE_SIGNAL — fires in 4.7% of bars with no oversold filter",
        "category": "Candle",
    },
    "Shooting_Star": {
        "repaired_name": "Star_RSI65",
        "repair_code": "R5",
        "repair_protocol": "Shooting_Star AND RSI_14 > 65  →  gates to overbought reversals only",
        "v722_score": 25.0,
        "v722_failure": "SPARSE_SIGNAL — fires in 4.5% of bars with no overbought filter",
        "category": "Candle",
    },
}

# Promotion thresholds (stricter than V7.2.2 due to repair bias)
PROMOTE_MIN_SCORE = 65
WATCHLIST_MIN_SCORE = 40
STABLE_LABELS = ("STABLE", "MODERATE")


# =============================================================================
# PHASE 0 — DATA INFRASTRUCTURE
# =============================================================================


def generate_market_data(n_bars: int = 600, seed: int = 42) -> pd.DataFrame:
    """Identical to V7.2.2 & V7.2.3 — same seed ensures reproducibility."""
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


# ── Core indicator helpers ─────────────────────────────────────────────────────


def _rsi(c: pd.Series, p: int = 14) -> pd.Series:
    d = c.diff()
    g = d.clip(lower=0).ewm(com=p - 1, min_periods=p).mean()
    l = (-d.clip(upper=0)).ewm(com=p - 1, min_periods=p).mean()
    return (100 - 100 / (1 + g / l)).round(4)


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
    u = mid + std * sd
    l = mid - std * sd
    return u.round(4), mid.round(4), l.round(4), ((u - l) / mid * 100).round(4)


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


def _mi_score(x: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    try:
        xb = pd.cut(pd.Series(x).rank(pct=True), bins=bins, labels=False)
        yb = pd.cut(pd.Series(y).rank(pct=True), bins=bins, labels=False)
        return float(mutual_info_score(xb.fillna(0), yb.fillna(0)))
    except Exception:
        return 0.0


# =============================================================================
# PHASE 1 — REPAIR IMPLEMENTATIONS
# Each repaired feature is computed alongside its original for comparison.
# =============================================================================


def phase1_implement_repairs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute original rejected features + all 6 repaired variants.
    Repair protocols from V7.2.3 Failure Analysis.
    """
    c = df["Close"].copy()

    # ── Supporting indicators ──────────────────────────────────────────────────
    df["RSI_14"] = _rsi(c, 14)
    adx, _, _ = _adx(df, 14)
    df["ADX_14"] = adx
    df["ATR_14_raw"] = _atr(df, 14)

    # ══════════════════════════════════════════════════════════════════════════
    # REPAIR 1: ATR_14  →  ATR_Normalized
    # Protocol: ATR / Close * 100 (percentage-of-price)
    # Removes absolute-price drift that caused IC to flip at 60d+ horizon
    # ══════════════════════════════════════════════════════════════════════════
    df["ATR_14"] = df["ATR_14_raw"]
    df["ATR_Normalized"] = (df["ATR_14_raw"] / c * 100).round(6)

    # ══════════════════════════════════════════════════════════════════════════
    # REPAIR 2: BB_Width  →  ZScore_BB_Width
    # Protocol: Rolling 60-bar z-score of BB_Width
    # Makes series stationary — removes the volatile drift that reversed IC at 90d
    # ══════════════════════════════════════════════════════════════════════════
    _, _, _, bw = _bb(c, 20, 2)
    df["BB_Width"] = bw
    bw_mean = bw.rolling(60).mean()
    bw_std = bw.rolling(60).std()
    df["ZScore_BB_Width"] = ((bw - bw_mean) / (bw_std + 1e-10)).round(6)

    # ══════════════════════════════════════════════════════════════════════════
    # REPAIR 3: OBV  →  Regime_OBV
    # Protocol: (OBV - EMA_21_of_OBV) normalized by rolling 20-bar ATR proxy
    # Removes absolute trending drift; creates mean-reverting signal
    # ══════════════════════════════════════════════════════════════════════════
    raw_obv = _obv(df)
    df["OBV"] = raw_obv
    obv_ema21 = raw_obv.ewm(span=21, adjust=False).mean()
    obv_signal = raw_obv - obv_ema21  # detrended OBV
    # normalize by rolling std of OBV signal (makes comparable across regimes)
    obv_std = obv_signal.rolling(40).std().replace(0, np.nan)
    df["Regime_OBV"] = (obv_signal / obv_std).round(6)

    # ══════════════════════════════════════════════════════════════════════════
    # REPAIR 4: RSI_Divergence  →  RSI_Div_ADX
    # Protocol: RSI divergence GATED by ADX > 25 (trending market only)
    # Eliminates false divergences in Sideways regime where ADX < 20
    # ══════════════════════════════════════════════════════════════════════════
    rsi = df["RSI_14"].copy()
    raw_div = pd.Series(0.0, index=df.index)
    for i in range(20, len(df)):
        price_nh = c.iloc[i] > c.iloc[i - 10 : i].max()
        rsi_nc = rsi.iloc[i] < rsi.iloc[i - 10 : i].max()
        price_nl = c.iloc[i] < c.iloc[i - 10 : i].min()
        rsi_pc = rsi.iloc[i] > rsi.iloc[i - 10 : i].min()
        if price_nh and rsi_nc:
            raw_div.at[df.index[i]] = -1.0  # bearish divergence
        elif price_nl and rsi_pc:
            raw_div.at[df.index[i]] = 1.0  # bullish divergence
    df["RSI_Divergence"] = raw_div
    # Gate: only emit signal when ADX confirms a trending market
    adx_gate = (df["ADX_14"] > 25).astype(float)
    df["RSI_Div_ADX"] = (raw_div * adx_gate).round(6)

    # ══════════════════════════════════════════════════════════════════════════
    # REPAIR 5: Hammer  →  Hammer_RSI35
    # Protocol: Hammer AND RSI_14 < 35
    # Focuses signal exclusively on oversold reversal setups
    # ══════════════════════════════════════════════════════════════════════════
    body = (df["Close"] - df["Open"]).abs()
    rng = df["High"] - df["Low"]
    upper = df["High"] - pd.concat([df["Close"], df["Open"]], axis=1).max(axis=1)
    lower = pd.concat([df["Close"], df["Open"]], axis=1).min(axis=1) - df["Low"]
    ratio = body / (rng + 1e-10)
    hammer_raw = ((lower > body * 2) & (upper < body * 0.3)).astype(float)
    df["Hammer"] = hammer_raw
    df["Hammer_RSI35"] = (hammer_raw * (rsi < 35).astype(float)).round(6)

    # ══════════════════════════════════════════════════════════════════════════
    # REPAIR 6: Shooting_Star  →  Star_RSI65
    # Protocol: Shooting_Star AND RSI_14 > 65
    # Focuses signal on overbought reversal setups only
    # ══════════════════════════════════════════════════════════════════════════
    shooting_raw = ((upper > body * 2) & (lower < body * 0.3)).astype(float)
    df["Shooting_Star"] = shooting_raw
    df["Star_RSI65"] = (shooting_raw * (rsi > 65).astype(float)).round(6)

    # ── Forward returns ────────────────────────────────────────────────────────
    for h in [1, 5, 10, 20, 30, 60, 90]:
        df[f"fwd_{h}d"] = c.pct_change(h).shift(-h).round(6)

    return df


# =============================================================================
# SHARED AUDIT ENGINE
# Used by Phases 2, 3, 4 for both original and repaired features
# =============================================================================


def _safe_corr(x: pd.Series, y: pd.Series):
    sub = pd.concat([x, y], axis=1).dropna()
    if len(sub) < 10:
        return None, None, None, None, len(sub)
    try:
        pr, pp = pearsonr(sub.iloc[:, 0], sub.iloc[:, 1])
        sr, sp = spearmanr(sub.iloc[:, 0], sub.iloc[:, 1])
        return round(pr, 4), round(pp, 4), round(sr, 4), round(sp, 4), len(sub)
    except Exception:
        return None, None, None, None, len(sub)


def _nan_rate(df: pd.DataFrame, feat: str) -> float:
    return round(float(df[feat].isna().mean()), 4) if feat in df.columns else 1.0


def _fire_rate(df: pd.DataFrame, feat: str) -> dict:
    """For binary/sparse features: compute fire statistics."""
    if feat not in df.columns:
        return {"type": "MISSING", "fire_rate": 0}
    s = df[feat].dropna()
    if s.nunique() <= 3 and s.max() <= 1:
        fr = float((s > 0).mean())
        return {
            "type": "BINARY",
            "fire_rate": round(fr, 4),
            "total_fires": int((s > 0).sum()),
        }
    return {
        "type": "CONTINUOUS",
        "mean": round(float(s.mean()), 4),
        "std": round(float(s.std()), 4),
    }


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — STABILITY AUDIT
# ─────────────────────────────────────────────────────────────────────────────


def phase2_stability_audit(
    df: pd.DataFrame, feature: str, target: str = "fwd_5d"
) -> dict:
    """
    Split history into Period A / B / C.
    Measure: Pearson r, Spearman r, p-value per period.
    Output: stability label + correlation std.
    """
    n = len(df)
    periods = {
        "Period_A": df.iloc[: n // 3],
        "Period_B": df.iloc[n // 3 : 2 * n // 3],
        "Period_C": df.iloc[2 * n // 3 :],
    }
    if feature not in df.columns or target not in df.columns:
        return {"stability": "N/A", "corr_std": None, "period_details": {}}

    pstats = {}
    corrs = []
    pvals = []
    spearmans = []
    for pname, pdata in periods.items():
        sub = pdata[[feature, target]].dropna()
        if len(sub) < 15:
            pstats[pname] = {
                "pearson_r": None,
                "spearman_r": None,
                "p_value": None,
                "n": len(sub),
            }
            continue
        try:
            pr, pp = pearsonr(sub[feature], sub[target])
            sr, sp = spearmanr(sub[feature], sub[target])
            pstats[pname] = {
                "pearson_r": round(pr, 4),
                "spearman_r": round(sr, 4),
                "p_value": round(pp, 4),
                "n": len(sub),
            }
            corrs.append(pr)
            pvals.append(pp)
            spearmans.append(sr)
        except Exception:
            pstats[pname] = {
                "pearson_r": None,
                "spearman_r": None,
                "p_value": None,
                "n": len(sub),
            }

    if len(corrs) >= 2:
        cstd = float(np.std(corrs))
        sign_flip = len({np.sign(r) for r in corrs if r != 0}) > 1
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

    return {
        "stability": stab,
        "corr_std": round(cstd, 4) if cstd is not None else None,
        "sign_flip": sign_flip,
        "pval_max": round(pval_max, 4) if pval_max is not None else None,
        "rank_corr_std": round(rstd, 4) if rstd is not None else None,
        "correlations": {k: v.get("pearson_r") for k, v in pstats.items()},
        "period_details": pstats,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 — REGIME AUDIT
# ─────────────────────────────────────────────────────────────────────────────


def phase3_regime_audit(df: pd.DataFrame, feature: str, target: str = "fwd_5d") -> dict:
    """
    Evaluate feature separately in Bull / Bear / Sideways / HighVol / LowVol.
    Measure: avg corr, worst corr, regime variance, sign consistency.
    """
    regimes = ["Bull", "Bear", "Sideways", "HighVol", "LowVol"]
    if feature not in df.columns or target not in df.columns:
        return {"avg_correlation": None, "regime_variance": None, "regimes": {}}

    rc = {}
    cl = []
    for regime in regimes:
        sub = df[df["Regime"] == regime][[feature, target]].dropna()
        if len(sub) < 10:
            rc[regime] = {"r": None, "p": None, "n": len(sub), "sig": "INSUFFICIENT"}
            continue
        try:
            pr, pp = pearsonr(sub[feature], sub[target])
            sr, _ = spearmanr(sub[feature], sub[target])
            sig = "SIGNIFICANT" if pp < 0.05 else "MARGINAL" if pp < 0.10 else "WEAK"
            rc[regime] = {
                "r": round(pr, 4),
                "p": round(pp, 4),
                "spearman_r": round(sr, 4),
                "n": len(sub),
                "sig": sig,
            }
            cl.append(pr)
        except Exception:
            rc[regime] = {"r": None, "p": None, "n": len(sub), "sig": "ERROR"}

    vc = [v for v in cl if v is not None]
    signs = {np.sign(r) for r in vc if r != 0}
    return {
        "avg_correlation": round(float(np.mean(vc)), 4) if vc else None,
        "worst_correlation": round(float(min(vc, key=abs)), 4) if vc else None,
        "best_correlation": round(float(max(vc, key=abs)), 4) if vc else None,
        "regime_variance": round(float(np.var(vc)), 6) if len(vc) >= 2 else None,
        "sign_consistent": len(signs) <= 1,
        "n_regimes_tested": len(vc),
        "regimes": rc,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 — DECAY AUDIT
# ─────────────────────────────────────────────────────────────────────────────


def phase4_decay_audit(df: pd.DataFrame, feature: str) -> dict:
    """
    IC (Spearman rank correlation) at 5d, 10d, 20d, 30d, 60d, 90d.
    Classify: STABLE_ALPHA / IMPROVING / SATURATION / ALPHA_DECAY / SIGNAL_REVERSAL / MIXED.
    """
    horizons = {
        "5d": "fwd_5d",
        "10d": "fwd_10d",
        "20d": "fwd_20d",
        "30d": "fwd_30d",
        "60d": "fwd_60d",
        "90d": "fwd_90d",
    }
    if feature not in df.columns:
        return {"decay_type": "N/A", "ic_series": {}}

    hstats = {}
    icv = []
    for hl, hc in horizons.items():
        if hc not in df.columns:
            continue
        sub = df[[feature, hc]].dropna()
        if len(sub) < 15:
            hstats[hl] = {"IC": None, "p": None, "n": len(sub)}
            continue
        try:
            sr, sp = spearmanr(sub[feature], sub[hc])
            hstats[hl] = {"IC": round(sr, 4), "p": round(sp, 4), "n": len(sub)}
            icv.append(sr)
        except Exception:
            hstats[hl] = {"IC": None, "p": None, "n": len(sub)}

    if len(icv) >= 3:
        ia = np.array(icv)
        idd = np.diff(ia)
        signs = {np.sign(x) for x in ia if x != 0}
        if len(signs) > 1:
            dtype = "SIGNAL_REVERSAL"
        elif all(d < -0.01 for d in idd):
            dtype = "ALPHA_DECAY"
        elif all(abs(d) < 0.015 for d in idd):
            dtype = "SATURATION"
        elif all(d > 0 for d in idd):
            dtype = "IMPROVING"
        elif all(d > -0.005 for d in idd) and ia[-1] > ia[0]:
            dtype = "STABLE_ALPHA"
        else:
            dtype = "MIXED"
        max_ic = round(float(np.max(np.abs(ia))), 4)
        mean_ic = round(float(np.mean(ia)), 4)
    elif len(icv) >= 2:
        ia = np.array(icv)
        signs = {np.sign(x) for x in ia if x != 0}
        dtype = "SIGNAL_REVERSAL" if len(signs) > 1 else "MIXED"
        max_ic = round(float(np.max(np.abs(ia))), 4)
        mean_ic = round(float(np.mean(ia)), 4)
    else:
        dtype = "INSUFFICIENT_DATA"
        max_ic = None
        mean_ic = None

    return {
        "decay_type": dtype,
        "max_ic": max_ic,
        "mean_ic": mean_ic,
        "ic_series": hstats,
        "ic_values": icv,
    }


# ─────────────────────────────────────────────────────────────────────────────
# QUALITY SCORE — adapted for repaired features
# ─────────────────────────────────────────────────────────────────────────────


def compute_quality_score(
    df: pd.DataFrame,
    feature: str,
    stab: dict,
    regime: dict,
    decay: dict,
    target: str = "fwd_5d",
) -> dict:
    """
    Feature Quality Score 0–100:
      Correlation (20) + Mutual Info (15) + p-value (15) +
      Sample Size (10) + Time Stability (20) + Regime Stability (20)
    Decay penalty applied post-scoring.
    """
    if feature not in df.columns or target not in df.columns:
        return {"feature_quality_score": 0, "grade": "F", "parts": {}}

    sub = df[[feature, target]].dropna()
    n = len(sub)
    sc = 0.0
    parts = {}

    # 1. Pearson (20 pts)
    try:
        pr, pp = pearsonr(sub[feature], sub[target])
        c_pts = min(20.0, abs(pr) * 100)
    except Exception:
        pr, pp, c_pts = 0.0, 1.0, 0.0
    sc += c_pts
    parts["correlation"] = round(c_pts, 2)

    # 2. Mutual Information (15 pts)
    mi = _mi_score(sub[feature].values, sub[target].values)
    m_pts = min(15.0, mi * 30)
    sc += m_pts
    parts["mutual_info"] = round(m_pts, 2)

    # 3. p-value (15 pts)
    p_pts = 15.0 if pp < 0.01 else 10.0 if pp < 0.05 else 5.0 if pp < 0.10 else 0.0
    sc += p_pts
    parts["p_value"] = round(p_pts, 2)

    # 4. Sample size (10 pts)
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

    # 5. Time Stability (20 pts)
    tl = stab.get("stability", "N/A")
    t_pts = (
        20.0
        if tl == "STABLE"
        else 12.0
        if tl == "MODERATE"
        else 0.0
        if tl == "SIGN_FLIP"
        else 4.0
    )
    sc += t_pts
    parts["time_stability"] = round(t_pts, 2)

    # 6. Regime Stability (20 pts)
    rv = regime.get("regime_variance")
    rc_ = regime.get("avg_correlation")
    if rv is not None and rc_ is not None:
        r_pts = max(
            0.0, 20.0 - min(10.0, rv * 1000) - (5.0 if abs(rc_) < 0.05 else 0.0)
        )
    else:
        r_pts = 0.0
    sc += r_pts
    parts["regime_stability"] = round(r_pts, 2)

    # Decay penalties
    dt = decay.get("decay_type", "")
    notes = []
    if dt == "SIGNAL_REVERSAL":
        sc = max(0, sc - 15)
        notes.append("Signal reversal penalty: -15")
    elif dt == "ALPHA_DECAY":
        sc = max(0, sc - 8)
        notes.append("Alpha decay penalty: -8")

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

    return {
        "feature_quality_score": fs,
        "grade": gr,
        "pearson_r": round(pr, 4) if pr is not None else None,
        "p_value": round(pp, 4) if pp is not None else None,
        "n": n,
        "parts": parts,
        "notes": notes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────


def classify_repaired(score: float, stab: dict, decay: dict, regime: dict) -> tuple:
    """
    Returns (classification, reason).
    PROMOTED / WATCHLIST / REJECTED
    """
    tl = stab.get("stability", "UNKNOWN")
    dt = decay.get("decay_type", "")
    rv = regime.get("regime_variance") or 999
    sc_ok = regime.get("sign_consistent", False)

    if dt == "SIGNAL_REVERSAL":
        return (
            "REJECTED",
            "Signal reversal persists after repair — IC still crosses zero across horizons",
        )
    if score >= PROMOTE_MIN_SCORE and tl in STABLE_LABELS and sc_ok:
        return (
            "PROMOTED",
            f"Score {score}/100 | Stability: {tl} | Regime-consistent | Cleared for V7.3",
        )
    if score >= PROMOTE_MIN_SCORE and tl in STABLE_LABELS:
        return (
            "WATCHLIST",
            f"Score {score}/100 | Stability: {tl} but regime sign inconsistency detected",
        )
    if score >= WATCHLIST_MIN_SCORE:
        return (
            "WATCHLIST",
            f"Score {score}/100 — partial repair success, needs further validation",
        )
    return (
        "REJECTED",
        f"Score {score}/100 — repair insufficient, remains below qualification threshold",
    )


# =============================================================================
# PHASE 5 — HEAD-TO-HEAD COMPARISON ENGINE
# Original vs Repaired across all audit dimensions
# =============================================================================


def phase5_compare(
    df: pd.DataFrame, original: str, repaired: str, target: str = "fwd_5d"
) -> dict:
    """
    Side-by-side comparison of every metric between original and repaired feature.
    """

    def _audit(feat):
        stab = phase2_stability_audit(df, feat, target)
        regime = phase3_regime_audit(df, feat, target)
        decay = phase4_decay_audit(df, feat)
        qsc = compute_quality_score(df, feat, stab, regime, decay, target)
        nan_r = _nan_rate(df, feat)
        fire = _fire_rate(df, feat)
        return {
            "stability": stab,
            "regime": regime,
            "decay": decay,
            "quality": qsc,
            "nan_rate": nan_r,
            "fire_info": fire,
        }

    orig_data = _audit(original) if original in df.columns else None
    rep_data = _audit(repaired) if repaired in df.columns else None

    delta_score = None
    if orig_data and rep_data:
        delta_score = round(
            rep_data["quality"]["feature_quality_score"]
            - orig_data["quality"]["feature_quality_score"],
            1,
        )

    return {
        "original": orig_data,
        "repaired": rep_data,
        "delta_score": delta_score,
    }


# =============================================================================
# FULL PIPELINE
# =============================================================================


def run_repair_lab() -> dict:
    print("=" * 70)
    print("  WEALTHQUANT V7.2.4 — FEATURE REPAIR LAB")
    print("=" * 70)

    # ── Phase 0 ────────────────────────────────────────────────────────────────
    print("\n[PHASE 0] Building market data (600 bars, seed=42)...")
    df = generate_market_data(n_bars=600, seed=42)

    # ── Phase 1 ────────────────────────────────────────────────────────────────
    print("\n[PHASE 1] Implementing all 6 repair protocols...")
    df = phase1_implement_repairs(df)
    repaired_cols = [m["repaired_name"] for m in REPAIR_REGISTRY.values()]
    avail = [c for c in repaired_cols if c in df.columns]
    print(f"         Repaired features computed: {len(avail)}/{len(repaired_cols)}")
    for orig, meta in REPAIR_REGISTRY.items():
        rn = meta["repaired_name"]
        fr_o = _fire_rate(df, orig)
        fr_r = _fire_rate(df, rn)
        if fr_o.get("type") == "BINARY":
            print(
                f"         {orig:20s} -> {rn:20s}  "
                f"(original fires: {fr_o.get('total_fires', 0)} bars, "
                f"repaired: {fr_r.get('total_fires', fr_r.get('total_fires', 0))} bars)"
            )

    # ── Phases 2-5 per pair ────────────────────────────────────────────────────
    print("\n[PHASES 2-4] Running Stability / Regime / Decay audits...")
    print("[PHASE  5] Comparing original vs repaired...")
    results = {}
    for orig, meta in REPAIR_REGISTRY.items():
        rn = meta["repaired_name"]
        print(f"  {orig:20s} vs {rn}...")
        comparison = phase5_compare(df, orig, rn)

        # Classification of repaired
        rep = comparison.get("repaired")
        if rep:
            cls, rsn = classify_repaired(
                rep["quality"]["feature_quality_score"],
                rep["stability"],
                rep["decay"],
                rep["regime"],
            )
        else:
            cls, rsn = "REJECTED", "Feature not computed"

        results[orig] = {
            "meta": meta,
            "repaired_name": rn,
            "comparison": comparison,
            "classification": cls,
            "reason": rsn,
        }

    return df, results


# =============================================================================
# REPORT GENERATION
# =============================================================================


def generate_repair_report(
    df: pd.DataFrame, results: dict, output_path: str = None
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

    # ── Title ──────────────────────────────────────────────────────────────────
    h("# FEATURE REPAIR REPORT")
    h("## WealthQuant V7.2.4 — Feature Repair Lab")
    h("")
    h(f"**Generated:** {ts}")
    h(
        "**Source Audits:** V7.2.2 Alpha Stability Audit + V7.2.3 Feature Failure Analysis"
    )
    h(f"**Pairs Evaluated:** {len(results)} (Original vs Repaired)")
    h("**Target Variable:** 5-Day Forward Return (fwd_5d)")
    h("**Scope:** Research only — no Ensemble or Meta-Learning modifications")
    hr()

    # ── Repair Queue Summary ───────────────────────────────────────────────────
    h("## REPAIR QUEUE")
    h("")
    row(
        "Original Feature",
        "Repaired Feature",
        "Repair Protocol",
        "Code",
        "V7.2.2 Score",
    )
    div(5)
    for orig, meta in REPAIR_REGISTRY.items():
        row(
            f"`{orig}`",
            f"`{meta['repaired_name']}`",
            meta["repair_protocol"],
            f"`{meta['repair_code']}`",
            meta["v722_score"],
        )
    hr()

    # ── Executive Classification ────────────────────────────────────────────────
    h("## EXECUTIVE CLASSIFICATION")
    h("")
    promoted = [o for o, d in results.items() if d["classification"] == "PROMOTED"]
    watchlist = [o for o, d in results.items() if d["classification"] == "WATCHLIST"]
    rejected = [o for o, d in results.items() if d["classification"] == "REJECTED"]

    row("Classification", "Count", "Features")
    div(3)
    row(
        "PROMOTED",
        len(promoted),
        ", ".join(f"`{r['repaired_name']}`" for o in promoted for r in [results[o]])
        or "None",
    )
    row(
        "WATCHLIST",
        len(watchlist),
        ", ".join(f"`{r['repaired_name']}`" for o in watchlist for r in [results[o]])
        or "None",
    )
    row(
        "REJECTED",
        len(rejected),
        ", ".join(f"`{r['repaired_name']}`" for o in rejected for r in [results[o]])
        or "None",
    )
    h("")
    row(
        "Feature",
        "Original Score",
        "Repaired Score",
        "Delta",
        "Stability",
        "Decay",
        "Classification",
    )
    div(7)
    for orig, d in results.items():
        rn = d["repaired_name"]
        comp = d["comparison"]
        orig_q = (
            comp["original"]["quality"]["feature_quality_score"]
            if comp.get("original")
            else "—"
        )
        rep_q = (
            comp["repaired"]["quality"]["feature_quality_score"]
            if comp.get("repaired")
            else "—"
        )
        delta = comp["delta_score"]
        stab = (
            comp["repaired"]["stability"]["stability"] if comp.get("repaired") else "—"
        )
        decay = comp["repaired"]["decay"]["decay_type"] if comp.get("repaired") else "—"
        cls = d["classification"]
        delta_str = (
            f"+{delta}" if isinstance(delta, float) and delta > 0 else str(delta)
        )
        cls_icon = (
            "PROMOTED"
            if cls == "PROMOTED"
            else "WATCHLIST"
            if cls == "WATCHLIST"
            else "REJECTED"
        )
        row(f"`{orig}` -> `{rn}`", orig_q, rep_q, delta_str, stab, decay, cls_icon)
    hr()

    # ── Phase 1 detail ─────────────────────────────────────────────────────────
    h("## PHASE 1 — REPAIR IMPLEMENTATIONS")
    h("")
    for orig, d in results.items():
        rn = d["repaired_name"]
        meta = d["meta"]
        comp = d["comparison"]
        h(f"### {orig} -> {rn}")
        h(
            f"**Category:** {meta['category']} | **Repair Code:** `{meta['repair_code']}`"
        )
        h(f"**Protocol:** {meta['repair_protocol']}")
        h(f"**Original failure:** {meta['v722_failure']}")
        rep_fr = comp["repaired"]["fire_info"] if comp.get("repaired") else {}
        orig_fr = comp["original"]["fire_info"] if comp.get("original") else {}
        if rep_fr.get("type") == "BINARY":
            h(
                f"**Signal frequency (original):** {orig_fr.get('total_fires', '—')} events "
                f"({orig_fr.get('fire_rate', 0) * 100:.1f}%)"
            )
            h(
                f"**Signal frequency (repaired):** {rep_fr.get('total_fires', '—')} events "
                f"({rep_fr.get('fire_rate', 0) * 100:.1f}%)"
            )
        h("")

    hr()

    # ── Phase 2 — Stability ─────────────────────────────────────────────────────
    h("## PHASE 2 — STABILITY AUDIT")
    h("")
    h("*Period A = bars 1–200 | Period B = 201–400 | Period C = 401–600*")
    h("")
    for orig, d in results.items():
        rn = d["repaired_name"]
        comp = d["comparison"]
        h(f"### {orig} vs {rn}")
        h("")
        row("Feature", "Per-A r", "Per-B r", "Per-C r", "Corr Std", "Stability")
        div(6)
        for label, key in [
            (f"`{orig}` (original)", "original"),
            (f"`{rn}` (repaired)", "repaired"),
        ]:
            data = comp.get(key)
            if data:
                s = data["stability"]
                cs = s.get("correlations", {})
                row(
                    label,
                    cs.get("Period_A", "—"),
                    cs.get("Period_B", "—"),
                    cs.get("Period_C", "—"),
                    s.get("corr_std", "—"),
                    s.get("stability", "—"),
                )
        h("")

    hr()

    # ── Phase 3 — Regime ────────────────────────────────────────────────────────
    h("## PHASE 3 — REGIME AUDIT")
    h("")
    h("*Pearson r against 5d forward return within each market regime.*")
    h("")
    for orig, d in results.items():
        rn = d["repaired_name"]
        comp = d["comparison"]
        h(f"### {orig} vs {rn}")
        h("")
        row(
            "Feature",
            "Bull",
            "Bear",
            "Sideways",
            "HighVol",
            "LowVol",
            "AvgCorr",
            "RegVar",
            "Sign Consistent?",
        )
        div(9)
        for label, key in [(f"`{orig}`", "original"), (f"`{rn}`", "repaired")]:
            data = comp.get(key)
            if data:
                reg = data["regime"]
                rgs = reg.get("regimes", {})

                def _r(regime):
                    return rgs.get(regime, {}).get("r", "—")

                row(
                    label,
                    _r("Bull"),
                    _r("Bear"),
                    _r("Sideways"),
                    _r("HighVol"),
                    _r("LowVol"),
                    reg.get("avg_correlation", "—"),
                    reg.get("regime_variance", "—"),
                    "YES" if reg.get("sign_consistent") else "NO",
                )
        h("")

    hr()

    # ── Phase 4 — Decay ─────────────────────────────────────────────────────────
    h("## PHASE 4 — DECAY AUDIT")
    h("")
    h("*Information Coefficient (Spearman r) at 5d / 10d / 20d / 30d / 60d / 90d.*")
    h("")
    for orig, d in results.items():
        rn = d["repaired_name"]
        comp = d["comparison"]
        h(f"### {orig} vs {rn}")
        h("")
        row(
            "Feature",
            "IC-5d",
            "IC-10d",
            "IC-20d",
            "IC-30d",
            "IC-60d",
            "IC-90d",
            "Max|IC|",
            "Decay Type",
        )
        div(9)
        for label, key in [(f"`{orig}`", "original"), (f"`{rn}`", "repaired")]:
            data = comp.get(key)
            if data:
                dec = data["decay"]
                ics = dec.get("ic_series", {})

                def _ic(h_):
                    return ics.get(h_, {}).get("IC", "—")

                row(
                    label,
                    _ic("5d"),
                    _ic("10d"),
                    _ic("20d"),
                    _ic("30d"),
                    _ic("60d"),
                    _ic("90d"),
                    dec.get("max_ic", "—"),
                    dec.get("decay_type", "—"),
                )
        h("")

    hr()

    # ── Phase 5 — Head-to-Head Comparison ──────────────────────────────────────
    h("## PHASE 5 — HEAD-TO-HEAD COMPARISON")
    h("")
    h(
        "**Scoring:** Corr(20) + MI(15) + p-val(15) + Sample(10) + TimeStab(20) + RegimeStab(20) = 100"
    )
    h("")
    for orig, d in results.items():
        rn = d["repaired_name"]
        comp = d["comparison"]
        cls = d["classification"]
        rsn = d["reason"]

        h(f"### {orig}  vs  {rn}")
        h("")
        row("Metric", f"`{orig}` (Original)", f"`{rn}` (Repaired)", "Delta", "Winner")
        div(5)

        def _compare_row(label, orig_val, rep_val, higher_is_better=True):
            try:
                ov = float(orig_val) if orig_val not in (None, "—") else None
                rv = float(rep_val) if rep_val not in (None, "—") else None
                if ov is None or rv is None:
                    row(label, orig_val, rep_val, "—", "—")
                    return
                delta = round(rv - ov, 4)
                if higher_is_better:
                    winner = (
                        f"`{rn}`" if rv > ov else (f"`{orig}`" if ov > rv else "TIE")
                    )
                else:
                    winner = (
                        f"`{rn}`" if rv < ov else (f"`{orig}`" if ov < rv else "TIE")
                    )
                row(
                    label,
                    round(ov, 4),
                    round(rv, 4),
                    f"+{delta}" if delta > 0 else str(delta),
                    winner,
                )
            except Exception:
                row(label, orig_val, rep_val, "—", "—")

        o_q = comp["original"]["quality"] if comp.get("original") else {}
        r_q = comp["repaired"]["quality"] if comp.get("repaired") else {}
        o_s = comp["original"]["stability"] if comp.get("original") else {}
        r_s = comp["repaired"]["stability"] if comp.get("repaired") else {}
        o_g = comp["original"]["regime"] if comp.get("original") else {}
        r_g = comp["repaired"]["regime"] if comp.get("repaired") else {}
        o_d = comp["original"]["decay"] if comp.get("original") else {}
        r_d = comp["repaired"]["decay"] if comp.get("repaired") else {}

        _compare_row(
            "Quality Score",
            o_q.get("feature_quality_score", "—"),
            r_q.get("feature_quality_score", "—"),
        )
        _compare_row(
            "Pearson r (global)", o_q.get("pearson_r", "—"), r_q.get("pearson_r", "—")
        )
        _compare_row(
            "Correlation pts",
            o_q.get("parts", {}).get("correlation", "—"),
            r_q.get("parts", {}).get("correlation", "—"),
        )
        _compare_row(
            "Mutual Info pts",
            o_q.get("parts", {}).get("mutual_info", "—"),
            r_q.get("parts", {}).get("mutual_info", "—"),
        )
        _compare_row(
            "p-value pts",
            o_q.get("parts", {}).get("p_value", "—"),
            r_q.get("parts", {}).get("p_value", "—"),
        )
        _compare_row(
            "Time Stab pts",
            o_q.get("parts", {}).get("time_stability", "—"),
            r_q.get("parts", {}).get("time_stability", "—"),
        )
        _compare_row(
            "Regime Stab pts",
            o_q.get("parts", {}).get("regime_stability", "—"),
            r_q.get("parts", {}).get("regime_stability", "—"),
        )
        _compare_row(
            "Corr Std (lower=better)",
            o_s.get("corr_std", "—"),
            r_s.get("corr_std", "—"),
            higher_is_better=False,
        )
        _compare_row(
            "Regime Variance (lower=better)",
            o_g.get("regime_variance", "—"),
            r_g.get("regime_variance", "—"),
            higher_is_better=False,
        )
        _compare_row("Max |IC|", o_d.get("max_ic", "—"), r_d.get("max_ic", "—"))

        h("")
        h(
            f"**Stability:** `{orig}` → {o_s.get('stability', '—')} | `{rn}` → {r_s.get('stability', '—')}"
        )
        h(
            f"**Decay:**     `{orig}` → {o_d.get('decay_type', '—')} | `{rn}` → {r_d.get('decay_type', '—')}"
        )
        h(f"**Delta Score:** {comp.get('delta_score', '—')}")
        h("")
        cls_icon = (
            "PROMOTED"
            if cls == "PROMOTED"
            else "WATCHLIST"
            if cls == "WATCHLIST"
            else "REJECTED"
        )
        h(f"> **VERDICT: {cls_icon}**")
        h(f"> {rsn}")
        h("")

    hr()

    # ── V7.3 Eligibility Summary ────────────────────────────────────────────────
    h("## V7.3 INTEGRATION ELIGIBILITY")
    h("")
    h("### Q1: Which repaired features survived?")
    h("")
    survivors = promoted + watchlist
    if survivors:
        h(f"**{len(survivors)} repaired features survive** (PROMOTED + WATCHLIST):")
        h("")
        row("Repaired Feature", "Score", "Stability", "Decay", "Status")
        div(5)
        for orig in survivors:
            d = results[orig]
            rn = d["repaired_name"]
            comp = d["comparison"]
            rep = comp.get("repaired", {})
            row(
                f"`{rn}`",
                rep.get("quality", {}).get("feature_quality_score", "—"),
                rep.get("stability", {}).get("stability", "—"),
                rep.get("decay", {}).get("decay_type", "—"),
                d["classification"],
            )
    else:
        h("*No repaired features survived the audit.*")
    h("")

    h("### Q2: Which remain unstable?")
    h("")
    unstable = [
        o
        for o in survivors
        if results[o]["comparison"]
        .get("repaired", {})
        .get("stability", {})
        .get("stability")
        == "SIGN_FLIP"
    ]
    unstable += rejected
    if unstable:
        h(f"**{len(unstable)} features remain unstable:**")
        h("")
        for orig in unstable:
            d = results[orig]
            rn = d["repaired_name"]
            comp = d["comparison"]
            rep = comp.get("repaired", {})
            stab = rep.get("stability", {}).get("stability", "—")
            decay = rep.get("decay", {}).get("decay_type", "—")
            h(f"- `{rn}` — Stability: {stab} | Decay: {decay} | {d['reason']}")
    else:
        h("*All repaired features achieved stability.*")
    h("")

    h("### Q3: Which repaired features qualify for V7.3?")
    h("")
    v73_eligible = [o for o, d in results.items() if d["classification"] == "PROMOTED"]
    if v73_eligible:
        h(
            f"**{len(v73_eligible)} repaired features qualify for V7.3 Market Structure Engine:**"
        )
        h("")
        row(
            "Repaired Feature",
            "Quality Score",
            "Category",
            "Time Stability",
            "Regime Var",
            "Decay Type",
        )
        div(6)
        for orig in v73_eligible:
            d = results[orig]
            rn = d["repaired_name"]
            meta = d["meta"]
            comp = d["comparison"]
            rep = comp.get("repaired", {})
            row(
                f"`{rn}`",
                rep.get("quality", {}).get("feature_quality_score", "—"),
                meta["category"],
                rep.get("stability", {}).get("stability", "—"),
                rep.get("regime", {}).get("regime_variance", "—"),
                rep.get("decay", {}).get("decay_type", "—"),
            )
    else:
        h("**No repaired features qualify for V7.3 in this audit cycle.**")
        h("")
        h("> Recommendation: Features on WATCHLIST should complete further validation")
        h("> on live market data before V7.3 integration.")
    hr()

    # ── Final Metrics Summary ──────────────────────────────────────────────────
    h("## AUDIT METRICS SUMMARY")
    h("")
    row("Metric", "Value")
    div(2)
    row("Total Repair Pairs Evaluated", len(results))
    row("PROMOTED (V7.3 Eligible)", len(promoted))
    row("WATCHLIST (Needs Monitoring)", len(watchlist))
    row("REJECTED (Repair Failed)", len(rejected))
    avg_delta = round(
        np.mean(
            [
                d["comparison"]["delta_score"]
                for d in results.values()
                if d["comparison"].get("delta_score") is not None
            ]
        ),
        1,
    )
    row("Average Score Improvement", f"+{avg_delta}")
    best_pair = max(
        results.items(), key=lambda x: x[1]["comparison"].get("delta_score") or -999
    )
    row(
        "Best Repair",
        f"`{best_pair[0]}` -> `{best_pair[1]['repaired_name']}` "
        f"(delta +{best_pair[1]['comparison']['delta_score']})",
    )
    h("")
    h("> **RULE: ONLY PROMOTED features may enter V7.3 Market Structure Engine.**")
    h("> **WATCHLIST features require additional live-data validation.**")
    hr()
    h("*WealthQuant V7.2.4 Feature Repair Lab — generated by `feature_repair_lab.py`*")
    h("")

    report = "\n".join(L)
    if output_path is None:
        output_path = Path(__file__).parent / "FEATURE_REPAIR_REPORT.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n[REPORT] Written to: {output_path}")
    return report


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    df, results = run_repair_lab()
    generate_repair_report(df, results)

    # ── Console Summary ────────────────────────────────────────────────────────
    promoted = [o for o, d in results.items() if d["classification"] == "PROMOTED"]
    watchlist = [o for o, d in results.items() if d["classification"] == "WATCHLIST"]
    rejected = [o for o, d in results.items() if d["classification"] == "REJECTED"]

    print("\n" + "=" * 70)
    print("  REPAIR LAB COMPLETE")
    print("=" * 70)
    for orig, d in results.items():
        rn = d["repaired_name"]
        comp = d["comparison"]
        orig_s = (
            comp["original"]["quality"]["feature_quality_score"]
            if comp.get("original")
            else "?"
        )
        rep_s = (
            comp["repaired"]["quality"]["feature_quality_score"]
            if comp.get("repaired")
            else "?"
        )
        delta = comp.get("delta_score")
        delta_str = (
            f"+{delta}" if isinstance(delta, float) and delta > 0 else str(delta)
        )
        cls = d["classification"]
        print(
            f"  {orig:20s} -> {rn:22s}  "
            f"{str(orig_s):>6} -> {str(rep_s):>6}  ({delta_str:>6})  [{cls}]"
        )

    print(f"\n  PROMOTED  : {len(promoted)}")
    print(f"  WATCHLIST : {len(watchlist)}")
    print(f"  REJECTED  : {len(rejected)}")
    print("\n  Output    : FEATURE_REPAIR_REPORT.md")
    print("=" * 70)
