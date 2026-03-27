"""
Strategy V2 Router — JSON-first strategy API endpoints.

This router provides endpoints for:
- Validating Strategy V2 JSON
- Running backtests
- Saving/loading strategies
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.schemas.strategy_v2 import (
    StrategyV2,
    StrategyBacktestRequestV2,
    StrategyValidationResult,
    StrategyValidationResult,
)
from app.routers.auth import get_current_user, UserResponse
from app.core.strategy_engine_v2 import StrategyEngineV2, validate_strategy_v2

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/strategy/v2", tags=["strategy-v2"])

# Strategy storage directory
STORE = Path("strategies")
STORE.mkdir(exist_ok=True)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class SaveStrategyRequest(BaseModel):
    """Request to save a strategy."""

    strategy: StrategyV2
    strategy_id: Optional[str] = Field(
        default=None,
        description="Optional ID for update (generates new if not provided)",
    )


class SaveStrategyResponse(BaseModel):
    """Response after saving a strategy."""

    strategy_id: str
    name: str
    created_at: str
    symbols: list[str]


class LoadStrategyResponse(BaseModel):
    """Response when loading a strategy."""

    strategy: StrategyV2
    strategy_id: str
    created_at: str
    updated_at: Optional[str] = None


# ============================================================================
# VALIDATION ENDPOINT
# ============================================================================


@router.post("/validate", response_model=StrategyValidationResult)
async def validate_strategy_v2_endpoint(strategy: StrategyV2):
    """
    Validate a Strategy V2 JSON payload.

    Checks:
    - Required fields present
    - Indicator names valid
    - Exit rules have priorities
    - Entry/exit logic valid
    """
    try:
        # Convert to dict for validation
        strategy_dict = strategy.model_dump()

        # Run validation
        result = validate_strategy_v2(strategy_dict)

        # Add Pydantic validation summary
        result["summary"] = {
            **result.get("summary", {}),
            "name": strategy.name,
            "symbols": strategy.symbols,
            "timeframe": strategy.timeframe,
            "entry_logic": strategy.entry_logic,
            "entry_conditions_count": len(strategy.entry_conditions),
            "exit_rules_count": len(strategy.exit_rules),
            "risk_config": strategy.risk.model_dump() if strategy.risk else {},
        }

        return StrategyValidationResult(**result)

    except Exception as e:
        logger.error(f"Validation error: {e}")
        return StrategyValidationResult(
            valid=False,
            errors=[str(e)],
            warnings=[],
        )


# ============================================================================
# BACKTEST ENDPOINTS
# ============================================================================


@router.post("/backtest")
async def run_backtest_v2(request: StrategyBacktestRequestV2):
    """
    Run backtest on all symbols in the strategy.

    Returns:
    - Per-symbol results with trades and equity curves
    - Combined metrics across all symbols
    - Execution time
    """
    try:
        engine = StrategyEngineV2()
        results = engine.run(request.strategy, mode=request.mode)
        return results

    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")


@router.post("/backtest/quick")
async def run_quick_backtest_v2(
    strategy: StrategyV2,
    days: int = Query(default=90, ge=30, le=365, description="Days to backtest"),
):
    """
    Run a quick backtest (last N days).

    Shorthand for /backtest with mode='quick'.
    """
    try:
        # Override date range
        from datetime import date, timedelta

        strategy.backtest_to = date.today().isoformat()
        strategy.backtest_from = (date.today() - timedelta(days=days)).isoformat()

        engine = StrategyEngineV2()
        results = engine.run(strategy, mode="quick")
        return results

    except Exception as e:
        logger.error(f"Quick backtest error: {e}")
        raise HTTPException(status_code=500, detail=f"Quick backtest failed: {str(e)}")


# ============================================================================
# STRATEGY STORAGE ENDPOINTS
# ============================================================================


@router.post("/save", response_model=SaveStrategyResponse)
async def save_strategy_v2(
    request: SaveStrategyRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Save a Strategy V2 to the database.

    If strategy_id is provided, updates existing strategy.
    Otherwise, generates a new ID.
    """
    try:
        # Generate or use provided ID
        strategy_id = request.strategy_id or str(uuid.uuid4())[:8]

        # Build payload
        payload = request.strategy.model_dump()
        payload["strategy_id"] = strategy_id
        payload["user_id"] = current_user.id
        payload["version"] = "2.0"
        payload["created_at"] = datetime.utcnow().isoformat()

        # Check if updating existing
        existing_path = STORE / f"{strategy_id}.json"
        if existing_path.exists():
            existing = json.loads(existing_path.read_text())
            if existing.get("user_id") != current_user.id:
                raise HTTPException(403, "Not authorized to modify this strategy")
            if existing.get("version") != "2.0":
                raise HTTPException(400, "Cannot update v1 strategy with v2 endpoint")
            payload["created_at"] = existing.get("created_at")
            payload["updated_at"] = datetime.utcnow().isoformat()

        # Save to file
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        existing_path.write_text(json.dumps(payload, indent=2))

        logger.info(f"[V2] Strategy saved: {strategy_id} by user {current_user.id}")

        return SaveStrategyResponse(
            strategy_id=strategy_id,
            name=request.strategy.name,
            created_at=payload["created_at"],
            symbols=request.strategy.symbols,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Save error: {e}")
        raise HTTPException(status_code=500, detail=f"Save failed: {str(e)}")


@router.get("/load/{strategy_id}", response_model=LoadStrategyResponse)
async def load_strategy_v2(
    strategy_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Load a Strategy V2 by ID.
    """
    try:
        path = STORE / f"{strategy_id}.json"

        if not path.exists():
            raise HTTPException(404, "Strategy not found")

        data = json.loads(path.read_text())

        # Check version
        if data.get("version") != "2.0":
            raise HTTPException(400, "This is not a v2 strategy")

        # Check ownership
        if data.get("user_id") and data.get("user_id") != current_user.id:
            raise HTTPException(404, "Strategy not found")

        # Parse into StrategyV2
        strategy = StrategyV2(**data)

        return LoadStrategyResponse(
            strategy=strategy,
            strategy_id=strategy_id,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Load error: {e}")
        raise HTTPException(status_code=500, detail=f"Load failed: {str(e)}")


@router.get("/list")
async def list_strategies_v2(
    current_user: UserResponse = Depends(get_current_user),
):
    """
    List all Strategy V2 for the current user.
    """
    try:
        strategies = []

        for f in sorted(
            STORE.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True
        ):
            try:
                data = json.loads(f.read_text())

                # Only v2 strategies
                if data.get("version") != "2.0":
                    continue

                # Check ownership
                if data.get("user_id") and data.get("user_id") != current_user.id:
                    continue

                strategies.append(
                    {
                        "strategy_id": data.get("strategy_id", f.stem),
                        "name": data.get("name", "Unnamed"),
                        "symbols": data.get("symbols", []),
                        "timeframe": data.get("timeframe", "1d"),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                    }
                )

            except Exception as e:
                logger.warning(f"Error reading strategy file {f}: {e}")
                continue

        return strategies

    except Exception as e:
        logger.error(f"List error: {e}")
        raise HTTPException(status_code=500, detail=f"List failed: {str(e)}")


@router.delete("/{strategy_id}")
async def delete_strategy_v2(
    strategy_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Delete a Strategy V2.
    """
    try:
        path = STORE / f"{strategy_id}.json"

        if not path.exists():
            raise HTTPException(404, "Strategy not found")

        data = json.loads(path.read_text())

        # Check version
        if data.get("version") != "2.0":
            raise HTTPException(400, "This is not a v2 strategy")

        # Check ownership
        if data.get("user_id") and data.get("user_id") != current_user.id:
            raise HTTPException(403, "Not authorized to delete this strategy")

        # Delete
        path.unlink()

        logger.info(f"[V2] Strategy deleted: {strategy_id}")

        return {"status": "success", "message": "Strategy deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


# ============================================================================
# INDICATOR REGISTRY ENDPOINT
# ============================================================================


class IndicatorInfo(BaseModel):
    """Information about an indicator."""

    name: str
    params: list[dict]
    description: str


@router.get("/indicators", response_model=list[IndicatorInfo])
async def list_indicators():
    """
    List all available indicators in the registry.
    """
    from app.schemas.strategy_v2 import INDICATOR_REGISTRY

    indicators = []
    for name, info in INDICATOR_REGISTRY.items():
        indicators.append(
            IndicatorInfo(
                name=name,
                params=[
                    {"name": p[0], "type": p[1].__name__, "default": p[2]}
                    for p in info["params"]
                ],
                description=info["description"],
            )
        )

    return indicators
