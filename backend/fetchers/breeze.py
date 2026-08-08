from datetime import datetime, timedelta

from core.shared_features import *

from .config import *


def _get_client():
    """Lazy-init Breeze client. Re-uses existing session."""
    global _client
    if _client:
        return _client
    if not BREEZE_API_KEY:
        raise OSError("BREEZE_API_KEY not set in .env")
    try:
        from breeze_connect import BreezeConnect

        client = BreezeConnect(api_key=BREEZE_API_KEY)
        client.generate_session(
            api_secret=BREEZE_API_SECRET,
            session_token=BREEZE_SESSION,
        )
        _client = client
        logger.info("Breeze session established.")
        return client
    except ImportError:
        logger.error("breeze-connect not installed. Run: pip install breeze-connect")
        raise
    except Exception as e:
        logger.error(f"Breeze login failed: {e}")
        raise RuntimeError(f"Breeze login failed: {e}")


def reset_breeze_session():
    """Call this if session expires (daily token rotation)."""
    global _client
    _client = None
    logger.info("Breeze session reset.")


def fetch_breeze_ltp(symbol: str) -> dict:
    """
    Real-time LTP via Breeze API. Latency < 100ms.
    """
    try:
        client = _get_client()
        code = BREEZE_STOCK_CODE.get(symbol.upper(), symbol.upper())

        r = client.get_quotes(
            stock_code=code,
            exchange_code="NSE",
            product_type="cash",
            right="others",
            strike_price="0",
        )

        if not r or "Success" not in r or not r["Success"]:
            raise ValueError(f"Breeze returned no data for {symbol}")

        s = r["Success"][0]

        def f(key, fallback=None):
            try:
                val = s.get(key)
                return float(val) if val else fallback
            except Exception:
                return fallback

        ltp = f("ltp") or f("last_rate")
        prev_close = f("previous_close") or f("prev_close")
        chg = round(ltp - prev_close, 2) if ltp and prev_close else None
        chg_pct = round((chg / prev_close) * 100, 2) if chg and prev_close else None

        return {
            "source": "breeze",
            "symbol": symbol,
            "ltp": round(ltp, 2) if ltp else None,
            "open": round(f("open"), 2) if f("open") else None,
            "high": round(f("high"), 2) if f("high") else None,
            "low": round(f("low"), 2) if f("low") else None,
            "prev_close": round(prev_close, 2) if prev_close else None,
            "volume": int(f("total_quantity_traded") or f("volume", 0)),
            "chg": chg,
            "chg_pct": chg_pct,
            "fetched_at": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.warning(f"Breeze LTP failed for {symbol}: {e}")
        return {"source": "breeze", "error": str(e)}


def fetch_breeze_ohlc(symbol: str, interval: str = "5m", days_back: int = 5) -> dict:
    """
    Historical + live OHLC candles via Breeze API.
    """
    try:
        client = _get_client()
        code = BREEZE_STOCK_CODE.get(symbol.upper(), symbol.upper())
        ivl = BREEZE_INTERVAL.get(interval, "5minute")
        now = datetime.now()
        from_dt = (now - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00.000Z")
        to_dt = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        r = client.get_historical_data_v2(
            interval_type=ivl,
            from_date=from_dt,
            to_date=to_dt,
            stock_code=code,
            exchange_code="NSE",
            product_type="cash",
        )

        if not r or "Success" not in r or not r["Success"]:
            return {"source": "breeze", "error": "No candles returned"}

        candles = []
        for c in r["Success"]:
            dt_str = c.get("datetime") or c.get("date") or ""
            try:
                ts = int(
                    datetime.fromisoformat(dt_str.replace("Z", "+00:00")).timestamp()
                )
            except Exception:
                ts = dt_str

            candles.append(
                {
                    "time": ts,
                    "open": float(c.get("open", 0)),
                    "high": float(c.get("high", 0)),
                    "low": float(c.get("low", 0)),
                    "close": float(c.get("close", 0)),
                    "volume": int(c.get("volume", 0)),
                }
            )

        return {
            "source": "breeze",
            "symbol": symbol,
            "interval": interval,
            "candles": candles,
        }
    except Exception as e:
        logger.warning(f"Breeze OHLC failed for {symbol}: {e}")
        return {"source": "breeze", "error": str(e)}


def fetch_breeze_option_chain(
    symbol: str, expiry_date: str, right: str = "both"
) -> dict:
    """
    F&O option chain with live prices + Greeks via Breeze.
    expiry_date format: "28-Nov-2024"
    """
    try:
        client = _get_client()
        code = BREEZE_STOCK_CODE.get(symbol.upper(), symbol.upper())

        def get_chain(right_type):
            r = client.get_option_chain_quotes(
                stock_code=code,
                exchange_code="NFO",
                product_type="options",
                expiry_date=expiry_date,
                right=right_type,
                strike_price="0",
            )
            if r and "Success" in r:
                return r["Success"]
            return []

        calls, puts = [], []
        if right in ("call", "both"):
            for item in get_chain("call"):
                calls.append(
                    {
                        "strike": float(item.get("strike_price", 0)),
                        "ltp": float(item.get("last_rate", 0)),
                        "oi": int(item.get("open_interest", 0)),
                        "volume": int(item.get("volume", 0)),
                        "iv": float(item.get("implied_volatility", 0) or 0),
                        "delta": float(item.get("delta", 0) or 0),
                        "theta": float(item.get("theta", 0) or 0),
                        "vega": float(item.get("vega", 0) or 0),
                        "gamma": float(item.get("gamma", 0) or 0),
                    }
                )

        if right in ("put", "both"):
            for item in get_chain("put"):
                puts.append(
                    {
                        "strike": float(item.get("strike_price", 0)),
                        "ltp": float(item.get("last_rate", 0)),
                        "oi": int(item.get("open_interest", 0)),
                        "volume": int(item.get("volume", 0)),
                        "iv": float(item.get("implied_volatility", 0) or 0),
                        "delta": float(item.get("delta", 0) or 0),
                        "theta": float(item.get("theta", 0) or 0),
                        "vega": float(item.get("vega", 0) or 0),
                        "gamma": float(item.get("gamma", 0) or 0),
                    }
                )

        return {
            "source": "breeze",
            "symbol": symbol,
            "expiry": expiry_date,
            "calls": sorted(calls, key=lambda x: x["strike"]),
            "puts": sorted(puts, key=lambda x: x["strike"]),
        }
    except Exception as e:
        logger.error(f"Breeze option chain failed: {e}")
        return {"source": "breeze", "error": str(e)}


def subscribe_live_feed(symbol: str, on_tick: callable) -> None:
    """
    Subscribe to real-time WebSocket tick feed via Breeze.
    """
    try:
        client = _get_client()
        code = BREEZE_STOCK_CODE.get(symbol.upper(), symbol.upper())

        def _on_ticks(ticks):
            if ticks:
                on_tick(
                    {
                        "source": "breeze_ws",
                        "symbol": symbol,
                        "ltp": float(ticks.get("last", 0)),
                        "volume": int(ticks.get("volume", 0)),
                        "timestamp": ticks.get("timestamp"),
                    }
                )

        client.on_ticks = _on_ticks
        client.subscribe_feeds(
            stock_code=code,
            exchange_code="NSE",
            product_type="cash",
            get_exchange_quotes=True,
            get_market_depth=False,
        )
        logger.info(f"Subscribed to Breeze live feed for {symbol}")
    except Exception as e:
        logger.error(f"Breeze WebSocket failed: {e}")
