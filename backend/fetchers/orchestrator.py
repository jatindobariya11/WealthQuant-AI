import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime

import numpy as np
import pandas as pd
import requests

import cache as C
import cache as _cache
import yfinance as yf
from base_indicators import safe
from core.shared_features import *

from .config import *


def fetch_global_data() -> dict:
    """yfinance: VIX, S&P500, NASDAQ, DXY, Dow, Asian/European indices, Crude, USD/INR, Gold. Cached 60s."""
    cached = _cache.get("global_data_v2")
    if cached is not None:
        return cached

    symbols = {
        "india_vix": "^INDIAVIX",
        "sp500": "^GSPC",
        "nasdaq": "^IXIC",
        "dxy": "DX-Y.NYB",
        "gift_nifty": "^NSEI",  # approximate — replace with GIFT NIFTY when available
        "dow_jones": "^DJI",
        "nikkei": "^N225",
        "hang_seng": "^HSI",
        "kospi": "^KS11",
        "dax": "^GDAXI",
        "ftse": "^FTSE",
        "brent_crude": "BZ=F",
        "usd_inr": "INR=X",
        "gold": "GC=F",
    }

    result = {}
    # Batch download all at once instead of 14 individual Ticker.history() calls
    try:
        tickers_str = " ".join(symbols.values())
        with _cache.YF_LOCK:
            all_df = yf.download(
                tickers_str,
                period="5d",
                interval="1d",
                progress=False,
                auto_adjust=True,
                group_by="ticker",
                timeout=15,
            )
        if not all_df.empty:
            all_df = all_df.loc[~all_df.index.duplicated(keep="last")]

        for key, sym in symbols.items():
            try:
                sub = pd.DataFrame()
                if isinstance(all_df.columns, pd.MultiIndex):
                    if sym in all_df.columns.get_level_values(0):
                        sub = all_df[sym]
                        # Flatten MultiIndex columns if still nested
                        if isinstance(sub.columns, pd.MultiIndex):
                            sub.columns = sub.columns.get_level_values(-1)
                        sub = sub.dropna(subset=["Close"])
                if sub.empty or len(sub) < 2:
                    result[key] = None
                    continue
                if isinstance(sub.columns, pd.MultiIndex):
                    sub.columns = sub.columns.get_level_values(-1)
                prev = float(sub["Close"].iloc[-2])
                curr = float(sub["Close"].iloc[-1])
                chg = round(curr - prev, 2)
                chg_pct = round((chg / prev) * 100, 2)
                result[key] = {"value": round(curr, 2), "chg": chg, "chg_pct": chg_pct}
            except Exception as e:
                logger.warning(f"Global parse failed for {key}: {e}")
                result[key] = None
    except Exception as e:
        logger.warning(f"Global batch download failed: {e}")
        for key in symbols:
            result[key] = None

    # VIX regime
    vix_data = result.get("india_vix") or {}
    vix_val = vix_data.get("value", 0) or 0
    regime = "extreme_fear" if vix_val > 25 else "fear" if vix_val > 18 else "calm"

    out = {
        "vix": {**(result.get("india_vix") or {}), "regime": regime}
        if result.get("india_vix")
        else None,
        "global": {
            "sp500": result.get("sp500"),
            "nasdaq": result.get("nasdaq"),
            "dxy": result.get("dxy"),
            "gift_nifty": result.get("gift_nifty"),
            "dow_jones": result.get("dow_jones"),
            "nikkei": result.get("nikkei"),
            "hang_seng": result.get("hang_seng"),
            "kospi": result.get("kospi"),
            "dax": result.get("dax"),
            "ftse": result.get("ftse"),
            "brent_crude": result.get("brent_crude"),
            "usd_inr": result.get("usd_inr"),
            "gold": result.get("gold"),
        },
    }
    _cache.put("global_data_v2", out, _cache.TTL_GLOBAL)
    return out


