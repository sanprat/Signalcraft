"""
quotes.py — Real-time market quotes via WebSocket.

Architecture:
  1. Backend connects to Dhan WebSocket using existing access token
  2. On any auth/connection failure → falls back to simulation (ticking prices)
  3. Broadcasts live LTP for NIFTY, BANKNIFTY, FINNIFTY, SENSEX to all
     connected frontend clients every second via /ws/quotes
"""

import asyncio
import json
import logging
import os
import struct
from pathlib import Path
from datetime import datetime, timezone, timedelta

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.dhan_auth import refresh_token_if_needed

router = APIRouter(tags=["quotes"])
logger = logging.getLogger(__name__)

# ── Symbol mapping for Nifty 500 ──
SYMBOL_MAP = {}
try:
    # Look for mapping in common locations: inside /app or relative to script
    potential_paths = [
        Path("/app/data-scripts/nifty500_dhan_mapping.json"),
        Path(__file__).parent.parent.parent / "data-scripts" / "nifty500_dhan_mapping.json"
    ]
    mapping_path = next((p for p in potential_paths if p.exists()), None)
    
    if mapping_path:
        with open(mapping_path, "r") as f:
            SYMBOL_MAP = json.load(f)
        logger.info(f"Loaded {len(SYMBOL_MAP)} stock mappings from {mapping_path}")
    else:
        logger.error(f"Could not find nifty500_dhan_mapping.json in {potential_paths}")
except Exception as e:
    logger.error(f"Error loading stock mappings: {e}")

# ── Dhan token map ────────────────────────────────────────────────────────────
# Initial indices to subscribe to, mapped to their Dhan Tokens (V2)
DHAN_TOKENS = {
    "NIFTY 50": {"exchange_segment": "IDX_I", "security_id": 13},
    "BANKNIFTY": {"exchange_segment": "IDX_I", "security_id": 25},
    "FINNIFTY": {"exchange_segment": "IDX_I", "security_id": 27},
    "SENSEX": {"exchange_segment": "IDX_I", "security_id": 51},
}
# Reverse map: security_id → symbol name
_TOKEN_TO_SYM = {str(v["security_id"]): k for k, v in DHAN_TOKENS.items()}

# ── Open price baselines (for % change calculation) ───────────────────────────
_OPEN: dict[str, float] = {}
_PREV_CLOSE: dict[str, float] = {}

import threading
import pandas as pd
import redis as redis_lib

# ── Redis client for quote caching ────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")
_REDIS_QUOTES_KEY = "signalcraft:quotes:latest"
try:
    _redis = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
    _redis.ping()
    logger.info("Redis connected for quote caching")
except Exception as e:
    _redis = None
    logger.warning(f"Redis unavailable for quote caching: {e}")

# ── Latest quote store (starts with realistic values, will be overwritten) ────
_quotes: dict[str, dict] = {
    "NIFTY 50":  {"ltp": 0.0, "chg": 0.0, "up": True},
    "BANKNIFTY": {"ltp": 0.0, "chg": 0.0, "up": True},
    "FINNIFTY":  {"ltp": 0.0, "chg": 0.0, "up": True},
    "SENSEX":    {"ltp": 0.0, "chg": 0.0, "up": True},
}

_active_subs: set[str] = {"26000", "26009", "26037", "1"} # Track security IDs
_sub_queue = asyncio.Queue()

def _save_quotes_to_redis():
    """Persist current quotes to Redis so they survive backend restarts."""
    if not _redis:
        return
    try:
        _redis.set(_REDIS_QUOTES_KEY, json.dumps(_quotes))
    except Exception:
        pass  # Silently fail — non-critical

