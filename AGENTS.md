# Pytrader — Agent Memory & Rules

## Project Overview
- **Name:** SignalCraft / Zenalys
- **Website:** https://www.zenalys.com
- **VPS:** Contabo (217.217.250.174)
- **Language:** Python (3.11+)
- **Framework:** FastAPI with Uvicorn
- **Frontend:** Next.js React
- **Database:** PostgreSQL (primary), SQLite (dev fallback)
- **Cache:** Redis
- **Infrastructure:** Docker, Docker Compose, Nginx
- **Git:** github.com/sanprat/Signalcraft

## Production Architecture (VPS)
```
User → https://www.zenalys.com (Nginx)
                  ├── / (static) → Next.js Frontend
                  └── /api/* → FastAPI Backend (port 8001)

All services run on VPS (217.217.250.174) via Docker:
- signalcraft-backend: FastAPI on port 8001
- signalcraft-db: PostgreSQL on port 5432
- signalcraft-redis: Redis on port 6379
```

## Directory Structure
- `backend/app/` — FastAPI application (main, routers, models, core)
- `backend/scripts/` — data fetching and processing scripts
- `data-scripts/` — daily updaters and historical downloaders
- `data/candles/` — OHLCV parquet files (NIFTY500 stocks, FnO options)
- `backend/tests/` — test suite
- `frontend/` — Next.js React frontend
- `strategies/` — stored algorithmic strategies
- `backtests/` — backtest results (generated at runtime)

## Build / Lint / Test Commands

### Docker Operations
```bash
# Start all services (postgres, redis, backend, frontend)
docker-compose up -d

# Rebuild containers (after Dockerfile/requirements.txt changes)
docker-compose up -d --build

# View backend logs
docker logs signalcraft-backend -f

# Restart specific service
docker-compose restart backend
```

### Backend (Python)
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run FastAPI dev server (local)
uvicorn app.main:app --reload --port 8001

# Run a single test file
python -m pytest tests/test_user_isolation.py -v

# Run a specific test function
python -m pytest tests/test_user_isolation.py::test_isolation -v

# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=app --cov-report=html
```

### Frontend (Next.js)
```bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev

# Build for production
npm run build

# Start production server
npm run start
```

## Code Style Guidelines

### Imports (PEP 8 Order)
1. Standard library imports (os, sys, datetime, typing, etc.)
2. Third-party imports (fastapi, pandas, numpy, etc.)
3. Local application imports (from app.core..., from app.routers...)

```python
# Good example
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd

from app.core.config import settings
from app.core.database import get_db
```

### Formatting
- Indentation: 4 spaces (no tabs)
- Line length: 88-100 characters (Black-compatible)
- Use double quotes for strings
- Trailing commas in multi-line structures

### Type Hints
- Use type hints for function parameters and return values
- Use `Optional[Type]` for nullable values
- Use `List[Type]`, `Dict[Key, Value]` from typing module
- Use Pydantic models for request/response validation

```python
def calculate_pnl(entry: float, exit: float, qty: int) -> float:
    return (exit - entry) * qty

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    ...
```

### Naming Conventions
- Functions/variables: `snake_case` (`get_candle_data`, `entry_price`)
- Classes: `PascalCase` (`StrategyRequest`, `PositionManager`)
- Constants: `UPPER_SNAKE_CASE` (`MAX_TRADES_PER_DAY`)
- Private methods: `_leading_underscore` (`_validate_input`)

### Error Handling
- Always catch specific exceptions, not bare `except:`
- Use `logging` module, never `print()` for errors
- Return meaningful error messages in API responses
- Use FastAPI's `HTTPException` with proper status codes

```python
import logging

logger = logging.getLogger(__name__)

try:
    data = fetch_dhan_data(symbol)
except requests.RequestException as e:
    logger.error(f"Failed to fetch data for {symbol}: {e}")
    raise HTTPException(status_code=503, detail="Broker API unavailable")
except ValueError as e:
    logger.warning(f"Invalid data format for {symbol}: {e}")
    raise HTTPException(status_code=422, detail="Invalid data format")
```

### Database Operations
- Use context managers for DB connections
- Always close connections properly
- Use parameterized queries (never f-strings for SQL)

```python
with get_db() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    result = cursor.fetchone()
```

## Critical Rules — All Agents Must Follow
- NEVER hardcode API keys, secrets, or credentials
- ALWAYS use environment variables for sensitive config (see `.env`, `.env.db`)
- Trading logic errors = immediate block — financial loss risk
- ALWAYS handle exceptions in trade execution and API calls
- NEVER modify `.env` files directly
- NEVER commit `.env` files or database backups

## Coding Conventions
- Use descriptive commit messages: `[feat/fix/refactor]: description`
- Follow existing naming conventions in the codebase
- Always add error handling for Dhan API calls
- Use logging not print statements
- Add docstrings for public functions and classes

## Known Patterns
- Dhan API returns column-oriented format `{open: [...], high: [...]}` not row-oriented
- FnO options use OHLCV including volume for strategy/backtesting
- `ec0_*` files = current week live options
- `ec1_*` files = expired options historical data
- DataFrame columns: `open`, `high`, `low`, `close`, `volume`

## Docker
- Rebuild required if: Dockerfile or requirements.txt changed
- No rebuild needed for: pure Python script changes
- Services: postgres (5433→5432), redis (6380→6379), backend (8001), frontend (3000)
- Nginx handles routing: zenalys.com → frontend, zenalys.com/api → backend

## VPS Deployment
- All services run via Docker on VPS: `docker compose` commands
- After reviewer approves → manually run `git pull origin main` on VPS, then rebuild if needed
- Check logs: `docker logs signalcraft-backend -f`
- Restart backend: `docker compose restart backend`
- Restart all services: `docker compose up -d`
- Data location on VPS: `/home/signalcraft/data/candles/NIFTY500/`
