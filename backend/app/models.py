"""Pydantic models for strategy and backtest."""

from pydantic import BaseModel
from typing import Optional, Literal, List
from datetime import date


class EntryCondition(BaseModel):
    indicator: Literal["EMA_CROSS", "RSI_LEVEL", "PRICE_ACTION", "SUPERTREND"]
    params: dict  # e.g. {"fast": 9, "slow": 21} for EMA_CROSS
    logic: Literal["AND", "OR"] = "AND"


class ExitCondition(BaseModel):
    target_pct: Optional[float] = None       # e.g. 50.0 = 50% profit
    stoploss_pct: Optional[float] = None     # e.g. 30.0 = 30% loss
    trailing_sl_pct: Optional[float] = None
    time_exit: Optional[str] = None          # "15:15" IST


class RiskSettings(BaseModel):
    max_trades_per_day: int = 3
    max_loss_per_day: float = 5000.0         # Rs.
    quantity_lots: int = 1
    lot_size: int = 1                        # 1 for equity (shares), 50 for NIFTY FnO, etc.
    reentry_after_sl: bool = False


class StrategyRequest(BaseModel):
    name: str
    asset_type: Literal["EQUITY", "FNO"] = "EQUITY"
    # Equity fields - support single symbol or multiple symbols
    symbols: Optional[List[str]] = None      # e.g. ["RELIANCE", "TCS"] - NEW: multi-stock support
    symbol: Optional[str] = None             # e.g. "RELIANCE" - legacy single symbol (for backward compat)
    # FnO fields (optional, only required when asset_type == "FNO")
    index: Optional[Literal["NIFTY", "BANKNIFTY", "FINNIFTY"]] = None
    option_type: Optional[Literal["CE", "PE", "BOTH"]] = None
    strike_type: Optional[Literal["ATM", "ITM1", "ITM2", "ITM3", "OTM1", "OTM2", "OTM3"]] = None
    timeframe: Literal["1min", "5min", "15min", "1D"] = "1D"
    entry_conditions: list[EntryCondition]
    exit_conditions: ExitCondition
    risk: RiskSettings
    backtest_from: Optional[date] = None
    backtest_to: Optional[date] = None
    creation_prices: Optional[dict[str, float]] = None


class StrategyResponse(BaseModel):
    strategy_id: str
    name: str
    created_at: str
    symbols: Optional[List[str]] = None  # Return list of symbols
    creation_prices: Optional[dict[str, float]] = None


class BacktestRequest(BaseModel):
    strategy_id: str
    symbol: Optional[str] = None  # Optional: run backtest for specific symbol from multi-stock strategy


class TradeRecord(BaseModel):
    trade_no: int
    entry_time: str
    entry_price: float
    exit_time: str
    exit_price: float
    pnl: float
    pnl_pct: float
    exit_reason: str  # "TARGET", "SL", "TIME", "TRAILING"


class BacktestSummary(BaseModel):
    backtest_id: str
    strategy_id: str
    symbol: Optional[str] = None  # Symbol this backtest is for (for multi-stock strategies)
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    max_drawdown: float
    avg_trade_pnl: float
    best_trade: float
    worst_trade: float
    candle_count: int
    date_range: str


class CandleData(BaseModel):
    time: list[int]    # Unix timestamps
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[int]


# --- Live Trading Module Models ---

class LiveStrategy(BaseModel):
    id: Optional[int] = None
    strategy_id: str
    name: str
    user_id: int
    broker: str
    status: str = "ACTIVE"
    symbols: List[str]
    risk_settings: RiskSettings
    entry_conditions: List[EntryCondition]
    exit_conditions: ExitCondition
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class Position(BaseModel):
    id: Optional[int] = None
    live_strategy_id: int
    symbol: str
    exchange: str = "NSE"
    entry_price: float
    quantity: int
    product_type: str = "INTRADAY"
    stoploss: Optional[float] = None
    target: Optional[float] = None
    status: str = "OPEN"
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    exit_reason: Optional[str] = None
    broker_order_id: Optional[str] = None
    broker_exit_order_id: Optional[str] = None


class TradingLog(BaseModel):
    id: Optional[int] = None
    live_strategy_id: int
    position_id: Optional[int] = None
    event_type: str
    details: Optional[str] = None
    event_data: Optional[dict] = None
    timestamp: Optional[str] = None


class TradingActivateRequest(BaseModel):
    strategy_id: str
    broker: str
    risk_custom: Optional[RiskSettings] = None


class PositionResponse(BaseModel):
    position: Position
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
