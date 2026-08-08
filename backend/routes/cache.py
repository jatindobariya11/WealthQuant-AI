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

@router.get("/api/cache/status")
def cache_status():
    """Diagnostic: see what's cached and TTL remaining."""
    return cache.status()

@router.post("/api/cache/clear", dependencies=[Depends(verify_token)])
@limiter.limit("5/minute")
def cache_clear(request: Request):
    """Force-clear all caches for fresh data on next request."""
    cache.invalidate()
    return {"status": "cleared", "timestamp": datetime.utcnow().isoformat() + "Z"}

