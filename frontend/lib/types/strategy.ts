/**
 * Strategy V2 Types
 * TypeScript definitions for the Visual Strategy Builder
 */

// ============================================================================
// INDICATOR TYPES
// ============================================================================

export type IndicatorName =
    | 'RSI'
    | 'SMA'
    | 'EMA'
    | 'SUPERTREND'
    | 'MACD'
    | 'ATR'
    | 'ADX'
    | 'BBANDS'
    | 'STOCH'
    | 'CCI'
    | 'ROC'
    | 'WILLR'
    | 'OBV'
    | 'VWAP'

export interface IndicatorParam {
    name: string
    type: string
    default: number | string
}

export interface IndicatorDefinition {
    name: IndicatorName
    params: IndicatorParam[]
    description: string
}

// ============================================================================
// MATH EXPRESSION TYPES (Recursive)
// ============================================================================

export type MathOperand =
    | IndicatorRef
    | PriceRef
    | ValueRef
    | MathExpr
    | number

export interface IndicatorRef {
    type: 'indicator'
    name: string
    params: (number | string)[]
}

export interface PriceRef {
    type: 'price'
    field: PriceField
}

export type PriceField =
    | 'close'
    | 'open'
    | 'high'
    | 'low'
    | 'volume'
    | 'ohlc'
    | 'hl2'
    | 'hlc3'
    | 'hlcc4'

export interface ValueRef {
    type: 'value'
    value: number
}

export interface MathExpr {
    type: 'math'
    left: MathOperand
    operator: MathOperator
    right: MathOperand
}

export type MathOperator = '*' | '+' | '-' | '/'

// ============================================================================
// CONDITION TYPES
// ============================================================================

export type ComparisonOperator = '<' | '>' | '<=' | '>=' | '==' | '!='

export interface Condition {
    id: string
    left: MathOperand
    operator: ComparisonOperator
    right: MathOperand
}

// ============================================================================
// EXIT RULE TYPES
// ============================================================================

export type ExitRuleType = 'stoploss' | 'target' | 'trailing' | 'time' | 'indicator_exit'

export interface StopLossRule {
    type: 'stoploss'
    id: string
    percent: number
    priority: number
    trailing: boolean
}

export interface TargetRule {
    type: 'target'
    id: string
    percent: number
    priority: number
}

export interface TrailingStopRule {
    type: 'trailing'
    id: string
    percent: number
    priority: number
    activationPercent?: number
}

export interface TimeExitRule {
    type: 'time'
    id: string
    time: string
    priority: number
}

export interface IndicatorExitRule {
    type: 'indicator_exit'
    id: string
    condition: Condition
    priority: number
}

export type ExitRule =
    | StopLossRule
    | TargetRule
    | TrailingStopRule
    | TimeExitRule
    | IndicatorExitRule

// ============================================================================
// RISK CONFIGURATION
// ============================================================================

export interface RiskConfig {
    max_trades_per_day: number
    max_loss_per_day: number
    quantity: number
    reentry_after_sl: boolean
    max_concurrent_trades: number
    partial_exit_pct?: number
}

// ============================================================================
// STRATEGY V2
// ============================================================================

export type AssetType = 'EQUITY' | 'FNO'
export type IndexType = 'NIFTY' | 'BANKNIFTY' | 'FINNIFTY'
export type OptionType = 'CE' | 'PE' | 'BOTH'
export type StrikeType = 'ATM' | 'ITM1' | 'ITM2' | 'ITM3' | 'OTM1' | 'OTM2' | 'OTM3'
export type TimeframeType = '1m' | '5m' | '15m' | '30m' | '1h' | '1d' | '1w'
export type LogicType = 'ALL' | 'ANY'

export interface StrategyV2 {
    name: string
    version: '2.0'
    symbols: string[]
    asset_type: AssetType
    index?: IndexType
    option_type?: OptionType
    strike_type?: StrikeType
    timeframe: TimeframeType
    entry_logic: LogicType
    entry_conditions: Condition[]
    exit_logic: LogicType
    exit_rules: ExitRule[]
    risk: RiskConfig
    backtest_from?: string
    backtest_to?: string
}

// ============================================================================
// API REQUEST/RESPONSE TYPES
// ============================================================================

export interface ValidationError {
    field?: string
    message: string
    severity: 'error' | 'warning'
}

export interface ValidationResult {
    valid: boolean
    errors: string[]
    warnings: string[]
    summary?: {
        name: string
        symbols: string[]
        timeframe: string
        entry_logic: LogicType
        entry_conditions_count: number
        exit_rules_count: number
        risk_config: RiskConfig
    }
}

export interface SaveStrategyRequest {
    strategy: StrategyV2
    strategy_id?: string
}

export interface SaveStrategyResponse {
    strategy_id: string
    name: string
    created_at: string
    symbols: string[]
}

export interface LoadStrategyResponse {
    strategy: StrategyV2
    strategy_id: string
    created_at: string
    updated_at?: string
}

// ============================================================================
// BUILDER STATE TYPES
// ============================================================================

export interface BuilderState {
    strategy: StrategyV2
    isDirty: boolean
    isValidating: boolean
    isSaving: boolean
    isBacktesting: boolean
    validationResult: ValidationResult | null
    editMode: boolean
    strategyId?: string
}