def fetch_quant_mtf(symbol: str) -> dict:
    """
    Multi-timeframe returns + daily/weekly EMA alignment. Cached 60s.
    """
    cache_key = f"quant_mtf_fetcher:{symbol.upper()}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    yf_sym = YFINANCE_MAP.get(symbol.upper(), symbol + ".NS")

    try:
        # Daily data for returns + daily MTF
        with _cache.YF_LOCK:
            df_daily = yf.download(
                yf_sym,
                period="1y",
                interval="1d",
                progress=False,
                auto_adjust=True,
                timeout=10,
            )
        if df_daily.empty:
            return {"error": "Empty data", "confidence_pct": 0, "mtf": {}}

        # Flatten MultiIndex columns if present
        if isinstance(df_daily.columns, pd.MultiIndex):
            for i in range(df_daily.columns.nlevels):
                if "Close" in df_daily.columns.get_level_values(i):
                    df_daily.columns = df_daily.columns.get_level_values(i)
                    break
            else:
                df_daily.columns = df_daily.columns.get_level_values(0)

        # Force squeeze and select first column if DataFrame
        close = df_daily["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        close = close.squeeze().ffill()

        # Indicators for scoring
        from base_indicators import calc_rsi, horizon_return

        rsi_val = calc_rsi(close).iloc[-1] if len(close) >= 14 else 50.0

        returns = {
            "1w": horizon_return(close, 5),
            "1m": horizon_return(close, 21),
            "3m": horizon_return(close, 63),
            "6m": horizon_return(close, 126),
            "1y": horizon_return(close, 252),
        }

        positive = sum(1 for v in returns.values() if v is not None and v > 0)
        total = sum(1 for v in returns.values() if v is not None)
        conf_pct = round(positive / total * 100, 1) if total > 0 else 0

        # Daily EMA alignment
        ema9_d = close.ewm(span=9, adjust=False).mean()
        ema21_d = close.ewm(span=21, adjust=False).mean()
        daily_bullish = bool(
            float(close.iloc[-1]) > float(ema9_d.iloc[-1]) > float(ema21_d.iloc[-1])
        )
        daily_bearish = bool(
            float(close.iloc[-1]) < float(ema9_d.iloc[-1]) < float(ema21_d.iloc[-1])
        )

        # Weekly EMA alignment
        weekly_bullish = False
        weekly_bearish = False
        try:
            with _cache.YF_LOCK:
                df_weekly = yf.download(
                    yf_sym,
                    period="6mo",
                    interval="1wk",
                    progress=False,
                    auto_adjust=True,
                    timeout=8,
                )
            if not df_weekly.empty:
                if isinstance(df_weekly.columns, pd.MultiIndex):
                    for i in range(df_weekly.columns.nlevels):
                        if "Close" in df_weekly.columns.get_level_values(i):
                            df_weekly.columns = df_weekly.columns.get_level_values(i)
                            break
                    else:
                        df_weekly.columns = df_weekly.columns.get_level_values(0)

                wc = df_weekly["Close"]
                if isinstance(wc, pd.DataFrame):
                    wc = wc.iloc[:, 0]
                wc = wc.squeeze().ffill()

                we9 = wc.ewm(span=9, adjust=False).mean()
                we21 = wc.ewm(span=21, adjust=False).mean()
                weekly_bullish = bool(
                    float(wc.iloc[-1]) > float(we9.iloc[-1]) > float(we21.iloc[-1])
                )
                weekly_bearish = bool(
                    float(wc.iloc[-1]) < float(we9.iloc[-1]) < float(we21.iloc[-1])
                )
        except Exception as e:
            logger.warning(f"Weekly MTF failed for {symbol}: {e}")

        # Compute multi-timeframe quantitative scoring and signal mapping
        score = 0.0
        score += 2.0 if daily_bullish else (-2.0 if daily_bearish else 0.0)
        score += 2.0 if weekly_bullish else (-2.0 if weekly_bearish else 0.0)
        score += (
            1.0
            if (rsi_val and rsi_val > 50)
            else (-1.0 if (rsi_val and rsi_val < 50) else 0.0)
        )
        for ret in returns.values():
            if ret is not None:
                score += 1.0 if ret > 0 else -1.0

        max_score = 9.0
        confidence = (
            max(-1.0, min(1.0, round(score / max_score, 4)))
            if not np.isnan(score)
            else 0.0
        )
        confidence_pct = round(confidence * 100, 1)

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

        result = {
            "source": "yfinance",
            "signal": signal,
            "score": score,
            "confidence": confidence,
            "confidence_pct": confidence_pct,
            "returns": returns,
            "mtf": {
                "daily_bullish": daily_bullish,
                "weekly_bullish": weekly_bullish,
                "aligned": daily_bullish and weekly_bullish,
            },
        }
        _cache.put(cache_key, result, _cache.TTL_QUANT)
        return result
    except Exception as e:
        logger.error(f"quant_mtf failed for {symbol}: {e}")
        return {"error": str(e), "confidence_pct": None, "mtf": {}}


def fetch_live_ltp(symbol: str) -> dict:
    """
    Get live LTP for an index from NSE.
    """
    index_name = NSE_INDEX_MAP.get(symbol.upper(), symbol)
    try:
        data = _nse_get("https://www.nseindia.com/api/allIndices")
        indices = data.get("data", [])

        for idx in indices:
            name = idx.get("indexSymbol", "") or idx.get("index", "")
            if name.upper() == index_name.upper():
                ltp = idx.get("last") or idx.get("ltp")
                prev_close = idx.get("previousClose") or idx.get("previousDay")
                open_ = idx.get("open")
                high_ = idx.get("high")
                low_ = idx.get("low")
                chg = idx.get("change") or idx.get("netChange")
                chg_pct = idx.get("percentChange") or idx.get("pChange")
                return {
                    "source": "nse",
                    "symbol": symbol,
                    "ltp": float(ltp) if ltp else None,
                    "prev_close": float(prev_close) if prev_close else None,
                    "open": float(open_) if open_ else None,
                    "high": float(high_) if high_ else None,
                    "low": float(low_) if low_ else None,
                    "chg": float(chg) if chg else None,
                    "chg_pct": float(chg_pct) if chg_pct else None,
                }
    except Exception as e:
        logger.warning(f"NSE LTP fetch failed for {symbol}: {e}")
        return {"source": "nse", "error": str(e)}

    return {"source": "nse", "error": f"Index '{index_name}' not found"}


def get_ltp_with_fallback(symbol: str) -> dict:
    """
    LTP priority: TrueData → Breeze → NSE scraper → yfinance
    Returns first successful result. Skips unconfigured sources.
    Cached 10s to avoid hammering sources.
    """
    cache_key = f"ltp_fallback:{symbol.upper()}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    sources = []
    # Only attempt sources that are actually configured
    if TRUEDATA_USER:
        sources.append(("truedata", lambda: fetch_truedata_ltp(symbol)))
    if BREEZE_API_KEY:
        sources.append(("breeze", lambda: fetch_breeze_ltp(symbol)))
    # NSE scraper — always available but can be slow
    sources.append(("nse", lambda: fetch_live_ltp(symbol)))
    # yfinance — always available, reliable fallback
    sources.append(("yfinance", lambda: _yfinance_ltp(symbol)))

    for name, fn in sources:
        try:
            result = fn()
            if "error" not in result and result.get("ltp"):
                logger.info(f"LTP from {name}: {result['ltp']}")
                _cache.put(cache_key, result, 10)  # 10s TTL for LTP
                return result
        except Exception as e:
            logger.warning(f"LTP source {name} failed: {e}")
    return {"source": "none", "ltp": None, "error": "All LTP sources failed"}


def get_ohlc_with_fallback(symbol: str, interval: str) -> dict:
    """
    OHLC priority: TrueData → Breeze → yfinance
    """
    sources = [
        ("truedata", lambda: fetch_truedata_ohlc(symbol, interval)),
        ("breeze", lambda: fetch_breeze_ohlc(symbol, interval)),
        ("yfinance", lambda: fetch_ohlc_and_indicators(symbol, interval)),
    ]
    for name, fn in sources:
        try:
            result = fn()
            if "error" not in result and result.get("candles"):
                logger.info(f"OHLC from {name}: {len(result['candles'])} candles")
                return result
        except Exception as e:
            logger.warning(f"OHLC source {name} failed: {e}")
    return {"source": "none", "candles": [], "error": "All OHLC sources failed"}


def get_all_data(symbol: str, interval: str = "5m") -> dict:
    """
    Master function — fetches ALL data from all sources.
    Called by your FastAPI endpoint:
        data = get_all_data("NIFTY", "5m")

    Returns full WealthQuant response dict.
    """
    from data_fetchers import get_multi_tf

    fetched_at = {}
    results = {}

    futures = {
        "ohlc": _EXECUTOR.submit(fetch_ohlc_and_indicators, symbol, interval),
        "ltp": _EXECUTOR.submit(get_ltp_with_fallback, symbol),
        "global": _EXECUTOR.submit(fetch_global_data),
        "opts": _EXECUTOR.submit(fetch_options_chain, symbol),
        "fii": _EXECUTOR.submit(fetch_fii_dii),
        "adv": _EXECUTOR.submit(fetch_market_breadth_unified),
        "quant": _EXECUTOR.submit(fetch_quant_mtf, symbol),
        "multitf": _EXECUTOR.submit(get_multi_tf, symbol),
    }

    # Wait for all futures with a GLOBAL timeout — keep well under frontend 15s limit
    done, not_done = wait(futures.values(), timeout=10)

    for key, fut in futures.items():
        t0 = time.time()
        if fut in done:
            try:
                results[key] = fut.result()
            except Exception as e:
                logger.warning(f"Task {key} failed: {e}")
                results[key] = {}
        else:
            logger.warning(f"Task {key} timed out (global 10s limit) — using fallback")
            results[key] = {}
            fut.cancel()  # Try to stop it
        fetched_at[key] = round(time.time() - t0, 2)

    # Extract for convenience
    ohlc = results.get("ohlc", {})
    ltp = results.get("ltp", {})
    global_data = results.get("global", {})
    opts = results.get("opts", {})
    fii = results.get("fii", {})
    adv = results.get("adv", {})
    quant = results.get("quant", {})
    multitf = results.get("multitf", {})

    # Define live_ltp early so it can be used for Options max_pain fallback calculation
    mo = ohlc.get("market_overview", {})
    live_ltp = ltp.get("ltp")
    if not live_ltp and mo.get("ltp"):
        live_ltp = mo["ltp"]
        logger.info(f"Using OHLC fallback price: {live_ltp}")

    if live_ltp:
        ltp["ltp"] = live_ltp
        mo["ltp"] = live_ltp

    # Options fallback if fetch failed
    if not opts or "error" in opts:
        opts = {
            "error": opts.get(
                "error",
                "Options chain data is currently unavailable. No live data available.",
            )
            if isinstance(opts, dict)
            else "Options chain data is currently unavailable. No live data available.",
            "source": "fallback_error",
            "oi_score": None,
            "pcr": None,
            "oi_signal": None,
            "max_pain": None,
            "atm_iv": None,
        }

    greeks = {}
    if TRUEDATA_USER and opts.get("expiry"):
        try:
            greeks = fetch_truedata_option_greeks(symbol, expiry=opts.get("expiry"))
        except Exception as e:
            logger.warning(f"Greeks fetch failed: {e}")

    # ── Build final response ─────────────────────────────────────
    response = {
        "meta": {
            "symbol": symbol,
            "interval": interval,
            "generated_at": datetime.now().isoformat(),
            "fetched_at": fetched_at,
            "data_sources": {
                "ohlc": ohlc.get("source", "yfinance"),
                "ltp": ltp.get("source", "unknown"),
                "options": opts.get("source", "nse"),
                "fii_dii": fii.get("source", "nse"),
            },
        },
        "ltp": ltp.get("ltp"),
        "candles": ohlc.get("candles", []),
        "market_overview": mo,
        "vix": global_data.get("vix"),
        "global": global_data.get("global"),
        "options": opts,
        "fii_dii": fii,
        "adv_dec": adv,
        "quant": quant,
        "quant_mtf": quant,
        "multitf": multitf,
        "option_greeks": greeks,
    }

    if "news_sentiment" not in response:
        response["news_sentiment"] = {"score": 0, "label": "NEUTRAL", "source": "none"}

    return response


def get_multi_tf(symbol, ema_len=50):
    """FIX #3 — Multi-TF using 5m instead of 1m which fails for indices.
    Uses concurrent downloads for all timeframes (~3s instead of ~9s)."""
    cache_key = f"mtf:{symbol}"
    hit = C.get(cache_key)
    if hit is not None:
        return hit

    from concurrent.futures import as_completed

    from base_indicators import calc_adx, calc_macd, calc_rsi

    tfs = {"5M": ("2d", "5m"), "15M": ("5d", "15m"), "1H": ("1mo", "60m")}

    # Map symbols for Yahoo Finance
    yf_sym = symbol
    if symbol == "NIFTY":
        yf_sym = "^NSEI"
    elif symbol == "BANKNIFTY":
        yf_sym = "^NSEBANK"

    def _fetch_tf(label, period, interval):
        try:
            df = yf.download(
                yf_sym,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
                timeout=8,
            )
            if df.empty or len(df) < 20:
                print(f"[MultiTF] Validation Error: Missing/Empty candles for {label}")
                return label, {
                    "rsi": None,
                    "macd": None,
                    "adx": None,
                    "bias": "DEGRADED",
                }
            df = df.loc[~df.index.duplicated(keep="last")]

            # FIX-002: Validation
            validation_errors = []
            if df.index.tzinfo is None:
                validation_errors.append("Timezone mismatch")

            df["date_only"] = df.index.date
            diffs = (
                df.groupby("date_only")
                .apply(lambda x: x.index.to_series().diff())
                .dropna()
            )
            expected_delta = pd.Timedelta(
                interval.replace("m", "min").replace("h", "h")
            )
            if (diffs > expected_delta).any():
                validation_errors.append("Missing intervals")

            if validation_errors:
                print(f"[MultiTF] Validation Error {label}: {validation_errors}")
                return label, {
                    "rsi": None,
                    "macd": None,
                    "adx": None,
                    "bias": "DEGRADED",
                }

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(-1)
            rsi_v = safe(calc_rsi(df["Close"]).iloc[-1])
            m, s, _ = calc_macd(df["Close"])
            macd_v = safe(m.iloc[-1])
            adx_s, _, _ = calc_adx(df)
            adx_v = safe(adx_s.iloc[-1])
            bias = (
                "BULLISH"
                if (rsi_v or 50) > 55 and (macd_v or 0) > 0
                else "BEARISH"
                if (rsi_v or 50) < 45 and (macd_v or 0) < 0
                else "NEUTRAL"
            )
            return label, {"rsi": rsi_v, "macd": macd_v, "adx": adx_v, "bias": bias}
        except (
            TimeoutError,
            ConnectionError,
            requests.exceptions.HTTPError,
            ValueError,
            KeyError,
            OSError,
        ) as e:
            print(f"[MultiTF] Fetch failed {label}: {e}")
            return label, {"rsi": None, "macd": None, "adx": None, "bias": "DEGRADED"}

    result = {}
    # Run all 3 timeframe downloads concurrently
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(_fetch_tf, label, period, interval): label
            for label, (period, interval) in tfs.items()
        }
        for fut in as_completed(futures, timeout=15):
            try:
                label, data = fut.result()
                result[label] = data
            except (
                TimeoutError,
                ConnectionError,
                requests.exceptions.HTTPError,
                ValueError,
                KeyError,
                OSError,
            ) as e:
                label = futures[fut]
                print(f"[MultiTF] Concurrent fetch failed {label}: {e}")
                result[label] = {
                    "rsi": None,
                    "macd": None,
                    "adx": None,
                    "bias": "DEGRADED",
                }

    bear = sum(1 for v in result.values() if v["bias"] == "BEARISH")
    bull = sum(1 for v in result.values() if v["bias"] == "BULLISH")
    alignment = (
        "FULL_BEAR"
        if bear == 3
        else "PARTIAL_BEAR"
        if bear == 2
        else "FULL_BULL"
        if bull == 3
        else "PARTIAL_BULL"
        if bull == 2
        else "MIXED"
    )
    out = {"timeframes": result, "alignment": alignment}
    C.put(cache_key, out, C.TTL_MULTI_TF)
    return out
