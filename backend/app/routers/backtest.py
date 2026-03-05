"""Backtest execution router."""

import uuid
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models import BacktestRequest, BacktestSummary
from app.core.backtest_engine import run_backtest
import pandas as pd

router = APIRouter(prefix="/api/backtest", tags=["backtest"])
STRATEGY_STORE = Path("strategies")
BACKTEST_STORE = Path("backtests")
BACKTEST_STORE.mkdir(exist_ok=True)


@router.post("/run")
def run(body: BacktestRequest):
    strat_path = STRATEGY_STORE / f"{body.strategy_id}.json"
    if not strat_path.exists():
        raise HTTPException(404, "Strategy not found")

    strategy = json.loads(strat_path.read_text())
    backtest_id = str(uuid.uuid4())[:8]

    result = run_backtest(strategy, backtest_id)

    # Store candles separately (large data)
    candles_df: pd.DataFrame = result.pop("candles", pd.DataFrame())
    result["summary"]["backtest_id"] = backtest_id

    out_dir = BACKTEST_STORE / backtest_id
    out_dir.mkdir(exist_ok=True)

    # Save summary + trades
    (out_dir / "summary.json").write_text(json.dumps(result["summary"]))
    (out_dir / "trades.json").write_text(json.dumps(result["trades"]))

    # Save candles as Parquet for fast retrieval
    if not candles_df.empty:
        candles_df["time"] = candles_df["time"].astype(str)
        candles_df[["time","open","high","low","close","volume"]].to_parquet(
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
        LIMIT {page_size} OFFSET {page * page_size}
    """).df()

    df["time_ts"] = pd.to_datetime(df["time"]).astype("int64") // 10**9

    return {
        "page": page,
        "total": int(duckdb.query(f"SELECT COUNT(*) FROM read_parquet('{path}')").fetchone()[0]),
        "candles": {
            "time":   df["time_ts"].tolist(),
            "open":   df["open"].tolist(),
            "high":   df["high"].tolist(),
            "low":    df["low"].tolist(),
            "close":  df["close"].tolist(),
            "volume": df["volume"].tolist(),
        }
    }
