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

import pandas as pd

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.schemas.strategy_v2 import (
    StrategyV2,
    StrategyBacktestRequestV2,
    StrategyValidationResult,
    StrategyValidationResult,
)
from app.routers.auth import get_current_user, UserResponse
from app.core.strategy_engine_v2 import (
    StrategyEngineV2,
    validate_strategy_v2,
    DATA_DIR,
    TIMEFRAME_MAP,
    _normalize_candle_times,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/strategy/v2", tags=["strategy-v2"])

# Strategy storage directory
STORE = Path("strategies")
STORE.mkdir(exist_ok=True)

# Backtest results directory
BACKTESTS = Path("backtests")
BACKTESTS.mkdir(exist_ok=True)


def _save_candles_parquet(
    backtest_dir: Path,
    symbols: list,
    timeframe: str,
    from_date: str,
    to_date: str,
):
    """Load candles from data dir and save as parquet for chart display."""
    tf_file = TIMEFRAME_MAP.get(timeframe, timeframe)
    all_candles = []

    for symbol in symbols:
        parquet_path = DATA_DIR / "NIFTY500" / symbol / f"{tf_file}.parquet"
        if not parquet_path.exists():
            logger.warning(f"[V2] Candle file not found: {parquet_path}")
            continue

        try:
            df = pd.read_parquet(parquet_path)

            # Normalize time column
            if "__index_level_0__" in df.columns:
                df = df.rename(columns={"__index_level_0__": "time"})
            elif df.index.name and "time" not in df.columns:
                df = df.reset_index().rename(columns={df.index.name: "time"})

            if "time" in df.columns:
                df = _normalize_candle_times(df, parquet_path, symbol, timeframe)

            # Filter by date range if provided
            if from_date and to_date and "time" in df.columns:
                start = pd.Timestamp(from_date).tz_localize("Asia/Kolkata")
                end = pd.Timestamp(to_date).tz_localize("Asia/Kolkata")
                df = df[df["time"] >= start]
                df = df[df["time"] <= end]

            # Keep only needed columns
            keep = [
                c
                for c in ["time", "open", "high", "low", "close", "volume"]
                if c in df.columns
            ]
            if keep:
                df = df[keep]
                all_candles.append(df)
                logger.info(f"[V2] Loaded {len(df)} candles for {symbol}")
        except Exception as e:
            logger.error(f"[V2] Failed to load candles for {symbol}: {e}")

    if all_candles:
        combined = pd.concat(all_candles, ignore_index=True)
        combined["time"] = combined["time"].astype(str)
        combined.to_parquet(
            backtest_dir / "candles.parquet", compression="lz4", index=False
        )
        logger.info(
            f"[V2] Saved {len(combined)} candles to {backtest_dir / 'candles.parquet'}"
        )
    else:
        logger.warning(f"[V2] No candle data to save for backtest in {backtest_dir}")


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
        # Return error with summary
        return StrategyValidationResult(
            valid=False,
            errors=[str(e)],
            warnings=[],
            summary={
                "name": strategy.name if strategy else "Unknown",
                "symbols": strategy.symbols if strategy else [],
                "timeframe": strategy.timeframe if strategy else "N/A",
                "entry_logic": strategy.entry_logic if strategy else "N/A",
                "entry_conditions_count": len(strategy.entry_conditions)
                if strategy
                else 0,
                "exit_rules_count": len(strategy.exit_rules) if strategy else 0,
                "risk_config": strategy.risk.model_dump()
                if strategy and strategy.risk
                else {},
            },
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

        # Get backtest_id from results (generated by engine)
        backtest_id = results.get("backtest_id", str(uuid.uuid4())[:8])

        # Create backtest directory
        backtest_dir = BACKTESTS / backtest_id
        backtest_dir.mkdir(parents=True, exist_ok=True)

        # Extract combined metrics for summary
        combined = results.get("combined", {})

        # Collect all trades from per_symbol results
        all_trades = []
        for symbol, symbol_result in results.get("per_symbol", {}).items():
            trades = symbol_result.get("trades", [])
            for trade in trades:
                trade["symbol"] = symbol  # Tag with symbol
            all_trades.extend(trades)

        # Calculate summary metrics
        trades_count = len(all_trades)
        winning_trades = len([t for t in all_trades if t.get("pnl", 0) > 0])
        losing_trades = len([t for t in all_trades if t.get("pnl", 0) <= 0])
        win_rate = (winning_trades / trades_count * 100) if trades_count > 0 else 0
        total_pnl = sum(t.get("pnl", 0) for t in all_trades)
        avg_trade_pnl = total_pnl / trades_count if trades_count > 0 else 0

        # Find best/worst trades
        best_trade = max((t.get("pnl", 0) for t in all_trades), default=0)
        worst_trade = min((t.get("pnl", 0) for t in all_trades), default=0)

        # Calculate max drawdown from equity curve (aggregate all)
        max_drawdown = combined.get("max_drawdown", 0)

        # Count total candles processed
        total_candles = sum(
            len(symbol_result.get("equity_curve", []))
            for symbol_result in results.get("per_symbol", {}).values()
        )

        # Save summary.json
        summary = {
            "backtest_id": backtest_id,
            "strategy_name": results.get("strategy_name", "Unknown"),
            "timeframe": request.strategy.timeframe,
            "mode": results.get("mode", "quick"),
            "total_trades": trades_count,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "max_drawdown": round(max_drawdown, 2),
            "avg_trade_pnl": round(avg_trade_pnl, 2),
            "best_trade": round(best_trade, 2),
            "worst_trade": round(worst_trade, 2),
            "candle_count": total_candles,
            "date_range": results.get("date_range", ""),
            "execution_time_ms": results.get("execution_time_ms", 0),
            "symbols": request.strategy.symbols,
        }
        (backtest_dir / "summary.json").write_text(json.dumps(summary, indent=2))

        # Save trades.json
        (backtest_dir / "trades.json").write_text(json.dumps(all_trades, indent=2))

        # Save candles.parquet for chart display
        _save_candles_parquet(
            backtest_dir=backtest_dir,
            symbols=request.strategy.symbols,
            timeframe=request.strategy.timeframe,
            from_date=request.strategy.backtest_from or "",
            to_date=request.strategy.backtest_to or "",
        )

        # Collect all equity curve points for combined chart
        all_equity_points = []
        current_equity = 0.0
        for symbol, symbol_result in results.get("per_symbol", {}).items():
            for point in symbol_result.get("equity_curve", []):
                # Adjust equity to be cumulative across symbols
                all_equity_points.append(
                    {
                        "time": point.get("time", ""),
                        "equity": point.get("equity", 0) + current_equity,
                        "symbol": symbol,
                    }
                )
                current_equity = point.get("equity", 0)

        # Save equity_curve.json
        (backtest_dir / "equity_curve.json").write_text(
            json.dumps(all_equity_points, indent=2)
        )

        # Save per_symbol results for detailed analysis
        (backtest_dir / "per_symbol.json").write_text(
            json.dumps(results.get("per_symbol", {}), indent=2, default=str)
        )

        logger.info(
            f"[V2] Backtest completed: {backtest_id}, {trades_count} trades, PnL: {total_pnl:.2f}"
        )

        # Return response with backtest_id and summary
        return {
            "backtest_id": backtest_id,
            "summary": summary,
            "message": "Backtest completed successfully",
        }

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

        # Get backtest_id from results
        backtest_id = results.get("backtest_id", str(uuid.uuid4())[:8])

        # Create backtest directory
        backtest_dir = BACKTESTS / backtest_id
        backtest_dir.mkdir(parents=True, exist_ok=True)

        # Extract combined metrics
        combined = results.get("combined", {})

        # Collect all trades
        all_trades = []
        for symbol, symbol_result in results.get("per_symbol", {}).items():
            trades = symbol_result.get("trades", [])
            for trade in trades:
                trade["symbol"] = symbol
            all_trades.extend(trades)

        # Calculate summary metrics
        trades_count = len(all_trades)
        winning_trades = len([t for t in all_trades if t.get("pnl", 0) > 0])
        losing_trades = len([t for t in all_trades if t.get("pnl", 0) <= 0])
        win_rate = (winning_trades / trades_count * 100) if trades_count > 0 else 0
        total_pnl = sum(t.get("pnl", 0) for t in all_trades)
        avg_trade_pnl = total_pnl / trades_count if trades_count > 0 else 0
        best_trade = max((t.get("pnl", 0) for t in all_trades), default=0)
        worst_trade = min((t.get("pnl", 0) for t in all_trades), default=0)
        max_drawdown = combined.get("max_drawdown", 0)
        total_candles = sum(
            len(symbol_result.get("equity_curve", []))
            for symbol_result in results.get("per_symbol", {}).values()
        )

        # Save summary.json
        summary = {
            "backtest_id": backtest_id,
            "strategy_name": results.get("strategy_name", "Unknown"),
            "timeframe": strategy.timeframe,
            "mode": "quick",
            "total_trades": trades_count,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "max_drawdown": round(max_drawdown, 2),
            "avg_trade_pnl": round(avg_trade_pnl, 2),
            "best_trade": round(best_trade, 2),
            "worst_trade": round(worst_trade, 2),
            "candle_count": total_candles,
            "date_range": results.get("date_range", ""),
            "execution_time_ms": results.get("execution_time_ms", 0),
            "symbols": strategy.symbols,
        }
        (backtest_dir / "summary.json").write_text(json.dumps(summary, indent=2))

        # Save trades.json
        (backtest_dir / "trades.json").write_text(json.dumps(all_trades, indent=2))

        # Save candles.parquet for chart display
        _save_candles_parquet(
            backtest_dir=backtest_dir,
            symbols=strategy.symbols,
            timeframe=strategy.timeframe,
            from_date=strategy.backtest_from or "",
            to_date=strategy.backtest_to or "",
        )

        # Save equity_curve.json
        all_equity_points = []
        current_equity = 0.0
        for symbol, symbol_result in results.get("per_symbol", {}).items():
            for point in symbol_result.get("equity_curve", []):
                all_equity_points.append(
                    {
                        "time": point.get("time", ""),
                        "equity": point.get("equity", 0) + current_equity,
                        "symbol": symbol,
                    }
                )
                current_equity = point.get("equity", 0)
        (backtest_dir / "equity_curve.json").write_text(
            json.dumps(all_equity_points, indent=2)
        )

        # Save per_symbol results
        (backtest_dir / "per_symbol.json").write_text(
            json.dumps(results.get("per_symbol", {}), indent=2, default=str)
        )

        logger.info(
            f"[V2] Quick backtest completed: {backtest_id}, {trades_count} trades, PnL: {total_pnl:.2f}"
        )

        return {
            "backtest_id": backtest_id,
            "summary": summary,
            "message": "Quick backtest completed successfully",
        }

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

                entry_conditions = data.get("entry_conditions") or data.get("entry_logic_details", [])
                exit_rules = data.get("exit_rules") or data.get("exit_logic_details", [])

                strategies.append(
                    {
                        "id": data.get("strategy_id", f.stem),
                        "name": data.get("name", "Unnamed"),
                        "asset_type": data.get("asset_type", "EQUITY"),
                        "symbols": data.get("symbols", []),
                        "timeframe": data.get("timeframe", "1d"),
                        "entry_conditions_count": len(entry_conditions) if isinstance(entry_conditions, list) else 0,
                        "exit_rules_count": len(exit_rules) if isinstance(exit_rules, list) else 0,
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
