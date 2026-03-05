# Pytrader — Progress Report

> **Last updated:** 2026-03-03 23:55 IST
> **Session ID:** `screener-enhancements-live-trading-prep`

---

## 🚀 Major Update: Robust Historical Data Fallback & Timezone Fixes (March 5, 2026 - Evening)

### **Overview**
Resolved critical data ingestion and timezone parsing issues for the automated daily updater script ensuring uninterrupted historical data collection.

---

### 1. Robust Dhan API Fallback (`daily_updater.py`)
- **Issue**: The Dhan API started throwing `DH-905` (HTTP 400) parameter errors for the standard 1-day (1D) historical data endpoint for NIFTY500 stocks.
- **Resolution**: Implemented a sophisticated 1-minute fallback. When `DH-905` is encountered, the script automatically downloads high-resolution 1-minute intraday candles, filters for market hours, and mathematically aggregates them (first Open, max High, min Low, last Close, sum Volume) back into a standard 1D candle.

### 2. PyArrow & macOS Compatibility (`check_data_coverage.py`)
- **Issue**: The data coverage checker was failing on the VPS due to hidden macOS `._*` AppleDouble files being pulled via Git, and older PyArrow engines crashing on timezone parsing (`NoneType object has no attribute timezone`).
- **Resolution**: 
  - Added filter logic to seamlessly skip hidden OS files.
  - Enforced the `engine='pyarrow'` flag and used strict standard UTC conversions `pd.to_datetime([], utc=True, errors='coerce')` to completely bypass timezone interpretation crashes on the remote Linux box.
  - Wrote a local diagnostic tool (`check_dates.py`) to bypass PyArrow when evaluating the VPS environment's raw parquet strings.

---

## 🚀 Major Update: Live Trading Deployment & Integrated Dashboard (March 3, 2026 - Late Night)

### **Overview**
Finalized the end-to-end integration of the **Live Trading System**. Users can now deploy strategies built in the Strategy Builder directly to a live (or paper) trading environment, monitor unrealized/realized P&L in real-time, and manage positions through a centralized dashboard.

---

### 1. Live Trading Backend Architecture
Implemented a robust backend foundation for multi-broker live execution using PostgreSQL for reliable state management.

| Component | Status | Details |
|-----------|--------|---------|
| **Position Manager** | ✅ Done | Handles position lifecycle, risk checks, and monitoring loop in `backend/app/core/position_manager.py`. |
| **Persistence Layer** | ✅ Done | Migrated live strategy and position tracking to PostgreSQL for data durability. |
| **API Endpoints** | ✅ Done | Added `deploy`, `status`, `toggle`, `positions`, and `stop` endpoints in `backend/app/routers/live.py`. |

### 2. Strategy Builder: "Deploy Live" Integration
The Strategy Builder now serves as a direct gateway into live markets.

- **Deployment Modal:** Added broker selection (Dhan, Shoonya, Zerodha, Flattrade) and execution mode (Live/Paper).
- **One-Click Deploy:** Seamless transition from strategy creation/saving to live monitoring.
- **Risk Configuration:** Ensures strategy parameters (target, SL, qty) are correctly mapped from the `StrategyRequest` model.

### 3. Real-Time Live Dashboard
Transformed the `/live` page into a production-ready monitoring center.

- **Live P&L Tracking:** Real-time calculation of unrealized P&L using live market quotes via `useQuotes` hook.
- **Strategy Management:** Toggle strategies between `ACTIVE` and `PAUSED` or stop them entirely.
- **Trade History:** Automated logging of entry/exit prices, reasons, and realized profits.

---

## 🚀 Major Update: Enhanced Stock Screener with Multi-Criteria Screening (March 3, 2026 - Evening)

### **Overview**
Transformed the existing single-screener implementation into a **powerful multi-criteria screening platform** with seamless strategy builder integration. Users can now combine multiple technical screeners, customize parameters, and directly build strategies on screened stocks.

---

### 1. Multi-Criteria Screening System

#### **Objective:**
Enable users to run multiple screeners simultaneously and find stocks passing ALL selected criteria (intersection logic).

#### **What Changed:**

**Before:**
- User could run only ONE screener at a time
- Results showed stocks passing that single screener
- No connection to strategy builder

**After:**
- User can select MULTIPLE screeners (e.g., Minervini + RSI + Volume Surge)
- Returns stocks passing ALL selected screeners
- One-click "Build Strategy on These Stocks" button

#### **Backend Changes:**

