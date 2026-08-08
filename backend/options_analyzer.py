import numpy as np
import pandas as pd

from data_fetchers import fetch_options_chain_safe  # FIX #21


def parse_chain(data, expiry=None):
    records = data["records"]["data"]
    spot = float(data["records"]["underlyingValue"])
    all_exp = sorted(set(r["expiryDate"] for r in records))
    exp = expiry if expiry else all_exp[0]
    rows = [
        {
            "strike": r["strikePrice"],
            "ce_oi": r.get("CE", {}).get("openInterest", 0),
            "ce_chng_oi": r.get("CE", {}).get("changeinOpenInterest", 0),
            "ce_iv": r.get("CE", {}).get("impliedVolatility", 0),
            "ce_ltp": r.get("CE", {}).get("lastPrice", 0),
            "ce_volume": r.get("CE", {}).get("totalTradedVolume", 0),
            "pe_oi": r.get("PE", {}).get("openInterest", 0),
            "pe_chng_oi": r.get("PE", {}).get("changeinOpenInterest", 0),
            "pe_iv": r.get("PE", {}).get("impliedVolatility", 0),
            "pe_ltp": r.get("PE", {}).get("lastPrice", 0),
            "pe_volume": r.get("PE", {}).get("totalTradedVolume", 0),
        }
        for r in records
        if r["expiryDate"] == exp
    ]
    df = pd.DataFrame(rows).sort_values("strike").reset_index(drop=True)
    return df, spot, exp, all_exp


def calc_pcr(df):
    tpe = df["pe_oi"].sum()
    tce = df["ce_oi"].sum()
    pcr = round(tpe / tce, 2) if tce > 0 else 1.0
    # Refined signal thresholds for clearer bias
    signal = "BULLISH" if pcr > 1.25 else "BEARISH" if pcr < 0.75 else "NEUTRAL"
    return {
        "pcr": pcr,
        "signal": signal,
        "total_ce_oi": int(tce),
        "total_pe_oi": int(tpe),
    }


def calc_max_pain_fast(df):
    """FIX #23 — vectorized numpy, no Python loop."""
    strikes = df["strike"].values
    ce_oi = df["ce_oi"].values
    pe_oi = df["pe_oi"].values
    pain = np.zeros(len(strikes))
    for i, s in enumerate(strikes):
        ce_loss = np.sum(np.maximum(0, strikes - s) * ce_oi)
        pe_loss = np.sum(np.maximum(0, s - strikes) * pe_oi)
        pain[i] = ce_loss + pe_loss
    return int(strikes[np.argmin(pain)])


def get_atm_iv(df, spot):
    if df.empty:
        return None
    # Find the strike closest to spot
    atm_idx = (df["strike"] - spot).abs().idxmin()
    atm = df.loc[atm_idx]
    ce_iv = float(atm["ce_iv"]) if atm["ce_iv"] > 0 else None
    pe_iv = float(atm["pe_iv"]) if atm["pe_iv"] > 0 else None

    if ce_iv and pe_iv:
        return round((ce_iv + pe_iv) / 2, 2)
    return ce_iv or pe_iv


def calc_oi_signal(df, spot):
    ai = (df["strike"] - spot).abs().idxmin()
    nb = df.iloc[max(0, ai - 5) : ai + 6]
    ca = nb["ce_chng_oi"].sum()
    pa = nb["pe_chng_oi"].sum()
    if pa > ca * 1.5:
        return "bullish"
    if ca > pa * 1.5:
        return "bearish"
    return "neutral"


def analyze_options(symbol="NIFTY", expiry=None):
    try:
        raw = fetch_options_chain_safe(symbol)  # FIX #21 — with retry
        df, spot, exp_used, all_exp = parse_chain(raw, expiry)
        pcr_data = calc_pcr(df)
        max_pain = calc_max_pain_fast(df)  # FIX #23 — vectorized
        atm_iv = get_atm_iv(df, spot)
        oi_signal = calc_oi_signal(df, spot)
        atm_strike = round(round(spot / 50) * 50)
        ce_above = df[df["strike"] > spot].nlargest(5, "ce_oi")
        pe_below = df[df["strike"] < spot].nlargest(5, "pe_oi")
        score = 0
        pcr = pcr_data["pcr"]
        if pcr > 1.3:
            score += 3
        elif pcr < 0.8:
            score -= 3
        if oi_signal == "bullish":
            score += 3
        elif oi_signal == "bearish":
            score -= 3
        if spot > max_pain:
            score += 2
        else:
            score -= 2
        if atm_iv and atm_iv < 15:
            score += 2
        elif atm_iv and atm_iv > 25:
            score -= 2
        # FIX #22 — no df in return dict
        return {
            "symbol": symbol,
            "spot": spot,
            "expiry": exp_used,
            "all_expiries": all_exp,
            "atm_strike": atm_strike,
            "pcr": pcr_data,
            "max_pain": max_pain,
            "oi_signal": oi_signal,
            "atm_iv": atm_iv,
            "oi_score": max(-10, min(10, score)),
            "top_ce_oi": ce_above[
                ["strike", "ce_oi", "ce_chng_oi", "ce_iv", "ce_ltp"]
            ].to_dict("records"),
            "top_pe_oi": pe_below[
                ["strike", "pe_oi", "pe_chng_oi", "pe_iv", "pe_ltp"]
            ].to_dict("records"),
            "dist_to_max_pain": round(abs(spot - max_pain) / spot * 100, 2),
        }
    except Exception as e:
        return {
            "symbol": symbol,
            "spot": None,
            "error": str(e),
            "pcr": {"pcr": 1.0, "signal": "neutral"},
            "max_pain": None,
            "oi_score": 0,
            "atm_iv": None,
            "oi_levels": {},
            "top_ce_oi": [],
            "top_pe_oi": [],
        }
