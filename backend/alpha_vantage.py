"""
alpha_vantage.py
Secondary data source using Alpha Vantage API.
Used as fallback when yfinance fails, or for extended fundamental data.

Free tier limits: 25 requests/day, 5 requests/minute.
"""

import os
import time

import pandas as pd
import requests

AV_API_KEY = os.getenv("AV_API_KEY", "")
AV_BASE = "https://www.alphavantage.co/query"

# Map internal symbol → Alpha Vantage symbol
AV_SYM_MAP = {
    "RELIANCE": "RELIANCE.BSE",
    "TCS": "TCS.BSE",
    "INFY": "INFY.BSE",
    "HDFCBANK": "HDFCBANK.BSE",
    "ICICIBANK": "ICICIBANK.BSE",
    "WIPRO": "WIPRO.BSE",
    "BAJFINANCE": "BAJFINANCE.BSE",
    "TATAMOTORS": "TATAMOTORS.BSE",
    "SBIN": "SBIN.BSE",
    "LT": "LT.BSE",
    "AXISBANK": "AXISBANK.BSE",
    "MARUTI": "MARUTI.BSE",
    "SUNPHARMA": "SUNPHARMA.BSE",
    "NESTLEIND": "NESTLEIND.BSE",
    "TITAN": "TITAN.BSE",
}


def _get(params: dict, retries: int = 2) -> dict:
    """Safe GET with retry logic."""
    params["apikey"] = AV_API_KEY
    for attempt in range(retries):
        try:
            r = requests.get(AV_BASE, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            # AV returns {"Note": "..."} on rate limit
            if "Note" in data or "Information" in data:
                print(
                    f"[AlphaVantage] Rate limit hit: {data.get('Note') or data.get('Information')}"
                )
                return {"rate_limit": True}
            return data
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                print(f"[AlphaVantage] Error: {e}")
    return {}


def get_daily_ohlcv(symbol: str, outputsize: str = "compact") -> pd.DataFrame:
    """
    Fetch daily OHLCV data. Returns a pandas DataFrame sorted oldest-first.
    outputsize: 'compact' = last 100 rows, 'full' = 20+ years.
    """
    av_sym = AV_SYM_MAP.get(symbol.upper(), f"{symbol.upper()}.BSE")
    data = _get(
        {
            "function": "TIME_SERIES_DAILY",
            "symbol": av_sym,
            "outputsize": outputsize,
        }
    )
    ts = data.get("Time Series (Daily)", {})
    if not ts:
        return pd.DataFrame()

    rows = []
    for date_str, vals in ts.items():
        rows.append(
            {
                "Date": pd.to_datetime(date_str),
                "Open": float(vals["1. open"]),
                "High": float(vals["2. high"]),
                "Low": float(vals["3. low"]),
                "Close": float(vals["4. close"]),
                "Volume": int(vals["5. volume"]),
            }
        )

    df = pd.DataFrame(rows).sort_values("Date").reset_index(drop=True)
    df.set_index("Date", inplace=True)
    return df


def get_quote(symbol: str) -> dict:
    """
    Get real-time quote (price, change, volume) for a BSE symbol.
    Returns a clean dict or {} on failure.
    """
    av_sym = AV_SYM_MAP.get(symbol.upper(), f"{symbol.upper()}.BSE")
    data = _get(
        {
            "function": "GLOBAL_QUOTE",
            "symbol": av_sym,
        }
    )
    q = data.get("Global Quote", {})
    if not q:
        return {}
    try:
        return {
            "symbol": q.get("01. symbol"),
            "price": float(q.get("05. price", 0)),
            "open": float(q.get("02. open", 0)),
            "high": float(q.get("03. high", 0)),
            "low": float(q.get("04. low", 0)),
            "volume": int(q.get("06. volume", 0)),
            "prev_close": float(q.get("08. previous close", 0)),
            "change": float(q.get("09. change", 0)),
            "change_pct": q.get("10. change percent", "0%").replace("%", ""),
            "source": "alpha_vantage",
        }
    except Exception as e:
        print(f"[AlphaVantage] Quote parse error: {e}")
        return {}


def get_overview(symbol: str) -> dict:
    """
    Fundamental overview: P/E, EPS, Market Cap, 52-week range, etc.
    Only works for US/global tickers with AV free tier.
    """
    av_sym = AV_SYM_MAP.get(symbol.upper(), f"{symbol.upper()}.BSE")
    data = _get({"function": "OVERVIEW", "symbol": av_sym})
    if not data or "Symbol" not in data:
        return {}
    return {
        "name": data.get("Name"),
        "sector": data.get("Sector"),
        "industry": data.get("Industry"),
        "market_cap": data.get("MarketCapitalization"),
        "pe_ratio": data.get("PERatio"),
        "eps": data.get("EPS"),
        "beta": data.get("Beta"),
        "52w_high": data.get("52WeekHigh"),
        "52w_low": data.get("52WeekLow"),
        "div_yield": data.get("DividendYield"),
        "analyst_target": data.get("AnalystTargetPrice"),
        "source": "alpha_vantage",
    }