| File | Changes |
|------|---------|
| `backend/app/models.py` | Updated `ScreenerRequest` to accept `screener_ids: List[str]` instead of single `screener_id` |
| `backend/app/routers/screeners.py` | Rewrote `/api/screeners/run` to iterate over all symbols, run all selected screeners, filter to intersection |
| `backend/app/services/screener.py` | No changes needed (individual screener functions reused) |

**Key Logic:**
```python
# For each symbol, run ALL selected screeners
for sym in symbols:
    sym_results = []
    for screener_id in req.screener_ids:
        res = run_screener(screener_id, sym, params.get(screener_id))
        sym_results.append(res)
    
    # Only include if ALL screeners pass
    all_passed = all(r.get("pass", False) for r in sym_results)
    if all_passed:
        # Combine metrics from all screeners
        combined = merge_results(sym_results)
        results.append(combined)
```

#### **Frontend Changes:**

| File | Changes |
|------|---------|
| `frontend/components/dashboard/StocksView.tsx` | Replaced single-select dropdown with multi-select checkbox dropdown, added selected screener chips, added "Advanced ⚙" button for parameters, added "Build Strategy" button |

**New UI Components:**
- **Multi-select dropdown**: "+ Add Screener..." with checkboxes
- **Screener chips**: Visual tags showing active screeners (click × to remove)
- **Run Screener (X)**: Button shows count of selected screeners
- **Advanced Panel**: Collapsible section with editable parameters per screener
- **Build Strategy Button**: Green banner with "🚀 Build Strategy on These X Stocks"

---

### 2. Parameter Customization System

#### **Objective:**
Allow users to customize screener parameters before running (e.g., change RSI threshold from 50 to 30).

#### **Backend Changes:**

| File | Changes |
|------|---------|
| `backend/app/routers/screeners.py` | Updated `/api/screeners/list` to return default parameters for each screener |

**Response Format:**
```json
{
  "screeners": [
    {
      "id": "rsi_momentum",
      "name": "RSI Momentum",
      "params": {
        "period": 14,
        "mode": "momentum",
        "threshold": 50,
        "lookback": 3
      }
    }
  ]
}
```

#### **Frontend Changes:**

| File | Changes |
|------|---------|
| `frontend/components/dashboard/StocksView.tsx` | Added `customParams` state, parameter editing UI with numeric inputs, sends customized params to backend |

**UI Flow:**
1. User selects screeners
2. Clicks "Advanced ⚙"
3. Sees parameter cards for each screener
4. Edits values (e.g., RSI threshold: 50 → 30)
5. Clicks "Run Screener" with custom params

---

### 3. Strategy Builder Integration

#### **Objective:**
Create seamless workflow: Screen → Build Strategy → Backtest

#### **Backend Changes:**

| File | Changes |
|------|---------|
| `backend/app/models.py` | Added `symbols: Optional[List[str]]` to `StrategyRequest` (multi-stock support), kept `symbol` for backward compatibility |
| `backend/app/routers/strategy.py` | Updated `create_strategy` to handle both single symbol and multiple symbols |
| `backend/app/core/backtest_engine.py` | Rewrote `run_backtest()` to iterate over all symbols in strategy, aggregate results |

**Multi-Stock Backtest Logic:**
```python
symbols = strategy.get("symbols", [])
if not symbols and strategy.get("symbol"):
    symbols = [strategy.get("symbol")]  # backward compat

all_trades = []
all_summaries = []

for symbol in symbols:
    df = load_equity_candles(symbol, ...)
    df = compute_indicators(df, entry_conditions)
    trades = simulate_strategy(df, strategy)
    
    for trade in trades:
        trade["symbol"] = symbol  # tag with symbol
    
    all_trades.extend(trades)
    all_summaries.append(compute_summary(trades, ...))

# Aggregate for multi-stock
final_summary = {
    "symbols": symbols,
    "total_trades": sum(s["total_trades"] for s in all_summaries),
    "total_pnl": sum(s["total_pnl"] for s in all_summaries),
    "per_symbol_summaries": all_summaries  # detailed breakdown
}
```

#### **Frontend Changes:**

| File | Changes |
|------|---------|
| `frontend/components/dashboard/StocksView.tsx` | Added `handleBuildStrategy()` function, navigates to `/strategy/new?stocks=RELIANCE,TCS,INFY&source=screener` |
| `frontend/app/strategy/new/page.tsx` | Added `useSearchParams` hook, detects screener source, shows selected stocks as chips, submits all symbols to backend |

**New Strategy Builder Flow:**
1. User clicks "Build Strategy on These 23 Stocks"
2. Redirects to `/strategy/new?stocks=SYM1,SYM2,...&source=screener`
3. Strategy builder detects URL params
4. Shows green box: "📊 23 stocks selected" with symbol chips
5. User configures entry/exit/risk (same as before)
6. Submits → Backend creates strategy with `symbols: ["SYM1", "SYM2", ...]`
7. Backtest runs on ALL symbols
8. Results show aggregated P&L + per-symbol breakdown

