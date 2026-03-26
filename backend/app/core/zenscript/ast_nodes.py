"""
AST Node Definitions for ZenScript

Each node represents a part of the parsed strategy.
"""

from typing import List, Optional, Union, Any
from enum import Enum


class NodeType(Enum):
    """Enumeration of all AST node types."""

    STRATEGY = "strategy"
    IF_STATEMENT = "if_statement"
    CONDITION = "condition"
    CONDITION_GROUP = "condition_group"
    COMPARISON = "comparison"
    INDICATOR_EXPR = "indicator_expr"
    ACTION = "action"
    EXIT_STATEMENT = "exit_statement"
    ASSIGNMENT = "assignment"
    VARIABLE = "variable"


class LogicalOp(Enum):
    """Logical operators for combining conditions."""

    AND = "AND"
    OR = "OR"


class ComparisonOp(Enum):
    """Comparison operators."""

    LT = "<"
    GT = ">"
    LTE = "<="
    GTE = ">="
    EQ = "=="
    NE = "!="


class Indicator(Enum):
    """Supported technical indicators."""

    RSI = "RSI"
    SMA = "SMA"
    EMA = "EMA"
    SUPERTREND = "SUPERTREND"
    MACD = "MACD"
    BBANDS = "BBANDS"
    ADX = "ADX"
    CCI = "CCI"
    STOCH = "STOCH"
    ATR = "ATR"
    # Price-based
    PRICE = "PRICE"
    OPEN = "OPEN"
    HIGH = "HIGH"
    LOW = "LOW"
    CLOSE = "CLOSE"
    VOLUME = "VOLUME"


class ActionType(Enum):
    """Trading action types."""

    BUY = "BUY"
    SELL = "SELL"
    EXIT = "EXIT"
    SHORT = "SHORT"
    COVER = "COVER"


class ExitType(Enum):
    """Exit condition types."""

    TIME = "AT"
    TARGET = "TARGET"
    STOPLOSS = "SL"
    TRAILING = "TRAILING"


class Position:
    """Represents a line/column position in source."""

    def __init__(self, line: int, column: int):
        self.line = line
        self.column = column


class ASTNode:
    """Base class for all AST nodes."""

    node_type: NodeType

    def __init__(self, node_type: NodeType, **kwargs):
        self.node_type = node_type
        self.position = kwargs.get("position")

    def __repr__(self) -> str:
        return f"<{self.node_type.value}>"


class IndicatorExpr(ASTNode):
    """Represents an indicator expression like RSI(14) < 30."""

    def __init__(
        self,
        indicator: str,
        params: List[float],
        comparison: str = "<",
        value: float = 0.0,
        ref_indicator: Optional[str] = None,
        ref_params: Optional[List[float]] = None,
        **kwargs,
    ):
        super().__init__(NodeType.INDICATOR_EXPR, **kwargs)
        try:
            self.indicator = Indicator(indicator.upper())
        except ValueError:
            self.indicator = (
                Indicator.PRICE
                if indicator.upper() == "PRICE"
                else Indicator[indicator.upper()]
            )
        self.params = params
        try:
            self.comparison = ComparisonOp(comparison)
        except ValueError:
            self.comparison = ComparisonOp.EQ
        self.value = value
        if ref_indicator:
            try:
                self.ref_indicator = Indicator(ref_indicator.upper())
            except ValueError:
                self.ref_indicator = Indicator.PRICE
        else:
            self.ref_indicator = None
        if ref_params:
            self.ref_params = ref_params
        else:
            self.ref_params = None

    def to_dict(self) -> dict:
        """Convert to dictionary for strategy export."""
        result = {
            "indicator": self.indicator.value,
            "params": self.params,
            "comparison": self.comparison.value,
            "value": self.value,
        }
        if self.ref_indicator:
            result["ref_indicator"] = self.ref_indicator.value
            result["ref_params"] = self.ref_params or []
        return result


class Condition(ASTNode):
    """Represents a single condition."""

    def __init__(self, left, comparison: Optional[str] = None, right=None, **kwargs):
        super().__init__(NodeType.CONDITION, **kwargs)
        self.left = left
        if comparison:
            try:
                self.comparison = ComparisonOp(comparison)
            except ValueError:
                self.comparison = ComparisonOp.EQ
        else:
            self.comparison = None
        self.right = right

    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        if isinstance(self.left, IndicatorExpr):
            return self.left.to_dict()
        return {"type": "simple", "left": str(self.left)}


