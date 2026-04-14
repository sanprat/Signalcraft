"""
parquet_writer.py — Save OHLCV candles to Parquet files with deduplication.
Folder structure:
  data/candles/{INDEX}/{CE|PE}/{1min|5min|15min}/{EXPIRY_DATE}_{STRIKE}.parquet
Underlying spot index:
  data/underlying/{INDEX}/{1min|5min|15min}.parquet

Checkpoint tracking in:
  data/download_progress.json
"""

import json
import logging
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

BASE_DIR = Path("data")
PROGRESS_FILE = BASE_DIR / "download_progress.json"

SCHEMA = pa.schema(
    [
        ("time", pa.timestamp("s", tz="Asia/Kolkata")),
        ("open", pa.float32()),
        ("high", pa.float32()),
        ("low", pa.float32()),
        ("close", pa.float32()),
        ("volume", pa.int64()),
        ("oi", pa.float64()),
        ("iv", pa.float32()),
        ("spot", pa.float32()),
    ]
)

OPTIONS_SCHEMA = SCHEMA  # Canonical schema for options with oi, iv, spot


def _candles_path(
    index: str, option_type: str, interval: str, expiry: date, strike: int
) -> Path:
    filename = f"{expiry.strftime('%Y%m%d')}_{strike}.parquet"
    return BASE_DIR / "candles" / index / option_type / interval / filename


def _underlying_path(index: str, interval: str) -> Path:
    return BASE_DIR / "underlying" / index / f"{interval}.parquet"


def _raw_to_df(raw_candles: list, include_oi_iv_spot: bool = True) -> pd.DataFrame:
    """
    Convert raw candle list to DataFrame.
    Handles dict format with time, open, high, low, close, volume, oi, iv, spot.
    """
    if not raw_candles:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

    rows = []
    for c in raw_candles:
        try:
            ts = (
                pd.Timestamp(c["time"]).tz_localize("Asia/Kolkata")
                if pd.Timestamp(c["time"]).tzinfo is None
                else pd.Timestamp(c["time"]).tz_convert("Asia/Kolkata")
            )
            row = {
                "time": ts,
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "volume": int(c["volume"]),
            }
            if include_oi_iv_spot:
                row["oi"] = float(c.get("oi", 0))
                row["iv"] = float(c.get("iv", 0))
                row["spot"] = float(c.get("spot", 0))
            rows.append(row)
        except Exception as e:
            logger.debug(f"Skipping bad candle {c}: {e}")

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Keep only market hours: 9:15 to 15:30 IST
    df = df[
        (df["time"].dt.hour > 9)
        | ((df["time"].dt.hour == 9) & (df["time"].dt.minute >= 15))
    ]
    df = df[
        (df["time"].dt.hour < 15)
        | ((df["time"].dt.hour == 15) & (df["time"].dt.minute <= 30))
    ]
    return (
        df.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)
    )


def save_candles(
    raw_candles: list,
    index: str,
    option_type: str,
    interval: str,
    expiry: date,
    strike: int,
) -> int:
    """
    Save candles for a specific options contract.
    Merges with existing file if present (deduplication).
    Returns number of new rows written.
    """
    path = _candles_path(index, option_type, interval, expiry, strike)
    return _write_parquet(raw_candles, path)


def save_underlying(raw_candles: list, index: str, interval: str) -> int:
    """Save underlying spot index candles."""
    path = _underlying_path(index, interval)
    return _write_parquet(raw_candles, path)


def _write_parquet(raw_candles: list, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_df = _raw_to_df(raw_candles)

    if new_df.empty:
        return 0

    # Merge with existing if file present
    if path.exists():
        try:
            existing = pd.read_parquet(path)
            combined = pd.concat([existing, new_df], ignore_index=True)
            combined = (
                combined.drop_duplicates(subset=["time"])
                .sort_values("time")
                .reset_index(drop=True)
            )
        except Exception:
            combined = new_df
    else:
        combined = new_df

    table = pa.Table.from_pandas(combined, schema=SCHEMA, preserve_index=False)
    pq.write_table(table, path, compression="lz4")
    return len(combined)


# ─── Progress / checkpoint tracking ──────────────────────────────────────────


def _load_progress() -> set:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return set(json.load(f))
    return set()


def _save_progress(done: set):
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "w") as f:
        json.dump(sorted(done), f)


def job_key(
    index: str, expiry: date, strike: int, option_type: str, interval: str
) -> str:
    return f"{index}_{expiry}_{strike}_{option_type}_{interval}"


def load_completed_jobs() -> set:
    return _load_progress()


def mark_job_done(
    done: set, index: str, expiry: date, strike: int, option_type: str, interval: str
):
    done.add(job_key(index, expiry, strike, option_type, interval))
    _save_progress(done)
