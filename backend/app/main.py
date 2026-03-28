import asyncio
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

load_dotenv(dotenv_path="../.env")

# ── Configure root logger so ALL app module logs appear in Docker output ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Suppress noisy third-party loggers
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

from app.core.config import settings
from app.core.rate_limiter import limiter, rate_limit_exceeded_handler
from app.routers import strategy, backtest, live
from app.routers.strategy_v2 import router as strategy_v2_router
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

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    # Frontend runs on 3000; backend on 8001
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# HTTPS redirect middleware for production
logger = logging.getLogger(__name__)


@app.middleware("http")
async def https_redirect_middleware(request: Request, call_next):
    """Redirect HTTP to HTTPS in production."""
    # Only redirect if USE_HTTPS environment variable is set
    if os.getenv("USE_HTTPS", "").lower() == "true":
        if request.url.scheme == "http":
            # Convert http to https
            https_url = request.url.replace(scheme="https")
            return RedirectResponse(url=str(https_url), status_code=301)
    return await call_next(request)


app.include_router(strategy.router)
app.include_router(backtest.router)
app.include_router(live.router)
app.include_router(strategy_v2_router)
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

    # Position manager requires PostgreSQL with raw SQL support
    # For SQLite (local testing), it will fail gracefully
    try:
        await position_manager.start()
    except Exception as e:
        logger.warning(
            f"Position manager unavailable (SQLite mode or DB error): {e}. "
            "Live trading features will be limited."
        )


@app.get("/health")
def health():
    return {"status": "ok", "app": "SignalCraft", "port": 8001}