def _init_baseline_quotes():
    """Load baseline quotes: Redis first (last live data), then parquet fallback."""
    global _quotes
    
    # ── Strategy 1: Try Redis (has the most recent live data) ──
    if _redis:
        try:
            cached = _redis.get(_REDIS_QUOTES_KEY)
            if cached:
                cached_quotes = json.loads(cached)
                # Only use if we got non-zero prices
                has_data = any(q.get("ltp", 0) > 0 for q in cached_quotes.values())
                if has_data:
                    _quotes.update(cached_quotes)
                    summary = ', '.join(f'{k}={v["ltp"]}' for k, v in cached_quotes.items() if v.get('ltp', 0) > 0)
                    logger.info(f"Loaded baseline quotes from Redis: {summary}")
                    return
        except Exception as e:
            logger.warning(f"Redis baseline read failed: {e}")
    
    # ── Strategy 2: Fall back to parquet files (historical data) ──
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    
    index_dirs = {
        "NIFTY 50":  os.path.join(base_dir, "data", "underlying", "NIFTY"),
        "BANKNIFTY": os.path.join(base_dir, "data", "underlying", "BANKNIFTY"),
        "FINNIFTY":  os.path.join(base_dir, "data", "underlying", "FINNIFTY"),
        "SENSEX":    os.path.join(base_dir, "data", "underlying", "SENSEX"),
    }
    # Try these intervals in order of preference
    interval_fallbacks = ["1D.parquet", "15min.parquet", "5min.parquet", "1min.parquet"]
    
    logger.info("Loading baseline quotes from local parquet files...")
    for display_name, dir_path in index_dirs.items():
        try:
            if not os.path.isdir(dir_path):
                logger.warning(f"Data directory not found for {display_name}: {dir_path}")
                continue
            
            # Find first available interval file
            file_path = None
            for interval in interval_fallbacks:
                candidate = os.path.join(dir_path, interval)
                if os.path.exists(candidate):
                    file_path = candidate
                    break
            
            if not file_path:
                logger.warning(f"No parquet files found for {display_name} in {dir_path}")
                continue
            
            df = pd.read_parquet(file_path)
            if df.empty or len(df) < 2:
                logger.warning(f"Not enough data in parquet for {display_name}")
                continue
            
            latest_close = float(df["close"].iloc[-1])
            prev_close = float(df["close"].iloc[-2])
            
            chg = round(((latest_close - prev_close) / prev_close) * 100, 2) if prev_close else 0.0
            _quotes[display_name] = {"ltp": round(latest_close, 2), "chg": chg, "up": latest_close >= prev_close}
            _OPEN[display_name] = prev_close
            _PREV_CLOSE[str(DHAN_TOKENS[display_name]["security_id"])] = prev_close
            logger.info(f"Baseline {display_name}: {latest_close} ({chg:+.2f}%) from parquet")
        except Exception as e:
            logger.warning(f"Failed to load baseline for {display_name} from parquet: {e}")
    
    # Save parquet baseline to Redis for next restart
    _save_quotes_to_redis()

threading.Thread(target=_init_baseline_quotes, daemon=True).start()

_clients: set[WebSocket] = set()
_using_simulation = False
_broadcast_event = asyncio.Event()
FEED_REQUEST_CODE = int(os.getenv("DHAN_FEED_REQUEST_CODE", "17"))

# ── IST timezone helper ───────────────────────────────────────────────────────
_IST = timezone(timedelta(hours=5, minutes=30))

def _is_market_open() -> bool:
    """Return True if NSE market is currently open (Mon-Fri 09:15–15:30 IST)."""
    now = datetime.now(_IST)
    # Weekday: 0=Mon … 4=Fri, 5=Sat, 6=Sun
    if now.weekday() >= 5:
        return False
    t = now.hour * 60 + now.minute  # minutes since midnight
    return 9 * 60 + 15 <= t <= 15 * 60 + 30