class ConditionGroup(ASTNode):
    """Represents grouped conditions with logical operators."""

    def __init__(self, **kwargs):
        super().__init__(NodeType.CONDITION_GROUP, **kwargs)
        self.conditions = []
        self.logical_op = None

    def add_condition(self, condition: Condition, logical_op: Optional[str] = None):
        """Add a condition to the group."""
        self.conditions.append(condition)
        if logical_op:
            try:
                self.logical_op = LogicalOp(logical_op.upper())
            except ValueError:
                self.logical_op = LogicalOp.AND

    def to_dict(self) -> dict:
        """Convert to condition format for strategy."""
        conditions_list = []
        for cond in self.conditions:
            if isinstance(cond, IndicatorExpr):
                conditions_list.append(cond.to_dict())
            elif isinstance(cond, Condition):
                conditions_list.append(cond.to_dict())

        result = conditions_list[0] if len(conditions_list) == 1 else conditions_list
        if len(conditions_list) > 1 and self.logical_op:
            result = {"logic": self.logical_op.value, "conditions": conditions_list}
        return result


class Action(ASTNode):
    """Represents a trading action."""

    def __init__(self, action_type: str, time: Optional[str] = None, **kwargs):
        super().__init__(NodeType.ACTION, **kwargs)
        try:
            self.action_type = ActionType(action_type.upper())
        except ValueError:
            self.action_type = ActionType.BUY
        self.time = time

    def to_dict(self) -> dict:
        """Convert to action dictionary."""
        result = {"type": self.action_type.value}
        if self.time:
            result["time"] = self.time
        return result


class IfStatement(ASTNode):
    """Represents an IF condition THEN action statement."""

    def __init__(self, conditions: ConditionGroup, action: Action, **kwargs):
        super().__init__(NodeType.IF_STATEMENT, **kwargs)
        self.conditions = conditions
        self.action = action

    def to_dict(self) -> dict:
        """Convert to IF statement format."""
        return {
            "condition": self.conditions.to_dict(),
            "action": self.action.to_dict(),
        }


