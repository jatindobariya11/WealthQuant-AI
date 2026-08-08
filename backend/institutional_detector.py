"""
institutional_detector.py — Institutional Order Flow Detection Engine

Detects aggressive institutional execution by monitoring 1-minute bars for:
  1. Volume spikes > 500% of the 20-day average 1-minute volume
  2. Bid-Ask spread widening (proxied via High-Low range expansion > 2x average)

When BOTH conditions trigger simultaneously, an institution is aggressively
executing a large order (sweeping the order book).

The High-Low range proxy works because institutional sweeps consume multiple
price levels in the order book, causing the 1-min candle range to expand
well beyond its normal size.
"""

import traceback
from datetime import datetime

import cache
from cache import YF_LOCK

# ── Constants ──────────────────────────────────────────────
VOLUME_SPIKE_THRESHOLD = 5.0  # 500% of 20-day avg 1-min volume
RANGE_EXPANSION_THRESHOLD = 2.0  # 2x the avg 1-min high-low range
LOOKBACK_DAYS = 5  # yfinance only keeps 7d of 1m data
AVG_WINDOW = 20  # 20-period rolling average for volume and range
ALERT_LOOKBACK_HOURS = 72  # Show alerts from last 72 hours (covers weekends)
TTL_INSTITUTIONAL = 30  # Cache TTL in seconds

# Symbol mapping — reuse the one from data_fetcher for consistency
YFINANCE_MAP = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "FINNIFTY": "^CNXFIN",
    "MIDCPNIFTY": "^NSEMDCP50",
    "SENSEX": "^BSESN",
}

US_TICKERS = {
    "TSLA",
    "AAPL",
    "MSFT",
    "GOOG",
    "AMD",
    "NVDA",
    "AMZN",
    "META",
    "NFLX",
    "QQQ",
    "SPY",
}


def _to_yf_symbol(symbol: str) -> str:
    """Convert internal symbol to yfinance ticker."""
    s = symbol.upper()
    if s in YFINANCE_MAP:
        return YFINANCE_MAP[s]
    if s in US_TICKERS:
        return s
    if not s.endswith(".NS") and "^" not in s:
        return s + ".NS"
    return s


def compute_aggressor_side(open_: float, high: float, low: float, close: float) -> dict:
    """
    Determine the aggressor side from candle anatomy.

    If close > midpoint → buyer is the aggressor (institution buying)
    If close < midpoint → seller is the aggressor (institution selling)

    Returns dict with 'side' ('BUY' or 'SELL') and 'strength' (0.0 to 1.0).
    """
    range_ = high - low
    if range_ <= 0:
        return {"side": "NEUTRAL", "strength": 0.0}

    midpoint = (high + low) / 2.0
    # How far close is from the midpoint, normalized to half-range
    deviation = (close - midpoint) / (range_ / 2.0)
    # Clamp to [-1, 1]
    deviation = max(-1.0, min(1.0, deviation))

    if deviation > 0.1:
        side = "BUY"
        strength = round(abs(deviation), 2)
    elif deviation < -0.1:
        side = "SELL"
        strength = round(abs(deviation), 2)
    else:
        side = "NEUTRAL"
        strength = 0.0

    return {"side": side, "strength": strength}


