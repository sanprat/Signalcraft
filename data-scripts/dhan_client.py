"""
dhan_client.py — Dhan HQ API wrapper for expired options historical data.
Built from official docs: https://dhanhq.co/docs/v2/expired-options-data/

Key facts from the docs:
- Endpoint: POST /v2/charts/rollingoption
- requiredData is MANDATORY — must specify what fields to return
- Response is nested under data.ce or data.pe (not flat)
- strike in requiredData returns the ACTUAL absolute strike price per candle ✅
- expiryCode: 1 = nearest expired, 2 = second nearest, etc.
- expiryFlag: "WEEK" or "MONTH"
- Max 30 days per request, up to 5 years of history
- Auth: access-token header (pre-generated JWT, no TOTP needed)

Intraday active contracts: POST /v2/charts/intraday (up to 90 days/call)
"""

import logging
import time
from datetime import datetime, timedelta, date
from typing import Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.dhan.co/v2"

INTERVAL_MAP = {
    "1min":  "1",
    "5min":  "5",
    "15min": "15",
}

MAX_CHUNK_DAYS      = 30    # Dhan limit for rollingoption
MAX_INTRADAY_DAYS   = 88    # Dhan limit for intraday (we use 88 to be safe)
RATE_LIMIT_SLEEP    = 1.1   # 1 req/sec

# Underlying security IDs (from Dhan instrument master — IDX_I segment)
SECURITY_IDS = {
    "NIFTY":      13,
    "BANKNIFTY":  25,
    "FINNIFTY":   27,
    "GIFTNIFTY": 5024,  # GIFT NIFTY (NSE International Exchange - GIFT City)
}

OPTION_TYPE_MAP = {
    "CE": "CALL",
    "PE": "PUT",
}

REQUIRED_DATA = ["open", "high", "low", "close", "volume", "strike"]


def strike_label(offset: int) -> str:
    """Convert integer offset to Dhan ATM label: 0→'ATM', 1→'ATM+1', -2→'ATM-2'"""
    if offset == 0:
        return "ATM"
    elif offset > 0:
        return f"ATM+{offset}"
    else:
        return f"ATM{offset}"