# ── Dhan WebSocket connection ─────────────────────────────────────────────────
async def _dhan_feed():
    """Connect to Dhan WebSocket with automatic token refresh and REST fallback."""
    global _using_simulation

    client_id = os.getenv("DHAN_CLIENT_ID", "").strip()

    if not client_id or not os.getenv("DHAN_ACCESS_TOKEN", "").strip():
        logger.warning("DHAN credentials missing — simulation-only mode")
        _using_simulation = True
        return

    # Set open prices the first time
    for sym, q in _quotes.items():
        if sym not in _OPEN:
            _OPEN[sym] = q["ltp"]

    while True:  # Outer loop: never permanently give up
        # ── Refresh token before each WebSocket attempt cycle ──
        access_token = await _refresh_dhan_token()
        if not access_token:
            logger.error("Cannot obtain valid Dhan token — waiting 60s before retry")
            await asyncio.sleep(60)
            continue

        dhan_ws_url = f"wss://api-feed.dhan.co?version=2&token={access_token}&clientId={client_id}&authType=2"
        fail_count = 0

        # ── WebSocket connection loop (3 attempts per cycle) ──
        while fail_count < 3:
            try:
                logger.info(f"Connecting to Dhan WebSocket V2 (attempt {fail_count + 1})...")
                async with websockets.connect(
                    dhan_ws_url,
                    ping_interval=20,
                    open_timeout=15,
                ) as ws:
                    # Subscribe to index LTP
                    sub_payload = json.dumps({
                        "RequestCode": FEED_REQUEST_CODE,
                        "InstrumentCount": len(DHAN_TOKENS),
                        "InstrumentList": [
                            {
                                "ExchangeSegment": v["exchange_segment"],
                                "SecurityId": str(v["security_id"]),
                            }
                            for v in DHAN_TOKENS.values()
                        ]
                    })
                    await ws.send(sub_payload)
                    _using_simulation = False
                    logger.info(
                        f"Dhan WebSocket: subscribed to initial indices (RequestCode={FEED_REQUEST_CODE})"
                    )
                    fail_count = 0  # reset on successful connect + subscribe

                    # Sub-task to handle dynamic subscriptions from queue
                    async def sub_sender():
                        while True:
                            payload = await _sub_queue.get()
                            try:
                                await ws.send(json.dumps(payload))
                                logger.info(f"Dhan WebSocket: Sent dynamic sub for {payload.get('InstrumentList')}")
                            except Exception as e:
                                logger.error(f"Error sending dynamic sub: {e}")
                            finally:
                                _sub_queue.task_done()

                    sender_task = asyncio.create_task(sub_sender())

                    try:
                        async for raw in ws:
                            _parse_dhan_packet(raw)
                    finally:
                        sender_task.cancel()

            except asyncio.TimeoutError:
                logger.warning("Dhan WebSocket connection timed out")
                fail_count += 1
            except Exception as e:
                logger.error(f"Dhan WebSocket error: {e}")
                fail_count += 1
                # Exponential backoff: 5s, 15s, 45s
                backoff = 5 * (3 ** (fail_count - 1))
                logger.info(f"Waiting {backoff}s before next attempt...")
                await asyncio.sleep(backoff)

        # ── WebSocket failed 3 times — try REST fallback with token refresh ──
        logger.warning("Dhan WebSocket failed 3 times — switching to REST API polling")
        _using_simulation = True

        rest_fail_count = 0
        while rest_fail_count < 20:  # Don't poll REST forever, cycle back to WebSocket
            try:
                import requests as req_lib
                token = os.getenv("DHAN_ACCESS_TOKEN", "").strip()
                cid = os.getenv("DHAN_CLIENT_ID", "").strip()

                r = req_lib.post(
                    "https://api.dhan.co/v2/marketfeed/ltp",
                    headers={"access-token": token, "client-id": cid, "Content-Type": "application/json"},
                    json={"IDX_I": [13, 25, 27]},
                    timeout=5
                )
                if r.status_code == 200:
                    data = r.json()
                    if data.get("status") == "success" and "data" in data and "IDX_I" in data["data"]:
                        idx_data = data["data"]["IDX_I"]
                        if "13" in idx_data:
                            ltp = float(idx_data["13"]["last_price"])
                            _quotes["NIFTY 50"]["ltp"] = ltp
                            _quotes["NIFTY 50"]["up"] = ltp >= _OPEN.get("NIFTY 50", ltp)
                        if "25" in idx_data:
                            ltp = float(idx_data["25"]["last_price"])
                            _quotes["BANKNIFTY"]["ltp"] = ltp
                            _quotes["BANKNIFTY"]["up"] = ltp >= _OPEN.get("BANKNIFTY", ltp)
                        if "27" in idx_data:
                            ltp = float(idx_data["27"]["last_price"])
                            _quotes["FINNIFTY"]["ltp"] = ltp
                            _quotes["FINNIFTY"]["up"] = ltp >= _OPEN.get("FINNIFTY", ltp)

                    _save_quotes_to_redis()
                    _broadcast_event.set()
                    rest_fail_count = 0  # Reset on success

                elif r.status_code == 401:
                    # Token expired! Refresh immediately and break to retry WebSocket
                    logger.warning("REST fallback got 401 — token expired, refreshing...")
                    new_token = await _refresh_dhan_token()
                    if new_token:
                        logger.info("Token refreshed after 401 — retrying WebSocket connection")
                        break  # Break out of REST loop → outer loop will retry WebSocket
                    else:
                        logger.error("Token refresh failed after 401 — waiting 60s")
                        await asyncio.sleep(60)
                        rest_fail_count += 1
                else:
                    logger.warning(f"REST fallback failed: {r.status_code} {r.text[:100]}")
                    rest_fail_count += 1
            except Exception as e:
                logger.error(f"REST fallback error: {e}")
                rest_fail_count += 1

            await asyncio.sleep(3)

        # Loop back to top: refresh token and retry WebSocket
        logger.info("Cycling back to WebSocket connection with fresh token...")


