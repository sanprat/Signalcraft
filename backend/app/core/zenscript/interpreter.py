"""
ZenScript Interpreter

Compiles ZenScript AST into executable Strategy objects
that can be evaluated against candle data.
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd
import numpy as np

from .ast_nodes import (
    StrategyNode,
    IfStatement,
    ConditionGroup,
    Condition,
    IndicatorExpr,
    Action,
    ExitStatement,
    ExitCondition,
    Indicator,
    ComparisonOp,
    ActionType,
    ExitType,
    LogicalOp,
    CompiledCondition,
    CompiledExit,
    StrategySignal,
    StrategyContext,
    TradeState,
)

logger = logging.getLogger(__name__)


class EvaluatedCondition:
    """Result of evaluating a single condition."""

    def __init__(
        self,
        passed: bool,
        indicator_value: Optional[float] = None,
        comparison_value: Optional[float] = None,
        details: str = "",
    ):
        self.passed = passed
        self.indicator_value = indicator_value
        self.comparison_value = comparison_value
        self.details = details


class CompiledStrategy:
    """
    A compiled ZenScript strategy ready for evaluation.

    Contains precomputed indicator columns and evaluation logic.
    """

    def __init__(self, name: str = "Untitled Strategy"):
        self.name = name
        self.buy_conditions: List[CompiledCondition] = []
        self.sell_conditions: List[CompiledCondition] = []
        self.short_conditions: List[CompiledCondition] = []
        self.cover_conditions: List[CompiledCondition] = []
        self.exit_conditions = CompiledExit()
        self.buy_logic: str = "AND"  # AND or OR
        self.sell_logic: str = "AND"
        self.raw_script: str = ""

    def add_buy_condition(self, cond: CompiledCondition):
        """Add a BUY condition."""
        self.buy_conditions.append(cond)

    def add_sell_condition(self, cond: CompiledCondition):
        """Add a SELL condition."""
        self.sell_conditions.append(cond)

    def set_exit(self, exit_cond: CompiledExit):
        """Set exit conditions."""
        self.exit_conditions = exit_cond

    def to_strategy_dict(self) -> dict:
        """Convert to strategy dictionary for backtest engine."""
        # Build entry conditions for BUY (main case)
        entry_conditions = []

        if self.buy_conditions:
            if len(self.buy_conditions) == 1:
                entry_conditions.append(self.buy_conditions[0].to_dict())
            else:
                for cond in self.buy_conditions:
                    entry_conditions.append(
                        {
                            **cond.to_dict(),
                            "logic": self.buy_logic,
                        }
                    )

        return {
            "name": self.name,
            "entry_conditions": entry_conditions,
            "exit_conditions": self.exit_conditions.to_dict(),
            "raw_script": self.raw_script,
        }

    def evaluate_entry(self, ctx: StrategyContext) -> StrategySignal:
        """
        Evaluate entry conditions and return signal.

        Args:
            ctx: Strategy context with current candle and indicators

        Returns:
            StrategySignal: BUY, SELL, SHORT, COVER, or NONE
        """
        # Check BUY conditions
        if self.buy_conditions:
            buy_passed = self._evaluate_conditions(self.buy_conditions, ctx)
            if buy_passed:
                return StrategySignal.BUY

        # Check SHORT conditions
        if self.short_conditions:
            short_passed = self._evaluate_conditions(self.short_conditions, ctx)
            if short_passed:
                return StrategySignal.SHORT

        return StrategySignal.NONE

    def evaluate_exit(self, ctx: StrategyContext, trade: TradeState) -> StrategySignal:
        """
        Evaluate exit conditions and return signal.

        Args:
            ctx: Strategy context
            trade: Current trade state

        Returns:
            StrategySignal: EXIT, COVER, or NONE
        """
        exit_reason = self._should_exit(ctx, trade)
        if exit_reason:
            if trade.position_type == "long":
                return StrategySignal.EXIT
            elif trade.position_type == "short":
                return StrategySignal.COVER

        return StrategySignal.NONE

    def _evaluate_conditions(
        self, conditions: List[CompiledCondition], ctx: StrategyContext
    ) -> bool:
        """Evaluate a list of conditions with AND/OR logic."""
        if not conditions:
            return False

        for cond in conditions:
            passed = self._evaluate_single_condition(cond, ctx)
            if not passed:
                # AND logic - any failure means overall failure
                if self.buy_logic == "AND":
                    return False
            else:
                # OR logic - any success means overall success
                if self.buy_logic == "OR":
                    return True

        return True

    def _evaluate_single_condition(
        self, cond: CompiledCondition, ctx: StrategyContext
    ) -> bool:
        """Evaluate a single condition."""
        # Get indicator value
        ind_key = self._get_indicator_key(cond.indicator, cond.params)
        ind_value = ctx.indicators.get(ind_key)

        if ind_value is None:
            # Fallback: try to compute from price
            if cond.indicator == "PRICE" or cond.indicator == "CLOSE":
                ind_value = ctx.close
            elif cond.indicator == "OPEN":
                ind_value = ctx.open
            elif cond.indicator == "HIGH":
                ind_value = ctx.high
            elif cond.indicator == "LOW":
                ind_value = ctx.low
            elif cond.indicator == "VOLUME":
                ind_value = ctx.volume

        if ind_value is None:
            return False

        # Get comparison value
        if cond.ref_indicator:
            ref_key = self._get_indicator_key(cond.ref_indicator, cond.ref_params or [])
            comp_value = ctx.indicators.get(ref_key, 0)
        else:
            comp_value = cond.value

        # Perform comparison
        return self._compare(ind_value, cond.comparison, comp_value)

    def _get_indicator_key(self, indicator: str, params: List[float]) -> str:
        """Get the key used to store indicator values in context."""
        if indicator == "RSI":
            period = int(params[0]) if params else 14
            return f"rsi_{period}"
        elif indicator == "SMA":
            period = int(params[0]) if params else 20
            return f"sma_{period}"
        elif indicator == "EMA":
            period = int(params[0]) if params else 20
            return f"ema_{period}"
        elif indicator == "SUPERTREND":
            period = int(params[0]) if params else 7
            mult = params[1] if len(params) > 1 else 3.0
            return f"supertrend_{period}_{mult}"
        elif indicator == "MACD":
            return "macd"
        elif indicator == "BBANDS":
            return "bbands"
        elif indicator == "ADX":
            return "adx"
        elif indicator == "CCI":
            return "cci"
        elif indicator == "STOCH":
            return "stoch"
        elif indicator == "ATR":
            return "atr"
        elif indicator == "VWAP":
            return "vwap"
        else:
            return f"{indicator.lower()}"

    def _compare(self, left: float, op: str, right: float) -> bool:
        """Compare two values using the specified operator."""
        if op == "<":
            return left < right
        elif op == ">":
            return left > right
        elif op == "<=":
            return left <= right
        elif op == ">=":
            return left >= right
        elif op == "==":
            return left == right
        elif op == "!=":
            return left != right
        return False

    def _should_exit(self, ctx: StrategyContext, trade: TradeState) -> bool:
        """Check if exit conditions are met."""
        if not trade.in_position or trade.entry_price is None:
            return False

        pnl_pct = (ctx.close - trade.entry_price) / trade.entry_price * 100

        # Check time exit
        if self.exit_conditions.time_exit:
            current_time = ctx.time.strftime("%H:%M")
            if current_time >= self.exit_conditions.time_exit:
                return True

        # Check target
        if self.exit_conditions.target_pct:
            if pnl_pct >= self.exit_conditions.target_pct:
                return True

        # Check stoploss
        if self.exit_conditions.stoploss_pct:
            if pnl_pct <= -self.exit_conditions.stoploss_pct:
                return True

        # Check trailing stop
        if self.exit_conditions.trailing_sl_pct:
            if trade.position_type == "long":
                # Update highest price
                if ctx.high > (trade.highest_price or 0):
                    trade.highest_price = ctx.high
                    trade.trailing_stop = trade.highest_price * (
                        1 - self.exit_conditions.trailing_sl_pct / 100
                    )

                if trade.trailing_stop and ctx.close < trade.trailing_stop:
                    return True
            elif trade.position_type == "short":
                # Update lowest price
                if ctx.low < (trade.lowest_price or float("inf")):
                    trade.lowest_price = ctx.low
                    trade.trailing_stop = trade.lowest_price * (
                        1 + self.exit_conditions.trailing_sl_pct / 100
                    )

                if trade.trailing_stop and ctx.close > trade.trailing_stop:
                    return True

        return False


class ZenScriptInterpreter:
    """
    Interprets ZenScript AST and compiles it into a CompiledStrategy.

    Usage:
        interpreter = ZenScriptInterpreter()
        compiled = interpreter.compile(ast)
    """

    def __init__(self):
        self.indicator_registry = self._build_indicator_registry()

    def compile(self, ast: StrategyNode) -> CompiledStrategy:
        """
        Compile a ZenScript AST into a CompiledStrategy.

        Args:
            ast: Parsed ZenScript AST

        Returns:
            CompiledStrategy ready for evaluation
        """
        strategy = CompiledStrategy(name=ast.name)
        strategy.raw_script = ast.raw_script

        # Process each entry statement
        for stmt in ast.entry_statements:
            self._compile_if_statement(stmt, strategy)

        # Process exit statement
        if ast.exit_statement:
            self._compile_exit_statement(ast.exit_statement, strategy)

        return strategy

    def _compile_if_statement(self, stmt: IfStatement, strategy: CompiledStrategy):
        """Compile an IF statement into conditions."""
        conditions = stmt.conditions
        action = stmt.action

        # Determine logic type (default to AND for simplicity)
        logic = conditions.logical_op.value if conditions.logical_op else "AND"

        # Compile each condition
        compiled_conds = []
        for cond in conditions.conditions:
            if isinstance(cond, IndicatorExpr):
                compiled = self._compile_indicator_expr(cond)
                compiled_conds.append(compiled)
            elif isinstance(cond, Condition) and isinstance(cond.left, IndicatorExpr):
                compiled = self._compile_indicator_expr(cond.left)
                compiled_conds.append(compiled)

        # Add to appropriate condition list based on action
        for compiled in compiled_conds:
            if action.action_type == ActionType.BUY:
                strategy.add_buy_condition(compiled)
                strategy.buy_logic = logic
            elif action.action_type == ActionType.SELL:
                strategy.add_sell_condition(compiled)
                strategy.sell_logic = logic
            elif action.action_type == ActionType.SHORT:
                strategy.short_conditions.append(compiled)
            elif action.action_type == ActionType.COVER:
                strategy.cover_conditions.append(compiled)

    def _compile_indicator_expr(self, expr: IndicatorExpr) -> CompiledCondition:
        """Compile an indicator expression."""
        # Get the indicator name as string
        ind_name = (
            expr.indicator.value
            if hasattr(expr.indicator, "value")
            else str(expr.indicator)
        )

        # Build params dict for backtest engine
        params = {}
        if expr.params:
            # Map params based on indicator type
            if ind_name in ("RSI", "SMA", "EMA", "BBANDS", "CCI", "ADX", "ATR"):
                params["period"] = int(expr.params[0]) if expr.params else 14
            elif ind_name == "MACD":
                params["fast"] = int(expr.params[0]) if len(expr.params) > 0 else 12
                params["slow"] = int(expr.params[1]) if len(expr.params) > 1 else 26
                params["signal"] = int(expr.params[2]) if len(expr.params) > 2 else 9
            elif ind_name == "SUPERTREND":
                params["period"] = int(expr.params[0]) if len(expr.params) > 0 else 7
                params["multiplier"] = expr.params[1] if len(expr.params) > 1 else 3.0
            elif ind_name == "STOCH":
                params["k_period"] = int(expr.params[0]) if len(expr.params) > 0 else 14
                params["d_period"] = int(expr.params[1]) if len(expr.params) > 1 else 3
            else:
                # Generic: use first param as period
                params["period"] = int(expr.params[0]) if expr.params else 14

        # Get ref indicator name
        ref_ind_name = None
        if expr.ref_indicator:
            ref_ind_name = (
                expr.ref_indicator.value
                if hasattr(expr.ref_indicator, "value")
                else str(expr.ref_indicator)
            )

        # Build ref_params
        ref_params = {}
        if expr.ref_params and ref_ind_name:
            if ref_ind_name in ("RSI", "SMA", "EMA"):
                ref_params["period"] = (
                    int(expr.ref_params[0]) if expr.ref_params else 20
                )

        return CompiledCondition(
            indicator=ind_name,
            params=params,
            comparison=expr.comparison.value,
            value=expr.value,
            ref_indicator=ref_ind_name,
            ref_params=list(ref_params.values()) if ref_params else [],
        )

    def _compile_exit_statement(self, stmt: ExitStatement, strategy: CompiledStrategy):
        """Compile exit conditions."""
        exit_cond = CompiledExit()

        for cond in stmt.conditions:
            if cond.exit_type == ExitType.TIME:
                exit_cond.time_exit = cond.time
            elif cond.exit_type == ExitType.TARGET:
                exit_cond.target_pct = cond.value
            elif cond.exit_type == ExitType.STOPLOSS:
                exit_cond.stoploss_pct = cond.value
            elif cond.exit_type == ExitType.TRAILING:
                exit_cond.trailing_sl_pct = cond.value

        strategy.set_exit(exit_cond)

    def _build_indicator_registry(self) -> Dict[str, Callable]:
        """Build registry of indicator calculation functions."""
        return {
            "RSI": self._calc_rsi,
            "SMA": self._calc_sma,
            "EMA": self._calc_ema,
            "SUPERTREND": self._calc_supertrend,
            "MACD": self._calc_macd,
            "BBANDS": self._calc_bbands,
            "ADX": self._calc_adx,
            "CCI": self._calc_cci,
            "STOCH": self._calc_stoch,
            "ATR": self._calc_atr,
        }

    def _calc_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate RSI."""
        delta = df["close"].diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, 1e-10)
        return 100 - (100 / (1 + rs))

    def _calc_sma(self, df: pd.DataFrame, period: int = 20) -> pd.Series:
        """Calculate Simple Moving Average."""
        return df["close"].rolling(period).mean()

    def _calc_ema(self, df: pd.DataFrame, period: int = 20) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return df["close"].ewm(span=period, adjust=False).mean()

    def _calc_supertrend(
        self, df: pd.DataFrame, period: int = 7, multiplier: float = 3.0
    ) -> pd.Series:
        """Calculate Supertrend."""
        hl2 = (df["high"] + df["low"]) / 2
        tr = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - df["close"].shift()).abs(),
                (df["low"] - df["close"].shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(period).mean()
        upper = hl2 + multiplier * atr
        lower = hl2 - multiplier * atr
        return lower  # Simplified - just return lower band

    def _calc_macd(
        self, df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> pd.DataFrame:
        """Calculate MACD."""
        ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        return pd.DataFrame({"macd": macd, "signal": signal_line})

    def _calc_bbands(
        self, df: pd.DataFrame, period: int = 20, std_dev: float = 2.0
    ) -> pd.DataFrame:
        """Calculate Bollinger Bands."""
        sma = df["close"].rolling(period).mean()
        std = df["close"].rolling(period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return pd.DataFrame({"upper": upper, "middle": sma, "lower": lower})

    def _calc_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate ADX (simplified)."""
        # This is a simplified ADX - for production use a full implementation
        return pd.Series(0, index=df.index)

    def _calc_cci(self, df: pd.DataFrame, period: int = 20) -> pd.Series:
        """Calculate Commodity Channel Index."""
        tp = (df["high"] + df["low"] + df["close"]) / 3
        sma_tp = tp.rolling(period).mean()
        mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean())
        return (tp - sma_tp) / (0.015 * mad + 1e-10)

    def _calc_stoch(
        self, df: pd.DataFrame, k_period: int = 14, d_period: int = 3
    ) -> pd.DataFrame:
        """Calculate Stochastic Oscillator."""
        low_min = df["low"].rolling(k_period).min()
        high_max = df["high"].rolling(k_period).max()
        k = 100 * (df["close"] - low_min) / (high_max - low_min + 1e-10)
        d = k.rolling(d_period).mean()
        return pd.DataFrame({"k": k, "d": d})

    def _calc_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range."""
        tr = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - df["close"].shift()).abs(),
                (df["low"] - df["close"].shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.rolling(period).mean()


# Convenience functions
def compile_zenscript(code: str) -> CompiledStrategy:
    """Parse and compile ZenScript code in one step."""
    from .parser import parse_zenscript

    ast = parse_zenscript(code)
    interpreter = ZenScriptInterpreter()
    return interpreter.compile(ast)


def interpret(ast: StrategyNode) -> CompiledStrategy:
    """Interpret a ZenScript AST."""
    interpreter = ZenScriptInterpreter()
    return interpreter.compile(ast)