class DhanClient:
    """Dhan HQ API client — expired options + active intraday data."""

    def __init__(self, client_id: str, access_token: str):
        self.client_id    = client_id.strip()
        self.access_token = access_token.strip()
        self.session = requests.Session()
        self.session.headers.update({
            "access-token": self.access_token,
            "client-id":    self.client_id,
            "Content-Type": "application/json",
            "Accept":       "application/json",
        })
        self._last_request_time = 0.0

    def _throttle(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < RATE_LIMIT_SLEEP:
            time.sleep(RATE_LIMIT_SLEEP - elapsed)
        self._last_request_time = time.time()

    def verify_connection(self) -> bool:
        """Test connection using fund limit endpoint."""
        try:
            resp = self.session.get(f"{BASE_URL}/fundlimit", timeout=10)
            if resp.status_code == 200:
                logger.info("Dhan connection verified ✓")
                return True
            logger.error(f"Dhan auth failed: {resp.status_code} — {resp.text[:300]}")
            return False
        except Exception as e:
            logger.error(f"Dhan connection error: {e}")
            return False

    def get_expired_options_candles(
        self,
        index: str,
        strike_offset: int,     # -10 to +10 relative to ATM
        option_type: str,        # "CE" or "PUT"
        expiry_flag: str,        # "WEEK" or "MONTH"
        expiry_code: int,        # 1=nearest expired, 2=second nearest, etc.
        from_date: date,
        to_date: date,
        interval: str,
    ) -> list:
        """
        Fetch expired option candles for one 30-day chunk (per Dhan limit).
        Returns list of [timestamp_str, open, high, low, close, volume, actual_strike].
        The 'strike' field returns the ACTUAL absolute strike price for each candle.
        """
        self._throttle()

        payload = {
            "exchangeSegment": "NSE_FNO",
            "instrument":      "OPTIDX",
            "securityId":      SECURITY_IDS[index],
            "expiryFlag":      expiry_flag,
            "expiryCode":      expiry_code,
            "strike":          strike_label(strike_offset),
            "drvOptionType":   OPTION_TYPE_MAP[option_type],
            "interval":        INTERVAL_MAP[interval],
            "requiredData":    REQUIRED_DATA,   # MANDATORY per docs
            "fromDate":        from_date.strftime("%Y-%m-%d"),
            "toDate":          to_date.strftime("%Y-%m-%d"),
        }

        try:
            resp = self.session.post(
                f"{BASE_URL}/charts/rollingoption",
                json=payload,
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()

            # Response: {"data": {"ce": {...}, "pe": null}}
            inner = data.get("data", {})
            side_key = "ce" if option_type == "CE" else "pe"
            side = inner.get(side_key)

            if not side or not side.get("timestamp"):
                return []

            timestamps = side["timestamp"]
            opens      = side.get("open",   [0] * len(timestamps))
            highs      = side.get("high",   [0] * len(timestamps))
            lows       = side.get("low",    [0] * len(timestamps))
            closes     = side.get("close",  [0] * len(timestamps))
            volumes    = side.get("volume", [0] * len(timestamps))
            strikes    = side.get("strike", [0] * len(timestamps))

            normalized = []
            for i, ts in enumerate(timestamps):
                dt_str = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%dT%H:%M:%S+05:30")
                normalized.append({
                    "time":   dt_str,
                    "open":   float(opens[i]),
                    "high":   float(highs[i]),
                    "low":    float(lows[i]),
                    "close":  float(closes[i]),
                    "volume": int(float(volumes[i])),
                    "strike": float(strikes[i]),  # actual absolute strike ✅
                })
            return normalized

        except requests.exceptions.HTTPError as e:
            logger.warning(
                f"Dhan HTTP {e.response.status_code} for "
                f"{index} {strike_label(strike_offset)} {option_type} "
                f"expCode={expiry_code}: {e.response.text[:200]}"
            )
        except Exception as e:
            logger.warning(f"Dhan request error: {e}")
        return []

    def get_expired_options_full(
        self,
        index: str,
        strike_offset: int,
        option_type: str,
        expiry_flag: str,
        expiry_code: int,
        start: date,
        end: date,
        interval: str,
    ) -> list:
        """Fetch across multiple 30-day chunks and combine."""
        all_candles = []
        chunk_start = start
        while chunk_start <= end:
            chunk_end = min(chunk_start + timedelta(days=MAX_CHUNK_DAYS - 1), end)
            candles = self.get_expired_options_candles(
                index, strike_offset, option_type,
                expiry_flag, expiry_code,
                chunk_start, chunk_end, interval,
            )
            all_candles.extend(candles)
            chunk_start = chunk_end + timedelta(days=1)
        return all_candles

    def get_intraday_candles(
        self,
        security_id: str,
        exchange_segment: str,
        instrument: str,
        interval: str,
        from_datetime: str,     # "YYYY-MM-DD HH:MM:SS"
        to_datetime: str,
        oi: bool = False,
    ) -> list:
        """
        Fetch intraday candles for active/current instruments.
        Endpoint: POST /v2/charts/intraday
        Max 90 days per request.
        """
        self._throttle()
        payload = {
            "securityId":       security_id,
            "exchangeSegment":  exchange_segment,
            "instrument":       instrument,
            "interval":         INTERVAL_MAP.get(interval, interval),
            "oi":               oi,
            "fromDate":         from_datetime,
            "toDate":           to_datetime,
        }
        try:
            resp = self.session.post(
                f"{BASE_URL}/charts/intraday",
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            timestamps = data.get("timestamp", [])
            opens      = data.get("open",   [])
            highs      = data.get("high",   [])
            lows       = data.get("low",    [])
            closes     = data.get("close",  [])
            volumes    = data.get("volume", [])
            normalized = []
            for i, ts in enumerate(timestamps):
                dt_str = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%dT%H:%M:%S+05:30")
                normalized.append({
                    "time":   dt_str,
                    "open":   float(opens[i]),
                    "high":   float(highs[i]),
                    "low":    float(lows[i]),
                    "close":  float(closes[i]),
                    "volume": int(float(volumes[i])),
                    "strike": 0,
                })
            return normalized
        except requests.exceptions.HTTPError as e:
            logger.warning(f"Dhan intraday HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            logger.warning(f"Dhan intraday error: {e}")
        return []

    def get_historical_daily_candles(
        self,
        security_id: str,
        exchange_segment: str,
        instrument: str,
        from_date: str,         # "YYYY-MM-DD"
        to_date: str,           # "YYYY-MM-DD"
        expiry_code: int = 0
    ) -> list:
        """
        Fetch full daily (1D) historical data using the explicit daily endpoint.
        Endpoint: POST /v2/charts/historical
        Unlike intraday, this can fetch much longer ranges per request.
        """
        self._throttle()
        payload = {
            "securityId":       security_id,
            "exchangeSegment":  exchange_segment,
            "instrument":       instrument,
            "expiryCode":       expiry_code,
            "fromDate":         from_date,
            "toDate":           to_date,
        }
        try:
            resp = self.session.post(
                f"{BASE_URL}/charts/historical",
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            # Depending on if data holds array properly or if nested
            # Often data has dict of arrays format: "open": [...], "high": [...] inside "data" key
            inner = data.get("data", data)
            
            timestamps = inner.get("start_Time", inner.get("timestamp", []))
            opens      = inner.get("open",   [])
            highs      = inner.get("high",   [])
            lows       = inner.get("low",    [])
            closes     = inner.get("close",  [])
            volumes    = inner.get("volume", [])
            normalized = []
            
            for i, ts in enumerate(timestamps):
                # Need to handle if ts is given as date string or timestamp
                if isinstance(ts, (int, float)) or (isinstance(ts, str) and ts.isdigit()):
                    dt_str = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%dT00:00:00+05:30")
                else: 
                    # If returned as string like YYYY-MM-DD
                    dt_str = f"{ts}T00:00:00+05:30"

                normalized.append({
                    "time":   dt_str,
                    "open":   float(opens[i]),
                    "high":   float(highs[i]),
                    "low":    float(lows[i]),
                    "close":  float(closes[i]),
                    "volume": int(float(volumes[i])) if volumes and i < len(volumes) else 0,
                    "strike": 0,
                })
            return normalized
        except requests.exceptions.HTTPError as e:
            logger.warning(f"Dhan historical HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            logger.warning(f"Dhan historical error: {e}")
        return []
