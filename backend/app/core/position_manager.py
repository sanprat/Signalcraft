import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional

from app.core.database import get_db
from app.core.brokers import get_adapter
from app.core.config import settings
from app.core.notifications import send_user_telegram_message

logger = logging.getLogger(__name__)

class PositionManager:
    def __init__(self):
        self.active_positions: List[Dict[str, Any]] = []
        self.is_running = False
        self._IST = timezone(timedelta(hours=5, minutes=30))

    async def start(self):
        """Start the position monitoring background loop."""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("Position Manager starting...")
        
        # Load existing open positions from DB
        await self._sync_positions_from_db()
        
        # Start monitoring loop
        asyncio.create_task(self._monitor_loop())
        logger.info("Position Manager loop started.")

    async def _sync_positions_from_db(self):
        """Fetch all OPEN positions from the database."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, live_strategy_id, symbol, exchange, entry_price, 
                       quantity, product_type, stoploss, target, status, broker_order_id
                FROM positions
                WHERE status IN ('OPEN', 'PENDING')
            """)
            rows = cursor.fetchall()
            self.active_positions = []
            for row in rows:
                self.active_positions.append({
                    "id": row[0],
                    "live_strategy_id": row[1],
                    "symbol": row[2],
                    "exchange": row[3],
                    "entry_price": row[4],
                    "quantity": row[5],
                    "product_type": row[6],
                    "stoploss": row[7],
                    "target": row[8],
                    "status": row[9],
                    "broker_order_id": row[10]
                })
            cursor.close()
        logger.info(f"Position Manager: Synced {len(self.active_positions)} open positions.")

    async def handle_signal(self, strategy_data: dict, symbol: str, price: float):
        """Handle an entry signal from SignalMonitor."""
        logger.info(f"Position Manager: Handling signal for {symbol} at {price} (Strategy: {strategy_data['name']})")
        
        # 1. Risk Check: Max trades per day
        if not await self._check_risk_limits(strategy_data):
            logger.warning(f"Risk limit reached for strategy {strategy_data['name']}. Skipping signal.")
            return

        # 2. Open Position
        await self.open_position(strategy_data, symbol, price)

    async def _check_risk_limits(self, strategy_data: dict) -> bool:
        """Verify if we can take more trades today."""
        risk = strategy_data.get("risk", {})
        max_trades = risk.get("max_trades_per_day", 1)
        max_loss = float(risk.get("max_loss_per_day", 5000.0))
        
        with get_db() as conn:
            cursor = conn.cursor()
            today_start = datetime.now(self._IST).replace(hour=0, minute=0, second=0, microsecond=0)
            
            # 1. Count trades taken today
            cursor.execute("""
                SELECT COUNT(*) FROM positions 
                WHERE live_strategy_id = %s AND entry_time >= %s
            """, (strategy_data["id"], today_start))
            count = cursor.fetchone()[0]
            
            # 2. Check realized PnL for today
            cursor.execute("""
                SELECT SUM(pnl) FROM positions 
                WHERE live_strategy_id = %s AND exit_time >= %s AND status = 'CLOSED'
            """, (strategy_data["id"], today_start))
            today_realized_pnl = cursor.fetchone()[0] or 0.0
            
            cursor.close()
            
        if count >= max_trades:
            logger.warning(f"Trade limit ({max_trades}) reached for {strategy_data['name']}")
            return False
            
        if float(today_realized_pnl) <= -max_loss:
            logger.warning(f"Daily loss limit (₹{max_loss}) reached for {strategy_data['name']}. Current: ₹{today_realized_pnl}")
            await send_user_telegram_message(strategy_data.get("user_id"), f"🚨 *Risk Limit Reached*\nStrategy: {strategy_data['name']}\nReason: Daily loss limit of ₹{max_loss} hit.\nStopping for the day.")
            return False
            
        return True

    async def open_position(self, strategy_data: dict, symbol: str, price: float):
        """Execute order via broker and save to DB."""
        try:
            # 1. Get strategy details from DB (to stay sync)
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT broker, status FROM live_strategies WHERE id = %s", (strategy_data["id"],))
                row = cursor.fetchone()
                broker = row[0]
                strat_status = row[1]
                cursor.close()

            is_paper = strat_status == "PAPER"
            adapter = get_adapter(broker, strategy_data.get("user_id"))
            
            # TODO: Hardcoded quantity for now, should come from risk_settings
            quantity = strategy_data.get("risk", {}).get("quantity_lots", 1)
            
            broker_order_id = f"PAPER_ENTRY_{datetime.now(self._IST).strftime('%Y%m%d%H%M%S')}"

            if not is_paper:
                logger.info(f"Placing BUY order for {symbol}, qty={quantity} via {broker}...")
                # Place Order with retries
                retries = 3
                order_res = None
                for attempt in range(retries):
                    try:
                        order_res = adapter.place_order(
                            symbol=symbol,
                            exchange="NSE",
                            action="BUY",
                            qty=quantity,
                            price=0, # Market
                            order_type="MKT"
                        )
                        if order_res and order_res.get("status") != "error":
                            break
                        else:
                            msg = order_res.get("message") if order_res else "Unknown error"
                            logger.warning(f"Attempt {attempt+1} failed checking status: {msg}")
                    except Exception as e:
                        logger.warning(f"Attempt {attempt+1} raised exception: {e}")
                    
                    if attempt == retries - 1:
                        logger.error(f"Order placement failed after {retries} attempts.")
                        await send_user_telegram_message(strategy_data.get("user_id"), f"❌ *Order Placement Failed*\nStrategy: {strategy_data['name']}\nSymbol: {symbol}\nFailed after {retries} attempts.")
                        return
                    await asyncio.sleep(2)

                broker_order_id = order_res.get("data", {}).get("orderId") or order_res.get("order_id")
                # Wait for reconciliation
                pos_status = "PENDING"
                stoploss = 0.0
                target = 0.0
                entry_price_db = 0.0
            else:
                logger.info(f"PAPER TRADING: Simulating BUY order for {symbol}, qty={quantity}...")
                pos_status = "OPEN"
                entry_price_db = price
                # Calculate SL/TP
                exit_conds = strategy_data.get("exit_conditions", {})
                stoploss = price * (1 - exit_conds.get("stoploss_pct", 1.0) / 100)
                target = price * (1 + exit_conds.get("target_pct", 2.0) / 100)

            # Save to DB
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO positions (live_strategy_id, symbol, exchange, entry_price, quantity, stoploss, target, broker_order_id, status, entry_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    strategy_data["id"],
                    symbol,
                    "NSE",
                    entry_price_db,
                    quantity,
                    stoploss,
                    target,
                    broker_order_id,
                    pos_status,
                    datetime.now(self._IST)
                ))
                pos_id = cursor.fetchone()[0]
                cursor.execute("COMMIT")
                cursor.close()

            # Add to memory
            self.active_positions.append({
                "id": pos_id,
                "live_strategy_id": strategy_data["id"],
                "symbol": symbol,
                "exchange": "NSE",
                "entry_price": entry_price_db,
                "quantity": quantity,
                "stoploss": stoploss,
                "target": target,
                "broker_order_id": broker_order_id,
                "status": pos_status
            })
            
            if pos_status == "OPEN":
                logger.info(f"✅ Position opened! ID: {pos_id}, Symbol: {symbol}, Price: {price}, SL: {stoploss:.2f}, TP: {target:.2f}")
                await send_user_telegram_message(
                    strategy_data.get("user_id"),
                    f"🚀 *Position Opened*\nStrategy: {strategy_data['name']}\nSymbol: {symbol}\nPrice: ₹{price}\nQty: {quantity}\nSL: ₹{stoploss:.2f}\nTP: ₹{target:.2f}"
                )
            else:
                logger.info(f"⏳ Position PENDING! ID: {pos_id}, Symbol: {symbol}, waiting for broker execution...")
                await send_user_telegram_message(
                    strategy_data.get("user_id"),
                    f"⏳ *Order Sent*\nStrategy: {strategy_data['name']}\nSymbol: {symbol}\nQty: {quantity}\nWaiting for broker execution..."
                )

        except Exception as e:
            logger.error(f"Error opening position: {e}")

    async def _monitor_loop(self):
        """Loop to check SL/TP for all active positions and reconcile pending orders."""
        from app.routers.quotes import _quotes
        
        reconcile_counter = 0
        sync_counter = 0
        while self.is_running:
            try:
                # 1. Reconcile PENDING orders every 5 seconds
                reconcile_counter += 1
                if reconcile_counter >= 5:
                    await self._reconcile_pending_orders()
                    reconcile_counter = 0

                # 2. Sync broker positions every 60 seconds
                sync_counter += 1
                if sync_counter >= 60:
                    await self._sync_broker_positions()
                    sync_counter = 0

                # 3. Monitor OPEN orders for SL/TP
                for pos in self.active_positions[:]:
                    if pos["status"] != "OPEN":
                        continue
                        
                    symbol = pos["symbol"]
                    quote = _quotes.get(symbol)
                    if not quote:
                        continue
                        
                    ltp = quote.get("ltp", 0)
                    if ltp == 0:
                        continue
                        
                    # Check SL
                    stoploss = float(pos["stoploss"])
                    target = float(pos["target"])
                    
                    if stoploss > 0 and ltp <= stoploss:
                        await self.close_position(pos, ltp, "STOPLOSS")
                    # Check TP
                    elif target > 0 and ltp >= target:
                        await self.close_position(pos, ltp, "TARGET")
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                
            await asyncio.sleep(1)

    async def _sync_broker_positions(self):
        """Check if any OPEN positions were closed manually via the broker app."""
        open_positions = [p for p in self.active_positions if p["status"] == "OPEN"]
        if not open_positions: return

        # Load brokers for positions
        strat_info_cache = {}
        with get_db() as conn:
            cursor = conn.cursor()
            for pos in open_positions:
                sid = pos["live_strategy_id"]
                if sid not in strat_info_cache:
                    cursor.execute("SELECT broker, status, user_id FROM live_strategies WHERE id = %s", (sid,))
                    row = cursor.fetchone()
                    if row:
                        strat_info_cache[sid] = {"broker": row[0], "status": row[1], "user_id": row[2]}
            cursor.close()

        for pos in open_positions:
            strat_info = strat_info_cache.get(pos["live_strategy_id"])
            if not strat_info or strat_info["status"] == "PAPER": 
                continue # Ignore paper trades
            
            adapter = get_adapter(strat_info["broker"], strat_info.get("user_id"))
            try:
                qty = adapter.get_net_quantity(pos["symbol"])
            except Exception as e:
                logger.error(f"Error getting net quantity for {pos['symbol']}: {e}")
                continue
            
            # If qty is None, it means the API request failed (e.g. rate limit, connection issue)
            # We should skip to avoid falsely auto-closing positions
            if qty is None:
                continue

            if qty == 0:
                # The position was manually closed on the broker!
                logger.warning(f"⚠️ Position {pos['symbol']} was manually closed on the broker app! Auto-closing in Pytrader.")
                
                from app.routers.quotes import _quotes
                quote = _quotes.get(pos["symbol"])
                exit_price = quote.get("ltp", 0.0) if quote else float(pos["entry_price"])
                
                pnl = (exit_price - float(pos["entry_price"])) * int(pos["quantity"])
                pnl_pct = (pnl / (float(pos["entry_price"]) * int(pos["quantity"]))) * 100 if float(pos["entry_price"]) > 0 else 0
                
                # Update DB and memory
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE positions 
                        SET status = 'CLOSED', exit_price = %s, exit_time = %s, exit_reason = %s, pnl = %s, pnl_pct = %s
                        WHERE id = %s
                    """, (exit_price, datetime.now(self._IST), "BROKER_SYNC", pnl, pnl_pct, pos["id"]))
                    cursor.execute("COMMIT")
                    cursor.close()
                
                try:
                    self.active_positions.remove(pos)
                except ValueError: pass
                
                await send_user_telegram_message(strat_info.get("user_id"), f"⚠️ *Manual Intervention Detected*\nSymbol: {pos['symbol']}\nPorted to CLOSED because net quantity on {strat_info['broker']} is 0.")

    async def _reconcile_pending_orders(self):
        """Check status of PENDING orders with the broker."""
        pending_positions = [p for p in self.active_positions if p["status"] == "PENDING"]
        if not pending_positions: return

        # Load strategies info for their brokers and exit_conditions
        strat_info_cache = {}
        with get_db() as conn:
            cursor = conn.cursor()
            for pos in pending_positions:
                sid = pos["live_strategy_id"]
                if sid not in strat_info_cache:
                    cursor.execute("SELECT broker, exit_conditions, name, user_id FROM live_strategies WHERE id = %s", (sid,))
                    row = cursor.fetchone()
                    if row:
                        strat_info_cache[sid] = {
                            "broker": row[0],
                            "exit_conditions": row[1] if isinstance(row[1], dict) else json.loads(row[1] or "{}"),
                            "name": row[2],
                            "user_id": row[3]
                        }
            cursor.close()

        for pos in pending_positions:
            strat_info = strat_info_cache.get(pos["live_strategy_id"])
            if not strat_info: continue
            
            adapter = get_adapter(strat_info["broker"], strat_info.get("user_id"))
            broker_order_id = pos["broker_order_id"]
            if not broker_order_id: continue
            
            order_res = adapter.get_order_status(broker_order_id)
            st = order_res.get("status")
            
            if st == "COMPLETE":
                # Order executed!
                entry_price = float(order_res.get("average_price", 0.0))
                if entry_price == 0.0:
                    entry_price = float(pos.get("entry_price") or 0.0)
                
                # Calculate SL/TP
                exit_conds = strat_info["exit_conditions"]
                stoploss = entry_price * (1 - exit_conds.get("stoploss_pct", 1.0) / 100)
                target = entry_price * (1 + exit_conds.get("target_pct", 2.0) / 100)
                
                pos["status"] = "OPEN"
                pos["entry_price"] = entry_price
                pos["stoploss"] = stoploss
                pos["target"] = target
                
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE positions
                        SET status = 'OPEN', entry_price = %s, stoploss = %s, target = %s
                        WHERE id = %s
                    """, (entry_price, stoploss, target, pos["id"]))
                    cursor.execute("COMMIT")
                    cursor.close()
                    
                logger.info(f"✅ Order {broker_order_id} COMPLETE! Entry: {entry_price}, SL: {stoploss}, TP: {target}")
                await send_user_telegram_message(
                    strat_info.get("user_id"),
                    f"✅ *Order Executed*\nStrategy: {strat_info['name']}\nSymbol: {pos['symbol']}\nPorted to OPEN status.\nAvg Price: ₹{entry_price:.2f}\nSL: ₹{stoploss:.2f}\nTP: ₹{target:.2f}"
                )
                
            elif st == "REJECTED":
                logger.warning(f"❌ Order {broker_order_id} REJECTED by broker.")
                try:
                    self.active_positions.remove(pos)
                except ValueError:
                    pass
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE positions SET status = 'REJECTED' WHERE id = %s", (pos["id"],))
                    cursor.execute("COMMIT")
                    cursor.close()
                await send_user_telegram_message(strat_info.get("user_id"), f"❌ *Order Rejected*\nStrategy: {strat_info['name']}\nSymbol: {pos['symbol']}\nOrder was rejected by the broker.")

    async def close_position(self, position: dict, exit_price: float, reason: str):
        """Execute exit order and update DB."""
        try:
            # 1. Get strategy details from DB
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT broker, status, user_id FROM live_strategies WHERE id = %s", (position["live_strategy_id"],))
                row = cursor.fetchone()
                if not row:
                    logger.error(f"Cannot find strategy for position {position['id']}")
                    return
                broker, strategy_status, user_id = row[0], row[1], row[2]
                cursor.close()

            is_paper = strategy_status == "PAPER"
            adapter = get_adapter(broker, user_id)
            
            broker_exit_id = f"PAPER_EXIT_{datetime.now(self._IST).strftime('%Y%m%d%H%M%S')}"

            if not is_paper:
                logger.info(f"Closing position {position['id']} ({position['symbol']}) at {exit_price} due to {reason}...")
                # 2. Place Exit Order with retries
                retries = 3
                order_res = None
                for attempt in range(retries):
                    try:
                        order_res = adapter.place_order(
                            symbol=position["symbol"],
                            exchange=position["exchange"],
                            action="SELL",
                            qty=position["quantity"],
                            price=0,
                            order_type="MKT"
                        )
                        if order_res and order_res.get("status") != "error":
                            break
                        else:
                            msg = order_res.get("message") if order_res else "Unknown error"
                            logger.warning(f"Exit attempt {attempt+1} failed checking status: {msg}")
                    except Exception as e:
                        logger.warning(f"Exit attempt {attempt+1} raised exception: {e}")
                    
                    if attempt == retries - 1:
                        logger.error(f"Failed to close position {position['id']} after {retries} attempts.")
                        await send_user_telegram_message(user_id, f"🚨 *URGENT: Failed to Close Position*\nSymbol: {position['symbol']}\nAttempts: {retries}\nPlease check broker APP manually!")
                        return
                    await asyncio.sleep(2)
                
                broker_exit_id = order_res.get("data", {}).get("orderId") or order_res.get("order_id")
            else:
                logger.info(f"PAPER TRADING: Simulating SELL order for {position['symbol']} at {exit_price} (Reason: {reason})...")

            # 3. Calculate PnL
            # Entry price might be Decimal from DB
            entry_price = float(position["entry_price"])
            quantity = int(position["quantity"])
            pnl = (exit_price - entry_price) * quantity
            pnl_pct = (pnl / (entry_price * quantity)) * 100 if entry_price > 0 else 0

            # 4. Update DB
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE positions 
                    SET status = 'CLOSED', 
                        exit_price = %s, 
                        exit_time = %s, 
                        exit_reason = %s, 
                        pnl = %s, 
                        pnl_pct = %s,
                        broker_exit_order_id = %s
                    WHERE id = %s
                """, (
                    exit_price,
                    datetime.now(self._IST),
                    reason,
                    pnl,
                    pnl_pct,
                    broker_exit_id,
                    position["id"]
                ))
                cursor.execute("COMMIT")
                cursor.close()

            # 5. Remove from memory
            self.active_positions.remove(position)
            
            logger.info(f"✅ Position {position['id']} closed! PnL: {pnl:.2f} ({pnl_pct:.2f}%)")

            # Send Notification
            emoji = "💰" if pnl >= 0 else "📉"
            await send_user_telegram_message(
                user_id,
                f"{emoji} *Position Closed*\n"
                f"Symbol: {position['symbol']}\n"
                f"Exit Reason: {reason}\n"
                f"Exit Price: ₹{exit_price}\n"
                f"PnL: *₹{pnl:.2f}* ({pnl_pct:.2f}%)"
            )
            
        except Exception as e:
            logger.error(f"Error closing position {position['id']}: {e}")

# Singleton instance
position_manager = PositionManager()
