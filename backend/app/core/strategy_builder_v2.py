"""
Strategy Builder V2 — Converts JSON StrategyV2 to executable strategy.

This module transforms the Pydantic-validated JSON strategy into
executable conditions and rules that can be applied to price data.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
import numpy as np

from app.schemas.strategy_v2 import (
    StrategyV2,
    Condition,
    MathExpr,
    IndicatorRef,
    PriceRef,
    ValueRef,
    ExitRule,
    StopLossRule,
    TargetRule,
    TrailingStopRule,
    TimeExitRule,
    IndicatorExitRule,
    INDICATOR_REGISTRY,
)

logger = logging.getLogger(__name__)


# ============================================================================
# EXECUTABLE OBJECTS
# ============================================================================


@dataclass
class CompiledCondition:
    """Compiled condition that can be evaluated against a DataFrame row."""

    id: str
    evaluator: Callable[[pd.Series], bool]
    description: str
    source_condition: Optional[Condition] = None


@dataclass
class CompiledExitRule:
    """Compiled exit rule with priority and evaluator."""

    rule_type: str
    priority: int
    evaluator: Callable[[pd.Series, Dict], Optional[Dict[str, Any]]]
    config: Dict[str, Any]
    description: str


@dataclass
class ExecutableStrategy:
    """Fully compiled strategy ready for execution."""

    name: str
    symbols: List[str]
    timeframe: str
    entry_logic: str  # "ALL" or "ANY"
    entry_conditions: List[CompiledCondition]
    exit_logic: str
    exit_rules: List[CompiledExitRule]  # Sorted by priority
    risk_config: Dict[str, Any]

    def get_entry_lambda(self) -> Callable[[pd.Series], bool]:
        """Get lambda that evaluates ALL entry conditions."""
        if not self.entry_conditions:
            return lambda row: False

        evaluators = [c.evaluator for c in self.entry_conditions]

        if self.entry_logic == "ALL":
            return lambda row: all(e(row) for e in evaluators)
        else:  # ANY
            return lambda row: any(e(row) for e in evaluators)


# ============================================================================
# EXPRESSION EVALUATOR
# ============================================================================


class ExpressionEvaluator:
    """
    Recursively evaluates MathExpr, IndicatorRef, PriceRef, ValueRef.

    Handles nested expressions like:
    - SMA(VOLUME, 20) * 1.5
    - RSI(14) + 10
    - (close - open) / open * 100
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self._indicator_cache: Dict[str, pd.Series] = {}

    def evaluate(self, expr: Any, row_idx: int) -> float:
        """
        Recursively evaluate an expression at a specific row index.

        Returns the numeric value of the expression.
        """
        # Base cases
        if isinstance(expr, (int, float)):
            return float(expr)

        if isinstance(expr, ValueRef):
            return float(expr.value)

        if isinstance(expr, PriceRef):
            return self._get_price_value(expr.field, row_idx)

        if isinstance(expr, IndicatorRef):
            return self._get_indicator_value(expr.name, expr.params, row_idx)

        if isinstance(expr, MathExpr):
            return self._eval_math_expr(expr, row_idx)

        if isinstance(expr, dict):
            # Handle raw dict (from JSON parsing)
            expr_type = expr.get("type")
            if expr_type == "indicator":
                return self._get_indicator_value(expr["name"], expr["params"], row_idx)
            elif expr_type == "price":
                return self._get_price_value(expr["field"], row_idx)
            elif expr_type == "value":
                return float(expr["value"])
            elif expr_type == "math":
                # Reconstruct MathExpr from dict
                math_expr = MathExpr(**expr)
                return self._eval_math_expr(math_expr, row_idx)

        raise ValueError(f"Unknown expression type: {type(expr)}")

    def _get_price_value(self, field: str, row_idx: int) -> float:
        """Get price field value at row index."""
        df = self.df

        if field == "close":
            return float(df["close"].iloc[row_idx])
        elif field == "open":
            return float(df["open"].iloc[row_idx])
        elif field == "high":
            return float(df["high"].iloc[row_idx])
        elif field == "low":
            return float(df["low"].iloc[row_idx])
        elif field == "volume":
            return float(df["volume"].iloc[row_idx])
        elif field == "hl2":
            return (
                float(df["high"].iloc[row_idx]) + float(df["low"].iloc[row_idx])
            ) / 2
        elif field == "hlc3":
            return (
                float(df["high"].iloc[row_idx])
                + float(df["low"].iloc[row_idx])
                + float(df["close"].iloc[row_idx])
            ) / 3
        elif field == "hlcc4":
            return (
                float(df["high"].iloc[row_idx])
                + float(df["low"].iloc[row_idx])
                + 2 * float(df["close"].iloc[row_idx])
            ) / 4
        else:
            raise ValueError(f"Unknown price field: {field}")

    def _get_indicator_value(self, name: str, params: List, row_idx: int) -> float:
        """Get computed indicator value at row index."""
        cache_key = self._make_cache_key(name, params)

        if cache_key not in self._indicator_cache:
            self._compute_indicator(name, params)

        series = self._indicator_cache[cache_key]

        if row_idx >= len(series) or pd.isna(series.iloc[row_idx]):
            return np.nan

        return float(series.iloc[row_idx])

    def _make_cache_key(self, name: str, params: List) -> str:
        """Create cache key for indicator."""
        param_str = "_".join(str(p) for p in params)
        return f"{name}_{param_str}"

    def _compute_indicator(self, name: str, params: List) -> None:
        """Compute and cache an indicator."""
        cache_key = self._make_cache_key(name, params)

        if cache_key in self._indicator_cache:
            return

        df = self.df

        if name == "RSI":
            period = int(params[0]) if params else 14
            col = self._compute_rsi(period)

        elif name == "SMA":
            period = int(params[0]) if params else 20
            field = str(params[1]) if len(params) > 1 else "close"
            col = df[field].rolling(period).mean()

        elif name == "EMA":
            period = int(params[0]) if params else 20
            field = str(params[1]) if len(params) > 1 else "close"
            col = df[field].ewm(span=period, adjust=False).mean()

        elif name == "SUPERTREND":
            period = int(params[0]) if params else 7
            multiplier = float(params[1]) if len(params) > 1 else 3.0
            col = self._compute_supertrend(period, multiplier)

        elif name == "MACD":
            fast = int(params[0]) if len(params) > 0 else 12
            slow = int(params[1]) if len(params) > 1 else 26
            signal = int(params[2]) if len(params) > 2 else 9
            col = self._compute_macd(fast, slow, signal)

        elif name == "ATR":
            period = int(params[0]) if params else 14
            col = self._compute_atr(period)

        elif name == "ADX":
            period = int(params[0]) if params else 14
            col = self._compute_adx(period)

        elif name == "BBANDS":
            period = int(params[0]) if params else 20
            std_dev = float(params[1]) if len(params) > 1 else 2.0
            col = self._compute_bbands(period, std_dev)

        elif name == "STOCH":
            k_period = int(params[0]) if len(params) > 0 else 14
            d_period = int(params[1]) if len(params) > 1 else 3
            col = self._compute_stoch(k_period, d_period)

        elif name == "CCI":
            period = int(params[0]) if params else 20
            col = self._compute_cci(period)

        elif name == "ROC":
            period = int(params[0]) if params else 10
            col = self._compute_roc(period)

        elif name == "WILLR":
            period = int(params[0]) if params else 14
            col = self._compute_willr(period)

        elif name == "OBV":
            col = self._compute_obv()

        elif name == "VWAP":
            col = self._compute_vwap()

        elif name == "ORB_HIGH":
            period = int(params[0]) if params else 15
            col = self._compute_orb_high(period)

        elif name == "ORB_LOW":
            period = int(params[0]) if params else 15
            col = self._compute_orb_low(period)

        else:
            raise ValueError(f"Unknown indicator: {name}")

        self._indicator_cache[cache_key] = col

    def _compute_rsi(self, period: int) -> pd.Series:
        """Compute RSI indicator."""
        delta = self.df["close"].diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, 1e-10)
        return 100 - (100 / (1 + rs))

    def _compute_supertrend(self, period: int, multiplier: float) -> pd.Series:
        """Compute Supertrend indicator."""
        hl2 = (self.df["high"] + self.df["low"]) / 2
        tr = pd.concat(
            [
                self.df["high"] - self.df["low"],
                (self.df["high"] - self.df["close"].shift()).abs(),
                (self.df["low"] - self.df["close"].shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(period).mean()
        return hl2 - multiplier * atr

    def _compute_macd(self, fast: int, slow: int, signal: int) -> pd.Series:
        """Compute MACD (returns MACD line, not signal)."""
        ema_fast = self.df["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = self.df["close"].ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        return macd_line

    def _compute_atr(self, period: int) -> pd.Series:
        """Compute Average True Range."""
        tr = pd.concat(
            [
                self.df["high"] - self.df["low"],
                (self.df["high"] - self.df["close"].shift()).abs(),
                (self.df["low"] - self.df["close"].shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.rolling(period).mean()

    def _compute_adx(self, period: int) -> pd.Series:
        """Compute Average Directional Index."""
        high = self.df["high"]
        low = self.df["low"]
        close = self.df["close"]

        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0

        tr = pd.concat(
            [
                high - low,
                (high - close.shift()).abs(),
                (low - close.shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)

        atr = tr.rolling(period).mean()

        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(period).mean()

        return adx

    def _compute_bbands(self, period: int, std_dev: float) -> pd.Series:
        """Compute Bollinger Bands (returns middle band)."""
        sma = self.df["close"].rolling(period).mean()
        return sma

    def _compute_stoch(self, k_period: int, d_period: int) -> pd.Series:
        """Compute Stochastic Oscillator (returns %K)."""
        low_min = self.df["low"].rolling(k_period).min()
        high_max = self.df["high"].rolling(k_period).max()
        k = 100 * (self.df["close"] - low_min) / (high_max - low_min + 1e-10)
        return k

    def _compute_cci(self, period: int) -> pd.Series:
        """Compute Commodity Channel Index."""
        tp = (self.df["high"] + self.df["low"] + self.df["close"]) / 3
        sma = tp.rolling(period).mean()
        mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean())
        return (tp - sma) / (0.015 * mad + 1e-10)

    def _compute_roc(self, period: int) -> pd.Series:
        """Compute Rate of Change."""
        return (
            100
            * (self.df["close"] - self.df["close"].shift(period))
            / (self.df["close"].shift(period) + 1e-10)
        )

    def _compute_willr(self, period: int) -> pd.Series:
        """Compute Williams %R."""
        high = self.df["high"].rolling(period).max()
        low = self.df["low"].rolling(period).min()
        return -100 * (high - self.df["close"]) / (high - low + 1e-10)

    def _compute_obv(self) -> pd.Series:
        """Compute On Balance Volume."""
        obv = pd.Series(index=self.df.index, dtype=float)
        obv.iloc[0] = self.df["volume"].iloc[0]

        for i in range(1, len(self.df)):
            if self.df["close"].iloc[i] > self.df["close"].iloc[i - 1]:
                obv.iloc[i] = obv.iloc[i - 1] + self.df["volume"].iloc[i]
            elif self.df["close"].iloc[i] < self.df["close"].iloc[i - 1]:
                obv.iloc[i] = obv.iloc[i - 1] - self.df["volume"].iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i - 1]

        return obv

    def _compute_vwap(self) -> pd.Series:
        """Compute Volume Weighted Average Price."""
        tp = (self.df["high"] + self.df["low"] + self.df["close"]) / 3
        cum_vol = self.df["volume"].cumsum()
        cum_tp_vol = (tp * self.df["volume"]).cumsum()
        return cum_tp_vol / cum_vol

    def _infer_candle_minutes(self) -> int:
        """Infer candle timeframe in minutes from the data."""
        if "time" not in self.df.columns or len(self.df) < 2:
            return 5
        diff = (self.df["time"].iloc[1] - self.df["time"].iloc[0]).total_seconds() / 60
        if diff <= 1:
            return 1
        if diff <= 5:
            return 5
        if diff <= 15:
            return 15
        if diff <= 30:
            return 30
        if diff <= 60:
            return 60
        return 5

    def _compute_orb_high(self, period_minutes: int) -> pd.Series:
        """Compute Opening Range High.

        period_minutes: Opening range duration in minutes (5 or 15).
        Returns: Series where every candle of a day has the same ORB_HIGH value.
        """
        df = self.df
        if "time" not in df.columns:
            return pd.Series(index=df.index, dtype=float)
        candle_minutes = self._infer_candle_minutes()
        num_candles = max(1, period_minutes // candle_minutes)
        dates = df["time"].dt.date
        result = pd.Series(index=df.index, dtype=float)
        for _, group in df.groupby(dates):
            if len(group) == 0:
                continue
            orb_val = group.head(num_candles)["high"].max()
            result.loc[group.index] = orb_val
        return result

    def _compute_orb_low(self, period_minutes: int) -> pd.Series:
        """Compute Opening Range Low.

        period_minutes: Opening range duration in minutes (5 or 15).
        Returns: Series where every candle of a day has the same ORB_LOW value.
        """
        df = self.df
        if "time" not in df.columns:
            return pd.Series(index=df.index, dtype=float)
        candle_minutes = self._infer_candle_minutes()
        num_candles = max(1, period_minutes // candle_minutes)
        dates = df["time"].dt.date
        result = pd.Series(index=df.index, dtype=float)
        for _, group in df.groupby(dates):
            if len(group) == 0:
                continue
            orb_val = group.head(num_candles)["low"].min()
            result.loc[group.index] = orb_val
        return result

    def _eval_math_expr(self, expr: MathExpr, row_idx: int) -> float:
        """Recursively evaluate a math expression."""
        left_val = self.evaluate(expr.left, row_idx)
        right_val = self.evaluate(expr.right, row_idx)

        if expr.operator == "*":
            return left_val * right_val
        elif expr.operator == "+":
            return left_val + right_val
        elif expr.operator == "-":
            return left_val - right_val
        elif expr.operator == "/":
            return left_val / right_val if right_val != 0 else np.nan

        raise ValueError(f"Unknown operator: {expr.operator}")


# ============================================================================
# CONDITION BUILDER
# ============================================================================


class ConditionBuilder:
    """Builds compiled conditions from Condition schemas."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.evaluator = ExpressionEvaluator(df)

    def build(self, condition: Condition, condition_id: str) -> CompiledCondition:
        """Build a compiled condition from a Condition schema."""
        left = condition.left
        operator = condition.operator
        right = condition.right

        def evaluator(row: pd.Series) -> bool:
            row_idx = row.name if hasattr(row, "name") else 0
            try:
                left_val = self.evaluator.evaluate(left, row_idx)
                right_val = self.evaluator.evaluate(right, row_idx)

                if operator == "<":
                    return left_val < right_val
                elif operator == ">":
                    return left_val > right_val
                elif operator == "<=":
                    return left_val <= right_val
                elif operator == ">=":
                    return left_val >= right_val
                elif operator == "==":
                    return abs(left_val - right_val) < 1e-10
                elif operator == "!=":
                    return abs(left_val - right_val) > 1e-10

                return False
            except Exception as e:
                logger.debug(f"Condition evaluation error: {e}")
                return False

        description = self._build_description(left, operator, right)

        return CompiledCondition(
            id=condition_id,
            evaluator=evaluator,
            description=description,
        )

    def _build_description(self, left: Any, operator: str, right: Any) -> str:
        """Build human-readable description of condition."""
        left_str = self._expr_to_string(left)
        right_str = self._expr_to_string(right)
        return f"{left_str} {operator} {right_str}"

    def _expr_to_string(self, expr: Any) -> str:
        """Convert expression to string representation."""
        if isinstance(expr, IndicatorRef):
            params_str = ", ".join(str(p) for p in expr.params) if expr.params else ""
            return f"{expr.name}({params_str})"
        elif isinstance(expr, PriceRef):
            return expr.field.upper()
        elif isinstance(expr, ValueRef):
            return str(expr.value)
        elif isinstance(expr, MathExpr):
            left_str = self._expr_to_string(expr.left)
            right_str = self._expr_to_string(expr.right)
            return f"({left_str} {expr.operator} {right_str})"
        elif isinstance(expr, (int, float)):
            return str(expr)
        elif isinstance(expr, dict):
            expr_type = expr.get("type")
            if expr_type == "indicator":
                params = expr.get("params", [])
                params_str = ", ".join(str(p) for p in params)
                return f"{expr['name']}({params_str})"
            elif expr_type == "price":
                return expr.get("field", "close").upper()
            elif expr_type == "value":
                return str(expr.get("value"))
            elif expr_type == "math":
                left = self._expr_to_string(expr.get("left"))
                right = self._expr_to_string(expr.get("right"))
                return f"({left} {expr.get('operator')} {right})"
        return str(expr)


# ============================================================================
# EXIT RULE BUILDER
# ============================================================================


class ExitRuleBuilder:
    """Builds compiled exit rules from ExitRule schemas."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.evaluator = ExpressionEvaluator(df)

    def build(self, rule: ExitRule, trade_state: Dict) -> CompiledExitRule:
        """Build a compiled exit rule from an ExitRule schema."""
        rule_type = getattr(rule, "type", "unknown")

        if isinstance(rule, StopLossRule):
            return self._build_stoploss(rule, trade_state)
        elif isinstance(rule, TargetRule):
            return self._build_target(rule, trade_state)
        elif isinstance(rule, TrailingStopRule):
            return self._build_trailing(rule, trade_state)
        elif isinstance(rule, TimeExitRule):
            return self._build_time_exit(rule)
        elif isinstance(rule, IndicatorExitRule):
            return self._build_indicator_exit(rule)

        raise ValueError(f"Unknown exit rule type: {type(rule)}")

    def _build_stoploss(
        self, rule: StopLossRule, trade_state: Dict
    ) -> CompiledExitRule:
        """Build stop loss exit rule."""
        sl_pct = rule.percent
        is_trailing = rule.trailing

        def evaluator(row: pd.Series, state: Dict) -> Optional[Dict[str, Any]]:
            if not state.get("in_trade"):
                return None

            entry_price = state["entry_price"]
            current_low = float(row.get("low", row["close"]))
            current_close = float(row["close"])
            trigger_price = entry_price * (1 - sl_pct / 100)

            if is_trailing:
                # Trailing stop from entry
                highest_price = state.get("highest_price", entry_price)
                new_highest = max(highest_price, float(row.get("high", current_close)))
                state["highest_price"] = new_highest

                if new_highest > entry_price:
                    trigger_price = new_highest * (1 - sl_pct / 100)
                    if current_low <= trigger_price:
                        return {"reason": "TRAILING_SL", "exit_price": trigger_price}
            else:
                # Fixed stop loss
                if current_low <= trigger_price:
                    return {"reason": "SL", "exit_price": trigger_price}

            return None

        return CompiledExitRule(
            rule_type="stoploss",
            priority=rule.priority,
            evaluator=evaluator,
            config={"percent": sl_pct, "trailing": is_trailing},
            description=f"Stop Loss {sl_pct}%",
        )

    def _build_target(self, rule: TargetRule, trade_state: Dict) -> CompiledExitRule:
        """Build target/profit exit rule."""
        target_pct = rule.percent

        def evaluator(row: pd.Series, state: Dict) -> Optional[Dict[str, Any]]:
            if not state.get("in_trade"):
                return None

            entry_price = state["entry_price"]
            current_high = float(row.get("high", row["close"]))
            trigger_price = entry_price * (1 + target_pct / 100)

            if current_high >= trigger_price:
                return {"reason": "TARGET", "exit_price": trigger_price}

            return None

        return CompiledExitRule(
            rule_type="target",
            priority=rule.priority,
            evaluator=evaluator,
            config={"percent": target_pct},
            description=f"Target {target_pct}%",
        )

    def _build_trailing(
        self, rule: TrailingStopRule, trade_state: Dict
    ) -> CompiledExitRule:
        """Build trailing stop exit rule."""
        trailing_pct = rule.percent

        def evaluator(row: pd.Series, state: Dict) -> Optional[Dict[str, Any]]:
            if not state.get("in_trade"):
                return None

            current_price = float(row["close"])
            current_low = float(row.get("low", current_price))
            highest_price = state.get("highest_price", state["entry_price"])

            # Update highest
            current_high = float(row.get("high", current_price))
            if current_high > highest_price:
                state["highest_price"] = current_high
                highest_price = current_high

            # Check trailing stop from peak
            if highest_price > state["entry_price"]:
                trigger_price = highest_price * (1 - trailing_pct / 100)
                if current_low <= trigger_price:
                    return {"reason": "TRAILING", "exit_price": trigger_price}

            return None

        return CompiledExitRule(
            rule_type="trailing",
            priority=rule.priority,
            evaluator=evaluator,
            config={"percent": trailing_pct},
            description=f"Trailing Stop {trailing_pct}%",
        )

    def _build_time_exit(self, rule: TimeExitRule) -> CompiledExitRule:
        """Build time-based exit rule."""
        exit_time = rule.time

        def evaluator(row: pd.Series, state: Dict) -> Optional[Dict[str, Any]]:
            if not state.get("in_trade"):
                return None

            row_time = row["time"]
            if hasattr(row_time, "strftime"):
                bar_time = row_time.strftime("%H:%M")
                if bar_time >= exit_time:
                    return {"reason": "TIME", "exit_price": float(row["close"])}

            return None

        return CompiledExitRule(
            rule_type="time",
            priority=rule.priority,
            evaluator=evaluator,
            config={"time": exit_time},
            description=f"Time Exit {exit_time}",
        )

    def _build_indicator_exit(
        self, rule: IndicatorExitRule, trade_state: Dict
    ) -> CompiledExitRule:
        """Build indicator-based exit rule."""
        condition = rule.condition
        builder = ConditionBuilder(self.df)
        compiled = builder.build(condition, "indicator_exit")

        def evaluator(row: pd.Series, state: Dict) -> Optional[Dict[str, Any]]:
            if not state.get("in_trade"):
                return None

            if compiled.evaluator(row):
                return {"reason": "INDICATOR", "exit_price": float(row["close"])}

            return None

        return CompiledExitRule(
            rule_type="indicator_exit",
            priority=rule.priority,
            evaluator=evaluator,
            config={"condition": condition.model_dump()},
            description=f"Indicator Exit: {compiled.description}",
        )


# ============================================================================
# STRATEGY BUILDER
# ============================================================================


class StrategyBuilderV2:
    """
    Main strategy builder that converts StrategyV2 to ExecutableStrategy.

    Usage:
        builder = StrategyBuilderV2()
        executable = builder.build(json_strategy)
    """

    def __init__(self):
        pass

    def build(self, json_strategy: StrategyV2) -> ExecutableStrategy:
        """
        Convert a StrategyV2 (or dict) to an ExecutableStrategy.

        Args:
            json_strategy: StrategyV2 Pydantic model or dict

        Returns:
            ExecutableStrategy ready for execution
        """
        # Convert dict to StrategyV2 if needed
        if isinstance(json_strategy, dict):
            json_strategy = StrategyV2(**json_strategy)

        # Build entry conditions
        entry_conditions = self._build_entry_conditions(json_strategy)

        # Build exit rules sorted by priority
        exit_rules = self._build_exit_rules(json_strategy)

        # Extract risk config
        risk_config = {
            "max_trades_per_day": json_strategy.risk.max_trades_per_day,
            "max_loss_per_day": json_strategy.risk.max_loss_per_day,
            "quantity": json_strategy.risk.quantity,
            "reentry_after_sl": json_strategy.risk.reentry_after_sl,
            "max_concurrent_trades": json_strategy.risk.max_concurrent_trades,
            "partial_exit_pct": json_strategy.risk.partial_exit_pct,
        }

        return ExecutableStrategy(
            name=json_strategy.name,
            symbols=json_strategy.symbols,
            timeframe=json_strategy.timeframe,
            entry_logic=json_strategy.entry_logic,
            entry_conditions=entry_conditions,
            exit_logic=json_strategy.exit_logic,
            exit_rules=exit_rules,
            risk_config=risk_config,
        )

    def _build_entry_conditions(
        self, json_strategy: StrategyV2
    ) -> List[CompiledCondition]:
        """Build compiled entry conditions."""
        # For now, we create a placeholder evaluator
        # The actual DataFrame is needed for full compilation
        conditions = []

        for i, cond in enumerate(json_strategy.entry_conditions):
            # Create a simple condition wrapper
            # Full evaluation happens at runtime with the DataFrame
            conditions.append(
                CompiledCondition(
                    id=f"entry_{i}",
                    evaluator=self._make_condition_evaluator(cond),
                    description=str(cond),
                    source_condition=cond,
                )
            )

        return conditions

    def _make_condition_evaluator(
        self, condition: Condition
    ) -> Callable[[pd.Series], bool]:
        """Create a condition evaluator function."""

        def evaluator(row: pd.Series) -> bool:
            try:
                left = condition.left
                right = condition.right
                op = condition.operator

                # Get values - handle different types
                if isinstance(left, IndicatorRef):
                    left_val = row.get(
                        f"indicator_{left.name}_{'_'.join(str(p) for p in left.params)}",
                        np.nan,
                    )
                elif isinstance(left, PriceRef):
                    left_val = row.get(left.field, np.nan)
                elif isinstance(left, ValueRef):
                    left_val = left.value
                elif isinstance(left, MathExpr):
                    left_val = self._eval_simple_math_expr(left, row)
                elif isinstance(left, (int, float)):
                    left_val = float(left)
                else:
                    left_val = row.get(str(left), np.nan)

                if isinstance(right, IndicatorRef):
                    right_val = row.get(
                        f"indicator_{right.name}_{'_'.join(str(p) for p in right.params)}",
                        np.nan,
                    )
                elif isinstance(right, PriceRef):
                    right_val = row.get(right.field, np.nan)
                elif isinstance(right, ValueRef):
                    right_val = right.value
                elif isinstance(right, MathExpr):
                    right_val = self._eval_simple_math_expr(right, row)
                elif isinstance(right, (int, float)):
                    right_val = float(right)
                else:
                    right_val = row.get(str(right), np.nan)

                # Compare
                if op == "<":
                    return left_val < right_val
                elif op == ">":
                    return left_val > right_val
                elif op == "<=":
                    return left_val <= right_val
                elif op == ">=":
                    return left_val >= right_val
                elif op == "==":
                    return abs(left_val - right_val) < 1e-10
                elif op == "!=":
                    return abs(left_val - right_val) > 1e-10
                elif op in ("crosses_above", "crosses_below"):
                    return False

                return False
            except Exception as e:
                logger.debug(f"Condition evaluation error: {e}")
                return False

        return evaluator

    def _eval_simple_math_expr(self, expr: MathExpr, row: pd.Series) -> float:
        """Evaluate a simple math expression on a row."""
        # Get left value
        if isinstance(expr.left, IndicatorRef):
            left_val = row.get(
                f"indicator_{expr.left.name}_{'_'.join(str(p) for p in expr.left.params)}",
                np.nan,
            )
        elif isinstance(expr.left, PriceRef):
            left_val = row.get(expr.left.field, 0)
        elif isinstance(expr.left, ValueRef):
            left_val = expr.left.value
        elif isinstance(expr.left, MathExpr):
            left_val = self._eval_simple_math_expr(expr.left, row)
        elif isinstance(expr.left, (int, float)):
            left_val = float(expr.left)
        else:
            left_val = 0

        # Get right value
        if isinstance(expr.right, IndicatorRef):
            right_val = row.get(
                f"indicator_{expr.right.name}_{'_'.join(str(p) for p in expr.right.params)}",
                np.nan,
            )
        elif isinstance(expr.right, PriceRef):
            right_val = row.get(expr.right.field, 0)
        elif isinstance(expr.right, ValueRef):
            right_val = expr.right.value
        elif isinstance(expr.right, MathExpr):
            right_val = self._eval_simple_math_expr(expr.right, row)
        elif isinstance(expr.right, (int, float)):
            right_val = float(expr.right)
        else:
            right_val = 0

        # Apply operator
        if expr.operator == "*":
            return left_val * right_val
        elif expr.operator == "+":
            return left_val + right_val
        elif expr.operator == "-":
            return left_val - right_val
        elif expr.operator == "/":
            return left_val / right_val if right_val != 0 else np.nan

        return np.nan

    def _build_exit_rules(self, json_strategy: StrategyV2) -> List[CompiledExitRule]:
        """Build compiled exit rules sorted by priority."""
        exit_rules = []

        # We'll create placeholder rules - actual evaluation happens at runtime
        for rule in json_strategy.exit_rules:
            rule_type = getattr(rule, "type", "unknown")
            priority = getattr(rule, "priority", 5)

            # Create a simple evaluator based on rule type
            if rule_type == "stoploss":
                evaluator = self._make_stoploss_evaluator(rule)
            elif rule_type == "target":
                evaluator = self._make_target_evaluator(rule)
            elif rule_type == "trailing":
                evaluator = self._make_trailing_evaluator(rule)
            elif rule_type == "time":
                evaluator = self._make_time_evaluator(rule)
            elif rule_type == "indicator_exit":
                evaluator = self._make_indicator_exit_evaluator(rule)
            else:
                continue

            exit_rules.append(
                CompiledExitRule(
                    rule_type=rule_type,
                    priority=priority,
                    evaluator=evaluator,
                    config=rule.model_dump() if hasattr(rule, "model_dump") else {},
                    description=f"{rule_type} (priority={priority})",
                )
            )

        # Sort by priority (lower = higher priority)
        exit_rules.sort(key=lambda r: r.priority)
        return exit_rules

    def _make_stoploss_evaluator(self, rule: StopLossRule) -> Callable:
        """Create stop loss evaluator."""
        sl_pct = rule.percent

        def evaluator(row: pd.Series, state: Dict) -> Optional[Dict[str, Any]]:
            if not state.get("in_trade"):
                return None

            entry_price = state["entry_price"]
            current_low = float(row.get("low", row["close"]))
            trigger_price = entry_price * (1 - sl_pct / 100)

            if current_low <= trigger_price:
                return {"reason": "SL", "exit_price": trigger_price}

            return None

        return evaluator

    def _make_target_evaluator(self, rule: TargetRule) -> Callable:
        """Create target evaluator."""
        target_pct = rule.percent

        def evaluator(row: pd.Series, state: Dict) -> Optional[Dict[str, Any]]:
            if not state.get("in_trade"):
                return None

            entry_price = state["entry_price"]
            current_high = float(row.get("high", row["close"]))
            trigger_price = entry_price * (1 + target_pct / 100)

            if current_high >= trigger_price:
                return {"reason": "TARGET", "exit_price": trigger_price}

            return None

        return evaluator

    def _make_trailing_evaluator(self, rule: TrailingStopRule) -> Callable:
        """Create trailing stop evaluator."""
        trailing_pct = rule.percent

        def evaluator(row: pd.Series, state: Dict) -> Optional[Dict[str, Any]]:
            if not state.get("in_trade"):
                return None

            current_price = row["close"]
            current_low = float(row.get("low", current_price))
            current_high = float(row.get("high", current_price))
            highest_price = state.get("highest_price", state["entry_price"])

            # Update highest
            if current_high > highest_price:
                state["highest_price"] = current_high
                highest_price = current_high

            # Check trailing stop from peak
            if highest_price > state["entry_price"]:
                trigger_price = highest_price * (1 - trailing_pct / 100)
                if current_low <= trigger_price:
                    return {"reason": "TRAILING", "exit_price": trigger_price}

            return None

        return evaluator

    def _make_time_evaluator(self, rule: TimeExitRule) -> Callable:
        """Create time exit evaluator."""
        exit_time = rule.time

        def evaluator(row: pd.Series, state: Dict) -> Optional[Dict[str, Any]]:
            if not state.get("in_trade"):
                return None

            row_time = row["time"]
            if hasattr(row_time, "strftime"):
                bar_time = row_time.strftime("%H:%M")
                if bar_time >= exit_time:
                    return {"reason": "TIME", "exit_price": float(row["close"])}

            return None

        return evaluator

    def _make_indicator_exit_evaluator(self, rule: IndicatorExitRule) -> Callable:
        """Create indicator exit evaluator."""
        condition = rule.condition
        cond_evaluator = self._make_condition_evaluator(condition)

        def evaluator(row: pd.Series, state: Dict) -> Optional[Dict[str, Any]]:
            if not state.get("in_trade"):
                return None

            if cond_evaluator(row):
                return {"reason": "INDICATOR", "exit_price": float(row["close"])}

            return None

        return evaluator
