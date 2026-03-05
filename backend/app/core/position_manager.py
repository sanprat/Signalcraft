import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional

from app.core.database import get_db
from app.core.brokers import get_adapter
from app.core.config import settings
from app.core.notifications import send_telegram_message

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
                WHERE status = 'OPEN'
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
            await send_telegram_message(f"🚨 *Risk Limit Reached*\nStrategy: {strategy_data['name']}\nReason: Daily loss limit of ₹{max_loss} hit.\nStopping for the day.")
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
            adapter = get_adapter(broker)
            
            # TODO: Hardcoded quantity for now, should come from risk_settings
            quantity = strategy_data.get("risk", {}).get("quantity_lots", 1)
            
            broker_order_id = f"PAPER_ENTRY_{datetime.now(self._IST).strftime('%Y%m%d%H%M%S')}"

            if not is_paper:
                logger.info(f"Placing BUY order for {symbol}, qty={quantity} via {broker}...")
                # Place Order
                order_res = adapter.place_order(
                    symbol=symbol,
                    exchange="NSE",
                    action="BUY",
                    qty=quantity,
                    price=0, # Market
                    order_type="MKT"
                )
                
                if order_res.get("status") == "error":
                    logger.error(f"Order placement failed: {order_res.get('message')}")
                    return

                broker_order_id = order_res.get("data", {}).get("orderId") or order_res.get("order_id")
            else:
                logger.info(f"PAPER TRADING: Simulating BUY order for {symbol}, qty={quantity}...")

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
                    price,
                    quantity,
                    stoploss,
                    target,
                    broker_order_id,
                    "OPEN",
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
                "entry_price": price,
                "quantity": quantity,
                "stoploss": stoploss,
                "target": target,
                "broker_order_id": broker_order_id,
                "status": "OPEN"
            })
            
            logger.info(f"✅ Position opened! ID: {pos_id}, Symbol: {symbol}, Price: {price}, SL: {stoploss:.2f}, TP: {target:.2f}")

            # Send Notification
            await send_telegram_message(
                f"🚀 *Position Opened*\n"
                f"Strategy: {strategy_data['name']}\n"
                f"Symbol: {symbol}\n"
                f"Price: ₹{price}\n"
                f"Qty: {quantity}\n"
                f"SL: ₹{stoploss:.2f}\n"
                f"TP: ₹{target:.2f}"
            )

        except Exception as e:
            logger.error(f"Error opening position: {e}")

    async def _monitor_loop(self):
        """Loop to check SL/TP for all active positions."""
        from app.routers.quotes import _quotes
        
        while self.is_running:
            try:
                for pos in self.active_positions[:]:
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
                    
                    if ltp <= stoploss:
                        await self.close_position(pos, ltp, "STOPLOSS")
                    # Check TP
                    elif ltp >= target:
                        await self.close_position(pos, ltp, "TARGET")
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                
            await asyncio.sleep(1)

    async def close_position(self, position: dict, exit_price: float, reason: str):
        """Execute exit order and update DB."""
        try:
            # 1. Get strategy details from DB
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT broker, status FROM live_strategies WHERE id = %s", (position["live_strategy_id"],))
                row = cursor.fetchone()
                broker = row[0]
                strat_status = row[1]
                cursor.close()

            is_paper = strat_status == "PAPER"
            adapter = get_adapter(broker)
            
            broker_exit_id = f"PAPER_EXIT_{datetime.now(self._IST).strftime('%Y%m%d%H%M%S')}"

            if not is_paper:
                logger.info(f"Closing position {position['id']} ({position['symbol']}) at {exit_price} due to {reason}...")
                # 2. Place Exit Order
                order_res = adapter.place_order(
                    symbol=position["symbol"],
                    exchange=position["exchange"],
                    action="SELL",
                    qty=position["quantity"],
                    price=0,
                    order_type="MKT"
                )
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
            await send_telegram_message(
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
