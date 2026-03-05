"""
shoonya_client.py — Shoonya (Finvasia) NorenAPI wrapper
Used as fallback when Angel accounts are rate-limited or return missing data.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import pyotp
from NorenRestApiPy.NorenApi import NorenApi

logger = logging.getLogger(__name__)

# Shoonya uses integer interval in minutes
INTERVAL_MAP = {
    "1min":  1,
    "5min":  5,
    "15min": 15,
}

# Conservative chunk size (Shoonya not officially documented; 60 days works reliably)
MAX_CHUNK_DAYS = 60
RATE_LIMIT_SLEEP = 0.15  # 10 req/sec → 0.1s; use 0.15 for safety


class ShoonyaClient:
    """Shoonya NorenAPI client — fallback data source."""

    def __init__(
        self,
        user_id: str,
        password: str,
        api_key: str,
        vendor_code: str,
        imei: str,
        totp_secret: str,
    ):
        self.user_id = user_id
        self.password = password
        self.api_key = api_key
        self.vendor_code = vendor_code
        self.imei = imei
        self.totp_secret = totp_secret
        self.api = NorenApi(
            host="https://api.shoonya.com/NorenWClientTP/",
            websocket="wss://api.shoonya.com/NorenWSTP/",
        )
        self._last_request_time = 0.0

    def login(self):
        totp = pyotp.TOTP(self.totp_secret).now()
        ret = self.api.login(
            userid=self.user_id,
            password=self.password,
            twoFA=totp,
            vendor_code=self.vendor_code,
            api_secret=self.api_key,
            imei=self.imei,
        )
        if ret is None or ret.get("stat") != "Ok":
            raise RuntimeError(f"Shoonya login failed: {ret}")
        logger.info(f"Logged in Shoonya account: {self.user_id}")

    def _throttle(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < RATE_LIMIT_SLEEP:
            time.sleep(RATE_LIMIT_SLEEP - elapsed)
        self._last_request_time = time.time()

    def get_token(self, index: str, expiry_dt: datetime, strike: int, option_type: str) -> Optional[str]:
        """
        Resolve instrument token via searchscrip.
        Format: 'NIFTY 27FEB25 22000 CE'
        """
        expiry_str = expiry_dt.strftime("%d%b%y").upper()  # e.g. 27FEB25
        search_text = f"{index} {expiry_str} {strike} {option_type}"
        self._throttle()
        try:
            ret = self.api.searchscrip(exchange="NFO", searchtext=search_text)
            if ret and ret.get("stat") == "Ok" and ret.get("values"):
                # Return token of first matching result
                return ret["values"][0]["token"]
        except Exception as e:
            logger.warning(f"Shoonya searchscrip failed for {search_text}: {e}")
        return None

    def _fetch_chunk(self, token: str, interval: str, from_dt: datetime, to_dt: datetime) -> list:
        """Fetch one chunk of candles. Returns list of raw dicts from Shoonya."""
        self._throttle()
        try:
            ret = self.api.get_time_price_series(
                exchange="NFO",
                token=token,
                starttime=from_dt.timestamp(),
                endtime=to_dt.timestamp(),
                interval=INTERVAL_MAP[interval],
            )
            if ret and isinstance(ret, list):
                return ret
        except Exception as e:
            logger.warning(f"Shoonya get_time_price_series error: {e}")
        return []

    def get_candles_full(
        self,
        token: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> list:
        """
        Fetch candles in 60-day chunks.
        Returns combined list of raw Shoonya candle dicts.
        Each dict has keys: time, into, inth, intl, intc, intv (open/high/low/close/vol)
        """
        all_candles = []
        chunk_start = start

        while chunk_start < end:
            chunk_end = min(chunk_start + timedelta(days=MAX_CHUNK_DAYS), end)
            candles = self._fetch_chunk(token, interval, chunk_start, chunk_end)
            all_candles.extend(candles)
            chunk_start = chunk_end + timedelta(minutes=1)

        return all_candles

    @staticmethod
    def normalize_candles(raw: list) -> list:
        """
        Convert Shoonya raw candle dicts to standard format:
        [timestamp_str, open, high, low, close, volume]
        Compatible with Angel candle format.
        """
        normalized = []
        for c in raw:
            try:
                ts = datetime.fromtimestamp(float(c["time"])).strftime("%Y-%m-%dT%H:%M:%S+05:30")
                normalized.append([
                    ts,
                    float(c.get("into", 0)),
                    float(c.get("inth", 0)),
                    float(c.get("intl", 0)),
                    float(c.get("intc", 0)),
                    int(float(c.get("intv", 0))),
                ])
            except Exception:
                continue
        return normalized