async def _refresh_dhan_token() -> str | None:
    """Refresh Dhan token if needed. Returns the current valid token or None."""
    try:
        refresh_result = refresh_token_if_needed()
        if refresh_result.get("refreshed"):
            logger.info("Dhan token refreshed successfully")
        elif not refresh_result.get("success"):
            logger.warning(f"Token refresh failed: {refresh_result.get('message')}")
            return None
    except Exception as e:
        logger.warning(f"Token refresh error: {e}")
        return None

    token = os.getenv("DHAN_ACCESS_TOKEN", "").strip()
    return token if token else None


# Packet counter for debugging
_packet_count = 0

def _parse_dhan_packet(raw):
    """Parse Dhan LTP packet (binary or JSON) and update _quotes."""
    global _quotes, _packet_count
    _packet_count += 1
    if _packet_count % 100 == 1:  # Log every 100th packet
        logger.debug(f"Received packet #{_packet_count}, type={type(raw).__name__}, len={len(raw) if hasattr(raw, '__len__') else 'N/A'}")
    try:
        if isinstance(raw, str):
            data = json.loads(raw)
            token = str(data.get("tk") or data.get("Ttkn") or "")
            ltp = float(data.get("ltp") or data.get("Ltp") or 0)
            if _packet_count % 100 == 1:
                logger.debug(f"JSON packet: token={token}, ltp={ltp}")
        else:
            # DhanHQ V2 Binary: First 8 bytes = Response Header (Little Endian)
            # 1B FeedResponseCode, 2B MsgLen, 1B ExchangeSegment, 4B SecurityId
            if len(raw) >= 8:
                feed_response_code = raw[0]
                token = str(struct.unpack("<i", raw[4:8])[0])
                ltp = 0.0
                
                # 1=Index, 2=Ticker, 4=Quote, 8=Full, 6=Prev Close
                try:
                    if feed_response_code in (1, 2) and len(raw) >= 16:
                        ltp = struct.unpack("<f", raw[8:12])[0]
                    elif feed_response_code == 4 and len(raw) >= 50: # Quote packet is 50 bytes
                        ltp = struct.unpack("<f", raw[8:12])[0]
                        day_open = struct.unpack("<f", raw[34:38])[0]
                        day_close = struct.unpack("<f", raw[38:42])[0]
                        if day_open > 0:
                            _OPEN[token] = day_open
                        if day_close > 0:
                            _PREV_CLOSE[token] = day_close
                    elif feed_response_code == 8 and len(raw) >= 62:  # Full Packet
                        ltp = struct.unpack("<f", raw[8:12])[0]
                        day_open = struct.unpack("<f", raw[46:50])[0]
                        day_close = struct.unpack("<f", raw[50:54])[0]
                        if day_open > 0:
                            _OPEN[token] = day_open
                        if day_close > 0:
                            _PREV_CLOSE[token] = day_close
                    elif feed_response_code == 6 and len(raw) >= 12:  # Prev Close Packet
                        prev_close = struct.unpack("<f", raw[8:12])[0]
                        if prev_close > 0:
                            _PREV_CLOSE[token] = prev_close
                        return
                    elif feed_response_code == 50:  # Feed Disconnect
                        logger.warning(f"Dhan WS Disconnect Packet: {struct.unpack('<h', raw[8:10])[0]}")
                        return
                    else:
                        # Ignore other packet types for quotes
                        return
                except struct.error as e:
                    logger.debug(f"Struct unpack error: {e} | len={len(raw)}")
                    return
            else:
                return

        if ltp <= 0:
            return

        sym = _TOKEN_TO_SYM.get(token)
        if not sym:
            return

        old_ltp = _quotes[sym]["ltp"]
        open_price = _PREV_CLOSE.get(token) or _OPEN.get(token) or ltp
        chg = round((ltp - open_price) / open_price * 100, 2) if open_price else 0
        _quotes[sym] = {"ltp": round(ltp, 2), "chg": chg, "up": ltp >= old_ltp}
        # suppress debug for performance
        # logger.debug(f"Tick {sym}: {ltp} ({chg:+.2f}%)")

    except Exception as e:
        logger.debug(f"Packet parse error: {e}")


