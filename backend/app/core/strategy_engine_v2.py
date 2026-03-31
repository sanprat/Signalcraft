"""
Strategy Engine V2 — Main execution engine for JSON-first strategies.

This module handles:
- Multi-symbol backtesting
- Exit rule priority execution
- Risk management
- Result aggregation
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable

import pandas as pd
import numpy as np

from app.schemas.strategy_v2 import (
    StrategyV2,
    StrategyBacktestRequestV2,
    BacktestResultV2,
    SymbolResultV2,
    TradeRecordV2,
    EquityCurvePoint,
    INDICATOR_REGISTRY,
)
from app.core.strategy_builder_v2 import (
    StrategyBuilderV2,
    ExecutableStrategy,
    CompiledExitRule,
    ExpressionEvaluator,
    ConditionBuilder,
)

logger = logging.getLogger(__name__)


def _resolve_data_dir() -> Path:
    """Resolve candle data path across local and container layouts."""
    env_path = os.getenv("SIGNALCRAFT_DATA_DIR")
    candidates = [
        Path(env_path) if env_path else None,
        Path("/app/data/candles"),
        Path(__file__).resolve().parents[2] / "data" / "candles",
        Path(__file__).resolve().parents[3] / "data" / "candles",
    ]

    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate

    # Fall back to the expected container path for clearer logging.
    return Path("/app/data/candles")


# Path to Parquet data
DATA_DIR = _resolve_data_dir()

# Timeframe mapping to file format
TIMEFRAME_MAP = {
    "1m": "1m",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "1d": "1D",
    "1w": "1W",
}


class StrategyEngineV2:
    """
    Main execution engine for Strategy V2.

    Features:
    - Multi-symbol backtesting
    - Exit rule priority execution
    - Daily risk management
    - Equity curve tracking
    """

    def __init__(self):
        self.builder = StrategyBuilderV2()

    def run(self, strategy: StrategyV2, mode: str = "quick") -> Dict[str, Any]:
        """
        Run backtest on ALL symbols in strategy.

        Args:
            strategy: StrategyV2 Pydantic model
            mode: "quick" (last 6 months) or "full" (all data)

        Returns:
            Dictionary with per_symbol results and combined metrics
        """
        start_time = time.time()
        backtest_id = str(uuid.uuid4())[:8]

        # Determine date range
        from_date, to_date = self._get_date_range(strategy, mode)

        logger.info(
            f"[V2] Starting backtest: {strategy.name}, "
            f"symbols={strategy.symbols}, mode={mode}, "
            f"range={from_date} to {to_date}"
        )

        # Build executable strategy
        executable = self.builder.build(strategy)

        # Run on each symbol
        per_symbol_results = {}

        for symbol in strategy.symbols:
            try:
                result = self._run_single_symbol(
                    symbol=symbol,
                    executable=executable,
                    from_date=from_date,
                    to_date=to_date,
                    backtest_id=backtest_id,
                )
                per_symbol_results[symbol] = result
                logger.info(
                    f"[V2] {symbol}: {result.metrics.get('total_trades', 0)} trades, "
                    f"pnl={result.metrics.get('total_pnl', 0):.2f}"
                )
            except Exception as e:
                logger.error(f"[V2] Error running backtest for {symbol}: {e}")
                per_symbol_results[symbol] = SymbolResultV2(
                    symbol=symbol,
                    trades=[],
                    equity_curve=[],
                    metrics={"error": str(e)},
                )

        # Aggregate results
        combined = self._aggregate_results(per_symbol_results)

        execution_time_ms = (time.time() - start_time) * 1000

        return {
            "backtest_id": backtest_id,
            "strategy_name": strategy.name,
            "mode": mode,
            "per_symbol": {k: v.model_dump() for k, v in per_symbol_results.items()},
            "combined": combined,
            "date_range": f"{from_date} to {to_date}",
            "execution_time_ms": round(execution_time_ms, 2),
        }

    def _get_date_range(self, strategy: StrategyV2, mode: str) -> Tuple[date, date]:
        """Determine backtest date range."""
        to_date = date.today()

        # Check if strategy has explicit dates
        if strategy.backtest_to:
            try:
                to_date = date.fromisoformat(strategy.backtest_to)
            except ValueError:
                pass

        if strategy.backtest_from:
            try:
                from_date = date.fromisoformat(strategy.backtest_from)
                return from_date, to_date
            except ValueError:
                pass

        # Mode-based default
        if mode == "quick":
            from_date = to_date - timedelta(days=180)
        else:
            from_date = to_date - timedelta(days=365 * 3)  # 3 years

        return from_date, to_date

    def _run_single_symbol(
        self,
        symbol: str,
        executable: ExecutableStrategy,
        from_date: date,
        to_date: date,
        backtest_id: str,
    ) -> SymbolResultV2:
        """Run backtest for a single symbol."""
        # Load data
        df = self._load_candles(
            symbol=symbol,
            asset_type=executable.name,  # Use strategy name for FnO detection
            timeframe=executable.timeframe,
            from_date=from_date,
            to_date=to_date,
        )

        if df.empty:
            logger.warning(f"[V2] No data for {symbol}")
            return SymbolResultV2(
                symbol=symbol,
                trades=[],
                equity_curve=[],
                metrics={"total_trades": 0, "error": "No data available"},
            )

        # Compute indicators
        df = self._compute_indicators(df, executable)

        # Run backtest simulation
        trades, equity_curve = self._simulate(df, executable)

        # Compute metrics
        metrics = self._compute_metrics(trades, equity_curve, from_date, to_date)

        # Convert to response models
        trade_records = [TradeRecordV2(**trade) for trade in trades]

        equity_points = [EquityCurvePoint(**point) for point in equity_curve]

        return SymbolResultV2(
            symbol=symbol,
            trades=trade_records,
            equity_curve=equity_points,
            metrics=metrics,
        )

    def _load_candles(
        self,
        symbol: str,
        asset_type: str,
        timeframe: str,
        from_date: date,
        to_date: date,
    ) -> pd.DataFrame:
        """Load OHLCV candles from Parquet files."""
        # Determine file path
        tf_file = TIMEFRAME_MAP.get(timeframe, timeframe)

        # For EQUITY (NIFTY500 stocks)
        parquet_path = DATA_DIR / "NIFTY500" / symbol / f"{tf_file}.parquet"

        if not parquet_path.exists():
            logger.warning(f"[V2] Parquet not found: {parquet_path}")
            return pd.DataFrame()

        try:
            df = pd.read_parquet(parquet_path)

            # Handle index column if present
            if "__index_level_0__" in df.columns:
                df = df.rename(columns={"__index_level_0__": "time"})
            elif df.index.name and "time" not in df.columns:
                df = df.reset_index().rename(columns={df.index.name: "time"})

            # Ensure time column
            if "time" not in df.columns:
                logger.error(f"[V2] No 'time' column in {parquet_path}")
                return pd.DataFrame()

            # Convert time
            df["time"] = pd.to_datetime(df["time"], utc=True)
            df["time"] = df["time"].dt.tz_convert("Asia/Kolkata")

            # Filter by date range
            df = df[
                (df["time"].dt.date >= from_date) & (df["time"].dt.date <= to_date)
            ].sort_values("time")

            # Ensure required columns
            required_cols = ["time", "open", "high", "low", "close", "volume"]
            for col in required_cols:
                if col not in df.columns:
                    df[col] = 0

            # Filter market hours for intraday
            if timeframe != "1d" and timeframe != "1w":
                df = df[
                    (df["time"].dt.hour > 9)
                    | ((df["time"].dt.hour == 9) & (df["time"].dt.minute >= 15))
                ]
                df = df[
                    (df["time"].dt.hour < 15)
                    | ((df["time"].dt.hour == 15) & (df["time"].dt.minute <= 30))
                ]

            logger.info(f"[V2] Loaded {len(df)} candles for {symbol}")
            return df.reset_index(drop=True)

        except Exception as e:
            logger.error(f"[V2] Error loading {symbol}: {e}")
            return pd.DataFrame()

    def _compute_indicators(
        self, df: pd.DataFrame, executable: ExecutableStrategy
    ) -> pd.DataFrame:
        """Compute all indicators needed for the strategy."""
        from app.schemas.strategy_v2 import IndicatorRef

        # Collect all indicators and their params from the strategy conditions
        indicators_to_compute: Dict[str, List] = {}  # "SMA" -> [[20], [50]]

        def _extract_indicators(expr):
            """Recursively extract IndicatorRef from condition expressions."""
            if isinstance(expr, IndicatorRef):
                key = expr.name.upper()
                params = tuple(
                    int(p) if isinstance(p, float) and p == int(p) else p
                    for p in expr.params
                )
                if key not in indicators_to_compute:
                    indicators_to_compute[key] = []
                if params not in indicators_to_compute[key]:
                    indicators_to_compute[key].append(params)
            elif hasattr(expr, "__dict__"):
                for val in expr.__dict__.values():
                    if hasattr(val, "type") or isinstance(val, IndicatorRef):
                        _extract_indicators(val)

        for cond in executable.entry_conditions:
            # The compiled condition's description is str(cond) which isn't useful
            # We need to extract from the original Condition objects
            pass

        # Also extract from the strategy builder's source conditions
        # Since ExecutableStrategy doesn't store originals, extract from description
        # Better approach: compute indicators based on what the evaluators need

        # Collect indicator names referenced in evaluator descriptions
        all_indicator_names = set()
        for cond in executable.entry_conditions:
            desc = cond.description
            # Parse "IndicatorRef(name='SMA', params=[20])" patterns
            import re

            for match in re.finditer(r"name='(\w+)'.*?params=\[([^\]]*)\]", desc):
                name = match.group(1).upper()
                params_str = match.group(2)
                params = []
                for p in params_str.split(","):
                    p = p.strip().strip("'\"")
                    try:
                        params.append(int(p))
                    except ValueError:
                        try:
                            params.append(float(p))
                        except ValueError:
                            params.append(p)
                key = tuple(params) if params else ()
                all_indicator_names.add((name, key))

        # Compute indicators
        for name, params in all_indicator_names:
            col_key = "_".join(str(p) for p in params) if params else ""
            col_name = f"indicator_{name}_{col_key}" if col_key else f"indicator_{name}"

            if name == "SMA" and params:
                period = int(params[0])
                df[col_name] = df["close"].rolling(period).mean()
                logger.debug(f"[V2] Computed {col_name} with period={period}")

            elif name == "EMA" and params:
                period = int(params[0])
                df[col_name] = df["close"].ewm(span=period, adjust=False).mean()
                logger.debug(f"[V2] Computed {col_name} with period={period}")

            elif name == "RSI" and params:
                period = int(params[0])
                df[col_name] = self._compute_rsi(df["close"], period)
                logger.debug(f"[V2] Computed {col_name} with period={period}")

            elif name == "ATR" and params:
                period = int(params[0])
                high_low = df["high"] - df["low"]
                high_close = (df["high"] - df["close"].shift()).abs()
                low_close = (df["low"] - df["close"].shift()).abs()
                true_range = pd.concat([high_low, high_close, low_close], axis=1).max(
                    axis=1
                )
                df[col_name] = true_range.rolling(period).mean()

            elif name == "VOLUME":
                df[col_name] = df["volume"]

            else:
                logger.warning(f"[V2] Unknown indicator: {name} with params {params}")

        # Forward-fill NaN values
        df = df.ffill().fillna(0)

        return df

    def _compute_rsi(self, close: pd.Series, period: int) -> pd.Series:
        """Compute RSI indicator."""
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, 1e-10)
        return 100 - (100 / (1 + rs))

    def _simulate(
        self, df: pd.DataFrame, executable: ExecutableStrategy
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Simulate trading on the dataframe.

        Returns:
            Tuple of (trades, equity_curve)
        """
        trades = []
        equity_curve = []

        # State tracking
        in_trade = False
        entry_price = 0.0
        entry_time = None
        trade_no = 0
        equity = 0.0
        peak = 0.0

        # Daily tracking
        daily_trades: Dict[date, int] = {}
        daily_loss: Dict[date, float] = {}

        # Trade state for exit rules
        trade_state: Dict[str, Any] = {
            "in_trade": False,
            "entry_price": 0.0,
            "highest_price": 0.0,
        }

        risk = executable.risk_config
        max_trades_per_day = risk.get("max_trades_per_day", 3)
        max_loss_per_day = risk.get("max_loss_per_day", 5000)
        quantity = risk.get("quantity", 1)
        reentry_after_sl = risk.get("reentry_after_sl", False)

        # Get entry evaluator
        entry_evaluator = self._build_entry_evaluator(df, executable)

        # Get exit evaluators (sorted by priority)
        exit_evaluators = executable.exit_rules

        for idx, row in df.iterrows():
            bar_date = row["time"].date()
            bar_time = row["time"].strftime("%H:%M")

            # Reset daily counters
            if bar_date not in daily_trades:
                daily_trades[bar_date] = 0
                daily_loss[bar_date] = 0.0

            # Update equity curve
            if in_trade:
                # Unrealized P&L
                unrealized_pnl = (row["close"] - entry_price) * quantity
                current_equity = equity + unrealized_pnl
            else:
                current_equity = equity

            peak = max(peak, current_equity)
            drawdown = peak - current_equity
            drawdown_pct = (drawdown / peak * 100) if peak > 0 else 0

            equity_curve.append(
                {
                    "time": row["time"].isoformat(),
                    "equity": round(current_equity, 2),
                    "drawdown": round(drawdown, 2),
                    "drawdown_pct": round(drawdown_pct, 2),
                }
            )

            # Handle exit if in trade
            if in_trade:
                exit_reason = self._check_exit_rules(
                    row=row,
                    trade_state=trade_state,
                    exit_rules=exit_evaluators,
                )

                if exit_reason:
                    # Close trade
                    exit_price = row["close"]
                    pnl = (exit_price - entry_price) * quantity
                    pnl_pct = (exit_price - entry_price) / entry_price * 100

                    trades.append(
                        {
                            "trade_no": trade_no,
                            "symbol": row.get("symbol", "UNKNOWN"),
                            "entry_time": entry_time.isoformat() if entry_time else "",
                            "entry_price": round(entry_price, 2),
                            "exit_time": row["time"].isoformat(),
                            "exit_price": round(exit_price, 2),
                            "pnl": round(pnl, 2),
                            "pnl_pct": round(pnl_pct, 2),
                            "exit_reason": exit_reason,
                            "quantity": quantity,
                            "holding_period": len(equity_curve)
                            - trade_state.get("entry_bar", 0),
                        }
                    )

                    # Update equity
                    equity += pnl
                    daily_loss[bar_date] = daily_loss.get(bar_date, 0) + min(pnl, 0)
                    in_trade = False
                    trade_state["in_trade"] = False

                    # Check re-entry after SL
                    if exit_reason == "SL" and not reentry_after_sl:
                        continue

            # Check entry if not in trade
            if not in_trade:
                # Check daily limits
                if daily_trades.get(bar_date, 0) >= max_trades_per_day:
                    continue
                if abs(daily_loss.get(bar_date, 0)) >= max_loss_per_day:
                    continue

                # Check entry signal
                try:
                    if entry_evaluator(row):
                        # Enter trade
                        in_trade = True
                        entry_price = row["close"]
                        entry_time = row["time"]
                        trade_no += 1
                        daily_trades[bar_date] = daily_trades.get(bar_date, 0) + 1

                        # Update trade state
                        trade_state = {
                            "in_trade": True,
                            "entry_price": entry_price,
                            "entry_time": entry_time,
                            "highest_price": entry_price,
                            "entry_bar": len(equity_curve),
                        }
                except Exception as e:
                    logger.debug(f"Entry evaluation error: {e}")

        if in_trade and not df.empty:
            last_row = df.iloc[-1]
            exit_price = last_row["close"]
            pnl = (exit_price - entry_price) * quantity
            pnl_pct = (exit_price - entry_price) / entry_price * 100

            trades.append(
                {
                    "trade_no": trade_no,
                    "symbol": last_row.get("symbol", "UNKNOWN"),
                    "entry_time": entry_time.isoformat() if entry_time else "",
                    "entry_price": round(entry_price, 2),
                    "exit_time": last_row["time"].isoformat(),
                    "exit_price": round(exit_price, 2),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "exit_reason": "END_OF_TEST",
                    "quantity": quantity,
                    "holding_period": len(equity_curve) - trade_state.get("entry_bar", 0),
                }
            )
            equity += pnl

        return trades, equity_curve

    def _build_entry_evaluator(
        self, df: pd.DataFrame, executable: ExecutableStrategy
    ) -> Callable[[pd.Series], bool]:
        """Build entry condition evaluator for the strategy."""
        # Use the pre-built evaluators from StrategyBuilderV2
        # They already handle IndicatorRef, PriceRef, ValueRef, MathExpr correctly
        conditions = executable.entry_conditions
        logic = executable.entry_logic

        if not conditions:
            return lambda row: False

        # Pre-compute crossover states for crosses_above/crosses_below operators
        # Store previous bar's indicator values in a shifted column
        crossover_cols = {}
        for cond in conditions:
            desc = cond.description
            if "crosses_above" in desc or "crosses_below" in desc:
                # Extract indicator column names from description
                import re

                names = re.findall(r"name='(\w+)'.*?params=\[([^\]]*)\]", desc)
                for name, params_str in names:
                    params = params_str.replace(", ", "_").replace(",", "_")
                    col = (
                        f"indicator_{name}_{params}" if params else f"indicator_{name}"
                    )
                    prev_col = f"{col}_prev"
                    if col in df.columns and prev_col not in df.columns:
                        df[prev_col] = df[col].shift(1)
                        crossover_cols[col] = prev_col

        # Wrap the builder's evaluators to handle crossover detection
        def make_evaluator(cond):
            def evaluator(row: pd.Series) -> bool:
                desc = cond.description
                # Handle crosses_above: left > right AND left_prev <= right_prev
                if "crosses_above" in desc:
                    try:
                        left_val = self._get_indicator_value(row, desc, "left")
                        right_val = self._get_indicator_value(row, desc, "right")
                        left_prev = self._get_prev_indicator_value(
                            row, desc, "left", df, crossover_cols
                        )
                        right_prev = self._get_prev_indicator_value(
                            row, desc, "right", df, crossover_cols
                        )
                        if any(
                            np.isnan(v)
                            for v in [left_val, right_val, left_prev, right_prev]
                        ):
                            return False
                        return left_val > right_val and left_prev <= right_prev
                    except:
                        return False
                # Handle crosses_below: left < right AND left_prev >= right_prev
                elif "crosses_below" in desc:
                    try:
                        left_val = self._get_indicator_value(row, desc, "left")
                        right_val = self._get_indicator_value(row, desc, "right")
                        left_prev = self._get_prev_indicator_value(
                            row, desc, "left", df, crossover_cols
                        )
                        right_prev = self._get_prev_indicator_value(
                            row, desc, "right", df, crossover_cols
                        )
                        if any(
                            np.isnan(v)
                            for v in [left_val, right_val, left_prev, right_prev]
                        ):
                            return False
                        return left_val < right_val and left_prev >= right_prev
                    except:
                        return False
                # Default: use the builder's compiled evaluator
                else:
                    try:
                        return cond.evaluator(row)
                    except:
                        return False

            return evaluator

        condition_builders = [make_evaluator(cond) for cond in conditions]

        # Return combined evaluator
        if logic == "ALL":

            def entry_all(row: pd.Series) -> bool:
                try:
                    return all(e(row) for e in condition_builders)
                except:
                    return False

            return entry_all
        else:  # ANY

            def entry_any(row: pd.Series) -> bool:
                try:
                    return any(e(row) for e in condition_builders)
                except:
                    return False

            return entry_any

    def _get_indicator_value(self, row, desc, side):
        """Extract indicator value from row based on description."""
        import re

        # Find the IndicatorRef for the given side
        pattern = rf"{side}=IndicatorRef\(name='(\w+)', params=\[([^\]]*)\]\)"
        match = re.search(pattern, desc)
        if not match:
            # Try alternate format: left=IndicatorRef(...)
            pattern = r"name='(\w+)'.*?params=\[([^\]]*)\]"
            matches = re.findall(pattern, desc)
            if matches:
                name, params_str = matches[0] if side == "left" else matches[-1]
            else:
                return np.nan
        else:
            name = match.group(1)
            params_str = match.group(2)

        col_key = params_str.replace(", ", "_").replace(",", "_")
        col = f"indicator_{name}_{col_key}" if col_key else f"indicator_{name}"
        return row.get(col, np.nan)

    def _get_prev_indicator_value(self, row, desc, side, df, crossover_cols):
        """Get previous bar's indicator value (for crossover detection)."""
        val = self._get_indicator_value(row, desc, side)
        col = None
        import re

        pattern = r"name='(\w+)'.*?params=\[([^\]]*)\]"
        matches = re.findall(pattern, desc)
        if matches:
            idx = 0 if side == "left" else -1
            name, params_str = matches[idx]
            col_key = params_str.replace(", ", "_").replace(",", "_")
            col = f"indicator_{name}_{col_key}" if col_key else f"indicator_{name}"

        if col and col in crossover_cols:
            prev_col = crossover_cols[col]
            return row.get(prev_col, np.nan)
        return np.nan

    def _check_exit_rules(
        self,
        row: pd.Series,
        trade_state: Dict,
        exit_rules: List[CompiledExitRule],
    ) -> Optional[str]:
        """Check exit rules in priority order. Returns exit reason or None."""
        for rule in exit_rules:
            try:
                reason = rule.evaluator(row, trade_state)
                if reason:
                    return reason
            except Exception as e:
                logger.debug(f"Exit rule error ({rule.rule_type}): {e}")

        return None

    def _compute_metrics(
        self,
        trades: List[Dict],
        equity_curve: List[Dict],
        from_date: date,
        to_date: date,
    ) -> Dict[str, Any]:
        """Compute summary metrics from trades and equity curve."""
        if not trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "max_drawdown": 0.0,
                "max_drawdown_pct": 0.0,
                "avg_trade_pnl": 0.0,
                "best_trade": 0.0,
                "worst_trade": 0.0,
                "avg_holding_period": 0,
                "candle_count": len(equity_curve),
                "date_range": f"{from_date} to {to_date}",
            }

        pnls = [t["pnl"] for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        holding_periods = [t.get("holding_period", 0) for t in trades]

        # Calculate max drawdown from equity curve
        max_dd = 0.0
        max_dd_pct = 0.0
        for point in equity_curve:
            dd = point["drawdown"]
            dd_pct = point["drawdown_pct"]
            if dd > max_dd:
                max_dd = dd
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

        return {
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0.0,
            "total_pnl": round(sum(pnls), 2),
            "max_drawdown": round(max_dd, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "avg_trade_pnl": round(sum(pnls) / len(trades), 2) if trades else 0.0,
            "best_trade": round(max(pnls), 2) if pnls else 0.0,
            "worst_trade": round(min(pnls), 2) if pnls else 0.0,
            "avg_holding_period": round(sum(holding_periods) / len(holding_periods), 1)
            if holding_periods
            else 0,
            "candle_count": len(equity_curve),
            "date_range": f"{from_date} to {to_date}",
        }

    def _aggregate_results(
        self, per_symbol: Dict[str, SymbolResultV2]
    ) -> Dict[str, Any]:
        """Aggregate results across all symbols."""
        all_trades = []
        all_pnls = []
        total_candles = 0

        for symbol, result in per_symbol.items():
            trades_data = (
                result.trades if hasattr(result, "trades") else result.get("trades", [])
            )
            all_trades.extend(trades_data)

            for trade in trades_data:
                pnl = trade.pnl if hasattr(trade, "pnl") else trade.get("pnl", 0)
                if pnl:
                    all_pnls.append(pnl)

            equity_data = (
                result.equity_curve
                if hasattr(result, "equity_curve")
                else result.get("equity_curve", [])
            )
            total_candles += len(equity_data)

        if not all_trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "max_drawdown": 0.0,
                "avg_trade_pnl": 0.0,
                "symbols_traded": list(per_symbol.keys()),
            }

        wins = [p for p in all_pnls if p > 0]
        losses = [p for p in all_pnls if p <= 0]

        return {
            "total_trades": len(all_trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(len(wins) / len(all_trades) * 100, 1),
            "total_pnl": round(sum(all_pnls), 2),
            "max_drawdown": 0.0,  # Would need full equity curve
            "avg_trade_pnl": round(sum(all_pnls) / len(all_trades), 2),
            "best_trade": round(max(all_pnls), 2) if all_pnls else 0.0,
            "worst_trade": round(min(all_pnls), 2) if all_pnls else 0.0,
            "symbols_traded": list(per_symbol.keys()),
            "symbols_with_trades": len(
                [
                    s
                    for s, r in per_symbol.items()
                    if len(r.trades if hasattr(r, "trades") else r.get("trades", []))
                    > 0
                ]
            ),
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def validate_strategy_v2(strategy: Dict) -> Dict[str, Any]:
    """
    Validate a strategy JSON.

    Returns validation result with errors and warnings.
    """
    errors = []
    warnings = []

    # Check required fields
    required_fields = ["name", "symbols", "entry_conditions", "exit_rules"]
    for field in required_fields:
        if field not in strategy:
            errors.append(f"Missing required field: {field}")

    # Check symbols
    if "symbols" in strategy:
        if not isinstance(strategy["symbols"], list):
            errors.append("'symbols' must be a list")
        elif len(strategy["symbols"]) == 0:
            errors.append("'symbols' list cannot be empty")

    # Check entry conditions
    if "entry_conditions" in strategy:
        if not isinstance(strategy["entry_conditions"], list):
            errors.append("'entry_conditions' must be a list")
        elif len(strategy["entry_conditions"]) == 0:
            warnings.append("'entry_conditions' is empty - strategy will never trigger")

    # Check exit rules
    if "exit_rules" in strategy:
        if not isinstance(strategy["exit_rules"], list):
            errors.append("'exit_rules' must be a list")
        elif len(strategy["exit_rules"]) == 0:
            warnings.append("'exit_rules' is empty - trades will never close")

    # Validate indicator names
    if "entry_conditions" in strategy:
        for i, cond in enumerate(strategy.get("entry_conditions", [])):
            # Check for valid indicator references
            for side in ["left", "right"]:
                if side in cond:
                    if (
                        isinstance(cond[side], dict)
                        and cond[side].get("type") == "indicator"
                    ):
                        ind_name = cond[side].get("name", "").upper()
                        if ind_name not in INDICATOR_REGISTRY:
                            errors.append(
                                f"Unknown indicator '{ind_name}' in entry condition {i + 1}"
                            )

    # Check entry/exit logic
    valid_logics = ["ALL", "ANY"]
    if "entry_logic" in strategy and strategy["entry_logic"] not in valid_logics:
        errors.append(
            f"Invalid entry_logic: {strategy['entry_logic']}. Must be ALL or ANY"
        )

    if "exit_logic" in strategy and strategy["exit_logic"] not in valid_logics:
        errors.append(
            f"Invalid exit_logic: {strategy['exit_logic']}. Must be ALL or ANY"
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "symbols_count": len(strategy.get("symbols", [])),
            "entry_conditions_count": len(strategy.get("entry_conditions", [])),
            "exit_rules_count": len(strategy.get("exit_rules", [])),
        },
    }
