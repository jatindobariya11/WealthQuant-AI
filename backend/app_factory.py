from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import cache, market, quant, providers, health, websocket

def create_app() -> FastAPI:
    app = FastAPI(title="WealthQuant API")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.include_router(cache.router, tags=["cache"])
    app.include_router(market.router, tags=["market"])
    app.include_router(quant.router, tags=["quant"])
    app.include_router(providers.router, tags=["providers"])
    app.include_router(health.router, tags=["health"])
    app.include_router(websocket.router, tags=["websocket"])
    
    return app