# ── Simulation fallback ───────────────────────────────────────────────────────
async def _handle_dynamic_sub(symbol: str):
    """Subscribe to a new symbol at runtime."""
    global _active_subs, _quotes
    
    # Check if already subscribed
    symbol_upper = symbol.upper()
    
    # 1. Check if it's an index
    token = None
    exchange = "NSE_IDX"
    
    for k, v in DHAN_TOKENS.items():
        if k.upper() == symbol_upper or (k == "NIFTY 50" and symbol_upper == "NIFTY"):
            token = str(v["security_id"])
            exchange = v["exchange_segment"]
            break
            
    # 2. Check if it's a Nifty 500 stock
    if not token and symbol_upper in SYMBOL_MAP:
        token = SYMBOL_MAP[symbol_upper]
        exchange = "NSE_EQ"
        
    if not token:
        logger.warning(f"Cannot resolve symbol for subscription: {symbol}")
        return

    if token in _active_subs:
        return
        
    logger.info(f"Subscribing to dynamic symbol: {symbol_upper} (Token: {token})")
    _active_subs.add(token)
    _TOKEN_TO_SYM[token] = symbol_upper
    
    # Initialize quote if not exists
    if symbol_upper not in _quotes:
        _quotes[symbol_upper] = {"ltp": 0.0, "chg": 0.0, "up": True}
        
    # Queue the subscription request
    payload = {
        "RequestCode": FEED_REQUEST_CODE,
        "InstrumentCount": 1,
        "InstrumentList": [
            {
                "ExchangeSegment": exchange,
                "SecurityId": token,
            }
        ]
    }
    await _sub_queue.put(payload)

