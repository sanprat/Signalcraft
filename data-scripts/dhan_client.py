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
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.dhan.co/v2"

INTERVAL_MAP = {
    "1min": "1",
    "5min": "5",
    "15min": "15",
}

MAX_CHUNK_DAYS = 30  # Dhan limit for rollingoption
MAX_INTRADAY_DAYS = 88  # Dhan limit for intraday (we use 88 to be safe)
RATE_LIMIT_SLEEP = 1.1  # 1 req/sec

# Underlying security IDs (from Dhan instrument master — IDX_I segment)
SECURITY_IDS = {
    "NIFTY": 13,
    "BANKNIFTY": 25,
    "FINNIFTY": 27,
    "GIFTNIFTY": 5024,  # GIFT NIFTY (NSE International Exchange - GIFT City)
}

OPTION_TYPE_MAP = {
    "CE": "CALL",
    "PE": "PUT",
}

REQUIRED_DATA = ["open", "high", "low", "close", "volume", "oi", "iv", "spot", "strike"]
IST = ZoneInfo("Asia/Kolkata")


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
        self.client_id = client_id.strip()
        self.access_token = access_token.strip()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "access-token": self.access_token,
                "client-id": self.client_id,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        self._last_request_time = 0.0

    def _throttle(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < RATE_LIMIT_SLEEP:
            time.sleep(RATE_LIMIT_SLEEP - elapsed)
        self._last_request_time = time.time()

    @staticmethod
    def _epoch_to_ist_iso(ts: int | str) -> str:
        """
        Convert Dhan epoch seconds to an explicit Asia/Kolkata ISO timestamp.

        This must not depend on the host timezone. On a UTC VPS, using
        datetime.fromtimestamp(ts) would produce UTC wall-clock values and
        incorrectly label them as IST later in the pipeline.
        """
        return (
            datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(IST).isoformat()
        )

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
        strike_offset: int,  # -10 to +10 relative to ATM
        option_type: str,  # "CE" or "PUT"
        expiry_flag: str,  # "WEEK" or "MONTH"
        expiry_code: int,  # 1=nearest expired, 2=second nearest, etc.
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
            "instrument": "OPTIDX",
            "securityId": SECURITY_IDS[index],
            "expiryFlag": expiry_flag,
            "strike": strike_label(strike_offset),
            "drvOptionType": OPTION_TYPE_MAP[option_type],
            "interval": INTERVAL_MAP[interval],
            "requiredData": REQUIRED_DATA,  # MANDATORY per docs
            "fromDate": from_date.strftime("%Y-%m-%d"),
            "toDate": to_date.strftime("%Y-%m-%d"),
        }

        # Dhan API throws DH-905 if expiryCode is 0. Docs say it's 1-indexed for expired.
        # So we omit it for live options (0) to get current expiry.
        if expiry_code > 0:
            payload["expiryCode"] = expiry_code

        try:
            resp = self.session.post(
                f"{BASE_URL}/charts/rollingoption", json=payload, timeout=30
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
            opens = side.get("open", [0] * len(timestamps))
            highs = side.get("high", [0] * len(timestamps))
            lows = side.get("low", [0] * len(timestamps))
            closes = side.get("close", [0] * len(timestamps))
            volumes = side.get("volume", [0] * len(timestamps))
            strikes = side.get("strike", [0] * len(timestamps))
            ois = side.get("oi", [0.0] * len(timestamps))
            ivs = side.get("iv", [0.0] * len(timestamps))
            spots = side.get("spot", [0.0] * len(timestamps))

            normalized = []
            for i, ts in enumerate(timestamps):
                normalized.append(
                    {
                        "time": self._epoch_to_ist_iso(ts),
                        "open": float(opens[i]),
                        "high": float(highs[i]),
                        "low": float(lows[i]),
                        "close": float(closes[i]),
                        "volume": int(float(volumes[i])),
                        "strike": float(strikes[i]),
                        "oi": float(ois[i]),
                        "iv": float(ivs[i]),
                        "spot": float(spots[i]),
                    }
                )
            return normalized

        except requests.exceptions.HTTPError as e:
            if (
                e.response.status_code == 400
                and "DH-905" in e.response.text
                and expiry_code == 0
            ):
                # Dhan API recently patched their loophole that allowed fetching live (unexpired)
                # rolling options by omitting expiryCode. We silently fail here and rely on the
                # expired options backfiller.
                pass
            else:
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
                index,
                strike_offset,
                option_type,
                expiry_flag,
                expiry_code,
                chunk_start,
                chunk_end,
                interval,
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
        from_datetime: str,  # "YYYY-MM-DD HH:MM:SS"
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
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "instrument": instrument,
            "interval": INTERVAL_MAP.get(interval, interval),
            "oi": oi,
            "fromDate": from_datetime,
            "toDate": to_datetime,
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
            opens = data.get("open", [])
            highs = data.get("high", [])
            lows = data.get("low", [])
            closes = data.get("close", [])
            volumes = data.get("volume", [])
            normalized = []
            for i, ts in enumerate(timestamps):
                normalized.append(
                    {
                        "time": self._epoch_to_ist_iso(ts),
                        "open": float(opens[i]),
                        "high": float(highs[i]),
                        "low": float(lows[i]),
                        "close": float(closes[i]),
                        "volume": int(float(volumes[i])),
                        "strike": 0,
                    }
                )
            return normalized
        except requests.exceptions.HTTPError as e:
            logger.warning(
                f"Dhan intraday HTTP {e.response.status_code}: {e.response.text[:200]}"
            )
        except Exception as e:
            logger.warning(f"Dhan intraday error: {e}")
        return []

    def get_historical_daily_candles(
        self,
        security_id: str,
        exchange_segment: str,
        instrument: str,
        from_date: str,  # "YYYY-MM-DD"
        to_date: str,  # "YYYY-MM-DD"
        expiry_code: int = 0,
    ) -> list:
        """
        Fetch full daily (1D) historical data using the explicit daily endpoint.
        Endpoint: POST /v2/charts/historical
        Unlike intraday, this can fetch much longer ranges per request.
        """
        self._throttle()
        payload = {
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "instrument": instrument,
            "expiryCode": expiry_code,
            "fromDate": from_date,
            "toDate": to_date,
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
            opens = inner.get("open", [])
            highs = inner.get("high", [])
            lows = inner.get("low", [])
            closes = inner.get("close", [])
            volumes = inner.get("volume", [])
            normalized = []

            for i, ts in enumerate(timestamps):
                # Need to handle if ts is given as date string or timestamp
                if isinstance(ts, (int, float)) or (
                    isinstance(ts, str) and ts.isdigit()
                ):
                    dt_str = datetime.fromtimestamp(int(ts)).strftime(
                        "%Y-%m-%dT00:00:00+05:30"
                    )
                else:
                    # If returned as string like YYYY-MM-DD
                    dt_str = f"{ts}T00:00:00+05:30"

                normalized.append(
                    {
                        "time": dt_str,
                        "open": float(opens[i]),
                        "high": float(highs[i]),
                        "low": float(lows[i]),
                        "close": float(closes[i]),
                        "volume": int(float(volumes[i]))
                        if volumes and i < len(volumes)
                        else 0,
                        "strike": 0,
                    }
                )
            return normalized
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400 and "DH-905" in e.response.text:
                # Silently fail as this is an expected fallback condition for recent dates
                pass
            else:
                logger.warning(
                    f"Dhan historical HTTP {e.response.status_code}: {e.response.text[:200]}"
                )
        except Exception as e:
            logger.warning(f"Dhan historical error: {e}")
        return []

    def get_expiry_list(self, index: str) -> list:
        """
        Fetch list of active expiries for an index.
        Endpoint: POST /v2/optionchain/expirylist

        Returns list of expiry date strings (YYYY-MM-DD).

        Handles two response shapes:
        - {"data": ["2025-04-24", "2025-05-01"]}
        - {"data": {"expiryDates": ["2025-04-24", "2025-05-01"]}}
        """
        self._throttle()
        payload = {"UnderlyingScrip": SECURITY_IDS[index], "UnderlyingSeg": "IDX_I"}
        try:
            resp = self.session.post(
                f"{BASE_URL}/optionchain/expirylist",
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            resp_json = resp.json()
            expiry_data = resp_json.get("data", [])

            if isinstance(expiry_data, list):
                return expiry_data

            if isinstance(expiry_data, dict):
                return expiry_data.get("expiryDates", [])

            return []
        except requests.exceptions.HTTPError as e:
            logger.warning(
                f"Dhan expirylist HTTP {e.response.status_code}: {e.response.text[:200]}"
            )
        except Exception as e:
            logger.warning(f"Dhan expirylist error: {e}")
        return []

    def _load_instrument_master(self) -> pd.DataFrame:
        """Load Dhan instrument master CSV from cache."""
        master_path = Path(__file__).parent / "dhan_instrument_master.csv"
        if not master_path.exists():
            logger.warning(
                "Instrument master not found, run generate_nifty500_mapping.py first"
            )
            return pd.DataFrame()
        return pd.read_csv(master_path, low_memory=False)

    def resolve_active_weekly_options(
        self,
        index: str,
        expiry_date: str,
        strikes: list[int],
        option_type: str,
    ) -> list[dict]:
        """
        Resolve active option contract metadata for a given expiry and strike range.

        Uses Dhan instrument master CSV to find security IDs for:
          - index (NIFTY, BANKNIFTY, FINNIFTY)
          - expiry_date (YYYY-MM-DD of weekly expiry)
          - option_type (CE/PE)
          - strike (actual strike price)

        Returns list of dicts with:
          - security_id
          - exchange_segment
          - instrument
          - strike
          - option_type
          - expiry_date
        """
        master = self._load_instrument_master()
        if master.empty:
            logger.warning(
                "Cannot resolve active options: instrument master unavailable"
            )
            return []

        expiry_str = pd.to_datetime(expiry_date).strftime("%d-%b-%Y").upper()

        drv_type = "CALL" if option_type == "CE" else "PUT"

        mask = (
            (master["ExchangeSegment"] == "NSE_FNO")
            & (master["Instrument"] == "OPTIDX")
            & (master["DRVUnderlyingScripCode"] == SECURITY_IDS.get(index))
            & (master["OptionType"] == drv_type)
            & (master["ExpiryDate"].str.upper() == expiry_str)
            & (master["StrikePrice"].isin(strikes))
        )

        filtered = master[mask]

        results = []
        for _, row in filtered.iterrows():
            results.append(
                {
                    "security_id": str(row["SecurityId"]),
                    "exchange_segment": "NSE_FNO",
                    "instrument": "OPTIDX",
                    "strike": int(row["StrikePrice"]),
                    "option_type": option_type,
                    "expiry_date": expiry_date,
                }
            )

        logger.info(
            f"Resolved {len(results)} active {option_type} contracts for {index} {expiry_date}"
        )
        return results

    def get_active_option_intraday(
        self,
        security_id: str,
        exchange_segment: str,
        instrument: str,
        interval: str,
        start_dt: str,
        end_dt: str,
        oi: bool = True,
    ) -> list:
        """
        Fetch intraday candles for active (unexpired) option contracts.

        Uses /v2/charts/intraday endpoint which supports active instruments.
        Unlike rolling-option endpoint (which throws DH-905 for expiry_code=0),
        this endpoint works for current-week contracts.

        Note: intraday endpoint may not provide iv and spot. Those fields
        will be absent from returned data rather than fabricated.

        Args:
            security_id: Dhan security ID for the option contract
            exchange_segment: e.g., "NSE_FNO"
            instrument: e.g., "OPTIDX"
            interval: "1", "5", "15" (minutes)
            start_dt: "YYYY-MM-DD HH:MM:SS"
            end_dt: "YYYY-MM-DD HH:MM:SS"
            oi: Whether to include open interest (default True)

        Returns:
            List of candle dicts with time, open, high, low, close, volume, oi (if available)
        """
        self._throttle()

        payload = {
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "instrument": instrument,
            "interval": INTERVAL_MAP.get(interval, interval),
            "oi": oi,
            "fromDate": start_dt,
            "toDate": end_dt,
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
            if not timestamps:
                return []

            opens = data.get("open", [])
            highs = data.get("high", [])
            lows = data.get("low", [])
            closes = data.get("close", [])
            volumes = data.get("volume", [])
            ois = data.get("oi", [])

            normalized = []
            for i, ts in enumerate(timestamps):
                candle = {
                    "time": self._epoch_to_ist_iso(ts),
                    "open": float(opens[i]) if i < len(opens) else 0.0,
                    "high": float(highs[i]) if i < len(highs) else 0.0,
                    "low": float(lows[i]) if i < len(lows) else 0.0,
                    "close": float(closes[i]) if i < len(closes) else 0.0,
                    "volume": int(float(volumes[i])) if i < len(volumes) else 0,
                }
                if ois and i < len(ois):
                    candle["oi"] = float(ois[i])

                normalized.append(candle)

            return normalized

        except requests.exceptions.HTTPError as e:
            logger.warning(
                f"Dhan active option intraday HTTP {e.response.status_code}: {e.response.text[:200]}"
            )
        except Exception as e:
            logger.warning(f"Dhan active option intraday error: {e}")
        return []
