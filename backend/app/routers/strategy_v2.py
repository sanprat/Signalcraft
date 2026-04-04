"""
Strategy V2 Router — JSON-first strategy API endpoints.

This router provides endpoints for:
- Validating Strategy V2 JSON
- Running backtests
- Saving/loading strategies
"""

import json
import logging
import os
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

# ── Backtest cache (optional dependency) ────────────────────────────────────
try:
    from app.core.backtest_cache import (
        build_cache_key,
        build_deterministic_backtest_id,
        get_cached_backtest,
        set_cached_backtest,
        assemble_cache_payload,
        rebuild_artifacts_from_cache,
        purge_backtest_cache,
        register_cache_key_for_strategy,
        BACKTEST_CACHE_TTL_SECONDS,
    )

    _cache_available = True
except ImportError:
    _cache_available = False
    logger.warning("Backtest cache module not available; cache will be disabled")

router = APIRouter(prefix="/api/strategy/v2", tags=["strategy-v2"])

# Strategy storage directory
STORE = Path("strategies")
STORE.mkdir(exist_ok=True)

# Backtest results directory
BACKTESTS = Path("backtests")
BACKTESTS.mkdir(exist_ok=True)


def _aggregate_equity_curve(per_symbol: dict) -> list[dict]:
    """Combine per-symbol equity curves into a single cumulative list."""
    all_equity_points = []
    current_equity = 0.0
    for symbol, symbol_result in per_symbol.items():
        for point in symbol_result.get("equity_curve", []):
            all_equity_points.append(
                {
                    "time": point.get("time", ""),
                    "equity": point.get("equity", 0) + current_equity,
                    "symbol": symbol,
                }
            )
            current_equity = point.get("equity", 0)
    return all_equity_points


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


def _is_intraday(timeframe: str) -> bool:
    """A timeframe is intraday if it's NOT 1D/1W (case-insensitive)."""
    return timeframe.upper() not in ("1D", "1W")


