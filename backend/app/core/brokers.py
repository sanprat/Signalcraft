"""
brokers.py — Broker adapter pattern for live order placement.
Supports: Shoonya, Zerodha (KiteConnect), Flattrade, Dhan
"""

import logging
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# Add data-scripts to path for shoonya client
DATA_SCRIPTS = Path(__file__).parent.parent.parent.parent / "data-scripts"
sys.path.insert(0, str(DATA_SCRIPTS))


# ── Base adapter ───────────────────────────────────────────────────────────────
class BrokerAdapter(ABC):
    @abstractmethod
    def place_order(self, symbol: str, exchange: str, action: str,
                    qty: int, price: float = 0, order_type: str = "MKT") -> dict:
        ...

    @abstractmethod
    def get_positions(self) -> list:
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        ...

    @abstractmethod
    def get_order_status(self, order_id: str) -> dict:
        """Return dict with 'status' (e.g. 'COMPLETE', 'REJECTED', 'PENDING') and 'average_price'"""
        ...

    @abstractmethod
    def get_net_quantity(self, symbol: str) -> int | None:
        """Fetch the net open quantity for a symbol. Returns 0 if closed, None on error."""
        ...

    @abstractmethod
    def get_name(self) -> str:
        ...


# ── Shoonya ───────────────────────────────────────────────────────────────────
class ShoonyaAdapter(BrokerAdapter):
    def __init__(self, creds=None):
        if not creds: creds = {}
        try:
            from NorenRestApiPy.NorenApi import NorenApi
            import pyotp

            class ShoonyaApiPy(NorenApi):
                def __init__(self):
                    super().__init__(
                        host='https://api.shoonya.com/NorenWClient10/',
                        websocket='wss://api.shoonya.com/NorenWSClient10/'
                    )

            self.api = ShoonyaApiPy()
            totp_secret = creds.get("totp_secret") or os.environ.get("SHOONYA_TOTP_SECRET", "")
            totp = pyotp.TOTP(totp_secret).now() if totp_secret else ""
            self.api.login(
                userid=creds.get("userid") or os.environ.get("SHOONYA_USER_ID", ""),
                password=creds.get("password") or os.environ.get("SHOONYA_PASSWORD", ""),
                twoFA=totp,
                vendor_code=creds.get("vendor_code") or os.environ.get("SHOONYA_VENDOR_CODE", ""),
                api_secret=creds.get("api_secret") or os.environ.get("SHOONYA_API_SECRET", ""),
                imei=creds.get("imei") or os.environ.get("SHOONYA_IMEI", "abc1234"),
            )
            logger.info("Shoonya: connected")
        except Exception as e:
            logger.error(f"Shoonya init failed: {e}")
            self.api = None

    def place_order(self, symbol, exchange, action, qty, price=0, order_type="MKT"):
        if not self.api:
            return {"status": "error", "message": "Shoonya not connected"}
        ret = self.api.place_order(
            buy_or_sell='B' if action == 'BUY' else 'S',
            product_type='I',  # Intraday
            exchange=exchange,
            tradingsymbol=symbol,
            quantity=qty,
            discloseqty=0,
            price_type=order_type,
            price=price,
            trigger_price=None,
            retention='DAY',
            remarks='SignalCraft'
        )
        return ret or {"status": "error"}

    def get_positions(self):
        if not self.api:
            return []
        return self.api.get_positions() or []

    def cancel_order(self, order_id):
        if not self.api:
            return False
        return bool(self.api.single_order_history(orderno=order_id)) # Not cancel order API, wait, cancel order API is cancel_order
        return bool(self.api.cancel_order(orderno=order_id))

    def get_order_status(self, order_id):
        if not self.api:
             return {"status": "ERROR"}
        res = self.api.single_order_history(orderno=order_id)
        if not res or not isinstance(res, list):
             return {"status": "UNKNOWN"}
        # Usually the first object is the latest status in NorenApi
        latest = res[0]
        st = latest.get("status", "").upper()
        if "COMPLETE" in st:
            st = "COMPLETE"
        elif "REJECT" in st:
            st = "REJECTED"
        else:
            st = "PENDING"
        avg_price = float(latest.get("avgprc", 0.0))
        return {"status": st, "average_price": avg_price}

    def get_net_quantity(self, symbol):
        if not self.api: return None
        positions = self.api.get_positions()
        if positions is None: return None
        if not positions or not isinstance(positions, list): return 0
        for p in positions:
            if p.get("tsym", "") == symbol or symbol in p.get("tsym", ""):
                 return int(p.get("netqty", 0))
        return 0

    def get_name(self):
        return "shoonya"