async def _simulate_feed():
    """Simulate realistic ticking prices when broker WS unavailable.

    Only ticks when NSE market is open (Mon-Fri 09:15-15:30 IST).
    Outside market hours, prices are frozen.
    """
    import random
    logger.info("Starting simulation feed (Dhan WS unavailable)")

    # Wait for baseline quotes to be initialized
    await asyncio.sleep(2)
    
    while True:
        # Only simulate when Dhan WS is unavailable
        if _using_simulation and _is_market_open():
            # Dynamically get current symbols (handles dynamic subscriptions)
            for sym in list(_quotes.keys()):
                old = _quotes[sym]["ltp"]
                # Get or initialize base price
                base = _OPEN.get(sym, 0)
                if base <= 0:
                    if old > 0:
                        _OPEN[sym] = old
                        base = old
                    else:
                        continue
                # Random walk: ±0.05% per tick (realistic intraday movement)
                pct_move = random.gauss(0, 0.05) / 100
                ltp = round(old * (1 + pct_move), 2) if old > 0 else base
                chg = round((ltp - base) / base * 100, 2)
                _quotes[sym] = {"ltp": ltp, "chg": chg, "up": ltp >= old}
        # Outside market hours or Dhan is providing real ticks — prices frozen
        await asyncio.sleep(1)


# ── Broadcast to all frontend clients ─────────────────────────────────────────
async def _broadcast_loop():
    global _clients
    _redis_save_counter = 0
    while True:
        # Wait for an update or a ping interval
        try:
            await asyncio.wait_for(_broadcast_event.wait(), timeout=1.0)
            _broadcast_event.clear()
        except asyncio.TimeoutError:
            pass

        if _clients:
            market_open = _is_market_open()
            payload = json.dumps({
                "type": "quotes",
                "data": _quotes,
                "ts": datetime.now(_IST).strftime("%H:%M:%S"),
                "live": not _using_simulation,
                "market_open": market_open,
            })
            dead: set[WebSocket] = set()
            for ws in _clients.copy():
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.add(ws)
            _clients -= dead
        # Save to Redis every ~10 seconds (50 iterations × 200ms)
        _redis_save_counter += 1
        if _redis_save_counter >= 50:
            _redis_save_counter = 0
            _save_quotes_to_redis()
        # Broadcast every 200ms for smoother chart updates (5 updates/sec)
        await asyncio.sleep(0.2)


# ── FastAPI WebSocket endpoint ────────────────────────────────────────────────
@router.websocket("/ws/quotes")
async def ws_quotes(websocket: WebSocket):
    # Accept the connection explicitly without checking origin
    await websocket.accept()
    _clients.add(websocket)
    try:
        # Send snapshot immediately on connect (ensures frontend gets data fast)
        await websocket.send_text(json.dumps({
            "type": "quotes",
            "data": _quotes,
            "ts": datetime.now(_IST).strftime("%H:%M:%S"),
            "live": not _using_simulation,
            "market_open": _is_market_open(),
        }))
        while True:
            # We must await receive() to keep the connection open and handle client disconnects
                try:
                    data_str = await websocket.receive_text()
                    msg = json.loads(data_str)
                    if msg.get("type") == "subscribe" and msg.get("symbol"):
                        await _handle_dynamic_sub(msg["symbol"])
                except WebSocketDisconnect:
                    break
    except Exception as e:
        logger.error(f"WebSocket client error: {e}")
    finally:
        _clients.discard(websocket)


# ── REST fallback ─────────────────────────────────────────────────────────────
@router.get("/api/quotes")
def get_quotes():
    return {"quotes": _quotes, "live": not _using_simulation}

