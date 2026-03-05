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
    def get_name(self) -> str:
        ...


# ── Shoonya ───────────────────────────────────────────────────────────────────
class ShoonyaAdapter(BrokerAdapter):
    def __init__(self):
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
            totp = pyotp.TOTP(os.environ.get("SHOONYA_TOTP_SECRET", "")).now()
            self.api.login(
                userid=os.environ.get("SHOONYA_USER_ID", ""),
                password=os.environ.get("SHOONYA_PASSWORD", ""),
                twoFA=totp,
                vendor_code=os.environ.get("SHOONYA_VENDOR_CODE", ""),
                api_secret=os.environ.get("SHOONYA_API_SECRET", ""),
                imei=os.environ.get("SHOONYA_IMEI", ""),
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
        return bool(self.api.cancel_order(orderno=order_id))

    def get_name(self):
        return "shoonya"


# ── Flattrade ─────────────────────────────────────────────────────────────────
class FlattradeAdapter(BrokerAdapter):
    """Flattrade uses same NorenRestApiPy protocol as Shoonya."""

    def __init__(self):
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
            totp = pyotp.TOTP(os.environ.get("FLATTRADE_TOTP_SECRET", "")).now()
            self.api.login(
                userid=os.environ.get("FLATTRADE_USER_ID", ""),
                password=os.environ.get("FLATTRADE_PASSWORD", ""),
                twoFA=totp,
                vendor_code=os.environ.get("FLATTRADE_VENDOR_CODE", ""),
                api_secret=os.environ.get("FLATTRADE_API_SECRET", ""),
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
    def get_name(self): return "flattrade"


# ── Zerodha ───────────────────────────────────────────────────────────────────
class ZerodhaAdapter(BrokerAdapter):
    def __init__(self):
        try:
            from kiteconnect import KiteConnect
            self.kite = KiteConnect(api_key=os.environ.get("ZERODHA_API_KEY", ""))
            self.kite.set_access_token(os.environ.get("ZERODHA_ACCESS_TOKEN", ""))
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
    def get_name(self): return "zerodha"


# ── Dhan ──────────────────────────────────────────────────────────────────────
class DhanAdapter(BrokerAdapter):
    BASE = "https://api.dhan.co"

    def __init__(self):
        self.client_id    = os.environ.get("DHAN_CLIENT_ID", "")
        self.access_token = os.environ.get("DHAN_ACCESS_TOKEN", "")
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

    def get_name(self): return "dhan"


# ── Factory ───────────────────────────────────────────────────────────────────
_adapters: dict[str, BrokerAdapter] = {}

def get_adapter(broker: str) -> BrokerAdapter:
    if broker not in _adapters:
        match broker.lower():
            case "shoonya":   _adapters[broker] = ShoonyaAdapter()
            case "flattrade": _adapters[broker] = FlattradeAdapter()
            case "zerodha":   _adapters[broker] = ZerodhaAdapter()
            case "dhan":      _adapters[broker] = DhanAdapter()
            case _: raise ValueError(f"Unknown broker: {broker}")
    return _adapters[broker]