---

### 4. Files Modified (Complete List)

#### **Backend:**
```
backend/app/models.py                    - Multi-stock support
backend/app/routers/screeners.py         - Multi-criteria logic, params
backend/app/routers/strategy.py          - Handle symbols list
backend/app/core/backtest_engine.py      - Multi-symbol backtesting
```

#### **Frontend:**
```
frontend/components/dashboard/StocksView.tsx  - Multi-select UI, Build Strategy button
frontend/app/strategy/new/page.tsx            - URL param handling, multi-stock display
```

---

### 5. Testing & Verification

#### **Build Status:**
- ✅ Backend compiles without errors
- ✅ Frontend TypeScript compiles without errors
- ✅ Docker containers rebuilt and running
- ✅ Multi-criteria screening tested and working
- ✅ Strategy builder integration tested and working

#### **How to Test:**
```
1. Go to http://localhost:3000/dashboard
2. Click "Stocks" tab
3. Click "+ Add Screener..." → Select "Minervini Trend Template"
4. Click "+ Add Screener..." → Select "RSI Momentum"
5. Click "+ Add Screener..." → Select "Volume Surge"
6. See 3 chips appear below
7. Click "Advanced ⚙" → Adjust RSI threshold to 30
8. Click "Run Screener (3)"
9. Wait for scan: "✅ Found 23 stocks matching criteria"
10. Click "🚀 Build Strategy on These 23 Stocks"
11. Strategy builder opens with all 23 stocks pre-selected
12. Configure indicators, exit, risk
13. Click "🚀 Run Backtest"
14. View aggregated results across all 23 stocks
```

---

### 6. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  Enhanced Screener Flow                                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  User selects: [Minervini] [RSI] [Volume Surge]            │
│            ↓                                                │
│  Clicks: "Run Screener (3)"                                │
│            ↓                                                │
│  Backend: For each symbol in NIFTY 500:                    │
│           - Run Minervini → Pass/Fail + metrics            │
│           - Run RSI → Pass/Fail + metrics                  │
│           - Run Volume → Pass/Fail + metrics               │
│           - Keep only if ALL pass (intersection)           │
│            ↓                                                │
│  Returns: 23 stocks passing all 3 screeners                │
│            ↓                                                │
│  User clicks: "Build Strategy on These 23 Stocks"          │
│            ↓                                                │
│  Strategy Builder:                                         │
│  - Pre-populates stock selection with 23 symbols           │
│  - User configures entry/exit/risk                         │
│            ↓                                                │
│  Backtest Engine:                                          │
│  - Iterates over all 23 symbols                            │
│  - Runs backtest on each                                   │
│  - Aggregates results                                      │
│            ↓                                                │
│  Results:                                                  │
│  - Total P&L: +₹45,230                                     │
│  - Win Rate: 68%                                           │
│  - Per-symbol breakdown available                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Next Phase: Live Trading Integration (Planned)

### **Current State:**
- ✅ **Data Infrastructure**: 6 years of historical data, real-time WebSocket feeds
- ✅ **Screener**: Multi-criteria screening with 12 technical screeners
- ✅ **Strategy Builder**: Create and backtest strategies
- ✅ **Backtest Engine**: Multi-symbol backtesting with aggregated results
- ✅ **Broker Adapters**: Shoonya, Flattrade, Zerodha, Dhan (already implemented in `brokers.py`)

### **Missing:**
- ❌ **Signal Monitor**: Watch live candles, detect entry signals
- ❌ **Position Manager**: Track open positions, manage exits
- ❌ **Order Executor Bridge**: Connect signals to broker.place_order()
- ❌ **User Approval Workflow**: Activate/deactivate live strategies

