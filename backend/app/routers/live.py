"""Live trading router — deploy strategies and manage live orders."""

import json
from fastapi import APIRouter, HTTPException
from pathlib import Path
from pydantic import BaseModel
from app.core.brokers import get_adapter
from app.core.database import get_db

router = APIRouter(prefix="/api/live", tags=["live"])
STRATEGY_STORE = Path("strategies")


class DeployRequest(BaseModel):
    strategy_id: str
    broker: str  # shoonya | zerodha | flattrade | dhan
    paper: bool = False  # paper trading mode


class OrderRequest(BaseModel):
    symbol: str
    exchange: str
    action: str  # BUY | SELL
    qty: int
    price: float = 0
    order_type: str = "MKT"
    broker: str


@router.post("/deploy")
def deploy_strategy(body: DeployRequest):
    strat_path = STRATEGY_STORE / f"{body.strategy_id}.json"
    if not strat_path.exists():
        raise HTTPException(404, "Strategy not found")

    strategy = json.loads(strat_path.read_text())
    
    # Save to PostgreSQL
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO live_strategies (
                strategy_id, name, user_id, broker, status, symbols, 
                risk_settings, entry_conditions, exit_conditions
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            body.strategy_id,
            strategy.get("name", body.strategy_id),
            1, # Default to user 1 for now
            body.broker,
            "ACTIVE" if not body.paper else "PAPER",
            json.dumps(strategy.get("symbols", [])),
            json.dumps(strategy.get("risk", {})),
            json.dumps(strategy.get("entry_conditions", [])),
            json.dumps(strategy.get("exit_conditions", {}))
        ))
        live_id = cursor.fetchone()[0]
        cursor.execute("COMMIT")
        cursor.close()

    return {
        "status": "deployed",
        "live_id": live_id,
        "strategy_id": body.strategy_id,
        "broker": body.broker,
        "mode": "paper" if body.paper else "live",
    }


@router.get("/strategies")
def get_live_strategies():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, strategy_id, name, broker, status, symbols FROM live_strategies ORDER BY created_at DESC")
        rows = cursor.fetchall()
        strategies = []
        for r in rows:
            strategies.append({
                "id": r[0], "strategy_id": r[1], "name": r[2], 
                "broker": r[3], "status": r[4], "symbols": r[5]
            })
        cursor.close()
    return strategies


@router.get("/positions")
def get_positions():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM positions ORDER BY entry_time DESC")
        rows = cursor.fetchall()
        positions = []
        for r in rows:
            positions.append({
                "id": r[0], "live_strategy_id": r[1], "symbol": r[2], "exchange": r[3],
                "entry_price": float(r[4]) if r[4] else 0, 
                "quantity": r[5], "product_type": r[6],
                "stoploss": float(r[7]) if r[7] else None,
                "target": float(r[8]) if r[8] else None,
                "status": r[9], "entry_time": str(r[10]),
                "exit_time": str(r[11]) if r[11] else None,
                "exit_price": float(r[12]) if r[12] else None,
                "pnl": float(r[13]) if r[13] else None,
                "pnl_pct": float(r[14]) if r[14] else None,
                "exit_reason": r[15]
            })
        cursor.close()
    return positions


@router.post("/stop/{live_id}")
def stop_strategy(live_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE live_strategies SET status = 'STOPPED' WHERE id = %s", (live_id,))
        cursor.execute("COMMIT")
        cursor.close()
    return {"status": "stopped", "live_id": live_id}


@router.post("/toggle/{live_id}")
def toggle_strategy(live_id: int, status: str):
    # status: ACTIVE, PAUSED, STOPPED
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE live_strategies SET status = %s WHERE id = %s", (status, live_id))
        cursor.execute("COMMIT")
        cursor.close()
    return {"status": status, "live_id": live_id}


@router.post("/order")
def place_order(body: OrderRequest):
    """Manually place a single order via a broker."""
    try:
        adapter = get_adapter(body.broker)
        result = adapter.place_order(
            symbol=body.symbol, exchange=body.exchange,
            action=body.action, qty=body.qty,
            price=body.price, order_type=body.order_type,
        )
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(500, str(e))


from app.core.config import settings

from datetime import datetime, timezone, timedelta

@router.get("/analytics")
def get_analytics():
    """Get performance analytics and risk status."""
    ist = timezone(timedelta(hours=5, minutes=30))
    today_start = datetime.now(ist).replace(hour=0, minute=0, second=0, microsecond=0)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Equity Curve (Cumulative PnL from closed trades)
        cursor.execute("""
            SELECT exit_time, pnl FROM positions 
            WHERE status = 'CLOSED' AND pnl IS NOT NULL
            ORDER BY exit_time ASC
        """)
        rows = cursor.fetchall()
        
        equity_curve = []
        cum_pnl = 0
        for r in rows:
            cum_pnl += float(r[1])
            equity_curve.append({
                "time": str(r[0]),
                "pnl": cum_pnl
            })
            
        # 2. Risk Status for active strategies
        cursor.execute("SELECT id, name, risk_settings FROM live_strategies WHERE status != 'STOPPED'")
        strats = cursor.fetchall()
        
        risk_status = []
        for s_id, s_name, s_risk_json in strats:
            risk = s_risk_json if isinstance(s_risk_json, dict) else json.loads(s_risk_json)
            
            # Count trades today (IST)
            cursor.execute("""
                SELECT COUNT(*) FROM positions 
                WHERE live_strategy_id = %s AND entry_time >= %s
            """, (s_id, today_start))
            trades_today = cursor.fetchone()[0]
            
            # PnL today (IST)
            cursor.execute("""
                SELECT SUM(pnl) FROM positions 
                WHERE live_strategy_id = %s AND exit_time >= %s AND status = 'CLOSED'
            """, (s_id, today_start))
            pnl_today = cursor.fetchone()[0] or 0.0
            
            risk_status.append({
                "id": s_id,
                "name": s_name,
                "trades_today": trades_today,
                "max_trades": risk.get("max_trades_per_day", 1),
                "pnl_today": float(pnl_today),
                "max_loss": float(risk.get("max_loss_per_day", 5000.0)),
                "is_active": trades_today < risk.get("max_trades_per_day", 1) and float(pnl_today) > -float(risk.get("max_loss_per_day", 5000.0))
            })

        cursor.close()
        
    return {
        "equity_curve": equity_curve,
        "risk_status": risk_status,
        "total_realized_pnl": cum_pnl,
        "telegram_enabled": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)
    }
