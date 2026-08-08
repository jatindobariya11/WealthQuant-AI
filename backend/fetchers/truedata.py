import time
from datetime import datetime, timedelta

import requests

from core.shared_features import *

from .config import *


def _get_truedata_token() -> str:
    """Login to TrueData and get access token (cached 8h)."""
    global _truedata_token, _truedata_token_expiry
    if _truedata_token and time.time() < _truedata_token_expiry:
        return _truedata_token
    if not TRUEDATA_USER:
        raise ValueError("TRUEDATA_USER not set")
    r = requests.post(
        "https://history.truedata.in/login",
        json={"username": TRUEDATA_USER, "password": TRUEDATA_PASSWORD},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    _truedata_token = data.get("token") or data.get("access_token")
    _truedata_token_expiry = time.time() + 8 * 3600
    return _truedata_token


def fetch_truedata_ltp(symbol: str) -> dict:
    """TrueData: live tick price (< 50ms latency)."""
    try:
        token = _get_truedata_token()
        td_sym = TRUEDATA_SYMBOL_MAP.get(symbol, symbol)
        r = requests.get(
            f"https://history.truedata.in/getltp?symbol={td_sym}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        r.raise_for_status()
        data = r.json()
        ltp = data.get("ltp") or data.get("data", {}).get("ltp")
        return {
            "source": "truedata",
            "ltp": float(ltp) if ltp else None,
        }
    except Exception as e:
        logger.warning(f"TrueData LTP failed: {e}")
        return {"source": "truedata", "error": str(e)}


def fetch_truedata_ohlc(symbol: str, interval: str) -> dict:
    """TrueData: OHLC bars (official NSE authorized feed)."""
    try:
        token = _get_truedata_token()
        td_sym = TRUEDATA_SYMBOL_MAP.get(symbol, symbol)
        ivl = TRUEDATA_INTERVAL_MAP.get(interval, "5")
        from_d = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        to_d = datetime.now().strftime("%Y-%m-%d")

        r = requests.get(
            "https://history.truedata.in/getbars",
            params={
                "symbol": td_sym,
                "from": from_d,
                "to": to_d,
                "duration": ivl,
                "bidask": "0",
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        records = data.get("Records") or data.get("data", [])
        candles = []
        for rec in records:
            candles.append(
                {
                    "time": rec.get("time") or rec.get("timestamp"),
                    "open": float(rec.get("open", 0)),
                    "high": float(rec.get("high", 0)),
                    "low": float(rec.get("low", 0)),
                    "close": float(rec.get("close", 0)),
                    "volume": int(rec.get("volume", 0)),
                }
            )
        return {"source": "truedata", "candles": candles}
    except Exception as e:
        logger.warning(f"TrueData OHLC failed: {e}")
        return {"source": "truedata", "error": str(e)}


def fetch_truedata_option_greeks(symbol: str, expiry: str = None) -> dict:
    """TrueData: option greeks (IV, Delta, Theta, Vega, Gamma) for full chain."""
    try:
        token = _get_truedata_token()
        td_sym = TRUEDATA_SYMBOL_MAP.get(symbol, symbol).replace("-I", "")
        params = {"symbol": td_sym}
        if expiry:
            params["expiry"] = expiry

        r = requests.get(
            "https://history.truedata.in/getoptionchain",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return {"source": "truedata", "greeks": data}
    except Exception as e:
        logger.warning(f"TrueData greeks failed: {e}")
        return {"source": "truedata", "error": str(e)}