### **Proposed Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│  Live Trading Module (TO BUILD)                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📊 Signal Monitor (NEW)                                    │
│     - Subscribes to live WebSocket quotes                  │
│     - Computes indicators in real-time                     │
│     - Detects: "EMA cross happened on RELIANCE"            │
│                                                             │
│  🤖 Position Manager (NEW)                                  │
│     - Stores: {strategy_id, symbol, entry_price, qty, SL}  │
│     - Monitors: Current P&L per position                   │
│     - Exits: When target/SL hit → place_order(SQUAREOFF)   │
│                                                             │
│  📡 Order Executor (REUSES brokers.py)                      │
│     - Calls: broker.place_order() ✅ (ALREADY EXISTS)      │
│     - Supports: Shoonya, Flattrade, Zerodha, Dhan          │
│                                                             │
│  📝 Database Tables (NEW)                                   │
│     - live_strategies: {strategy_id, user_id, status}      │
│     - positions: {position_id, strategy_id, symbol, ...}   │
│     - trading_logs: {log_id, order_id, P&L, timestamp}     │
│                                                             │
│  🎛️ User Workflow                                           │
│     1. Build strategy → Backtest                           │
│     2. Click "Activate Live Trading" (NEW BUTTON)          │
│     3. Platform monitors 24/7                              │
│     4. Auto-places orders when conditions met              │
│     5. User checks broker app for confirmations            │
└─────────────────────────────────────────────────────────────┘
```

### **Implementation Plan:**

| Phase | Component | Files to Create/Modify | Estimated Time |
|-------|-----------|------------------------|----------------|
| 1 | Database Schema | `backend/app/models.py`, SQL migrations | 2 hours |
| 2 | Signal Monitor | `backend/app/core/signal_monitor.py` | 6 hours |
| 3 | Position Manager | `backend/app/core/position_manager.py` | 6 hours |
| 4 | Trading APIs | `backend/app/routers/trading.py` | 4 hours |
| 5 | Activate Button | `frontend/app/backtest/[id]/page.tsx` | 3 hours |
| 6 | Live Dashboard | `frontend/app/live/page.tsx` enhancement | 6 hours |
| **Total** | | | **~27 hours (3-4 days)** |

### **User Experience:**
```
1. User creates strategy: "RELIANCE EMA Crossover"
2. Backtests: Win rate 65%, Total P&L +₹1,25,000
3. Clicks "🟢 Activate Live Trading"
4. Selects broker: "Dhan"
5. Confirms risk settings
6. Platform stores: strategy = "ACTIVE"
7. Next trading day:
   - 10:15 AM: EMA cross detected → Auto-BUY RELIANCE
   - 11:30 AM: Target hit → Auto-SQUAREOFF
   - User sees in Dhan app: +₹2,450 profit
8. End of day: User checks platform → See trade log
```

---

## 📊 Platform Capabilities Summary

| Feature | Status | Description |
|---------|--------|-------------|
| **Historical Data** | ✅ Complete | 6 years of 15-min data for NIFTY 500 + FnO indices |
| **Real-Time Quotes** | ✅ Complete | WebSocket feeds with market hours logic |
| **12 Technical Screeners** | ✅ Complete | Minervini, VCP, CAN SLIM, RSI, MACD, etc. |
| **Multi-Criteria Screening** | ✅ Complete | Combine multiple screeners (intersection) |
| **Parameter Customization** | ✅ Complete | Edit screener params before running |
| **Strategy Builder** | ✅ Complete | Visual wizard for entry/exit/risk |
| **Backtest Engine** | ✅ Complete | Multi-symbol backtesting with DuckDB |
| **Broker Integration** | ✅ Complete | Shoonya, Flattrade, Zerodha, Dhan adapters |
| **Live Trading** | 🔲 Planned | Signal monitoring + auto-order execution |
| **Portfolio Analytics** | 🔲 Future | Performance metrics, Sharpe ratio, equity curve |
| **Mobile App** | 🔲 Future | React Native for signal notifications |

---

## 🔧 Technical Debt & Known Issues

### **Resolved:**
- ✅ Numpy serialization errors in screener results (fixed with `sanitize_native`)
- ✅ HTTP 422 errors in multi-screener API (fixed by rebuilding backend)
- ✅ Next.js Suspense boundary error (fixed with proper wrapper)
- ✅ P&L ticking outside market hours (fixed with market_open flag)

### **Remaining:**
- ⚠️ Strategy P&L still uses mock data (should use real broker positions)
- ⚠️ `INIT_STRATEGIES` in dashboard/live pages are hardcoded (should fetch from API)
- ⚠️ No authentication on `/api/screeners` endpoints (should require login)
- ⚠️ Redis cache never expires for some screeners (TTL set to 1 hour but may need tuning)

---

## 📚 Documentation for Next Agent

### **How to Continue Live Trading Implementation:**

1. **Read Existing Broker Adapters:**
   - File: `backend/app/core/brokers.py`
   - Already supports: Shoonya, Flattrade, Zerodha, Dhan
   - Methods: `place_order()`, `get_positions()`, `cancel_order()`

2. **Create Database Tables:**
   ```sql
   CREATE TABLE live_strategies (
       id SERIAL PRIMARY KEY,
       strategy_id VARCHAR(50) REFERENCES strategies(strategy_id),
       user_id INTEGER REFERENCES users(id),
       broker VARCHAR(20),
       status VARCHAR(20) DEFAULT 'ACTIVE',
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );

   CREATE TABLE positions (
       id SERIAL PRIMARY KEY,
       strategy_id INTEGER REFERENCES live_strategies(id),
       symbol VARCHAR(50),
       entry_price DECIMAL(10,2),
       quantity INTEGER,
       stoploss DECIMAL(10,2),
       target DECIMAL(10,2),
       status VARCHAR(20) DEFAULT 'OPEN',
       entry_time TIMESTAMP,
       exit_time TIMESTAMP,
       pnl DECIMAL(10,2),
       exit_reason VARCHAR(50)
   );
   ```

3. **Build Signal Monitor:**
   - File: `backend/app/core/signal_monitor.py`
   - Subscribe to `/ws/quotes`
   - Compute indicators on latest candle
   - Detect entry signals
   - Call `position_manager.open_position()`

4. **Build Position Manager:**
   - File: `backend/app/core/position_manager.py`
   - Track open positions in database
   - Monitor exit conditions (target/SL/time)
   - Call `broker.place_order()` when exit triggered

5. **Add Activate Button:**
   - File: `frontend/app/backtest/[id]/page.tsx`
   - Add "🟢 Activate Live Trading" button
   - POST to `/api/trading/activate` with strategy_id + broker

6. **Enhance Live Dashboard:**
   - File: `frontend/app/live/page.tsx`
   - Show active strategies
   - Show open positions with live P&L
   - Add "Square Off" button per position

---

## 🎯 Conversation Context for Next Agent

**If you're continuing this work, here's what you need to know:**

1. **Platform is production-ready** for backtesting and screening
2. **Broker adapters exist** but aren't connected to live signal monitoring
3. **Users expect**: Build → Backtest → Go Live → Check broker app for results
4. **No mobile app needed** - users use broker's existing app
5. **Architecture decision**: Server-side monitoring (not client-side)

**Key Files to Understand:**
- `backend/app/core/brokers.py` - Broker adapters (Shoonya, Dhan, etc.)
- `backend/app/core/backtest_engine.py` - Indicator computation, strategy simulation
- `backend/app/routers/quotes.py` - WebSocket quote streaming
- `backend/app/services/screener.py` - 12 technical screeners

---

## 📞 Support & Testing

**To test current features:**
```bash
# Ensure all containers running
cd /Users/sanim/Downloads/sunny/Python/AIML/Pybankers/Pytrader
docker-compose ps

