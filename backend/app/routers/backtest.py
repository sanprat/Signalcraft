"""Backtest execution router."""

import uuid
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from app.models import BacktestRequest, BacktestSummary
from app.core.backtest_engine import run_backtest
from app.routers.auth import get_current_user, UserResponse
import pandas as pd

router = APIRouter(prefix="/api/backtest", tags=["backtest"])
STRATEGY_STORE = Path("strategies")
BACKTEST_STORE = Path("backtests")
BACKTEST_STORE.mkdir(exist_ok=True)


@router.post("/run")
def run(body: BacktestRequest, current_user: UserResponse = Depends(get_current_user)):
    strat_path = STRATEGY_STORE / f"{body.strategy_id}.json"
    if not strat_path.exists():
        raise HTTPException(404, "Strategy not found")

    strategy = json.loads(strat_path.read_text())
    backtest_id = str(uuid.uuid4())[:8]

    result = run_backtest(strategy, backtest_id)

    # Check if backtest failed due to missing options data
    if result.get("summary", {}).get("error") == "MISSING_OPTIONS_DATA":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "MISSING_OPTIONS_DATA",
                "message": result["summary"]["error_message"],
                "required_files": result["summary"]["missing_data"],
                "hint": (
                    "Options backtesting requires two data files:\n"
                    "1. Underlying spot data (NIFTY/BANKNIFTY/FINNIFTY prices)\n"
                    "2. Options strike data (CE/PE parquet files with dhan_ec*_*.parquet naming)"
                ),
            },
        )

    # Store candles separately (large data)
    candles_df: pd.DataFrame = result.pop("candles", pd.DataFrame())
    result["summary"]["backtest_id"] = backtest_id
    result["summary"]["user_id"] = current_user.id  # Store owner
    result["summary"]["timeframe"] = strategy.get("timeframe")
    result["summary"]["strategy_name"] = strategy.get("name")

    if strategy.get("symbols") and "symbols" not in result["summary"]:
        result["summary"]["symbols"] = strategy.get("symbols")
    elif strategy.get("symbol") and "symbol" not in result["summary"]:
        result["summary"]["symbol"] = strategy.get("symbol")
    elif strategy.get("index") and "symbol" not in result["summary"]:
        result["summary"]["symbol"] = strategy.get("index")

    out_dir = BACKTEST_STORE / backtest_id
    out_dir.mkdir(exist_ok=True)

    # Save summary + trades
    (out_dir / "summary.json").write_text(json.dumps(result["summary"]))
    (out_dir / "trades.json").write_text(json.dumps(result["trades"]))

    # Save candles as Parquet for fast retrieval
    if not candles_df.empty:
        candles_df["time"] = candles_df["time"].astype(str)
        candles_df[["time", "open", "high", "low", "close", "volume"]].to_parquet(
            out_dir / "candles.parquet", compression="lz4", index=False
        )

    return result["summary"]


@router.get("/{backtest_id}/summary")
def get_summary(backtest_id: str):
    path = BACKTEST_STORE / backtest_id / "summary.json"
    if not path.exists():
        raise HTTPException(404, "Backtest not found")
    return json.loads(path.read_text())


@router.get("/{backtest_id}/trades")
def get_trades(backtest_id: str):
    path = BACKTEST_STORE / backtest_id / "trades.json"
    if not path.exists():
        raise HTTPException(404, "Backtest not found")
    return json.loads(path.read_text())


@router.get("/{backtest_id}/candles")
def get_candles(backtest_id: str, page: int = 0, page_size: int = 500):
    """Return candles in pages of 500 for chart streaming."""
    import duckdb

    path = BACKTEST_STORE / backtest_id / "candles.parquet"
    if not path.exists():
        raise HTTPException(404, "Candle data not found")

    df = duckdb.query(f"""
        SELECT time, open, high, low, close, volume
        FROM read_parquet('{path}')
        ORDER BY time
        LIMIT {page_size} OFFSET {page * page_size}
    """).df()

    parsed_time = pd.to_datetime(df["time"], utc=True).dt.tz_convert("Asia/Kolkata")
    df["time_iso"] = parsed_time.apply(lambda value: value.isoformat())

    return {
        "page": page,
        "total": int(
            duckdb.query(f"SELECT COUNT(*) FROM read_parquet('{path}')").fetchone()[0]
        ),
        "candles": {
            "time": df["time_iso"].tolist(),
            "open": df["open"].tolist(),
            "high": df["high"].tolist(),
            "low": df["low"].tolist(),
            "close": df["close"].tolist(),
            "volume": df["volume"].tolist(),
        },
    }


@router.get("")
def list_backtests(current_user: UserResponse = Depends(get_current_user)):
    """List all recent backtests for current user only."""
    results = []
    if not BACKTEST_STORE.exists():
        return results

    # Look for summary.json in each subfolder
    for d in sorted(
        BACKTEST_STORE.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True
    ):
        if d.is_dir():
            summary_path = d / "summary.json"
            if summary_path.exists():
                try:
                    summary = json.loads(summary_path.read_text())
                    # Filter by user_id (if stored, otherwise include for backward compat)
                    if (
                        summary.get("user_id") is None
                        or summary.get("user_id") == current_user.id
                    ):
                        results.append(summary)
                except Exception:
                    continue
    return results