def detect_institutional_activity(symbol: str) -> dict:
    """
    Scan 1-minute bars for institutional activity.

    Downloads 1m OHLCV data from yfinance (last 5 days, the max available
    for 1m interval), then:
      1. Computes 20-period rolling average of volume
      2. Computes 20-period rolling average of high-low range (spread proxy)
      3. Scans for bars where BOTH:
         - Volume > 500% of rolling average
         - High-Low range > 200% of rolling average
      4. Classifies each event as buyer/seller aggressor

    Returns:
        dict with 'active_alerts', 'total_events_24h', 'last_scan', etc.
    """
    import pandas as pd

    import yfinance as yf

    yf_symbol = _to_yf_symbol(symbol)

    try:
        with YF_LOCK:
            df = yf.download(
                yf_symbol,
                period=f"{LOOKBACK_DAYS}d",
                interval="1m",
                progress=False,
            )

        if df is None or df.empty:
            return _empty_response(symbol, "No 1-minute data available")

        # Flatten MultiIndex columns if present (yfinance sometimes returns MultiIndex)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Ensure we have required columns
        required = {"Open", "High", "Low", "Close", "Volume"}
        if not required.issubset(set(df.columns)):
            return _empty_response(
                symbol, f"Missing columns: {required - set(df.columns)}"
            )

        # Check if volume is reported — guard against MultiIndex residue returning a Series
        vol_series = df["Volume"]
        if isinstance(vol_series, pd.DataFrame):
            vol_series = vol_series.iloc[:, 0]
        vol_total = vol_series.sum(skipna=True)
        has_volume = bool(not pd.isna(vol_total) and float(vol_total) > 0)
        if has_volume:
            df = df[vol_series > 0].copy()

        if len(df) < AVG_WINDOW + 5:
            return _empty_response(symbol, "Insufficient data for analysis")

        # ── Compute rolling averages ──────────────────────────
        if has_volume:
            df["vol_ma"] = (
                df["Volume"].rolling(window=AVG_WINDOW, min_periods=AVG_WINDOW).mean()
            )
        else:
            df["vol_ma"] = 0.0

        df["range"] = df["High"] - df["Low"]
        df["range_ma"] = (
            df["range"].rolling(window=AVG_WINDOW, min_periods=AVG_WINDOW).mean()
        )

        # ── Compute ratios ────────────────────────────────────
        if has_volume:
            df["vol_ratio"] = df["Volume"] / df["vol_ma"]
        else:
            df["vol_ratio"] = 1.0

        df["range_ratio"] = df["range"] / df["range_ma"]

        # Drop NaN rows (first AVG_WINDOW rows won't have moving avg)
        if has_volume:
            df = df.dropna(subset=["vol_ratio", "range_ratio"])
        else:
            df = df.dropna(subset=["range_ratio"])

        if df.empty:
            return _empty_response(symbol, "Not enough bars after rolling computation")

        # ── Detect spikes ─────────────────────────────────────
        if has_volume:
            spike_mask = (df["vol_ratio"] >= VOLUME_SPIKE_THRESHOLD) & (
                df["range_ratio"] >= RANGE_EXPANSION_THRESHOLD
            )
        else:
            spike_mask = df["range_ratio"] >= RANGE_EXPANSION_THRESHOLD

        spike_bars = df[spike_mask].copy()

        # Filter to last 24 hours only
        now = pd.Timestamp.now(tz="UTC") if df.index.tz else pd.Timestamp.now()
        cutoff = now - pd.Timedelta(hours=ALERT_LOOKBACK_HOURS)
        spike_bars = spike_bars[spike_bars.index >= cutoff]

        # Build alert list
        alerts = []
        for ts, row in spike_bars.iterrows():
            aggressor = compute_aggressor_side(
                float(row["Open"]),
                float(row["High"]),
                float(row["Low"]),
                float(row["Close"]),
            )

            # Format timestamp for display
            try:
                ts_local = ts.tz_convert("Asia/Kolkata") if ts.tzinfo else ts
                time_str = ts_local.strftime("%H:%M")
                date_str = ts_local.strftime("%d %b %H:%M")
            except Exception:
                time_str = str(ts)[-8:-3]
                date_str = str(ts)

            # Determine strength label
            vol_r = float(row["vol_ratio"])
            if has_volume:
                strength = (
                    "EXTREME" if vol_r >= 10 else "STRONG" if vol_r >= 7 else "MODERATE"
                )
            else:
                range_r = float(row["range_ratio"])
                strength = (
                    "EXTREME"
                    if range_r >= 4.0
                    else "STRONG"
                    if range_r >= 3.0
                    else "MODERATE"
                )

            alerts.append(
                {
                    "timestamp": str(ts),
                    "time": time_str,
                    "date": date_str,
                    "price": round(float(row["Close"]), 2),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                    "volume_ratio": round(vol_r, 2),
                    "avg_volume": round(float(row["vol_ma"]), 0),
                    "range_value": round(float(row["range"]), 2),
                    "range_ratio": round(float(row["range_ratio"]), 2),
                    "aggressor": aggressor["side"],
                    "aggressor_strength": aggressor["strength"],
                    "strength": strength,
                }
            )

        # Sort by timestamp descending (newest first)
        alerts.sort(key=lambda x: x["timestamp"], reverse=True)

        # Summary stats
        buy_count = sum(1 for a in alerts if a["aggressor"] == "BUY")
        sell_count = sum(1 for a in alerts if a["aggressor"] == "SELL")

        return {
            "symbol": symbol,
            "active_alerts": alerts,
            "total_events_24h": len(alerts),
            "buy_events": buy_count,
            "sell_events": sell_count,
            "net_bias": "BUY"
            if buy_count > sell_count
            else "SELL"
            if sell_count > buy_count
            else "NEUTRAL",
            "thresholds": {
                "volume_spike": f"{VOLUME_SPIKE_THRESHOLD}x",
                "range_expansion": f"{RANGE_EXPANSION_THRESHOLD}x",
            },
            "last_scan": datetime.utcnow().isoformat() + "Z",
            "data_bars_analyzed": len(df),
        }

    except Exception as e:
        print(f"[InstitutionalDetector] Error for {symbol}: {e}")
        traceback.print_exc()
        return _empty_response(symbol, str(e))


def _empty_response(symbol: str, reason: str = "") -> dict:
    """Return a clean empty response when no data or error."""
    return {
        "symbol": symbol,
        "active_alerts": [],
        "total_events_24h": 0,
        "buy_events": 0,
        "sell_events": 0,
        "net_bias": "NEUTRAL",
        "thresholds": {
            "volume_spike": f"{VOLUME_SPIKE_THRESHOLD}x",
            "range_expansion": f"{RANGE_EXPANSION_THRESHOLD}x",
        },
        "last_scan": datetime.utcnow().isoformat() + "Z",
        "data_bars_analyzed": 0,
        "note": reason,
    }


def get_institutional_alerts(symbol: str) -> dict:
    """
    Cached wrapper around detect_institutional_activity.
    Returns institutional alerts for a given symbol.
    """
    cache_key = f"institutional:{symbol.upper()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = detect_institutional_activity(symbol.upper())
    cache.put(cache_key, result, TTL_INSTITUTIONAL)
    return result


def scan_institutional_all(symbols: list | None = None) -> dict:
    """
    Scan multiple symbols for institutional activity.
    Returns a summary with alerts per symbol.
    """
    if symbols is None:
        symbols = list(YFINANCE_MAP.keys())

    results = {}
    total_alerts = 0

    for sym in symbols:
        try:
            data = get_institutional_alerts(sym)
            count = data.get("total_events_24h", 0)
            results[sym] = {
                "total_events": count,
                "net_bias": data.get("net_bias", "NEUTRAL"),
                "latest_alert": data["active_alerts"][0]
                if data["active_alerts"]
                else None,
            }
            total_alerts += count
        except Exception as e:
            results[sym] = {"total_events": 0, "net_bias": "NEUTRAL", "error": str(e)}

    return {
        "scan_results": results,
        "total_alerts_all": total_alerts,
        "symbols_scanned": len(symbols),
        "last_scan": datetime.utcnow().isoformat() + "Z",
    }
