"""
FastAPI Server — Gamma Squeeze Platform API
REST endpoints + WebSocket for real-time signal streaming
"""

import asyncio
import json
import logging
from datetime import datetime

import numpy as np
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Corrected imports for active codebase hierarchy
from gamma_squeeze_engine import GammaSqueezeEngine
from signals.breakout_router import BreakoutRouter
from signals.live_chain_monitor import NSEChainFetcher

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# APP SETUP
# ══════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Gamma Squeeze Intelligence Platform",
    description="NSE India — Real-time Gamma Squeeze Detection for Nifty & Bank Nifty",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
fetcher = NSEChainFetcher()
engines = {
    "NIFTY": GammaSqueezeEngine("NIFTY"),
    "BANKNIFTY": GammaSqueezeEngine("BANKNIFTY"),
}
router_inst = BreakoutRouter(capital=500000, risk_pct=0.01)
ws_clients: list[WebSocket] = []


def fetch_live_metrics(
    symbol_upper: str, default_spot: float, raise_error: bool = True
):
    import pandas as pd

    import yfinance as yf
    from institutional_detector import YF_LOCK, _to_yf_symbol

    yf_symbol = _to_yf_symbol(symbol_upper)

    spot = default_spot
    prev_spot = spot
    volume_1min = 0.0
    avg_volume_20d = 1.0
    bid_ask_spread = 0.5

    try:
        with YF_LOCK:
            df = yf.download(
                yf_symbol,
                period="5d",
                interval="1m",
                progress=False,
            )

        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            last_row = df.iloc[-1]
            prev_row = df.iloc[-2] if len(df) >= 2 else last_row

            spot = float(last_row["Close"])
            prev_spot = float(prev_row["Close"])

            if "Volume" in df.columns:
                has_volume = float(df["Volume"].sum()) > 0
                if has_volume:
                    vol_ma = (
                        df["Volume"].rolling(window=20, min_periods=20).mean().iloc[-1]
                    )
                    volume_1min = float(last_row["Volume"])
                    avg_volume_20d = float(vol_ma) if not np.isnan(vol_ma) else 1.0

            bid_ask_spread = float(last_row["High"] - last_row["Low"])
            if bid_ask_spread <= 0:
                bid_ask_spread = 0.5
    except Exception as e:
        logger.warning(f"[fetch_live_metrics] yfinance fetch failed: {e}")
        if raise_error:
            raise HTTPException(
                status_code=503,
                detail=f"Live market metric stream is currently unavailable. Error: {str(e)}",
            )
        else:
            # Safe fallback metrics for WebSocket to prevent loop crash
            prev_spot = spot * 0.999
            volume_1min = 1000.0
            avg_volume_20d = 200.0
            bid_ask_spread = 0.5

    return spot, prev_spot, volume_1min, avg_volume_20d, bid_ask_spread


# ══════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE MODELS
# ══════════════════════════════════════════════════════════════════


class AnalyzeRequest(BaseModel):
    symbol: str = "NIFTY"
    expiry: str | None = None
    instrument_pref: str = "FUTURES"
    capital: float = 500000
    risk_pct: float = 0.01


class GEXProfileResponse(BaseModel):
    symbol: str
    spot: float
    expiry: str
    timestamp: str
    gex_data: list[dict]
    walls: dict
    summary: dict


