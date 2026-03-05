import asyncio
import json
import logging
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any

from app.core.database import get_db
from app.core.backtest_engine import compute_indicators
from app.core.position_manager import position_manager
from app.core.config import settings

logger = logging.getLogger(__name__)

class SignalMonitor:
    def __init__(self):
        self.active_strategies: Dict[int, Dict[str, Any]] = {}
        self.last_sync_time = None
        self.quote_queues: Dict[str, asyncio.Queue] = {} # symbol -> queue of ticks
        self.candles: Dict[str, Dict[str, pd.DataFrame]] = {} # symbol -> {interval -> df}
        self.is_running = False
        self._IST = timezone(timedelta(hours=5, minutes=30))

    async def start(self):
        """Start the background monitor and sync tasks."""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("Signal Monitor starting...")
        
        # Start background tasks
        asyncio.create_task(self._sync_loop())
        asyncio.create_task(self._monitor_quotes_internal())
        
        logger.info("Signal Monitor tasks started.")

    async def _sync_loop(self):
        """Periodically sync active strategies from database."""
        while self.is_running:
            try:
                await self.sync_strategies()
            except Exception as e:
                logger.error(f"Error syncing strategies: {e}")
            await asyncio.sleep(60) # Sync every minute

    async def sync_strategies(self):
        """Fetch active strategies from PostgreSQL."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, strategy_id, name, user_id, broker, status, symbols, 
                       risk_settings, entry_conditions, exit_conditions
                FROM live_strategies
                WHERE status = 'ACTIVE'
            """)
            rows = cursor.fetchall()
            
            new_strategies = {}
            for row in rows:
                strat_id_db = row[0]
                strat_data = {
                    "id": row[0],
                    "strategy_id": row[1],
                    "name": row[2],
                    "user_id": row[3],
                    "broker": row[4],
                    "symbols": row[6] if isinstance(row[6], list) else json.loads(row[6] or "[]"),
                    "risk": row[7] if isinstance(row[7], dict) else json.loads(row[7] or "{}"),
                    "entry_conditions": row[8] if isinstance(row[8], list) else json.loads(row[8] or "[]"),
                    "exit_conditions": row[9] if isinstance(row[9], dict) else json.loads(row[9] or "{}")
                }
                new_strategies[strat_id_db] = strat_data
                
                # Initialize quote queues for new symbols
                for symbol in strat_data["symbols"]:
                    if symbol not in self.quote_queues:
                        self.quote_queues[symbol] = asyncio.Queue()
                        logger.info(f"Signal Monitor: Subscribed to {symbol}")

            self.active_strategies = new_strategies
            self.last_sync_time = datetime.now()
            cursor.close()

    async def _monitor_quotes_internal(self):
        """
        Internal task to monitor the shared quote state from quotes.py.
        Since quotes.py already has a broadcast loop, we can tap into that 
        or simply poll the global _quotes dictionary if accessible.
        For a more decoupled approach, we'll poll the shared state.
        """
        from app.routers.quotes import _quotes  # Internal import to avoid circular dependency
        
        last_ticks = {} # symbol -> timestamp
        
        while self.is_running:
            current_time = datetime.now(self._IST)
            
            # Only process if market is open (or always if we want to support 24/7 simulation)
            for symbol, quote in _quotes.items():
                # If we have active strategies for this symbol
                if any(symbol in s["symbols"] for s in self.active_strategies.values()):
                    # Simple tick detection: if LTP changed, we process
                    ltp = quote.get("ltp", 0)
                    if ltp > 0 and last_ticks.get(symbol) != ltp:
                        last_ticks[symbol] = ltp
                        await self.process_tick(symbol, ltp, current_time)
            
            await asyncio.sleep(1) # Poll every second

    async def process_tick(self, symbol: str, price: float, timestamp: datetime):
        """Aggregate tick into candles and check for signals on candle close."""
        # For this MVP, we only support 1m candles for live alerts
        # In a full impl, we'd handle multiple timeframes
        
        if symbol not in self.candles:
            self.candles[symbol] = {"1min": pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])}
            # Seed with some historical data if available (optional for now)
            
        df = self.candles[symbol]["1min"]
        
        # Check if we need to start a new candle
        current_minute = timestamp.replace(second=0, microsecond=0)
        
        if df.empty or df.iloc[-1]["time"] < current_minute:
            # Previous candle just closed
            if not df.empty:
                await self.on_candle_close(symbol, "1min", df)
            
            # Start new candle
            new_row = {
                "time": current_minute,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": 0
            }
            self.candles[symbol]["1min"] = pd.concat([df, pd.DataFrame([new_row])]).tail(100) # Keep last 100
        else:
            # Update current candle
            idx = df.index[-1]
            df.at[idx, "high"] = max(df.at[idx, "high"], price)
            df.at[idx, "low"] = min(df.at[idx, "low"], price)
            df.at[idx, "close"] = price
            # volume incrementing skipped for indices/simulated data

    async def on_candle_close(self, symbol: str, interval: str, df: pd.DataFrame):
        """Evaluate strategies when a candle closes."""
        logger.debug(f"Candle closed for {symbol} ({interval}) at {df.iloc[-1]['time']}")
        
        for db_id, strategy in self.active_strategies.items():
            if symbol in strategy["symbols"]:
                await self.check_signals(db_id, strategy, symbol, df)

    async def check_signals(self, db_id: int, strategy: dict, symbol: str, df: pd.DataFrame):
        """Apply strategy logic to the candles."""
        try:
            # 1. Compute Indicators
            # Note: compute_indicators expects entry_conditions as a list of dicts
            df_with_inds = compute_indicators(df.copy(), strategy["entry_conditions"])
            
            # 2. Check for signal trigger on the LAST CLOSED bar
            # Signal columns start with 'signal_'
            signal_cols = [c for c in df_with_inds.columns if c.startswith("signal_")]
            if not signal_cols:
                return

            last_row = df_with_inds.iloc[-1]
            logic = strategy["entry_conditions"][0].get("logic", "AND") if strategy["entry_conditions"] else "AND"
            
            triggered = False
            if logic == "AND":
                triggered = all(last_row.get(c, False) for c in signal_cols)
            else:
                triggered = any(last_row.get(c, False) for c in signal_cols)
            
            if triggered:
                logger.info(f"🚀 SIGNAL DETECTED: Strategy '{strategy['name']}' triggered for {symbol}!")
                await self.log_signal(db_id, symbol, last_row.to_dict())
                
                # Trigger Position Manager
                await position_manager.handle_signal(strategy, symbol, last_row.get("close"))
                
        except Exception as e:
            logger.error(f"Error checking signals for {symbol}: {e}")

    async def log_signal(self, db_id: int, symbol: str, signal_data: dict):
        """Log the signal into trading_logs table."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trading_logs (live_strategy_id, event_type, details, event_data)
                VALUES (%s, %s, %s, %s)
            """, (
                db_id, 
                "SIGNAL_DETECTED", 
                f"Entry signal triggered for {symbol}",
                json.dumps({
                    "symbol": symbol,
                    "price": signal_data.get("close"),
                    "time": str(signal_data.get("time")),
                    "indicators": {k: v for k, v in signal_data.items() if not k.startswith("signal_") and k not in ["time", "open", "high", "low", "close", "volume"]}
                })
            ))
            cursor.execute("COMMIT")
            cursor.close()

# Singleton instance
signal_monitor = SignalMonitor()
