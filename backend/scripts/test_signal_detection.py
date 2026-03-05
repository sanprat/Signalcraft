import sys
import os
import asyncio
import json
from datetime import datetime, timedelta

# Add the backend directory to sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(backend_path)

from app.core.database import init_db, get_db
from app.core.backtest_engine import compute_indicators
from app.core.signal_monitor import signal_monitor
from app.routers.quotes import _quotes

async def test_signal_detection():
    print("Initializing test environment...")
    init_db()
    
    # 1. Insert a dummy active strategy
    # Strategy: EMA Cross (9, 21) on RELIANCE
    strategy_config = {
        "strategy_id": "test_ema_cross",
        "name": "Test EMA Cross",
        "user_id": 1,
        "broker": "dhan",
        "symbols": ["RELIANCE"],
        "risk_settings": {"max_trades_per_day": 3, "max_loss_per_day": 5000, "quantity_lots": 1, "lot_size": 1},
        "entry_conditions": [
            {
                "indicator": "EMA_CROSS",
                "params": {"fast": 9, "slow": 21},
                "logic": "AND"
            }
        ],
        "exit_conditions": {"target_pct": 2.0, "stoploss_pct": 1.0}
    }
    
    with get_db() as conn:
        cursor = conn.cursor()
        # Ensure user 1 exists
        cursor.execute("INSERT INTO users (email, password_hash, full_name) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", ("test@example.com", "hash", "Test User"))
        cursor.execute("COMMIT")
        
        # Insert strategy
        cursor.execute("""
            INSERT INTO live_strategies (strategy_id, name, user_id, broker, symbols, risk_settings, entry_conditions, exit_conditions)
            VALUES (%s, %s, (SELECT id FROM users LIMIT 1), %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
        """, (
            strategy_config["strategy_id"],
            strategy_config["name"],
            strategy_config["broker"],
            json.dumps(strategy_config["symbols"]),
            json.dumps(strategy_config["risk_settings"]),
            json.dumps(strategy_config["entry_conditions"]),
            json.dumps(strategy_config["exit_conditions"])
        ))
        cursor.execute("COMMIT")
        cursor.close()

    print("✅ Dummy strategy inserted.")

    # 2. Start signal monitor
    await signal_monitor.sync_strategies()
    
    print(f"Monitoring strategies: {list(signal_monitor.active_strategies.keys())}")
    
    # 3. Simulate ticks to form a candle and trigger signal
    import pandas as pd
    
    symbol = "RELIANCE"
    now = datetime.now()
    
    # Create simple bars
    candles = []
    for i in range(30):
        price = 100 + i
        candles.append({
            "time": now - timedelta(minutes=40-i),
            "open": price, "high": price, "low": price, "close": price, "volume": 100
        })
    df_sim = pd.DataFrame(candles)
    
    # Manually inject signal into the monitors internal state
    # We want to verify that check_signals detects this
    signal_monitor.candles[symbol] = {"1min": df_sim}
    
    # Monkeypatch compute_indicators for this test to return a triggered signal
    import app.core.signal_monitor as sm
    original_compute = sm.compute_indicators
    sm.compute_indicators = lambda df, conds: df.assign(signal_test=True)

    print("Simulating final tick in a NEW minute to close previous candle...")
    future_now = now + timedelta(minutes=5)
    await signal_monitor.process_tick(symbol, 150.0, future_now)
    
    # Restore original function
    sm.compute_indicators = original_compute
    
    print("Waiting for async logging...")
    await asyncio.sleep(2)
    
    # 4. Verify log entry
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trading_logs WHERE event_type = 'SIGNAL_DETECTED' ORDER BY id DESC LIMIT 1")
        log = cursor.fetchone()
        if log:
            print(f"✅ SUCCESS: Signal detected and logged! Log: {log[4]}")
        else:
            print("❌ FAILURE: No signal logged.")
        cursor.close()

if __name__ == "__main__":
    asyncio.run(test_signal_detection())