# ══════════════════════════════════════════════════════════════════
# REST ENDPOINTS
# ══════════════════════════════════════════════════════════════════


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    """
    Full gamma squeeze analysis for a symbol.
    Fetches live chain → computes GEX → scores IPI → generates trade signal.
    """
    sym = req.symbol.upper()
    if sym not in engines:
        raise HTTPException(status_code=400, detail=f"Symbol {sym} not supported")

    # Fetch live chain
    raw = fetcher.fetch_chain(sym)
    if not raw:
        raise HTTPException(status_code=503, detail="Could not fetch NSE chain data")

    spot, expiry, options = fetcher.parse_chain(raw, req.expiry)
    if spot == 0:
        raise HTTPException(status_code=503, detail="Invalid spot price from NSE")

    # Fetch live 1-minute historical metrics
    live_spot, prev_spot, volume_1min, avg_volume_20d, bid_ask_spread = (
        fetch_live_metrics(sym, spot)
    )

    # Run analysis
    signal = engines[sym].analyze(
        chain_data=options,
        spot=live_spot,
        prev_spot=prev_spot,
        expiry_days=1.0,
        volume_1min=volume_1min,
        avg_volume_20d=avg_volume_20d,
        bid_ask_spread=bid_ask_spread,
    )

    # Generate trade signal
    available_strikes = sorted(set(o.strike for o in options))
    trade_router = BreakoutRouter(req.capital, req.risk_pct)
    trade = trade_router.route(signal, expiry, available_strikes, req.instrument_pref)
    summary = engines[sym].get_squeeze_summary()

    return {
        "success": True,
        "symbol": sym,
        "spot": spot,
        "expiry": expiry,
        "timestamp": datetime.now().isoformat(),
        "squeeze": summary,
        "trade_signal": {
            "signal_id": trade.signal_id,
            "direction": trade.direction,
            "instrument": trade.instrument,
            "entry": trade.entry_price,
            "stop_loss": trade.stop_loss,
            "target_1": trade.target_1,
            "target_2": trade.target_2,
            "target_3": trade.target_3,
            "quantity": trade.quantity,
            "strike": trade.strike,
            "risk_reward": trade.risk_reward,
            "max_loss_inr": trade.max_loss_inr,
            "max_profit_inr": trade.max_profit_inr,
            "rationale": trade.rationale,
            "ipi_score": trade.ipi_score,
            "confidence": trade.confidence,
        },
    }


@app.get("/api/gex-profile")
async def gex_profile(
    symbol: str = Query("NIFTY"),
    expiry: str | None = Query(None),
):
    """
    Returns full GEX profile for visualization (heatmap/bar chart).
    Use this to render the Gamma Wall chart in the frontend.
    """
    raw = fetcher.fetch_chain(symbol.upper())
    if not raw:
        raise HTTPException(status_code=503, detail="NSE unavailable")

    spot, exp, options = fetcher.parse_chain(raw, expiry)
    engine = engines.get(symbol.upper(), GammaSqueezeEngine(symbol.upper()))
    gex_df = engine.gex_calc.compute_gex_profile(options, spot, expiry_days=1.0)
    walls = engine.gex_calc.find_gamma_walls(gex_df, spot)

    return {
        "symbol": symbol,
        "spot": spot,
        "expiry": exp,
        "timestamp": datetime.now().isoformat(),
        "gex_data": gex_df[
            ["strike", "net_gex", "call_gex", "put_gex", "call_oi", "put_oi", "iv_skew"]
        ].to_dict("records"),
        "walls": walls,
    }


@app.get("/api/max-pain")
async def max_pain(symbol: str = Query("NIFTY"), expiry: str | None = Query(None)):
    raw = fetcher.fetch_chain(symbol.upper())
    spot, exp, options = fetcher.parse_chain(raw, expiry)
    engine = engines.get(symbol.upper(), GammaSqueezeEngine(symbol.upper()))
    gex_df = engine.gex_calc.compute_gex_profile(options, spot)
    pain = engine._calculate_max_pain(gex_df, spot)

    return {
        "symbol": symbol,
        "spot": spot,
        "max_pain": pain,
        "distance": round((pain - spot) / spot * 100, 3),
        "expiry": exp,
    }