# ── Historical Data for Charts ────────────────────────────────────────────────
@router.get("/api/quotes/historical/{symbol}")
def get_historical_quotes(symbol: str, interval: str = "15min"):
    """
    Returns historical data for the requested NIFTY 500 stock or Index.
    Reads from local Parquet file. Defaults to 15-minute resolution.
    """
    import os
    import pandas as pd
    
    symbol_upper = symbol.upper()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    
    # 0. Clean up interval name and determine if intraday
    is_intraday_req = any(x in interval for x in ["1s", "5s", "1min", "1m", "5min", "5m", "15min", "15m"])
    if not interval.endswith(".parquet"):
        interval_file = f"{interval}.parquet"
    else:
        interval_file = interval
        
    # 1. Try NIFTY500 stocks first
    file_path = os.path.join(base_dir, "data", "candles", "NIFTY500", symbol_upper, interval_file)
    
    # Fallback to 1D if requested interval not found
    if not os.path.exists(file_path) and interval_file != "1D.parquet":
        file_path_1D = os.path.join(base_dir, "data", "candles", "NIFTY500", symbol_upper, "1D.parquet")
        if os.path.exists(file_path_1D):
            file_path = file_path_1D
            logger.info(f"Fallback to 1D for {symbol_upper} ({interval} not found)")

    # 2. Try Indices (underlying) if not found in NIFTY500 or fallback already occurred
    if not os.path.exists(file_path) or (not is_intraday_req and "1D" not in file_path):
        # Map some common aliases if needed
        idx_map = {
            "NIFTY 50": "NIFTY",
            "NIFTY50": "NIFTY",
            "NIFTY": "NIFTY",
            "BANKNIFTY": "BANKNIFTY",
            "FINNIFTY": "FINNIFTY",
            "GIFTNIFTY": "GIFTNIFTY",
            "SENSEX": "SENSEX"
        }
        mapped_symbol = idx_map.get(symbol_upper, symbol_upper)
        
        # Check in underlying folder for the requested interval
        idx_file_path = os.path.join(base_dir, "data", "underlying", mapped_symbol, interval_file)
        
        if os.path.exists(idx_file_path):
            file_path = idx_file_path
        elif not os.path.exists(file_path):
            # Fallback to 1D for indices
            idx_path_1D = os.path.join(base_dir, "data", "underlying", mapped_symbol, "1D.parquet")
            if os.path.exists(idx_path_1D):
                file_path = idx_path_1D
            else:
                return {"error": f"Historical data not found for {symbol}", "symbol": symbol}
        
    try:
        df = pd.read_parquet(file_path)
        logger.info(f"Serving historical data from: {file_path}")
        # TradingView wants time formatting specifically as UNIX timestamp or string "YYYY-MM-DD"
        if 'time' in df.columns:
            # Check if the ACTUAL file being served is intraday
            is_serving_intraday = any(x in file_path for x in ["1s", "5s", "1min", "5min", "15min"])
            if is_serving_intraday:
                # For intraday, convert to UNIX timestamp (seconds)
                # Handle timezone-aware datetimes and any precision (ms, ns, us)
                df['time'] = df['time'].apply(lambda x: int(x.timestamp()))
            else:
                df['time'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d')
        
        # lightweight-charts uses 'value' for volume if rendered as a histogram series
        if 'volume' in df.columns:
            df['value'] = df['volume']
        elif 'qty' in df.columns:
            df['value'] = df['qty']
        else:
            df['value'] = 0
            
        cols = ['time', 'open', 'high', 'low', 'close', 'value']
        # Filter to only existing columns to avoid key errors
        available_cols = [c for c in cols if c in df.columns]
        records = df[available_cols].to_dict(orient='records')
        
        # Final check if we are actually returning intraday data
        is_intraday_final = any(x in file_path for x in ["1s", "5s", "1min", "5min", "15min"])
        return {"data": records, "is_intraday": is_intraday_final, "debug_file_path": file_path}
    except Exception as e:
        logger.error(f"Error reading historical data for {symbol}: {e}")
        return {"error": str(e)}
