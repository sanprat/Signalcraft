"""
Strategy V2 schemas — JSON-first strategy definition.

This module provides Pydantic schemas for the JSON-first strategy engine.
Backend accepts ONLY JSON, never ZenScript.
"""

from __future__ import annotations

from typing import Optional, List, Union, Literal, Any
from pydantic import BaseModel, Field, field_validator, model_validator
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# INDICATOR REGISTRY
# ============================================================================

INDICATOR_REGISTRY: dict[str, dict] = {
    # name: {"params": [("param_name", type, default), ...], "returns": "series"}
    "RSI": {
        "params": [("period", int, 14)],
        "returns": "scalar",
        "description": "Relative Strength Index",
    },
    "SMA": {
        "params": [("period", int, 20), ("field", str, "close")],
        "returns": "scalar",
        "description": "Simple Moving Average",
    },
    "EMA": {
        "params": [("period", int, 20), ("field", str, "close")],
        "returns": "scalar",
        "description": "Exponential Moving Average",
    },
    "SUPERTREND": {
        "params": [("period", int, 7), ("multiplier", float, 3.0)],
        "returns": "scalar",
        "description": "Supertrend indicator",
    },
    "MACD": {
        "params": [("fast", int, 12), ("slow", int, 26), ("signal", int, 9)],
        "returns": "multi",
        "description": "MACD (returns macd, signal, histogram)",
    },
    "ATR": {
        "params": [("period", int, 14)],
        "returns": "scalar",
        "description": "Average True Range",
    },
    "ADX": {
        "params": [("period", int, 14)],
        "returns": "scalar",
        "description": "Average Directional Index",
    },
    "BBANDS": {
        "params": [("period", int, 20), ("std_dev", float, 2.0)],
        "returns": "multi",
        "description": "Bollinger Bands (returns upper, middle, lower)",
    },
    "STOCH": {
        "params": [("k_period", int, 14), ("d_period", int, 3)],
        "returns": "multi",
        "description": "Stochastic Oscillator (returns k, d)",
    },
    "CCI": {
        "params": [("period", int, 20)],
        "returns": "scalar",
        "description": "Commodity Channel Index",
    },
    "ROC": {
        "params": [("period", int, 10)],
        "returns": "scalar",
        "description": "Rate of Change",
    },
    "WILLR": {
        "params": [("period", int, 14)],
        "returns": "scalar",
        "description": "Williams %R",
    },
    "OBV": {
        "params": [],
        "returns": "scalar",
        "description": "On Balance Volume",
    },
    "VWAP": {
        "params": [],
        "returns": "scalar",
        "description": "Volume Weighted Average Price",
    },
}

# Valid price/field references
PRICE_FIELDS = {
    "close",
    "open",
    "high",
    "low",
    "volume",
    "ohlc",
    "hl2",
    "hlc3",
    "hlcc4",
}


# ============================================================================
# BASE TYPES FOR RECURSIVE EXPRESSIONS
# ============================================================================


class IndicatorRef(BaseModel):
    """Reference to an indicator with parameters."""

    type: Literal["indicator"] = "indicator"
    name: str = Field(..., description="Indicator name (e.g., RSI, SMA, EMA)")
    params: List[Union[int, float, str]] = Field(
        default_factory=list, description="Indicator parameters"
    )

    @field_validator("name")
    @classmethod
    def validate_indicator_name(cls, v: str) -> str:
        """Validate indicator name against registry."""
        if v.upper() not in INDICATOR_REGISTRY:
            raise ValueError(
                f"Unknown indicator '{v}'. Available: {list(INDICATOR_REGISTRY.keys())}"
            )
        return v.upper()

    @field_validator("params")
    @classmethod
    def validate_params(cls, v: List, info) -> List:
        """Validate parameter count against registry."""
        name = info.data.get("name", "").upper()
        if name in INDICATOR_REGISTRY:
            expected_params = INDICATOR_REGISTRY[name]["params"]
            expected_count = len(expected_params)
            # Allow partial params (use defaults)
            if len(v) > expected_count:
                raise ValueError(
                    f"Indicator '{name}' expects at most {expected_count} params, "
                    f"got {len(v)}"
                )
        return v


class PriceRef(BaseModel):
    """Reference to a price field."""

    type: Literal["price"] = "price"
    field: str = Field(
        default="close", description="Price field (close, open, high, low, volume)"
    )

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        """Validate price field."""
        if v.lower() not in PRICE_FIELDS:
            raise ValueError(
                f"Invalid price field '{v}'. Available: {list(PRICE_FIELDS)}"
            )
        return v.lower()


class ValueRef(BaseModel):
    """Reference to a constant value."""

    type: Literal["value"] = "value"
    value: float = Field(..., description="Constant numeric value")