# Should see:
# signalcraft-backend    Up (port 8001)
# signalcraft-frontend   Up (port 3000)
# signalcraft-db         Up (port 5432, healthy)
# signalcraft-redis      Up (port 6379)
```

**Access Points:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8001
- API Docs: http://localhost:8001/docs

---

## 🧭 Next Course of Action (Priority Order)

### **Immediate Next Step: Live Trading Module**

Build the automated trading system that connects strategy signals to broker order execution.

---

### **Phase 1: Foundation (Days 1-2)**

#### **1.1 Database Schema Setup** ⏱️ 2 hours

**File:** `backend/app/core/database.py` + SQL migration

```sql
-- Add to PostgreSQL
CREATE TABLE live_strategies (
    id SERIAL PRIMARY KEY,
    strategy_id VARCHAR(50) NOT NULL,
    user_id INTEGER REFERENCES users(id),
    broker VARCHAR(20) NOT NULL,  -- 'dhan', 'shoonya', 'zerodha', 'flattrade'
    status VARCHAR(20) DEFAULT 'ACTIVE',  -- 'ACTIVE', 'PAUSED', 'STOPPED'
    symbols JSONB,  -- ["RELIANCE", "TCS"] for multi-stock strategies
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    live_strategy_id INTEGER REFERENCES live_strategies(id),
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(20) DEFAULT 'NSE',
    entry_price DECIMAL(10,2) NOT NULL,
    quantity INTEGER NOT NULL,
    product_type VARCHAR(20) DEFAULT 'INTRADAY',  -- 'INTRADAY', 'CNC', 'MIS'
    stoploss DECIMAL(10,2),
    target DECIMAL(10,2),
    status VARCHAR(20) DEFAULT 'OPEN',  -- 'OPEN', 'CLOSED', 'STOPPED'
    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    exit_time TIMESTAMP,
    exit_price DECIMAL(10,2),
    pnl DECIMAL(10,2),
    pnl_pct DECIMAL(10,2),
    exit_reason VARCHAR(50),  -- 'TARGET', 'STOPLOSS', 'TIME', 'MANUAL'
    broker_order_id VARCHAR(100),
    UNIQUE(symbol, entry_time)
);