# ── Flattrade ─────────────────────────────────────────────────────────────────
class FlattradeAdapter(BrokerAdapter):
    """Flattrade uses same NorenRestApiPy protocol as Shoonya."""

    def __init__(self, creds=None):
        if not creds: creds = {}
        try:
            from NorenRestApiPy.NorenApi import NorenApi
            import pyotp

            class FlattradeApiPy(NorenApi):
                def __init__(self):
                    super().__init__(
                        host='https://authapi.flattrade.in/trade/apilogin/',
                        websocket='wss://piconnect.flattrade.in/PiConnectWSTp/'
                    )

            self.api = FlattradeApiPy()
            totp_secret = creds.get("totp_secret") or os.environ.get("FLATTRADE_TOTP_SECRET", "")
            totp = pyotp.TOTP(totp_secret).now() if totp_secret else ""
            self.api.login(
                userid=creds.get("userid") or os.environ.get("FLATTRADE_USER_ID", ""),
                password=creds.get("password") or os.environ.get("FLATTRADE_PASSWORD", ""),
                twoFA=totp,
                vendor_code=creds.get("vendor_code") or os.environ.get("FLATTRADE_VENDOR_CODE", ""),
                api_secret=creds.get("api_secret") or os.environ.get("FLATTRADE_API_SECRET", ""),
                imei="",
            )
        except Exception as e:
            logger.error(f"Flattrade init failed: {e}")
            self.api = None

    def place_order(self, symbol, exchange, action, qty, price=0, order_type="MKT"):
        if not self.api:
            return {"status": "error", "message": "Flattrade not connected"}
        return self.api.place_order(
            buy_or_sell='B' if action == 'BUY' else 'S',
            product_type='I', exchange=exchange, tradingsymbol=symbol,
            quantity=qty, discloseqty=0, price_type=order_type, price=price,
            trigger_price=None, retention='DAY', remarks='SignalCraft'
        ) or {"status": "error"}

    def get_positions(self): return self.api.get_positions() if self.api else []
    def cancel_order(self, order_id): return bool(self.api.cancel_order(orderno=order_id)) if self.api else False
    
    def get_order_status(self, order_id):
        if not self.api: return {"status": "ERROR"}
        res = self.api.single_order_history(orderno=order_id)
        if not res or not isinstance(res, list): return {"status": "UNKNOWN"}
        latest = res[0]
        st = latest.get("status", "").upper()
        if "COMPLETE" in st: st = "COMPLETE"
        elif "REJECT" in st: st = "REJECTED"
        else: st = "PENDING"
        avg_price = float(latest.get("avgprc", 0.0))
        return {"status": st, "average_price": avg_price}

    def get_net_quantity(self, symbol):
        if not self.api: return 0
        positions = self.api.get_positions()
        if not positions or not isinstance(positions, list): return 0
        for p in positions:
            if p.get("tsym", "") == symbol or symbol in p.get("tsym", ""):
                 return int(p.get("netqty", 0))
        return 0

    def get_name(self): return "flattrade"


# ── Zerodha ───────────────────────────────────────────────────────────────────
class ZerodhaAdapter(BrokerAdapter):
    def __init__(self, creds=None):
        if not creds: creds = {}
        try:
            from kiteconnect import KiteConnect
            api_key = creds.get("api_key") or os.environ.get("ZERODHA_API_KEY", "")
            access_token = creds.get("access_token") or os.environ.get("ZERODHA_ACCESS_TOKEN", "")
            self.kite = KiteConnect(api_key=api_key)
            if access_token:
                self.kite.set_access_token(access_token)
            logger.info("Zerodha: KiteConnect initialized")
        except Exception as e:
            logger.error(f"Zerodha init failed: {e}")
            self.kite = None

    def place_order(self, symbol, exchange, action, qty, price=0, order_type="MARKET"):
        if not self.kite:
            return {"status": "error", "message": "Zerodha not connected"}
        from kiteconnect import KiteConnect
        order_id = self.kite.place_order(
            variety=KiteConnect.VARIETY_REGULAR,
            exchange=exchange,
            tradingsymbol=symbol,
            transaction_type=KiteConnect.TRANSACTION_TYPE_BUY if action == 'BUY' else KiteConnect.TRANSACTION_TYPE_SELL,
            quantity=qty,
            product=KiteConnect.PRODUCT_MIS,
            order_type=KiteConnect.ORDER_TYPE_MARKET if order_type == "MKT" else KiteConnect.ORDER_TYPE_LIMIT,
            price=price or None,
            tag="signalcraft",
        )
        return {"status": "ok", "order_id": order_id}

    def get_positions(self): return self.kite.positions()["net"] if self.kite else []
    def cancel_order(self, order_id):
        from kiteconnect import KiteConnect
        self.kite.cancel_order(KiteConnect.VARIETY_REGULAR, order_id)
        return True

    def get_order_status(self, order_id):
        if not self.kite:
            return {"status": "ERROR"}
        try:
            history = self.kite.order_history(order_id=order_id)
            if not history: return {"status": "UNKNOWN"}
            latest = history[-1]
            st = latest.get("status", "").upper()
            if "COMPLETE" in st: st = "COMPLETE"
            elif "REJECT" in st: st = "REJECTED"
            else: st = "PENDING"
            avg_price = float(latest.get("average_price", 0.0))
            return {"status": st, "average_price": avg_price}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def get_net_quantity(self, symbol):
        if not self.kite: return None
        try:
            positions = self.kite.positions()
            if positions is None: return None
            for p in positions.get("net", []):
                if p.get("tradingsymbol") == symbol:
                    return int(p.get("quantity", 0))
        except: return None
        return 0

    def get_name(self): return "zerodha"