@app.get("/api/pcr")
async def pcr(symbol: str = Query("NIFTY"), expiry: str | None = Query(None)):
    raw = fetcher.fetch_chain(symbol.upper())
    spot, exp, options = fetcher.parse_chain(raw, expiry)
    total_call = sum(o.call_oi for o in options)
    total_put = sum(o.put_oi for o in options)
    pcr_val = total_put / total_call if total_call else 0

    signal = (
        "STRONG_BULLISH"
        if pcr_val > 1.4
        else "BULLISH"
        if pcr_val > 1.1
        else "STRONG_BEARISH"
        if pcr_val < 0.6
        else "BEARISH"
        if pcr_val < 0.9
        else "NEUTRAL"
    )

    return {
        "symbol": symbol,
        "expiry": exp,
        "pcr": round(pcr_val, 3),
        "call_oi": total_call,
        "put_oi": total_put,
        "signal": signal,
    }


@app.get("/api/ipi-history")
async def ipi_history(symbol: str = Query("NIFTY")):
    """Returns IPI score history for charting."""
    eng = engines.get(symbol.upper())
    if not eng or not eng.history:
        return {"symbol": symbol, "history": []}

    return {
        "symbol": symbol,
        "history": [
            {
                "timestamp": s.timestamp.isoformat(),
                "ipi_score": s.ipi_score,
                "direction": s.direction,
                "urgency": s.urgency,
                "confidence": s.confidence,
                "spot": s.spot_price,
            }
            for s in eng.history[-100:]  # Last 100 readings
        ],
    }


# ══════════════════════════════════════════════════════════════════
# WEBSOCKET — REAL-TIME SIGNAL STREAM
# ══════════════════════════════════════════════════════════════════


@app.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    """
    WebSocket endpoint for real-time signal streaming.
    Frontend connects here to receive live IPI updates every 60s.
    """
    from core.security import verify_token_websocket

    user_payload = await verify_token_websocket(websocket)
    if not user_payload:
        return

    await websocket.accept()
    if websocket not in ws_clients:
        ws_clients.append(websocket)
    logger.info(f"WS client connected. Total: {len(ws_clients)}")

    from starlette.websockets import WebSocketState

    try:
        while True:
            # Send a heartbeat / latest analysis every 60s
            for sym in ["NIFTY", "BANKNIFTY"]:
                try:
                    if websocket.client_state != WebSocketState.CONNECTED:
                        raise WebSocketDisconnect()

                    raw = fetcher.fetch_chain(sym)
                    if raw:
                        spot, expiry, options = fetcher.parse_chain(raw)
                        # Fetch live 1-minute historical metrics
                        (
                            live_spot,
                            prev_spot,
                            volume_1min,
                            avg_volume_20d,
                            bid_ask_spread,
                        ) = fetch_live_metrics(sym, spot, raise_error=False)
                        signal = engines[sym].analyze(
                            chain_data=options,
                            spot=live_spot,
                            prev_spot=prev_spot,
                            expiry_days=1.0,
                            volume_1min=volume_1min,
                            avg_volume_20d=avg_volume_20d,
                            bid_ask_spread=bid_ask_spread,
                        )
                        summary = engines[sym].get_squeeze_summary()

                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "signal_update",
                                    "symbol": sym,
                                    "data": summary,
                                },
                                default=str,
                            )
                        )
                except (WebSocketDisconnect, RuntimeError):
                    raise WebSocketDisconnect()
                except Exception as e:
                    logger.error(f"WS signal error for {sym}: {e}")

            await asyncio.sleep(60)
    except WebSocketDisconnect:
        if websocket in ws_clients:
            ws_clients.remove(websocket)
        logger.info(f"WS client disconnected. Total: {len(ws_clients)}")
    except Exception as e:
        if websocket in ws_clients:
            ws_clients.remove(websocket)
        logger.error(f"WS closed with error: {e}")


# ══════════════════════════════════════════════════════════════════
# STARTUP
# ══════════════════════════════════════════════════════════════════


@app.on_event("startup")
async def startup():
    logger.info("🚀 Gamma Squeeze Platform starting...")
    logger.info("📡 Connecting to NSE India...")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)
