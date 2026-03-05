-- Live Trading Module Schema
-- Created: 2026-03-03

-- Active live strategies configuration
CREATE TABLE IF NOT EXISTS live_strategies (
    id SERIAL PRIMARY KEY,
    strategy_id VARCHAR(100) NOT NULL,
    name VARCHAR(255),
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    broker VARCHAR(50) NOT NULL,  -- 'dhan', 'shoonya', 'zerodha', 'flattrade'
    status VARCHAR(50) DEFAULT 'ACTIVE',  -- 'ACTIVE', 'PAUSED', 'STOPPED'
    symbols JSONB,  -- Array of symbols for multi-stock strategies
    risk_settings JSONB,
    entry_conditions JSONB,
    exit_conditions JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Open and closed positions
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    live_strategy_id INTEGER REFERENCES live_strategies(id) ON DELETE CASCADE,
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(20) DEFAULT 'NSE',
    entry_price DECIMAL(15,2) NOT NULL,
    quantity INTEGER NOT NULL,
    product_type VARCHAR(20) DEFAULT 'INTRADAY',  -- 'INTRADAY', 'CNC', 'MIS'
    stoploss DECIMAL(15,2),
    target DECIMAL(15,2),
    status VARCHAR(50) DEFAULT 'OPEN',  -- 'OPEN', 'CLOSED', 'SQUARED_OFF'
    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    exit_time TIMESTAMP,
    exit_price DECIMAL(15,2),
    pnl DECIMAL(15,2),
    pnl_pct DECIMAL(10,2),
    exit_reason VARCHAR(100),  -- 'TARGET', 'STOPLOSS', 'TIME', 'MANUAL'
    broker_order_id VARCHAR(100),
    broker_exit_order_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit logs for automated trading events
CREATE TABLE IF NOT EXISTS trading_logs (
    id SERIAL PRIMARY KEY,
    live_strategy_id INTEGER REFERENCES live_strategies(id) ON DELETE CASCADE,
    position_id INTEGER REFERENCES positions(id) ON DELETE SET NULL,
    event_type VARCHAR(100) NOT NULL,  -- 'SIGNAL_DETECTED', 'ORDER_PLACED', 'ORDER_FILLED', 'EXIT_TRIGGERED'
    details TEXT,
    event_data JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common lookups
CREATE INDEX IF NOT EXISTS idx_live_strategies_user ON live_strategies(user_id);
CREATE INDEX IF NOT EXISTS idx_live_strategies_status ON live_strategies(status);
CREATE INDEX IF NOT EXISTS idx_positions_strategy ON positions(live_strategy_id);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_trading_logs_strategy ON trading_logs(live_strategy_id);