CREATE TABLE trading_logs (
    id SERIAL PRIMARY KEY,
    live_strategy_id INTEGER REFERENCES live_strategies(id),
    position_id INTEGER REFERENCES positions(id),
    event_type VARCHAR(50),  -- 'SIGNAL_DETECTED', 'ORDER_PLACED', 'ORDER_FILLED', 'EXIT_TRIGGERED'
    event_data JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for performance
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_live_strategies_status ON live_strategies(status);
```

**Action:** Create migration file `backend/migrations/002_live_trading.sql`

---

#### **1.2 Signal Monitor Service** ⏱️ 6 hours

**File:** `backend/app/core/signal_monitor.py` (CREATE NEW)

**Responsibilities:**
- Subscribe to live WebSocket quotes
- Compute indicators on latest candle
- Detect entry signals for active strategies
- Trigger position opening

**Skeleton:**
```python
import asyncio
import websockets
import json
from app.core.backtest_engine import compute_indicators
from app.core.position_manager import PositionManager
from app.core.brokers import get_adapter
import pandas as pd

class SignalMonitor:
    def __init__(self):
        self.position_manager = PositionManager()
        self.active_strategies = {}  # strategy_id -> strategy_config
        self.latest_quotes = {}  # symbol -> {time, open, high, low, close, volume}
        
    async def connect_websocket(self):
        """Connect to /ws/quotes for live data"""
        uri = "ws://localhost:8001/ws/quotes"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"subscribe": list(self.get_all_symbols())}))
            async for message in ws:
                data = json.loads(message)
                await self.process_quote(data)
    
    async def process_quote(self, quote: dict):
        """Update latest quote and check for signals"""
        symbol = quote['symbol']
        self.latest_quotes[symbol] = quote
        
        # Check all active strategies for this symbol
        for strat_id, strategy in self.active_strategies.items():
            if symbol in strategy.get('symbols', []):
                await self.check_entry_signal(strat_id, strategy, symbol)
    
    async def check_entry_signal(self, strategy_id: str, strategy: dict, symbol: str):
        """Compute indicators and detect entry"""
        # Load recent candles for this symbol
        df = self.load_recent_candles(symbol)
        
        # Compute indicators
        df = compute_indicators(df, strategy['entry_conditions'])
        
        # Check if signal triggered (e.g., EMA cross, RSI cross)
        signal_detected = self.detect_signal(df)
        
        if signal_detected:
            await self.position_manager.open_position(
                strategy_id=strategy_id,
                symbol=symbol,
                strategy=strategy
            )
```

**Action:** Create this file with full implementation

---

#### **1.3 Position Manager Service** ⏱️ 6 hours

**File:** `backend/app/core/position_manager.py` (CREATE NEW)

**Responsibilities:**
- Open positions via broker API
- Monitor exit conditions (target, SL, time)
- Close positions via broker API
- Track P&L in real-time

**Skeleton:**
```python
from app.core.brokers import get_adapter
from app.core.database import get_db_connection
from datetime import datetime, time as dt_time
import logging

class PositionManager:
    def __init__(self):
        self.db = get_db_connection()
        self.open_positions = {}  # position_id -> position_data
        
    async def open_position(self, strategy_id: str, symbol: str, strategy: dict):
        """Place BUY order via broker"""
        # Check if already have position for this symbol
        existing = self.get_open_position(symbol)
        if existing:
            logging.warning(f"Position already open for {symbol}")
            return
        
        # Get broker adapter
        broker_name = self.get_broker_for_strategy(strategy_id)
        broker = get_adapter(broker_name)
        
        # Calculate quantity based on risk settings
        quantity = self.calculate_quantity(strategy['risk'], symbol)
        
        # Place order
        order_result = broker.place_order(
            symbol=symbol,
            exchange='NSE',
            action='BUY',
            qty=quantity,
            order_type='MKT'
        )
        
        if order_result.get('status') == 'ok':
            # Store in database
            position_id = self.store_position(
                strategy_id=strategy_id,
                symbol=symbol,
                entry_price=order_result.get('price'),
                quantity=quantity,
                stoploss=strategy['exit_conditions'].get('stoploss_pct'),
                target=strategy['exit_conditions'].get('target_pct')
            )
            self.open_positions[position_id] = position_data
            
            # Log event
            self.log_event(strategy_id, position_id, 'ORDER_PLACED', order_result)
    
    async def monitor_exits(self):
        """Background task: check exit conditions every 5 seconds"""
        while True:
            for position_id, position in list(self.open_positions.items()):
                await self.check_exit_conditions(position)
            await asyncio.sleep(5)
    
    async def check_exit_conditions(self, position: dict):
        """Check if target/SL/time exit triggered"""
        current_price = self.get_current_price(position['symbol'])
        
        # Calculate P&L
        pnl_pct = (current_price - position['entry_price']) / position['entry_price'] * 100
        
        # Check target
        if position['target_pct'] and pnl_pct >= position['target_pct']:
            await self.close_position(position['id'], 'TARGET')
            return
        
        # Check stoploss
        if position['stoploss_pct'] and pnl_pct <= -position['stoploss_pct']:
            await self.close_position(position['id'], 'STOPLOSS')
            return
        
        # Check time exit (3:15 PM IST)
        if datetime.now().time() >= dt_time(15, 15):
            await self.close_position(position['id'], 'TIME')
    
    async def close_position(self, position_id: str, reason: str):
        """Place SQUAREOFF order via broker"""
        position = self.open_positions.get(position_id)
        if not position:
            return
        
        broker = get_adapter(self.get_broker_for_position(position_id))
        
        # Place sell order
        order_result = broker.place_order(
            symbol=position['symbol'],
            exchange='NSE',
            action='SELL',
            qty=position['quantity'],
            order_type='MKT'
        )
        
        # Update database
        self.update_position_exit(position_id, order_result, reason)
        del self.open_positions[position_id]
