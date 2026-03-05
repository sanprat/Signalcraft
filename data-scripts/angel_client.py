"""
angel_client.py — Angel One SmartAPI wrapper
Manages 2 accounts with round-robin rotation for doubled throughput.
"""

import time
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import pyotp
import requests
from SmartApi import SmartConnect

logger = logging.getLogger(__name__)

# SmartAPI interval strings
INTERVAL_MAP = {
    "1min":  "ONE_MINUTE",
    "5min":  "FIVE_MINUTE",
    "15min": "FIFTEEN_MINUTE",
}

# Max days per request per interval (Angel API limit)
MAX_DAYS = {
    "1min":  30,
    "5min":  100,
    "15min": 200,
}

# Rate limit: 3 requests/sec per account → 0.34s sleep between calls
RATE_LIMIT_SLEEP = 0.35

SCRIP_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
SCRIP_MASTER_CACHE = Path("data/scrip_master_angel.json")


class AngelAccount:
    """Single Angel One account session."""

    def __init__(self, client_id: str, api_key: str, mpin: str, totp_secret: str):
        self.client_id = client_id
        self.api_key = api_key
        self.mpin = mpin
        self.totp_secret = totp_secret
        self.api = None
        self.last_request_time = 0.0

    def login(self):
        totp = pyotp.TOTP(self.totp_secret).now()
        self.api = SmartConnect(api_key=self.api_key)
        # Angel One deprecated password login — now requires MPIN (4-digit PIN)
        data = self.api.generateSession(self.client_id, self.mpin, totp)
        if data["status"] is False:
            raise RuntimeError(f"Angel login failed for {self.client_id}: {data['message']}")
        logger.info(f"Logged in Angel account: {self.client_id}")

    def _throttle(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_SLEEP:
            time.sleep(RATE_LIMIT_SLEEP - elapsed)
        self.last_request_time = time.time()

    def get_candles(self, token: str, interval: str, from_dt: datetime, to_dt: datetime) -> list:
        """Fetch candles for a single chunk. Returns list of OHLCV dicts."""
        self._throttle()
        params = {
            "exchange": "NFO",
            "symboltoken": token,
            "interval": INTERVAL_MAP[interval],
            "fromdate": from_dt.strftime("%Y-%m-%d %H:%M"),
            "todate": to_dt.strftime("%Y-%m-%d %H:%M"),
        }
        try:
            resp = self.api.getCandleData(params)
            if resp and resp.get("status") and resp.get("data"):
                return resp["data"]  # list of [timestamp, open, high, low, close, volume]
            return []
        except Exception as e:
            logger.warning(f"Angel {self.client_id} candle fetch error: {e}")
            return []


class AngelClient:
    """
    Round-robin across 2 Angel accounts to double effective rate limit.
    Falls back to Shoonya on repeated failures.
    """

    def __init__(self, accounts: list[dict]):
        self.accounts = [AngelAccount(**a) for a in accounts]
        self._idx = 0
        self._scrip_master = None

    def login_all(self):
        for acc in self.accounts:
            acc.login()

    def _next_account(self) -> AngelAccount:
        acc = self.accounts[self._idx % len(self.accounts)]
        self._idx += 1
        return acc

    def load_scrip_master(self, force_refresh: bool = False):
        """Download and cache the Angel scrip master JSON."""
        if not force_refresh and SCRIP_MASTER_CACHE.exists():
            age_hours = (time.time() - SCRIP_MASTER_CACHE.stat().st_mtime) / 3600
            if age_hours < 24:
                with open(SCRIP_MASTER_CACHE) as f:
                    self._scrip_master = json.load(f)
                logger.info(f"Loaded scrip master from cache ({len(self._scrip_master)} instruments)")
                return

        logger.info("Downloading Angel scrip master...")
        SCRIP_MASTER_CACHE.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(SCRIP_MASTER_URL, timeout=60)
        resp.raise_for_status()
        self._scrip_master = resp.json()
        with open(SCRIP_MASTER_CACHE, "w") as f:
            json.dump(self._scrip_master, f)
        logger.info(f"Scrip master saved: {len(self._scrip_master)} instruments")

    def get_token(self, index: str, expiry_dt: datetime, strike: int, option_type: str) -> str | None:
        """
        Look up Angel token for a specific options contract.
        expiry_dt: datetime of expiry
        strike: integer strike price (e.g. 22000)
        option_type: 'CE' or 'PE'
        Returns symboltoken string or None if not found.
        """
        if self._scrip_master is None:
            self.load_scrip_master()

        # Angel strips decimal from strike (stored as strike * 100 in paise sometimes)
        expiry_str = expiry_dt.strftime("%d%b%Y").upper()  # e.g. 27FEB2025

        for inst in self._scrip_master:
            if (
                inst.get("exch_seg") == "NFO"
                and inst.get("instrumenttype") == "OPTIDX"
                and inst.get("name") == index
                and inst.get("expiry") == expiry_str
                and int(float(inst.get("strike", 0))) // 100 == strike  # paise → rupees
                and inst.get("symbol", "").endswith(option_type)
            ):
                return inst["token"]
        return None

    def get_candles_full(
        self,
        token: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> list:
        """
        Fetch candles across multiple chunks (respects max days per request).
        Returns combined list of [timestamp, open, high, low, close, volume].
        """
        max_days = MAX_DAYS[interval]
        all_candles = []
        chunk_start = start

        while chunk_start < end:
            chunk_end = min(chunk_start + timedelta(days=max_days), end)
            acc = self._next_account()
            candles = acc.get_candles(token, interval, chunk_start, chunk_end)
            all_candles.extend(candles)
            chunk_start = chunk_end + timedelta(minutes=1)

        return all_candles
