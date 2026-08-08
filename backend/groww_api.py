"""
groww_api.py
Official Groww Trading API integration.
Provides live NSE quotes, order management, holdings & positions.

Requires:
  - Active Groww account with Trading API subscription
  - API Auth Token from groww.in/trade-api > API Keys
  - Set GROWW_AUTH_TOKEN environment variable (or in .env file)
"""

import os
import traceback

from growwapi import GrowwAPI

# ── Auth Token ────────────────────────────────────────────────
GROWW_AUTH_TOKEN = os.getenv("GROWW_AUTH_TOKEN")
if not GROWW_AUTH_TOKEN:
    import logging

    logging.getLogger("groww_api").warning(
        "GROWW_AUTH_TOKEN not set. Groww API calls will fail."
    )

_client = None


def _get_client() -> GrowwAPI:
    global _client
    if _client is None:
        if not GROWW_AUTH_TOKEN:
            raise ValueError(
                "Groww API token not set. "
                "Edit GROWW_AUTH_TOKEN in groww_api.py or set GROWW_TOKEN env variable."
            )
        _client = GrowwAPI(GROWW_AUTH_TOKEN)
    return _client


# ── Symbol helpers ────────────────────────────────────────────
GROWW_IDX_MAP = {
    "NIFTY": "NIFTY",
    "BANKNIFTY": "BANKNIFTY",
    "FINNIFTY": "FINNIFTY",
    "MIDCPNIFTY": "MIDCPNIFTY",
    "SENSEX": "SENSEX",
}


def get_groww_quote(symbol: str) -> dict:
    """
    Fetch real-time NSE Cash segment quote for a stock or index.
    Returns clean dict or raises on failure.
    """
    try:
        g = _get_client()
        trading_sym = GROWW_IDX_MAP.get(symbol.upper(), symbol.upper())
        resp = g.get_quote(
            exchange=g.EXCHANGE_NSE,
            segment=g.SEGMENT_CASH,
            trading_symbol=trading_sym,
        )
        return {
            "symbol": symbol.upper(),
            "exchange": "NSE",
            "price": resp.get("last_traded_price") or resp.get("ltp"),
            "open": resp.get("open"),
            "high": resp.get("high"),
            "low": resp.get("low"),
            "close": resp.get("close") or resp.get("prev_close"),
            "volume": resp.get("volume"),
            "change": resp.get("change"),
            "change_pct": resp.get("change_percent"),
            "bid": resp.get("best_bid_price"),
            "ask": resp.get("best_ask_price"),
            "source": "groww_api",
            "raw": resp,
        }
    except ValueError:
        raise  # re-raise config errors
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e), "source": "groww_api"}


def get_holdings() -> list:
    """Return the user's current holdings."""
    try:
        g = _get_client()
        # Try multiple possible method names from different growwapi versions
        for method_name in ["get_holdings", "holdings", "get_portfolio"]:
            fn = getattr(g, method_name, None)
            if fn:
                resp = fn()
                return resp if isinstance(resp, list) else resp.get("holdings", [])
        return [
            {"error": "Groww API: no holdings method available", "source": "groww_api"}
        ]
    except ValueError:
        return [{"error": "Groww API token not configured", "source": "groww_api"}]
    except Exception as e:
        traceback.print_exc()
        return [{"error": str(e), "source": "groww_api"}]


def get_positions() -> list:
    """Return intraday positions."""
    try:
        g = _get_client()
        for method_name in ["get_positions", "positions", "get_open_positions"]:
            fn = getattr(g, method_name, None)
            if fn:
                resp = fn()
                return resp if isinstance(resp, list) else resp.get("positions", [])
        return [
            {"error": "Groww API: no positions method available", "source": "groww_api"}
        ]
    except ValueError:
        return [{"error": "Groww API token not configured", "source": "groww_api"}]
    except Exception as e:
        traceback.print_exc()
        return [{"error": str(e), "source": "groww_api"}]


def get_order_book() -> list:
    """Return all orders for the session."""
    try:
        g = _get_client()
        for method_name in ["get_orders", "get_order_book", "orders", "order_book"]:
            fn = getattr(g, method_name, None)
            if fn:
                resp = fn()
                return resp if isinstance(resp, list) else resp.get("orders", [])
        return [
            {"error": "Groww API: no orders method available", "source": "groww_api"}
        ]
    except ValueError:
        return [{"error": "Groww API token not configured", "source": "groww_api"}]
    except Exception as e:
        traceback.print_exc()
        return [{"error": str(e), "source": "groww_api"}]


def place_order(
    symbol: str, qty: int, side: str, order_type: str = "MARKET", price: float = 0.0
) -> dict:
    """
    Place a buy/sell order.
    side: 'BUY' | 'SELL'
    order_type: 'MARKET' | 'LIMIT'
    """
    try:
        g = _get_client()
        resp = g.place_order(
            exchange=g.EXCHANGE_NSE,
            segment=g.SEGMENT_CASH,
            trading_symbol=symbol.upper(),
            transaction_type=side.upper(),
            order_type=order_type.upper(),
            quantity=qty,
            price=price if order_type.upper() == "LIMIT" else 0,
        )
        return {"status": "success", "order": resp}
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "error": str(e)}
