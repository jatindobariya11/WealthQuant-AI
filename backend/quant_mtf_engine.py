import time
from datetime import datetime

import numpy as np
import pandas as pd

import yfinance as yf
from base_indicators import calc_atr_raw, calc_rsi, calc_vwap, horizon_return, safe
from constants import SYM_MAP


def ema_s(series, length):
    return series.ewm(span=length, adjust=False).mean()


def fetch_tf(symbol, interval, period, ema_len=50):
    """Fetches data with automatic symbol mapping for indices."""
    try:
        # Map indices to Yahoo Finance tickers
        yf_sym = SYM_MAP.get(symbol.upper(), symbol)

        df = yf.download(
            yf_sym,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
            timeout=8,
        )
        if df.empty or len(df) < ema_len + 5:
            return None
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df = df.loc[:, ~df.columns.duplicated()]
        df = df.loc[~df.index.duplicated(keep="last")]
        df["EMA"] = ema_s(df["Close"], ema_len)
        return df
    except Exception as e:
        print(f"Error fetching {symbol} {interval}: {e}")
        return None


def fetch_weekly_from_daily(df_1d, ema_len=50):
    """Computes weekly by resampling daily data."""
    try:
        wk = (
            df_1d.resample("W")
            .agg(
                {
                    "Open": "first",
                    "High": "max",
                    "Low": "min",
                    "Close": "last",
                    "Volume": "sum",
                }
            )
            .dropna()
        )
        wk["EMA"] = ema_s(wk["Close"], ema_len)
        return wk if len(wk) > ema_len + 2 else None
    except:
        return None


