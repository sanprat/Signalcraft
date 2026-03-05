import sys
import os
import asyncio
import json
from datetime import datetime, timedelta

# Add the backend directory to sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(backend_path)

from app.core.database import get_db, init_db
from app.core.position_manager import position_manager
from app.core.signal_monitor import signal_monitor
from app.routers.quotes import _quotes

async def test_order_placement():
    print("Initializing test environment for order placement...")
    init_db()
    
    # 1. Setup active strategy
    strategy_config = {
        "id": 9991, # Use a high ID to avoid collisions
        "strategy_id": "test_order_strat",
        "name": "Test Order Placement",
        "user_id": 1,
        "broker": "dhan",
        "symbols": ["RELIANCE"],
        "risk": {"max_trades_per_day": 5, "quantity_lots": 1},
        "entry_conditions": [],
        "exit_conditions": {"target_pct": 1.0, "stoploss_pct": 0.5}
    }
    
    # 2. Insert dummy strategy into DB to satisfy FK constraint
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO live_strategies (id, strategy_id, name, user_id, broker, symbols, risk_settings, entry_conditions, exit_conditions, status)
            VALUES (%s, %s, %s, (SELECT id FROM users LIMIT 1), %s, %s, %s, %s, %s, 'ACTIVE')
            ON CONFLICT (id) DO UPDATE SET status = 'ACTIVE'
        """, (
            strategy_config["id"],
            strategy_config["strategy_id"],
            strategy_config["name"],
            strategy_config["broker"],
            json.dumps(strategy_config["symbols"]),
            json.dumps(strategy_config["risk"]),
            json.dumps(strategy_config["entry_conditions"]),
            json.dumps(strategy_config["exit_conditions"])
        ))
        cursor.execute("COMMIT")
        cursor.close()
    print("✅ Dummy strategy inserted.")

    # 3. Mock the DhanAdapter
    import app.core.brokers as brokers
    class MockDhanAdapter:
        def place_order(self, **kwargs):
            print(f"MOCK ORDER: {kwargs}")
            return {"status": "ok", "data": {"orderId": "MOCK_ORD_123"}}
        def get_name(self): return "dhan"
        def get_positions(self): return []
        def cancel_order(self, id): return True

    original_get_adapter = brokers.get_adapter
    brokers.get_adapter = lambda name: MockDhanAdapter() if name == "dhan" else original_get_adapter(name)

    # 4. Start Position Manager loop
    await position_manager.start()
    print("Position Manager loop started.")

    print("Triggering mock signal...")
    # This should trigger position_manager.open_position()
    await position_manager.handle_signal(strategy_config, "RELIANCE", 2500.0)
    
    # 3. Verify position in DB
    await asyncio.sleep(1)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM positions WHERE symbol = 'RELIANCE' AND status = 'OPEN' ORDER BY id DESC LIMIT 1")
        pos = cursor.fetchone()
        if pos:
            print(f"✅ SUCCESS: Position opened in DB! SL: {pos[7]}, TP: {pos[8]}")
            pos_dict = {
                "id": pos[0], "symbol": pos[2], "exchange": pos[3], "entry_price": pos[4],
                "quantity": pos[5], "stoploss": pos[7], "target": pos[8], "status": pos[9]
            }
        else:
            print("❌ FAILURE: No position found in DB.")
            return
        cursor.close()

    # 4. Test Exit Condition (Stop Loss)
    print("Simulating price drop to trigger SL...")
    _quotes["RELIANCE"] = {"ltp": 2400.0} # Far below SL
    
    await asyncio.sleep(2) # Wait for monitor loop
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, exit_reason, pnl FROM positions WHERE id = %s", (pos_dict["id"],))
        closed_pos = cursor.fetchone()
        if closed_pos and closed_pos[0] == "CLOSED":
            print(f"✅ SUCCESS: Position closed via {closed_pos[1]}! PnL: {closed_pos[2]}")
        else:
            print(f"❌ FAILURE: Position not closed. Current status: {closed_pos[0] if closed_pos else 'None'}")
        cursor.close()

    # Restore original get_adapter
    brokers.get_adapter = original_get_adapter

if __name__ == "__main__":
    asyncio.run(test_order_placement())