# Forward reference for recursive MathExpr
MathExprT = Union["MathExpr", IndicatorRef, PriceRef, ValueRef, float]


class MathExpr(BaseModel):
    """
    Recursive math expression for combining indicators/prices.

    Examples:
    - SMA(VOLUME, 20) * 1.5
    - RSI(14) + 10
    - (close - open) / open * 100
    """

    type: Literal["math"] = "math"
    left: MathExprT = Field(..., description="Left operand")
    operator: Literal["*", "+", "-", "/"] = Field(..., description="Math operator")
    right: MathExprT = Field(..., description="Right operand")

    model_config = {"arbitrary_types_allowed": True}


class Condition(BaseModel):
    """
    Single condition for entry/exit logic.

    Compares left side to right side using the operator.
    """

    id: Optional[str] = Field(default=None, description="Frontend-generated ID")
    left: MathExprT = Field(..., description="Left side of comparison")
    operator: Literal[
        "<",
        ">",
        "<=",
        ">=",
        "==",
        "!=",
        "crosses_above",
        "crosses_below",
    ] = Field(
        ..., description="Comparison operator"
    )
    right: MathExprT = Field(..., description="Right side of comparison")

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def validate_comparison(self) -> "Condition":
        """Validate that the condition makes sense."""
        # Basic validation - more complex validation happens in builder
        return self


# ============================================================================
# EXIT RULES
# ============================================================================


class StopLossRule(BaseModel):
    """Stop loss exit rule."""

    type: Literal["stoploss"] = "stoploss"
    percent: float = Field(..., gt=0, description="Stop loss percentage")
    priority: int = Field(
        default=1, ge=1, le=4, description="Execution priority (1=highest)"
    )
    trailing: bool = Field(default=False, description="Use trailing stop loss")
    # Optional fields for frontend compatibility
    id: Optional[str] = Field(default=None, description="Frontend-generated ID")


class TargetRule(BaseModel):
    """Target/profit exit rule."""

    type: Literal["target"] = "target"
    percent: float = Field(..., gt=0, description="Target profit percentage")
    priority: int = Field(
        default=3, ge=1, le=4, description="Execution priority (1=highest)"
    )
    # Optional fields for frontend compatibility
    id: Optional[str] = Field(default=None, description="Frontend-generated ID")


class TrailingStopRule(BaseModel):
    """Trailing stop exit rule."""

    type: Literal["trailing"] = "trailing"
    percent: float = Field(..., gt=0, description="Trailing stop percentage from peak")
    priority: int = Field(
        default=2, ge=1, le=4, description="Execution priority (1=highest)"
    )
    # Optional fields for frontend compatibility
    id: Optional[str] = Field(default=None, description="Frontend-generated ID")
    activationPercent: Optional[float] = Field(
        default=None, gt=0, description="Activation threshold for trailing stop"
    )


class TimeExitRule(BaseModel):
    """Time-based exit rule."""

    type: Literal["time"] = "time"
    time: str = Field(
        ..., pattern=r"^\d{2}:\d{2}$", description="Exit time in HH:MM format (IST)"
    )
    priority: int = Field(
        default=4, ge=1, le=4, description="Execution priority (1=highest)"
    )
    # Optional fields for frontend compatibility
    id: Optional[str] = Field(default=None, description="Frontend-generated ID")


class IndicatorExitRule(BaseModel):
    """Exit when indicator condition is met."""

    type: Literal["indicator_exit"] = "indicator_exit"
    condition: Condition = Field(..., description="Indicator condition to trigger exit")
    priority: int = Field(default=5, ge=1, le=10, description="Execution priority")
    # Optional fields for frontend compatibility
    id: Optional[str] = Field(default=None, description="Frontend-generated ID")


# Union type for all exit rules
ExitRule = Union[
    StopLossRule, TargetRule, TrailingStopRule, TimeExitRule, IndicatorExitRule
]


# ============================================================================
# RISK CONFIGURATION
# ============================================================================


class RiskConfig(BaseModel):
    """Risk management configuration."""

    max_trades_per_day: int = Field(default=3, ge=1, description="Max trades per day")
    max_loss_per_day: float = Field(
        default=5000.0, ge=0, description="Max daily loss (Rs)"
    )
    quantity: int = Field(default=1, gt=0, description="Quantity per trade")
    reentry_after_sl: bool = Field(
        default=False, description="Allow re-entry after stop loss"
    )
    max_concurrent_trades: int = Field(
        default=1, ge=1, description="Max concurrent open positions"
    )
    partial_exit_pct: Optional[float] = Field(
        default=None, ge=0, le=100, description="Partial exit percentage at target"
    )