def _build_chart_payload(backtest_dir: Path, full: bool = False) -> Optional[Path]:
    """
    Build a chart.json artifact for instant chart rendering.

    Reads trades.json and candles.parquet from backtest_dir, computes a
    smart display range around trades (or 90-day fallback), builds
    annotations from trades, and writes chart.json atomically.

    When full=True, writes to chart.full.json instead of chart.json.

    Returns the path to chart.json, or None if candles.parquet is missing.
    """
    import duckdb

    candles_path = backtest_dir / "candles.parquet"
    trades_path = backtest_dir / "trades.json"

    if not candles_path.exists():
        return None

    # Load trades
    trades: list = []
    if trades_path.exists():
        trades = json.loads(trades_path.read_text())

    # Load summary for symbol, timeframe
    summary_path = backtest_dir / "summary.json"
    summary: dict = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())

    symbols = summary.get("symbols", [])
    symbol = symbols[0] if symbols else ""
    # summary.json stores "timeframe"; fallback from directory contents
    timeframe = summary.get("timeframe", "1d")
    backtest_id = backtest_dir.name

    # Determine time range
    if trades:
        sorted_trades = sorted(trades, key=lambda t: t.get("entry_time", "") or "")
        first_entry = sorted_trades[0].get("entry_time")
        last_exit = sorted_trades[-1].get("exit_time")

        first_ts = pd.Timestamp(first_entry, tz="UTC")
        last_ts = pd.Timestamp(last_exit, tz="UTC")

        intraday = _is_intraday(timeframe)
        if intraday:
            # ±5 trading days (~1 week calendar)
            buffer = pd.Timedelta(days=9)
        else:
            # ±20 candles (daily/weekly)
            buffer = pd.Timedelta(days=20)

        display_from = first_ts - buffer
        display_to = last_ts + buffer
    else:
        # No trades: fallback to last 90 days from latest candle
        latest_ts = duckdb.query(f"""
            SELECT MAX(time) FROM read_parquet('{candles_path}')
        """).fetchone()[0]
        latest_ts = pd.Timestamp(latest_ts, tz="UTC")
        display_from = latest_ts - pd.Timedelta(days=90)
        display_to = latest_ts

    # Check if we need to cap at 5000 candles
    candle_count_in_range = duckdb.query(f"""
        SELECT COUNT(*) FROM read_parquet('{candles_path}')
        WHERE time >= '{display_from.isoformat()}'
          AND time <= '{display_to.isoformat()}'
    """).fetchone()[0]

    # Get full range stats always
    full_row = duckdb.query(f"""
        SELECT MIN(time) as min_t, MAX(time) as max_t
        FROM read_parquet('{candles_path}')
    """).fetchone()
    full_from = pd.Timestamp(full_row[0], tz="UTC")
    full_to = pd.Timestamp(full_row[1], tz="UTC")

    df = None
    is_partial = False

    if candle_count_in_range <= 5000 or full:
        # Fetch everything in range
        df = duckdb.query(f"""
            SELECT time, open, high, low, close, volume
            FROM read_parquet('{candles_path}')
            WHERE time BETWEEN '{display_from.isoformat()}'
                        AND '{display_to.isoformat()}'
            ORDER BY time
        """).df()
        is_partial = candle_count_in_range > 5000
    else:
        # Smart-capped: ensure full trade window, split remaining budget
        if trades:
            first_entry = pd.Timestamp(sorted_trades[0]["entry_time"], tz="UTC")
            last_exit = pd.Timestamp(sorted_trades[-1]["exit_time"], tz="UTC")

            window_count = duckdb.query(f"""
                SELECT COUNT(*) FROM read_parquet('{candles_path}')
                WHERE time >= '{first_entry.isoformat()}'
                  AND time <= '{last_exit.isoformat()}'
            """).fetchone()[0]

            remaining = max(0, 5000 - window_count)
            half = remaining // 2

            left_df = duckdb.query(f"""
                SELECT time, open, high, low, close, volume
                FROM read_parquet('{candles_path}')
                WHERE time < '{first_entry.isoformat()}'
                ORDER BY time DESC
                LIMIT {half}
            """).df()

            right_remaining = remaining - len(left_df)
            center_df = duckdb.query(f"""
                SELECT time, open, high, low, close, volume
                FROM read_parquet('{candles_path}')
                WHERE time >= '{first_entry.isoformat()}'
                  AND time <= '{last_exit.isoformat()}'
                ORDER BY time
            """).df()

            right_df = duckdb.query(f"""
                SELECT time, open, high, low, close, volume
                FROM read_parquet('{candles_path}')
                WHERE time > '{last_exit.isoformat()}'
                ORDER BY time ASC
                LIMIT {max(0, right_remaining)}
            """).df()

            df = pd.concat([left_df[::-1], center_df, right_df], ignore_index=True)
        else:
            # No trades: cap to 5000 evenly via LIMIT
            df = duckdb.query(f"""
                SELECT time, open, high, low, close, volume
                FROM read_parquet('{candles_path}')
                ORDER BY time
                LIMIT 5000
            """).df()

    if df is None or df.empty:
        return None

    # Convert times to Asia/Kolkata ISO strings
    tz_mumbai = "Asia/Kolkata"
    parsed_times = pd.to_datetime(df["time"], utc=True).dt.tz_convert(tz_mumbai)
    df["time_iso"] = parsed_times.apply(lambda v: v.isoformat())

    # Convert display_from and display_to to Kolkata time
    def _to_kolkata(ts):
        return pd.Timestamp(ts, tz="UTC").tz_convert(tz_mumbai)

    display_from_str = df["time_iso"].iloc[0]
    display_to_str = df["time_iso"].iloc[-1]
    full_from_str = _to_kolkata(full_from).isoformat()
    full_to_str = _to_kolkata(full_to).isoformat()

    # Build annotations
    annotations: list = []
    for trade in trades:
        entry_time_iso = trade.get("entry_time", "")
        annotations.append(
            {
                "time": int(pd.Timestamp(entry_time_iso).timestamp() * 1000),
                "value": trade.get("entry_price", 0),
                "text": f"BUY {trade.get('trade_no', '')}",
                "color": "#059669",
                "backgroundColor": "#ECFDF5",
                "side": "below",
            }
        )
        exit_time_iso = trade.get("exit_time", "")
        annotations.append(
            {
                "time": int(pd.Timestamp(exit_time_iso).timestamp() * 1000),
                "value": trade.get("exit_price", 0),
                "text": f"SELL {trade.get('trade_no', '')}",
                "color": "#DC2626",
                "backgroundColor": "#FEF2F2",
                "side": "above",
            }
        )

    # Check if more data exists on either side
    has_more_left = False
    has_more_right = False
    df_times = pd.to_datetime(df["time"], utc=True)
    if len(df_times) > 0:
        min_display = df_times.min()
        max_display = df_times.max()
        if min_display > full_from:
            has_more_left = True
        if max_display < full_to:
            has_more_right = True

    payload = {
        "backtest_id": backtest_id,
        "generated_at": datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "trade_count": len(trades),
        "symbol": symbol,
        "timeframe": timeframe,
        "display_from": display_from_str,
        "display_to": display_to_str,
        "full_from": full_from_str,
        "full_to": full_to_str,
        "is_partial": is_partial,
        "has_more_left": has_more_left,
        "has_more_right": has_more_right,
        "candles": {
            "time": df["time_iso"].tolist(),
            "open": df["open"].tolist(),
            "high": df["high"].tolist(),
            "low": df["low"].tolist(),
            "close": df["close"].tolist(),
            "volume": df["volume"].tolist(),
        },
        "annotations": annotations,
    }

    # Atomic write
    filename = "chart.full.json" if full else "chart.json"
    tmp_path = candles_path.with_name(filename + ".tmp")
    target = candles_path.with_name(filename)
    with open(tmp_path, "w") as f:
        json.dump(payload, f)
    os.replace(str(tmp_path), str(target))

    return target