def run_quant_mtf_engine(symbol, ema_len=50, rsi_len=14, risk_reward=2.0):
    """
    Main entry point for the Quant MTF Engine.
    Combines 15m, 1D, and resampled 1W data for a unified direction score.
    """
    # 1. Fetch multi-timeframe data
    df_15m = fetch_tf(symbol, "15m", "5d", ema_len)
    df_1d = fetch_tf(symbol, "1d", "2y", ema_len)

    if df_1d is None:
        return {"error": f"No data for {symbol}"}

    # 2. Resample Weekly for better reliability
    df_1w = fetch_weekly_from_daily(df_1d, ema_len)

    # Current Price Action (Daily)
    close = df_1d["Close"]
    price = safe(close.iloc[-1])

    # Basic Indicators
    ema_val = safe(ema_s(close, ema_len).iloc[-1])
    vwap_val = safe(calc_vwap(df_1d).iloc[-1])
    rsi_val = safe(calc_rsi(close, rsi_len).iloc[-1])
    atr_val = safe(calc_atr_raw(df_1d).iloc[-1])
    vol_avg = safe(df_1d["Volume"].rolling(20).mean().iloc[-1])
    vol_now = safe(df_1d["Volume"].iloc[-1])

    # MTF Status
    daily_close = safe(df_1d["Close"].iloc[-1])
    daily_ema = safe(df_1d["EMA"].iloc[-1])
    weekly_close = safe(df_1w["Close"].iloc[-1]) if df_1w is not None else None
    weekly_ema = safe(df_1w["EMA"].iloc[-1]) if df_1w is not None else None

    daily_bull = (daily_close > daily_ema) if (daily_close and daily_ema) else False
    daily_bear = (daily_close < daily_ema) if (daily_close and daily_ema) else False
    weekly_bull = (
        (weekly_close > weekly_ema) if (weekly_close and weekly_ema) else False
    )
    weekly_bear = (
        (weekly_close < weekly_ema) if (weekly_close and weekly_ema) else False
    )

    # Scoring Logic
    trend_bull = (
        (price > ema_val and price > vwap_val)
        if (price and ema_val and vwap_val)
        else False
    )
    trend_bear = (
        (price < ema_val and price < vwap_val)
        if (price and ema_val and vwap_val)
        else False
    )
    mom_bull = (rsi_val > 50) if rsi_val else False
    mom_bear = (rsi_val < 50) if rsi_val else False
    vol_spike = (vol_now > vol_avg * 1.5) if (vol_now and vol_avg) else False

    # Historical Performance Benchmarks
    ret_week = horizon_return(close, 5)
    ret_month = horizon_return(close, 21)
    ret_quarter = horizon_return(close, 63)
    ret_6month = horizon_return(close, 126)
    ret_year = horizon_return(close, 252)

    # Detailed Breakdown calculation
    score = 0.0
    breakdown = {}
    ct = 2 if trend_bull else (-2 if trend_bear else 0)
    score += ct
    breakdown["Current Trend"] = ct
    dt = 2 if daily_bull else (-2 if daily_bear else 0)
    score += dt
    breakdown["Daily Trend"] = dt
    wt = 2 if weekly_bull else (-2 if weekly_bear else 0)
    score += wt
    breakdown["Weekly Trend"] = wt
    mo = 1 if mom_bull else (-1 if mom_bear else 0)
    score += mo
    breakdown["Momentum (RSI)"] = mo

    for lbl, ret in [
        ("1-Week", ret_week),
        ("1-Month", ret_month),
        ("3-Month", ret_quarter),
        ("6-Month", ret_6month),
        ("1-Year", ret_year),
    ]:
        if ret is not None:
            pts = 1 if ret > 0 else -1
            score += pts
            breakdown[lbl] = pts
        else:
            breakdown[lbl] = None

    vs = 1 if vol_spike else 0
    score += vs
    breakdown["Volume Spike"] = vs

    max_score = 14.0
    confidence = (
        max(-1.0, min(1.0, round(score / max_score, 4))) if not np.isnan(score) else 0.0
    )

    if confidence >= 0.75:
        signal = "STRONG BUY"
    elif confidence >= 0.40:
        signal = "BUY"
    elif confidence <= -0.75:
        signal = "STRONG SELL"
    elif confidence <= -0.40:
        signal = "SELL"
    else:
        signal = "NEUTRAL"

    # Strategy Params
    long_sl = round(price - atr_val, 2) if atr_val else None
    long_tp = round(price + atr_val * risk_reward, 2) if atr_val else None
    short_sl = round(price + atr_val, 2) if atr_val else None
    short_tp = round(price - atr_val * risk_reward, 2) if atr_val else None

    # Chart Records Generation
    chart_df = df_1d.copy()
    chart_df["RSI"] = calc_rsi(close, rsi_len)
    chart_df["EMA_50"] = ema_s(close, ema_len)
    chart_df["VWAP"] = calc_vwap(df_1d)
    chart_df["Vol_Avg"] = df_1d["Volume"].rolling(20).mean()
    chart_df = chart_df.tail(60)
    try:
        chart_df.index = chart_df.index.tz_localize(None).strftime("%Y-%m-%d")
    except TypeError:
        chart_df.index = chart_df.index.tz_convert(None).strftime("%Y-%m-%d")
    chart = []
    for row in (
        chart_df.reset_index().rename(columns={"index": "Date"}).to_dict("records")
    ):
        chart.append({k: (str(v) if k == "Date" else safe(v)) for k, v in row.items()})

    return _sanitize_dict(
        {
            "symbol": symbol,
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M IST"),
            "signal": signal,
            "score": round(score, 2),
            "confidence": confidence,
            "confidence_pct": round(confidence * 100, 1),
            "max_score": max_score,
            "indicators": {
                "price": price,
                "ema": ema_val,
                "vwap": vwap_val,
                "rsi": safe(rsi_val),
                "atr": atr_val,
                "volume_spike": vol_spike,
            },
            "mtf": {
                "daily_bullish": daily_bull,
                "weekly_bullish": weekly_bull,
            },
            "returns": {
                "1w": ret_week,
                "1m": ret_month,
                "3m": ret_quarter,
                "6m": ret_6month,
                "1y": ret_year,
            },
            "breakdown": breakdown,
            "trade": {
                "entry": price,
                "sl": long_sl if signal in ["BUY", "STRONG BUY"] else short_sl,
                "tp": long_tp if signal in ["BUY", "STRONG BUY"] else short_tp,
            },
            "chart": chart,
        }
    )


def _sanitize_dict(d):
    """Recursively replace NaN/Inf with None in a dict for JSON safety."""
    if isinstance(d, dict):
        return {k: _sanitize_dict(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_sanitize_dict(v) for v in d]
    if isinstance(d, float):
        if np.isnan(d) or np.isinf(d):
            return None
    return d


def scan_with_quant_engine(symbols, ema_len=50, rsi_len=14, rr=2.0):
    results = []
    for sym in symbols:
        try:
            r = run_quant_mtf_engine(sym, ema_len, rsi_len, rr)
            if "error" not in r:
                results.append(
                    {
                        "symbol": sym,
                        "signal": r["signal"],
                        "score": safe(r["score"]),
                        "confidence": safe(r["confidence_pct"]),
                        "price": safe(r["indicators"]["price"]),
                        "ret_1m": safe(r["returns"]["1m"], 4),
                        "ret_1y": safe(r["returns"]["1y"], 4),
                    }
                )
        except:
            pass
        time.sleep(0.3)
    if not results:
        return pd.DataFrame()
    return (
        pd.DataFrame(results)
        .sort_values("score", ascending=False)
        .reset_index(drop=True)
    )
