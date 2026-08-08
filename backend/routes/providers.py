from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse
import asyncio
import time
import json
import logging
from typing import Optional

# import whatever is needed
from core.shared_features import *
import cache
import database as DB
from prediction_engine import *

router = APIRouter()

@router.get("/api/av/quote/{symbol}")
def av_quote(symbol: str):
    """Real-time BSE quote with Groww fallback."""
    try:
        result = get_quote(symbol.upper())
        if result.get("rate_limit") or not result:
            print(f"[Fallback] AV quote failed for {symbol}. Using Groww.")
            return get_groww_quote(symbol.upper())
        return result
    except Exception as e:
        print(f"[Fallback] AV quote error: {e}")
        return get_groww_quote(symbol.upper())

@router.get("/api/av/ohlcv/{symbol}")
def av_ohlcv(symbol: str, outputsize: str = Query("compact")):
    """Daily OHLCV history with yfinance fallback."""
    try:
        df = get_daily_ohlcv(symbol.upper(), outputsize)
        if df.empty:
            print(f"[Fallback] AV OHLCV empty for {symbol}. Using yfinance.")
            yf_sym = symbol.upper() + ".NS" if "." not in symbol else symbol.upper()
            yf_df = yf.download(yf_sym, period="1mo", interval="1d", progress=False)
            if yf_df.empty:
                raise HTTPException(404, detail="No data available from any source")
            df = yf_df

        df_out = df.tail(100).copy()
        df_out.index = df_out.index.strftime("%Y-%m-%d")
        return {
            "symbol": symbol,
            "source": "fallback",
            "data": df_out.reset_index().to_dict("records"),
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))

@router.get("/api/av/overview/{symbol}")
def av_overview(symbol: str):
    """Fundamental data from Alpha Vantage."""
    try:
        result = get_overview(symbol.upper())
        if not result or result.get("rate_limit"):
            return {
                "symbol": symbol,
                "note": "Fundamental data currently unavailable (Rate Limit)",
            }
        return result
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

@router.get("/api/groww/quote/{symbol}")
def groww_quote(symbol: str):
    """Real-time NSE quote from Groww API."""
    try:
        result = get_groww_quote(symbol.upper())
        if "error" in result:
            raise HTTPException(503, detail=f"Groww API error: {result['error']}")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(503, detail=str(e))  # token not configured
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))

@router.get("/api/groww/holdings", dependencies=[Depends(verify_token)])
@limiter.limit("30/minute")
def groww_holdings(request: Request):
    """User's current stock holdings via Groww."""
    try:
        return {"holdings": get_holdings()}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))

@router.get("/api/groww/positions", dependencies=[Depends(verify_token)])
@limiter.limit("30/minute")
def groww_positions(request: Request):
    """Current intraday positions via Groww."""
    try:
        return {"positions": get_positions()}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))

@router.get("/api/groww/orders", dependencies=[Depends(verify_token)])
@limiter.limit("30/minute")
def groww_orders(request: Request):
    """Order book for current session via Groww."""
    try:
        return {"orders": get_order_book()}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))

@router.post("/api/groww/order", dependencies=[Depends(verify_token)])
@limiter.limit("5/minute")
def groww_place_order(
    request: Request,
    symbol: str,
    qty: int,
    side: str,
    order_type: str = "MARKET",
    price: float = 0.0,
):
    """Place a BUY/SELL order via Groww. POST only for safety."""
    try:
        result = place_order(symbol, qty, side, order_type, price)
        if result.get("status") == "error":
            raise HTTPException(400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))