def _ensure_chart_json(backtest_dir: Path) -> Optional[Path]:
    """
    Staleness-aware builder. Builds chart.json if missing, or if
    trades.json or candles.parquet have been modified since last build.
    """
    chart_path = backtest_dir / "chart.json"
    trades_path = backtest_dir / "trades.json"
    candles_path = backtest_dir / "candles.parquet"

    if candles_path.exists():
        candles_mtime = candles_path.stat().st_mtime

        trades_mtime = trades_path.stat().st_mtime if trades_path.exists() else 0

        rebuild = False
        if chart_path.exists():
            chart_mtime = chart_path.stat().st_mtime
            if candles_mtime > chart_mtime or trades_mtime > chart_mtime:
                rebuild = True
        else:
            rebuild = True

        if rebuild:
            return _build_chart_payload(backtest_dir)
        return chart_path

    return chart_path if chart_path.exists() else None


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

    Results are cached in Redis keyed by strategy content hash,
    symbols, timeframe, date range, and data file mtimes.
    Same exact backtest returns the cached result on second run.
    """
    try:
        # Build deterministic cache key and backtest_id
        strategy_dict = request.strategy.model_dump()
        strategy_id = (
            request.strategy.strategy_id
            if hasattr(request.strategy, "strategy_id")
            else None
        )
        cache_key = (
            build_cache_key(
                strategy_dict=strategy_dict,
                strategy_id=strategy_id,
                mode=request.mode,
                symbols=request.strategy.symbols,
                timeframe=request.strategy.timeframe,
                backtest_from=request.strategy.backtest_from or "",
                backtest_to=request.strategy.backtest_to or "",
            )
            if _cache_available
            else None
        )

        deterministic_id = (
            build_deterministic_backtest_id(cache_key)
            if cache_key
            else str(uuid.uuid4())[:10]
        )
        backtest_dir = BACKTESTS / deterministic_id

        # ── Cache hit ────────────────────────────────────────────────────
        if _cache_available and cache_key:
            cached = get_cached_backtest(cache_key)
            if cached:
                summary = cached.get("summary", {})
                summary["backtest_id"] = deterministic_id

                # Rebuild disk artifacts if missing (frontend chart page needs them)
                if not (backtest_dir / "summary.json").exists():
                    logger.warning(
                        "[V2] Cache hit but artifacts missing for %s, "
                        "rebuilding from cached payload",
                        deterministic_id,
                    )
                    rebuild_artifacts_from_cache(
                        backtest_id=deterministic_id,
                        backtests_dir=BACKTESTS,
                        cached_payload=cached,
                    )

                # Restore candles.parquet if it was in the original payload but
                # is now missing on disk (rebuild_artifacts_from_cache skips it)
                if (
                    cached.get("had_candles_parquet")
                    and not (backtest_dir / "candles.parquet").exists()
                ):
                    logger.info(
                        "[V2] Cache hit: restoring candles.parquet for %s",
                        deterministic_id,
                    )
                    _save_candles_parquet(
                        backtest_dir=backtest_dir,
                        symbols=request.strategy.symbols,
                        timeframe=request.strategy.timeframe,
                        from_date=request.strategy.backtest_from or "",
                        to_date=request.strategy.backtest_to or "",
                    )

                # Ensure chart.json exists and is fresh
                _ensure_chart_json(backtest_dir)

                logger.info(
                    f"[V2] Backtest cache HIT: {deterministic_id}, "
                    f"{summary.get('total_trades', 0)} trades",
                )
                return {
                    "backtest_id": deterministic_id,
                    "summary": summary,
                    "message": "Backtest loaded from cache",
                }

            logger.info(
                f"[V2] Backtest cache MISS for key={cache_key[:24]!r}, computing...",
            )

        # ── Run engine ───────────────────────────────────────────────────
        engine = StrategyEngineV2()
        results = engine.run(
            request.strategy,
            mode=request.mode,
            deterministic_id=deterministic_id,
        )

        # Create backtest directory (may already exist from earlier rebuild)
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

        # Collect equity curve points
        all_equity_points = _aggregate_equity_curve(results.get("per_symbol", {}))

        # ── Save to disk ─────────────────────────────────────────────────
        summary = {
            "backtest_id": deterministic_id,
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
        (backtest_dir / "trades.json").write_text(json.dumps(all_trades, indent=2))
        (backtest_dir / "equity_curve.json").write_text(
            json.dumps(all_equity_points, indent=2)
        )
        (backtest_dir / "per_symbol.json").write_text(
            json.dumps(results.get("per_symbol", {}), indent=2, default=str)
        )

        # Save candles.parquet for chart display (check existing first)
        has_candles = (backtest_dir / "candles.parquet").exists()
        if not has_candles:
            _save_candles_parquet(
                backtest_dir=backtest_dir,
                symbols=request.strategy.symbols,
                timeframe=request.strategy.timeframe,
                from_date=request.strategy.backtest_from or "",
                to_date=request.strategy.backtest_to or "",
            )
            has_candles = (backtest_dir / "candles.parquet").exists()

        # Build chart.json artifact
        _build_chart_payload(backtest_dir)

        # ── Store in Redis ───────────────────────────────────────────────
        if _cache_available and cache_key:
            payload = assemble_cache_payload(
                summary=summary,
                trades=all_trades,
                per_symbol=results.get("per_symbol", {}),
                equity_curve=all_equity_points,
                has_candles_parquet=has_candles,
            )
            set_cached_backtest(cache_key, payload, ttl=BACKTEST_CACHE_TTL_SECONDS)
            if strategy_id:
                register_cache_key_for_strategy(strategy_id, cache_key)

        logger.info(
            f"[V2] Backtest completed: {deterministic_id}, "
            f"{trades_count} trades, PnL: {total_pnl:.2f}"
        )

        return {
            "backtest_id": deterministic_id,
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

    Shorthand for /backtest with mode='quick'. Shares the same cache.
    """
    try:
        from datetime import date, timedelta

        # Override date range
        strategy.backtest_to = date.today().isoformat()
        strategy.backtest_from = (date.today() - timedelta(days=days)).isoformat()
        mode = "quick"

        # Build cache key
        strategy_dict = strategy.model_dump()
        strategy_id = strategy.strategy_id if hasattr(strategy, "strategy_id") else None
        cache_key = (
            build_cache_key(
                strategy_dict=strategy_dict,
                strategy_id=strategy_id,
                mode=mode,
                symbols=strategy.symbols,
                timeframe=strategy.timeframe,
                backtest_from=strategy.backtest_from or "",
                backtest_to=strategy.backtest_to or "",
            )
            if _cache_available
            else None
        )

        deterministic_id = (
            build_deterministic_backtest_id(cache_key)
            if cache_key
            else str(uuid.uuid4())[:10]
        )
        backtest_dir = BACKTESTS / deterministic_id

        # Cache hit
        if _cache_available and cache_key:
            cached = get_cached_backtest(cache_key)
            if cached:
                summary = cached.get("summary", {})
                summary["backtest_id"] = deterministic_id
                if not (backtest_dir / "summary.json").exists():
                    rebuild_artifacts_from_cache(
                        backtest_id=deterministic_id,
                        backtests_dir=BACKTESTS,
                        cached_payload=cached,
                    )
                if (
                    cached.get("had_candles_parquet")
                    and not (backtest_dir / "candles.parquet").exists()
                ):
                    _save_candles_parquet(
                        backtest_dir=backtest_dir,
                        symbols=strategy.symbols,
                        timeframe=strategy.timeframe,
                        from_date=strategy.backtest_from or "",
                        to_date=strategy.backtest_to or "",
                    )
                # Ensure chart.json exists and is fresh
                _ensure_chart_json(backtest_dir)

                logger.info(
                    f"[V2] Quick backtest cache HIT: {deterministic_id}",
                )
                return {
                    "backtest_id": deterministic_id,
                    "summary": summary,
                    "message": "Quick backtest loaded from cache",
                }

            logger.info(
                f"[V2] Quick backtest cache MISS, computing...",
            )

        engine = StrategyEngineV2()
        results = engine.run(strategy, mode=mode, deterministic_id=deterministic_id)

        backtest_dir.mkdir(parents=True, exist_ok=True)

        combined = results.get("combined", {})
        all_trades = []
        for symbol, symbol_result in results.get("per_symbol", {}).items():
            for trade in symbol_result.get("trades", []):
                trade["symbol"] = symbol
            all_trades.extend(trades)

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

        all_equity_points = _aggregate_equity_curve(results.get("per_symbol", {}))

        summary = {
            "backtest_id": deterministic_id,
            "strategy_name": results.get("strategy_name", "Unknown"),
            "timeframe": strategy.timeframe,
            "mode": mode,
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
        (backtest_dir / "trades.json").write_text(json.dumps(all_trades, indent=2))
        (backtest_dir / "equity_curve.json").write_text(
            json.dumps(all_equity_points, indent=2)
        )
        (backtest_dir / "per_symbol.json").write_text(
            json.dumps(results.get("per_symbol", {}), indent=2, default=str)
        )

        has_candles = (backtest_dir / "candles.parquet").exists()
        if not has_candles:
            _save_candles_parquet(
                backtest_dir=backtest_dir,
                symbols=strategy.symbols,
                timeframe=strategy.timeframe,
                from_date=strategy.backtest_from or "",
                to_date=strategy.backtest_to or "",
            )
            has_candles = (backtest_dir / "candles.parquet").exists()

        # Build chart.json artifact
        _build_chart_payload(backtest_dir)

        if _cache_available and cache_key:
            payload = assemble_cache_payload(
                summary=summary,
                trades=all_trades,
                per_symbol=results.get("per_symbol", {}),
                equity_curve=all_equity_points,
                has_candles_parquet=has_candles,
            )
            set_cached_backtest(cache_key, payload, ttl=BACKTEST_CACHE_TTL_SECONDS)
            if strategy_id:
                register_cache_key_for_strategy(strategy_id, cache_key)

        logger.info(
            f"[V2] Quick backtest completed: {deterministic_id}, "
            f"{trades_count} trades, PnL: {total_pnl:.2f}"
        )

        return {
            "backtest_id": deterministic_id,
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
        payload["created_at"] = datetime.now(datetime.timezone.utc).isoformat()

        # Check if updating existing
        existing_path = STORE / f"{strategy_id}.json"
        if existing_path.exists():
            existing = json.loads(existing_path.read_text())
            if existing.get("user_id") != current_user.id:
                raise HTTPException(403, "Not authorized to modify this strategy")
            if existing.get("version") != "2.0":
                raise HTTPException(400, "Cannot update v1 strategy with v2 endpoint")
            payload["created_at"] = existing.get("created_at")
            payload["updated_at"] = datetime.now(datetime.timezone.utc).isoformat()

            # Check for rename collision with another user strategy
            if existing.get("name", "").lower() != request.strategy.name.lower():
                for f in STORE.glob("*.json"):
                    try:
                        data = json.loads(f.read_text())
                        if (
                            data.get("user_id") == current_user.id
                            and data.get("version") == "2.0"
                            and data.get("name", "").lower()
                            == request.strategy.name.lower()
                        ):
                            raise HTTPException(
                                400,
                                f"A strategy with the name '{request.strategy.name}' already exists.",
                            )
                    except HTTPException:
                        raise
                    except Exception:
                        logger.warning(f"Failed to read strategy file {f}: skipping")
                        continue
        else:
            # New strategy – check for duplicate name among current user's strategies
            for f in STORE.glob("*.json"):
                try:
                    data = json.loads(f.read_text())
                    if (
                        data.get("user_id") == current_user.id
                        and data.get("version") == "2.0"
                        and data.get("name", "").lower()
                        == request.strategy.name.lower()
                    ):
                        raise HTTPException(
                            400,
                            f"A strategy with the name '{request.strategy.name}' already exists.",
                        )
                except HTTPException:
                    raise
                except Exception:
                    logger.warning(f"Failed to read strategy file {f}: skipping")
                    continue

        # Save to file
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        existing_path.write_text(json.dumps(payload, indent=2))

        # Invalidate all cached backtests for this strategy
        if _cache_available:
            purged = purge_backtest_cache(strategy_id)
            if purged:
                logger.info(
                    f"[V2] Purged {purged} backtest cache entries "
                    f"for strategy {strategy_id}"
                )

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

                entry_conditions = data.get("entry_conditions") or data.get(
                    "entry_logic_details", []
                )
                exit_rules = data.get("exit_rules") or data.get(
                    "exit_logic_details", []
                )

                strategies.append(
                    {
                        "strategy_id": data.get("strategy_id", f.stem),
                        "name": data.get("name", "Unnamed"),
                        "asset_type": data.get("asset_type", "EQUITY"),
                        "symbols": data.get("symbols", []),
                        "timeframe": data.get("timeframe", "1d"),
                        "entry_conditions_count": len(entry_conditions)
                        if isinstance(entry_conditions, list)
                        else 0,
                        "exit_rules_count": len(exit_rules)
                        if isinstance(exit_rules, list)
                        else 0,
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
