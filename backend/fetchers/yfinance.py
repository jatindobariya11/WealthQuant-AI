import pandas as pd

import cache as _cache
import yfinance as yf
from base_indicators import candle_pattern
from core.shared_features import *

from .config import *


def fetch_ohlc_and_indicators(symbol: str, interval: str) -> dict:
    """
    yfinance: OHLC candles + RSI + MACD + Bollinger + StochRSI +
              Supertrend + ATR + Volume + EMA9/21/50/200
    Cached for 30s to avoid duplicate downloads.
    """
    cache_key = f"ohlc_ind:{symbol.upper()}:{interval}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    yf_sym = YFINANCE_MAP.get(
        symbol.upper(), symbol + ".NS" if "." not in symbol else symbol
    )
    yf_int, yf_per = INTERVAL_MAP.get(interval, ("5m", "5d"))

    try:
        with _cache.get_symbol_yf_lock(symbol):
            try:
                df = yf.download(
                    yf_sym,
                    period=yf_per,
                    interval=yf_int,
                    progress=False,
                    auto_adjust=True,
                    timeout=12,
                )
            except Exception as download_err:
                logger.warning(
                    f"yf.download failed for {yf_sym}, falling back to Ticker.history: {download_err}"
                )
                ticker = yf.Ticker(yf_sym)
                df = ticker.history(period=yf_per, interval=yf_int, timeout=12)

        if df is None or df.empty:
            logger.warning(
                f"Empty dataframe from yfinance for {symbol}. Generating fallback candles."
            )
            df = _generate_fallback_df(symbol, interval)

        # FIX: Deduplicate index to prevent "cannot reindex on an axis with duplicate labels"
        df = df[~df.index.duplicated(keep="last")]

        # Flatten MultiIndex columns if present (yf 0.2.x fix)
        if isinstance(df.columns, pd.MultiIndex):
            # Find the level that contains 'Close'
            for i in range(df.columns.nlevels):
                if "Close" in df.columns.get_level_values(i):
                    df.columns = df.columns.get_level_values(i)
                    break
            else:
                df.columns = df.columns.get_level_values(-1)

        # FIX: Deduplicate columns to prevent duplicate column DataFrames
        df = df.loc[:, ~df.columns.duplicated(keep="first")]

        # Second dedup+sort after MultiIndex flatten — column flattening can reintroduce dups
        if df.index.duplicated().any():
            df = df[~df.index.duplicated(keep="last")]
        df = df.sort_index()

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        vol = df["Volume"]

        # Force convert to Series if they are DataFrames
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        if isinstance(high, pd.DataFrame):
            high = high.iloc[:, 0]
        if isinstance(low, pd.DataFrame):
            low = low.iloc[:, 0]
        if isinstance(vol, pd.DataFrame):
            vol = vol.iloc[:, 0]

        close = close.squeeze()
        high = high.squeeze()
        low = low.squeeze()
        vol = vol.squeeze()

        # ── Indicators ───────────────────────────────────────────
        rsi_series = compute_rsi(close)
        stoch_k, stoch_d = compute_stoch_rsi(close)
        macd_line, macd_sig, hist = compute_macd(close)

        # Force-fill NaN with forward fill before reading last value
        macd_line = macd_line.ffill()
        macd_sig = macd_sig.ffill()

        bb_upper, bb_mid, bb_lower = compute_bollinger_bands(close)
        atr_series = compute_atr(high, low, close)
        st_val, st_dir = _supertrend(df)

        ema9 = close.ewm(span=9, adjust=False).mean()
        ema21 = close.ewm(span=21, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        ema200 = close.ewm(span=200, adjust=False).mean()

        vol_ma20 = vol.rolling(20).mean().ffill()
        vol_ratio = (
            round(float(vol.iloc[-1] / vol_ma20.iloc[-1]), 2)
            if vol_ma20.iloc[-1] > 0
            else 1.0
        )

        # ── Candles (last 100) ───────────────────────────────────
        candles = []
        start = max(0, len(df) - 100)
        for i in range(start, len(df)):
            row = df.iloc[i]
            candles.append(
                {
                    "Datetime": df.index[i].strftime("%Y-%m-%d %H:%M:%S"),
                    "Open": round(float(row["Open"]), 2),
                    "High": round(float(row["High"]), 2),
                    "Low": round(float(row["Low"]), 2),
                    "Close": round(float(row["Close"]), 2),
                    "Volume": int(_safe(row["Volume"]) or 0),
                    "RSI": _safe(rsi_series.iloc[i]),
                    "MACD": _safe(macd_line.iloc[i]),
                    "MACD_Signal": _safe(macd_sig.iloc[i]),
                    "MACD_Hist": _safe(hist.iloc[i]),
                    "BB_Upper": _safe(bb_upper.iloc[i]),
                    "BB_Lower": _safe(bb_lower.iloc[i]),
                    "Stoch_K": _safe(stoch_k.iloc[i]),
                    "Stoch_D": _safe(stoch_d.iloc[i]),
                    "Supertrend": _safe(st_val.iloc[i]),
                    "Supertrend_Dir": int(st_dir.iloc[i]),
                    "EMA_9": _safe(ema9.iloc[i]),
                    "EMA_20": _safe(ema21.iloc[i]),
                    "EMA_50": _safe(ema50.iloc[i]),
                    "EMA_200": _safe(ema200.iloc[i]),
                    "ATR": _safe(atr_series.iloc[i]),
                }
            )

        ltp = round(float(close.iloc[-1]), 2)
        result = {
            "source": "yfinance",
            "ltp": ltp,
            "candles": candles,
            "market_overview": {
                "ltp": ltp,
                "change_pct": round(
                    float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100), 2
                )
                if len(close) >= 2
                else 0,
                "rsi": _safe(rsi_series.iloc[-1]),
                "stoch_k": _safe(stoch_k.iloc[-1]),
                "stoch_d": _safe(stoch_d.iloc[-1]),
                "macd": _safe(macd_line.iloc[-1]),
                "macd_signal": _safe(macd_sig.iloc[-1]),
                "macd_hist": _safe(hist.iloc[-1]),
                "bb_upper": _safe(bb_upper.iloc[-1]),
                "bb_lower": _safe(bb_lower.iloc[-1]),
                "bb_mid": _safe(bb_mid.iloc[-1]),
                "atr": _safe(atr_series.iloc[-1]),
                "ema9": _safe(ema9.iloc[-1]),
                "ema21": _safe(ema21.iloc[-1]),
                "ema50": _safe(ema50.iloc[-1]),
                "ema200": _safe(ema200.iloc[-1]),
                "supertrend": _safe(st_val.iloc[-1]),
                "supertrend_dir": int(st_dir.iloc[-1]),
                "volume": {
                    "current": int(_safe(vol.iloc[-1]) or 0),
                    "avg20": int(_safe(vol_ma20.iloc[-1]) or 0),
                    "ratio": vol_ratio,
                },
                "candle": candle_pattern(df),
            },
        }
        _cache.put(cache_key, result, 30)  # 30s cache
        return result

    except Exception as e:
        import traceback

        logger.error(
            f"yfinance fetch failed for {symbol}: {e}\n{traceback.format_exc()}"
        )
        return {"source": "yfinance", "error": str(e), "market_overview": {}}


def _yfinance_ltp(symbol: str) -> dict:
    """Safe yfinance LTP fetch with NaN and MultiIndex protection."""
    import pandas as pd

    try:
        ticker = YFINANCE_MAP.get(symbol.upper(), symbol + ".NS")
        h = yf.Ticker(ticker).history(period="5d", interval="1m")
        if h is None or h.empty:
            return {"source": "yfinance", "error": "Empty history"}
        # Flatten MultiIndex columns (yfinance >=0.2 returns ticker-keyed MultiIndex)
        if isinstance(h.columns, pd.MultiIndex):
            h.columns = h.columns.get_level_values(0)
        close = h["Close"].dropna()
        if close.empty:
            return {"source": "yfinance", "error": "No valid Close data"}
        return {"source": "yfinance", "ltp": round(float(close.iloc[-1]), 2)}
    except Exception as e:
        logger.warning(f"yfinance LTP fetch failed for {symbol}: {e}")
        return {"source": "yfinance", "error": str(e)}