# ── Dhan ──────────────────────────────────────────────────────────────────────
class DhanAdapter(BrokerAdapter):
    BASE = "https://api.dhan.co"

    def __init__(self, creds=None):
        if not creds: creds = {}
        self.client_id    = creds.get("client_id") or os.environ.get("DHAN_CLIENT_ID", "")
        self.access_token = creds.get("access_token") or os.environ.get("DHAN_ACCESS_TOKEN", "")
        self.headers = {
            "Content-Type": "application/json",
            "access-token": self.access_token,
            "client-id": self.client_id,
        }

    def place_order(self, symbol, exchange, action, qty, price=0, order_type="MARKET"):
        payload = {
            "dhanClientId":    self.client_id,
            "transactionType": "BUY" if action == "BUY" else "SELL",
            "exchangeSegment": exchange,
            "productType":     "INTRADAY",
            "orderType":       "MARKET" if order_type == "MKT" else "LIMIT",
            "validity":        "DAY",
            "tradingSymbol":   symbol,
            "quantity":        qty,
            "price":           price,
            "triggerPrice":    0,
            "afterMarketOrder":False,
        }
        r = requests.post(f"{self.BASE}/orders", json=payload, headers=self.headers, timeout=10)
        return r.json()

    def get_positions(self):
        r = requests.get(f"{self.BASE}/positions", headers=self.headers, timeout=10)
        return r.json()

    def cancel_order(self, order_id):
        r = requests.delete(f"{self.BASE}/orders/{order_id}", headers=self.headers, timeout=10)
        return r.status_code == 200

    def get_order_status(self, order_id):
        try:
            r = requests.get(f"{self.BASE}/orders/{order_id}", headers=self.headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if "data" in data: data = data["data"]
                st = data.get("orderStatus", "").upper()
                if "TRADED" in st or "COMPLETE" in st: st = "COMPLETE"
                elif "REJECT" in st or "CANCEL" in st: st = "REJECTED"
                else: st = "PENDING"
                avg_price = float(data.get("tradedPrice", 0.0) or 0.0)
                return {"status": st, "average_price": avg_price}
            return {"status": "ERROR"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def get_net_quantity(self, symbol):
        try:
            r = requests.get(f"{self.BASE}/positions", headers=self.headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if not data: return None
                data_list = data.get("data", [])
                for p in data_list:
                    if p.get("tradingSymbol") == symbol:
                        return int(p.get("netQty", 0))
            else:
                return None
        except: return None
        return 0

    def get_name(self): return "dhan"


# ── Factory ───────────────────────────────────────────────────────────────────
_adapters: dict[str, BrokerAdapter] = {}

def get_adapter(broker: str, user_id: int = None) -> BrokerAdapter:
    from app.core.database import get_broker_credentials
    cache_key = f"{broker}_{user_id}" if user_id else broker
    
    if cache_key not in _adapters:
        creds = get_broker_credentials(user_id, broker) if user_id else {}
        if not creds: creds = {}
        
        match broker.lower():
            case "shoonya":   _adapters[cache_key] = ShoonyaAdapter(creds)
            case "flattrade": _adapters[cache_key] = FlattradeAdapter(creds)
            case "zerodha":   _adapters[cache_key] = ZerodhaAdapter(creds)
            case "dhan":      _adapters[cache_key] = DhanAdapter(creds)
            case _: raise ValueError(f"Unknown broker: {broker}")
    return _adapters[cache_key]

def clear_adapter_cache(broker: str, user_id: int):
    cache_key = f"{broker}_{user_id}"
    if cache_key in _adapters:
        del _adapters[cache_key]
        logger.info(f"Cleared broker adapter cache for {cache_key}")