# ============================================================================
# STRATEGY V2
# ============================================================================


class StrategyV2(BaseModel):
    """
    Complete strategy definition for JSON-first engine.

    JSON is the source of truth. Backend accepts only JSON, never ZenScript.
    """

    # Basic info
    name: str = Field(..., min_length=1, max_length=100, description="Strategy name")
    version: Literal["2.0"] = Field(default="2.0", description="Strategy version")

    # Symbol configuration
    symbols: List[str] = Field(
        ..., min_length=1, description="Trading symbols (e.g., ['RELIANCE', 'TCS'])"
    )

    # Asset type and FnO specifics
    asset_type: Literal["EQUITY", "FNO"] = Field(
        default="EQUITY", description="Asset type"
    )
    index: Optional[Literal["NIFTY", "BANKNIFTY", "FINNIFTY"]] = Field(
        default=None, description="Index for FnO strategies"
    )
    option_type: Optional[Literal["CE", "PE", "BOTH"]] = Field(
        default=None, description="Option type for FnO"
    )
    strike_type: Optional[
        Literal["ATM", "ITM1", "ITM2", "ITM3", "OTM1", "OTM2", "OTM3"]
    ] = Field(default=None, description="Strike type for FnO")

    # Timeframe
    timeframe: Literal["1m", "5m", "15m", "30m", "1h", "1d", "1w"] = Field(
        default="1d", description="Candle timeframe"
    )

    # Entry logic - GLOBAL (ALL or ANY, not per-condition)
    entry_logic: Literal["ALL", "ANY"] = Field(
        default="ALL", description="Entry condition logic: ALL (AND) or ANY (OR)"
    )
    entry_conditions: List[Condition] = Field(
        ..., min_length=1, description="Entry conditions"
    )

    # Exit logic - GLOBAL (ALL or ANY for exit rules)
    exit_logic: Literal["ALL", "ANY"] = Field(
        default="ANY", description="Exit rule logic: ALL (AND) or ANY (OR)"
    )
    exit_rules: List[ExitRule] = Field(
        ..., min_length=1, description="Exit rules with priority"
    )

    # Risk management
    risk: RiskConfig = Field(default_factory=RiskConfig)

    # Backtest date range (optional)
    backtest_from: Optional[str] = Field(
        default=None, description="Backtest start date (YYYY-MM-DD)"
    )
    backtest_to: Optional[str] = Field(
        default=None, description="Backtest end date (YYYY-MM-DD)"
    )

    @model_validator(mode="after")
    def validate_strategy(self) -> "StrategyV2":
        """Validate complete strategy."""
        # FnO requires index and option_type
        if self.asset_type == "FNO":
            if not self.index:
                raise ValueError("FnO strategies require 'index' field")
            if not self.option_type:
                raise ValueError("FnO strategies require 'option_type' field")

        # Validate exit rules have correct priorities
        priorities = [r.priority for r in self.exit_rules]
        if len(priorities) != len(set(priorities)):
            # Allow same priority but warn
            logger.warning("Multiple exit rules have the same priority")

        return self

    model_config = {"arbitrary_types_allowed": True}


# ============================================================================
# API REQUEST/RESPONSE MODELS
# ============================================================================


class StrategyBacktestRequestV2(BaseModel):
    """Request model for V2 backtest."""

    strategy: StrategyV2
    mode: Literal["quick", "full"] = Field(
        default="quick", description="Backtest mode (quick=last 6mo, full=all data)"
    )


class StrategyValidationResult(BaseModel):
    """Result of strategy validation."""

    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    summary: Optional[dict] = None


class TradeRecordV2(BaseModel):
    """Trade record from V2 backtest."""

    trade_no: int
    symbol: str
    entry_time: str
    entry_price: float
    exit_time: Optional[str] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    exit_reason: Optional[str] = None
    quantity: int
    holding_period: Optional[int] = None  # in candles

    model_config = {"arbitrary_types_allowed": True}


class EquityCurvePoint(BaseModel):
    """Single point in equity curve."""

    time: str
    equity: float
    drawdown: float
    drawdown_pct: float


class SymbolResultV2(BaseModel):
    """Backtest result for a single symbol."""

    symbol: str
    trades: List[TradeRecordV2]
    equity_curve: List[EquityCurvePoint]
    metrics: dict


class BacktestResultV2(BaseModel):
    """Complete V2 backtest result."""

    strategy_name: str
    mode: str
    per_symbol: Dict[str, SymbolResultV2] = Field(description="Per-symbol results")
    combined: dict = Field(description="Aggregated metrics across all symbols")
    date_range: str
    execution_time_ms: float

    model_config = {"arbitrary_types_allowed": True}
