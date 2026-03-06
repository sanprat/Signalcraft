"""Strategy management router."""

import uuid
import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from app.models import StrategyRequest, StrategyResponse
from app.routers.auth import get_current_user, UserResponse

router = APIRouter(prefix="/api/strategy", tags=["strategy"])
STORE = Path("strategies")
STORE.mkdir(exist_ok=True)
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "candles"


@router.get("/symbols")
def list_symbols():
    """List available equity stock symbols."""
    nifty500 = DATA_DIR / "NIFTY500"
    if not nifty500.exists():
        return []
    symbols = sorted([d.name for d in nifty500.iterdir() if d.is_dir()])
    return symbols

@router.post("", response_model=StrategyResponse)
def create_strategy(body: StrategyRequest, current_user: UserResponse = Depends(get_current_user)):
    strategy_id = str(uuid.uuid4())[:8]
    payload = body.model_dump()
    payload["strategy_id"] = strategy_id
    payload["user_id"] = current_user.id  # Store owner user_id
    payload["created_at"] = datetime.utcnow().isoformat()

    # Handle backward compatibility: if symbols not provided but symbol is, convert to list
    if body.symbols is None and body.symbol is not None:
        payload["symbols"] = [body.symbol]
    elif body.symbols is not None:
        payload["symbols"] = body.symbols
    else:
        payload["symbols"] = []

    # Convert date objects to strings for JSON serialisation
    for k in ("backtest_from", "backtest_to"):
        if payload.get(k):
            payload[k] = str(payload[k])

    (STORE / f"{strategy_id}.json").write_text(json.dumps(payload, indent=2))

    # Return with symbols list
    return StrategyResponse(
        strategy_id=strategy_id,
        name=body.name,
        created_at=payload["created_at"],
        symbols=payload["symbols"]
    )


@router.get("/{strategy_id}")
def get_strategy(strategy_id: str, current_user: UserResponse = Depends(get_current_user)):
    path = STORE / f"{strategy_id}.json"
    if not path.exists():
        raise HTTPException(404, "Strategy not found")
    
    strategy = json.loads(path.read_text())
    # Verify ownership
    if strategy.get("user_id") is not None and strategy.get("user_id") != current_user.id:
        raise HTTPException(404, "Strategy not found")
    
    return strategy


@router.get("")
def list_strategies(current_user: UserResponse = Depends(get_current_user)):
    """List strategies for current user only."""
    strategies = []
    for f in sorted(STORE.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        strategy = json.loads(f.read_text())
        # Filter by user_id (if stored, otherwise include for backward compat)
        if strategy.get("user_id") is None or strategy.get("user_id") == current_user.id:
            strategies.append(strategy)
    return strategies