class ExitCondition(ASTNode):
    """Represents an exit condition."""

    def __init__(
        self,
        exit_type: str,
        value: Optional[float] = None,
        time: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(NodeType.EXIT_STATEMENT, **kwargs)
        # Normalize exit_type to enum value
        normalized = exit_type.upper()
        if normalized == "SL":
            normalized = "SL"  # Keep as SL for the enum
        try:
            self.exit_type = ExitType(normalized)
        except ValueError:
            # Default to TIME if unknown type
            self.exit_type = ExitType.TIME
        self.value = value
        self.time = time

    def to_dict(self) -> dict:
        """Convert to exit condition dictionary."""
        result = {}
        if self.exit_type == ExitType.TIME:
            result["time_exit"] = self.time
        elif self.exit_type == ExitType.TARGET:
            result["target_pct"] = self.value
        elif self.exit_type == ExitType.STOPLOSS:
            result["stoploss_pct"] = self.value
        elif self.exit_type == ExitType.TRAILING:
            result["trailing_sl_pct"] = self.value
        return result


class ExitStatement(ASTNode):
    """Represents EXIT statement with multiple conditions."""

    def __init__(self, conditions: List[ExitCondition] = None, **kwargs):
        super().__init__(NodeType.EXIT_STATEMENT, **kwargs)
        self.conditions = conditions or []

    def add_condition(self, condition: ExitCondition):
        """Add an exit condition."""
        self.conditions.append(condition)

    def to_dict(self) -> dict:
        """Convert to exit conditions dictionary."""
        result = {}
        for cond in self.conditions:
            result.update(cond.to_dict())
        return result


class Variable(ASTNode):
    """Represents a variable assignment."""

    def __init__(self, name: str, value: Any, **kwargs):
        super().__init__(NodeType.VARIABLE, **kwargs)
        self.name = name
        self.value = value


class StrategyNode(ASTNode):
    """Root node representing a complete strategy."""

    def __init__(self, name: str = "Untitled Strategy", **kwargs):
        super().__init__(NodeType.STRATEGY, **kwargs)
        self.name = name
        self.entry_statements = []
        self.exit_statement = None
        self.variables = []
        self.raw_script = ""

    def add_entry(self, statement: IfStatement):
        """Add an entry statement."""
        self.entry_statements.append(statement)

    def set_exit(self, statement: ExitStatement):
        """Set the exit statement."""
        self.exit_statement = statement

    def add_variable(self, variable: Variable):
        """Add a variable."""
        self.variables.append(variable)

    def to_dict(self) -> dict:
        """Convert to complete strategy dictionary."""
        # Convert entry conditions
        entry_conditions = []
        for stmt in self.entry_statements:
            entry_conditions.append(stmt.conditions.to_dict())

        # Convert exit conditions
        exit_conditions = {}
        if self.exit_statement:
            exit_conditions = self.exit_statement.to_dict()

        return {
            "name": self.name,
            "entry_conditions": entry_conditions,
            "exit_conditions": exit_conditions,
            "variables": [(v.name, v.value) for v in self.variables],
            "raw_script": self.raw_script,
        }


# Backward compatibility - these are used by interpreter.py
class CompiledCondition:
    """Compiled condition ready for evaluation."""

    def __init__(
        self,
        indicator: str,
        params: List[float],
        comparison: str,
        value: float,
        ref_indicator: Optional[str] = None,
        ref_params: Optional[List[float]] = None,
    ):
        self.indicator = indicator
        self.params = params
        self.comparison = comparison
        self.value = value
        self.ref_indicator = ref_indicator
        self.ref_params = ref_params

    def to_dict(self) -> dict:
        """Convert to condition dictionary for backtest engine."""
        # params can be a dict or list - normalize to dict for backtest engine
        if isinstance(self.params, dict):
            params_dict = self.params
        else:
            # Legacy: list format - convert to dict
            params_dict = {}
            if self.indicator in ("RSI", "SMA", "EMA", "BBANDS", "CCI", "ADX", "ATR"):
                params_dict["period"] = int(self.params[0]) if self.params else 14
            elif self.indicator == "MACD":
                params_dict["fast"] = (
                    int(self.params[0]) if len(self.params) > 0 else 12
                )
                params_dict["slow"] = (
                    int(self.params[1]) if len(self.params) > 1 else 26
                )
                params_dict["signal"] = (
                    int(self.params[2]) if len(self.params) > 2 else 9
                )
            elif self.indicator == "SUPERTREND":
                params_dict["period"] = (
                    int(self.params[0]) if len(self.params) > 0 else 7
                )
                params_dict["multiplier"] = (
                    self.params[1] if len(self.params) > 1 else 3.0
                )
            else:
                params_dict["period"] = int(self.params[0]) if self.params else 14

        result = {
            "indicator": self.indicator,
            "params": params_dict,
            "comparison": self.comparison,
            "value": self.value,
        }
        if self.ref_indicator:
            result["ref_indicator"] = self.ref_indicator
            if isinstance(self.ref_params, dict):
                result["ref_params"] = self.ref_params
            else:
                result["ref_params"] = list(self.ref_params) if self.ref_params else []
        return result


class CompiledExit:
    """Compiled exit conditions."""

    def __init__(
        self,
        time_exit: Optional[str] = None,
        target_pct: Optional[float] = None,
        stoploss_pct: Optional[float] = None,
        trailing_sl_pct: Optional[float] = None,
    ):
        self.time_exit = time_exit
        self.target_pct = target_pct
        self.stoploss_pct = stoploss_pct
        self.trailing_sl_pct = trailing_sl_pct

    def to_dict(self) -> dict:
        """Convert to exit conditions dictionary."""
        return {
            "time_exit": self.time_exit,
            "target_pct": self.target_pct,
            "stoploss_pct": self.stoploss_pct,
            "trailing_sl_pct": self.trailing_sl_pct,
        }


class StrategySignal(Enum):
    """Trading signals generated by strategy evaluation."""

    NONE = "none"
    BUY = "buy"
    SELL = "sell"
    EXIT = "exit"
    SHORT = "short"
    COVER = "cover"


class StrategyContext:
    """Context for strategy evaluation - contains current candle and computed indicators."""

    def __init__(
        self,
        current_idx: int,
        time,
        open: float,
        high: float,
        low: float,
        close: float,
        volume: int,
    ):
        self.current_idx = current_idx
        self.time = time
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.indicators = {}
        self.bars_since_entry = 0
        self.entry_price = None
        self.bars_in_trade = 0


class TradeState:
    """Current trading state."""

    def __init__(self):
        self.in_position = False
        self.position_type = None
        self.entry_price = None
        self.entry_time = None
        self.highest_price = None
        self.lowest_price = None
        self.trailing_stop = None
