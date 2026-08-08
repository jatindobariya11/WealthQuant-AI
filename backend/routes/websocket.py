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

@router.websocket("/ws/live/{symbol}")
async def websocket_live_route(websocket: WebSocket, symbol: str):
    """Compatibility alias that forwards to the existing websocket implementation."""
    await websocket_signals(websocket)

