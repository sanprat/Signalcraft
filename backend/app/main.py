import asyncio
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(dotenv_path="../.env")

from app.core.config import settings
from app.routers import strategy, backtest, live
from app.routers.quotes import (
    router as quotes_router,
    _dhan_feed,
    _broadcast_loop,
    _simulate_feed,
)
from app.routers.dhan import router as dhan_router
from app.routers.auth import router as auth_router
from app.routers.admin import router as admin_router
from app.routers.stocks import router as stocks_router
from app.routers.screeners import router as screeners_router
from app.routers.settings import router as settings_router
from app.core.signal_monitor import signal_monitor
from app.core.position_manager import position_manager

app = FastAPI(title=settings.API_TITLE, version=settings.API_VERSION)

app.add_middleware(
    CORSMiddleware,
    # Frontend runs on 3000; backend on 8001
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(strategy.router)
app.include_router(backtest.router)
app.include_router(live.router)
app.include_router(quotes_router)
app.include_router(dhan_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(stocks_router)
app.include_router(screeners_router)
app.include_router(settings_router)

@app.on_event("startup")
async def startup():
    # Simulation runs ALWAYS as baseline — Dhan data overrides when available
    asyncio.create_task(_simulate_feed())
    # Try real Dhan WebSocket in parallel (updates _quotes when ticks arrive)
    asyncio.create_task(_dhan_feed())
    # Broadcast latest _quotes to all connected frontend clients every second
    asyncio.create_task(_broadcast_loop())
    
    # Start services for automated trading
    await signal_monitor.start()
    await position_manager.start()


@app.get("/health")
def health():
    return {"status": "ok", "app": "SignalCraft", "port": 8001}