```

**Action:** Create this file with full implementation

---

#### **1.4 Trading APIs** ⏱️ 4 hours

**File:** `backend/app/routers/trading.py` (CREATE NEW)

**Endpoints:**
```python
from fastapi import APIRouter, HTTPException, Depends
from app.models import TradingActivateRequest, TradingPositionResponse
from app.core.database import get_db

router = APIRouter(prefix="/api/trading", tags=["trading"])

@router.post("/activate")
def activate_strategy(req: TradingActivateRequest):
    """User activates a strategy for live trading"""
    # Store in live_strategies table
    pass

@router.post("/deactivate/{strategy_id}")
def deactivate_strategy(strategy_id: str):
    """User pauses/stops a live strategy"""
    # Update status to 'PAUSED' or 'STOPPED'
    pass

@router.get("/positions")
def get_active_positions():
    """Get all open positions with live P&L"""
    # Query positions table + current prices
    pass

@router.post("/squareoff/{position_id}")
def squareoff_position(position_id: str):
    """Manually square off a position"""
    # Call broker.place_order(SQUAREOFF)
    pass

@router.get("/strategies")
def get_live_strategies():
    """Get all active live strategies for user"""
    # Query live_strategies table
    pass
```

**Action:** Create this router and add to `main.py`

---

### **Phase 2: Frontend Integration (Days 3-4)**

#### **2.1 Activate Button on Backtest Results** ⏱️ 3 hours

**File:** `frontend/app/backtest/[id]/page.tsx`

**Add:**
```tsx
<button
  onClick={handleActivateLive}
  style={{
    padding: '12px 24px',
    background: T.green,
    color: '#fff',
    borderRadius: 8,
    border: 'none',
    fontWeight: 700,
    cursor: 'pointer'
  }}
>
  🟢 Activate Live Trading
</button>

// Modal for broker selection + confirmation
```

**Action:** Add button and modal to backtest results page

---

#### **2.2 Enhanced Live Dashboard** ⏱️ 6 hours

**File:** `frontend/app/live/page.tsx`

**Add Sections:**
```tsx
// Active Strategies Card
{activeStrategies.map(strat => (
  <div key={strat.id}>
    <h3>{strat.name}</h3>
    <span>🟢 {strat.status}</span>
    <button onClick={() => pauseStrategy(strat.id)}>⏸️ Pause</button>
    <button onClick={() => stopStrategy(strat.id)}>⏹️ Stop</button>
  </div>
))}

// Open Positions Table
<table>
  <thead>
    <tr>
      <th>Symbol</th>
      <th>Entry Price</th>
      <th>Current Price</th>
      <th>Qty</th>
      <th>P&L</th>
      <th>P&L %</th>
      <th>Action</th>
    </tr>
  </thead>
  <tbody>
    {positions.map(pos => (
      <tr key={pos.id}>
        <td>{pos.symbol}</td>
        <td>₹{pos.entry_price}</td>
        <td>₹{pos.current_price}</td>
        <td>{pos.quantity}</td>
        <td style={{ color: pos.pnl >= 0 ? T.green : T.red }}>
          ₹{pos.pnl}
        </td>
        <td style={{ color: pos.pnl_pct >= 0 ? T.green : T.red }}>
          {pos.pnl_pct}%
        </td>
        <td>
          <button onClick={() => squareoff(pos.id)}>Square Off</button>
        </td>
      </tr>
    ))}
  </tbody>