// ============================================================================
// CONSTANTS
// ============================================================================

export const TIMEFRAMES: { value: TimeframeType; label: string; description: string }[] = [
    { value: '1m', label: '1 Min', description: 'Fastest - real-time scalping' },
    { value: '5m', label: '5 Min', description: 'Best for intraday scalping' },
    { value: '15m', label: '15 Min', description: 'Best for intraday trends' },
    { value: '30m', label: '30 Min', description: 'Swing trading' },
    { value: '1h', label: '1 Hour', description: 'Position trading' },
    { value: '1d', label: 'Daily', description: 'Long-term investing' },
    { value: '1w', label: 'Weekly', description: 'Swing/position' },
]

export const OPERATORS: { value: ComparisonOperator; label: string; symbol: string }[] = [
    { value: '<', label: 'Less than', symbol: '<' },
    { value: '>', label: 'Greater than', symbol: '>' },
    { value: '<=', label: 'Less or equal', symbol: '≤' },
    { value: '>=', label: 'Greater or equal', symbol: '≥' },
    { value: '==', label: 'Equal to', symbol: '=' },
    { value: '!=', label: 'Not equal', symbol: '≠' },
]

export const INDICATORS_LIST: IndicatorDefinition[] = [
    { name: 'RSI', params: [{ name: 'period', type: 'number', default: 14 }], description: 'Relative Strength Index' },
    { name: 'SMA', params: [{ name: 'period', type: 'number', default: 20 }], description: 'Simple Moving Average' },
    { name: 'EMA', params: [{ name: 'period', type: 'number', default: 20 }], description: 'Exponential Moving Average' },
    { name: 'SUPERTREND', params: [{ name: 'period', type: 'number', default: 7 }, { name: 'multiplier', type: 'number', default: 3 }], description: 'Supertrend indicator' },
    { name: 'MACD', params: [{ name: 'fast', type: 'number', default: 12 }, { name: 'slow', type: 'number', default: 26 }, { name: 'signal', type: 'number', default: 9 }], description: 'MACD (signal line crossover)' },
    { name: 'ATR', params: [{ name: 'period', type: 'number', default: 14 }], description: 'Average True Range' },
    { name: 'ADX', params: [{ name: 'period', type: 'number', default: 14 }], description: 'Average Directional Index' },
    { name: 'BBANDS', params: [{ name: 'period', type: 'number', default: 20 }, { name: 'std_dev', type: 'number', default: 2 }], description: 'Bollinger Bands' },
    { name: 'STOCH', params: [{ name: 'k_period', type: 'number', default: 14 }, { name: 'd_period', type: 'number', default: 3 }], description: 'Stochastic Oscillator' },
    { name: 'CCI', params: [{ name: 'period', type: 'number', default: 20 }], description: 'Commodity Channel Index' },
    { name: 'ROC', params: [{ name: 'period', type: 'number', default: 10 }], description: 'Rate of Change' },
    { name: 'WILLR', params: [{ name: 'period', type: 'number', default: 14 }], description: 'Williams %R' },
    { name: 'OBV', params: [], description: 'On Balance Volume' },
    { name: 'VWAP', params: [], description: 'Volume Weighted Average Price' },
]

export const DATE_PRESETS = [
    { label: 'Last 30 Days', days: 30 },
    { label: 'Last 90 Days', days: 90 },
    { label: 'Year to Date', days: -1 },
    { label: 'Last 1 Year', days: 365 },
    { label: 'Last 2 Years', days: 730 },
    { label: 'All Time', days: -2 },
]

// ============================================================================
// DEFAULT VALUES
// ============================================================================

export const DEFAULT_RISK_CONFIG: RiskConfig = {
    max_trades_per_day: 3,
    max_loss_per_day: 5000,
    quantity: 1,
    reentry_after_sl: false,
    max_concurrent_trades: 1,
    partial_exit_pct: undefined,
}

export const createDefaultStrategy = (): StrategyV2 => ({
    name: '',
    version: '2.0',
    symbols: [],
    asset_type: 'EQUITY',
    timeframe: '15m',
    entry_logic: 'ALL',
    entry_conditions: [],
    exit_logic: 'ANY',
    exit_rules: [],
    risk: { ...DEFAULT_RISK_CONFIG },
    backtest_from: undefined,
    backtest_to: undefined,
})

export const createDefaultCondition = (): Condition => ({
    id: `cond_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    left: { type: 'indicator', name: 'RSI', params: [14] },
    operator: '<',
    right: { type: 'value', value: 30 },
})

export const createDefaultExitRule = (type: ExitRuleType): ExitRule => {
    const baseId = `exit_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    switch (type) {
        case 'stoploss':
            return { type: 'stoploss', id: baseId, percent: 2, priority: 1, trailing: false }
        case 'target':
            return { type: 'target', id: baseId, percent: 5, priority: 2 }
        case 'trailing':
            return { type: 'trailing', id: baseId, percent: 1.5, priority: 3, activationPercent: 3 }
        case 'time':
            return { type: 'time', id: baseId, time: '15:15', priority: 4 }
        default:
            return { type: 'stoploss', id: baseId, percent: 2, priority: 1, trailing: false }
    }
}