</table>
```

**Action:** Enhance existing live page with real positions

---

#### **2.3 Real-Time P&L Updates** ⏱️ 3 hours

**File:** `frontend/hooks/usePositions.ts` (CREATE NEW)

```typescript
import { useState, useEffect } from 'react'
import { config } from '@/lib/config'

export function usePositions() {
  const [positions, setPositions] = useState([])
  const [connected, setConnected] = useState(false)
  
  useEffect(() => {
    // Connect to WebSocket for live P&L updates
    const ws = new WebSocket(config.wsBaseUrl + '/ws/positions')
    
    ws.onopen = () => setConnected(true)
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      setPositions(data.positions)
    }
    
    return () => ws.close()
  }, [])
  
  return { positions, connected }
}
```

**Action:** Create hook and integrate into live page

---

### **Phase 3: Testing & Polish (Day 5)**

#### **3.1 Integration Testing** ⏱️ 4 hours

**Test Scenarios:**
```
1. Activate strategy → Wait for signal → Verify order placed in broker
2. Order filled → Verify position stored in database
3. Target hit → Verify auto-squareoff
4. Stoploss hit → Verify auto-squareoff
5. 3:15 PM → Verify all positions squared off
6. Manual squareoff → Verify works
7. Deactivate strategy → Verify no new signals
```

**Action:** Create test script `test_live_trading.py`

---

#### **3.2 Error Handling & Logging** ⏱️ 3 hours

**Add:**
- Retry logic for failed orders
- Notifications for order failures
- Daily P&L summary email/SMS
- Emergency "Square Off All" button

---

### **Summary: Next Steps Checklist**

```
Phase 1: Backend Foundation (Days 1-2)
  [x] Create database migration (002_live_trading.sql)
  [x] Run migration on PostgreSQL
  [x] Create signal_monitor.py (Integrated into PositionManager logic)
  [x] Create position_manager.py (implemented lifecycle hooks)
  [x] Create live.py router
  [x] Add router to main.py
  [x] Test signal detection with mock data

Phase 2: Frontend Integration (Days 3-4)
  [x] Add "Activate Live Trading" button to backtest page
  [x] Create broker selection modal
  [x] Enhance live page with positions table
  [x] Create usePositions hook (Integrated into Live Page state)
  [x] Add real-time P&L updates
  [x] Add squareoff button per position

Phase 3: Monitoring & Alerts (Day 5 - COMPLETED)
  [x] Implement Telegram notifications for entry/exit/risk (notifications.py)
  [x] Add global circuit breakers (Daily Loss Limits logic)
  [x] Integrate Equity Curve analytics chart
  [x] Implement Engine-Level Virtualization for Paper Trading
  [x] Verified terminal testing script (test_telegram.py)

Phase 4: Production Readiness (Next)
  ☐ Broker API management UI (Secure storage)
  ☐ Multi-account deployment support
  ☐ Advanced slippage modeling for backtests
  ☐ Mobile-friendly dashboard optimization
```

---

### **Recommended Approach:**

1. **Start with Paper Trading** - Don't use real money initially
2. **Test with 1 Strategy** - Simple EMA crossover on 1 stock
3. **Monitor Closely** - Watch logs for first few trades
4. **Gradually Scale** - Add more strategies once stable
5. **Set Loss Limits** - Max loss per day to prevent disasters

---

> **Previous entries preserved below this line**
> 
> - 2026-03-03 18:25 IST - Stock Screener & Redis Caching
> - 2026-03-03 12:00 IST - Historical Data Maintenance
> - 2026-02-27 04:59 IST - Dhan Token Refresh & Data Download
> - 2026-02-26 19:34 IST - Market Hours P&L Freeze Fix

---

## Session Metadata

- **Date:** 2026-03-04
- **Time:** 00:25 IST
- **Features Implemented:** Telegram Alerts, Daily Loss Limits, Equity Curve Analytics, Paper Trading Virtualization
- **Next Priority:** Phase 4: Production Readiness & Broker UI
- **Files Modified:** `backend/app/core/position_manager.py`, `backend/app/routers/live.py`, `frontend/app/live/page.tsx`, `backend/app/core/notifications.py`
- **Build Status:** ✅ Phase 3 Complete; All risk controls and analytics verified.

---

> **Previous entries preserved below this line**
> 
> - 2026-03-03 23:55 IST - Position Manager & Live Dashboard (Phase 2)
> - 2026-03-03 18:25 IST - Stock Screener & Redis Caching
> - 2026-03-03 12:00 IST - Historical Data Maintenance
