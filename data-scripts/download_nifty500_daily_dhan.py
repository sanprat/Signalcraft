#!/usr/bin/env python3
"""
download_nifty500_daily_dhan.py — Download NIFTY 500 Daily Data via Dhan API

Fetches 1-Day (1D) historical data for 500 stocks from Dhan API iteratively
using 1-year chunks from Jan 1, 2015 to present, avoiding DH-905 and rate limits.
Saves to data/candles/NIFTY500/{SYMBOL}/1D.parquet
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
from dhan_client import DhanClient

BASE_DIR   = Path(__file__).parent.parent / "data" / "candles" / "NIFTY500"
MAPPING    = Path(__file__).parent / "nifty500_dhan_mapping.json"
CHUNK_DAYS = 365 # Safe bounds for historical daily endpoint

# We try pulling backwards up to Jan 2015 for 11 years history.
DEFAULT_START = date(2015, 1, 1)

SCHEMA = pa.schema([
    ("time",   pa.timestamp("s", tz="Asia/Kolkata")),
    ("open",   pa.float32()),
    ("high",   pa.float32()),
    ("low",    pa.float32()),
    ("close",  pa.float32()),
    ("volume", pa.int64()),
])

log_file = BASE_DIR.parent.parent / "logs" / "nifty500_daily_dhan.log"
log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file),
    ]
)
log = logging.getLogger(__name__)

def date_chunks(start: date, end: date, chunk_days: int):
    cur = start
    while cur <= end:
        yield cur, min(cur + timedelta(days=chunk_days - 1), end)
        cur += timedelta(days=chunk_days)

def candles_to_df(raw: list) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw)[["time", "open", "high", "low", "close", "volume"]]
    df["time"] = pd.to_datetime(df["time"], utc=False).dt.tz_localize(
        None).dt.tz_localize("Asia/Kolkata")
    
    # Intraday filter normally filters specific market hours,
    # but since this is 1D, we just normalize it to midnight or drop duplicates.
    df["time"] = df["time"].dt.normalize()
    return df.drop_duplicates("time").sort_values("time").reset_index(drop=True)

def load_existing(path: Path) -> pd.DataFrame:
    if path.exists():
        try:
            return pd.read_parquet(path)
        except Exception:
            pass
    return pd.DataFrame()

def merge_and_save(new_df: pd.DataFrame, path: Path):
    existing = load_existing(path)
    if not existing.empty:
        # Standardize existing to midnight start boundary in case it was written differently
        existing["time"] = existing["time"].dt.normalize()
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    combined = (combined
                .drop_duplicates("time")
                .sort_values("time")
                .reset_index(drop=True))

    combined["time"]   = combined["time"].astype("datetime64[s, Asia/Kolkata]")
    combined["open"]   = combined["open"].astype("float32")
    combined["high"]   = combined["high"].astype("float32")
    combined["low"]    = combined["low"].astype("float32")
    combined["close"]  = combined["close"].astype("float32")
    combined["volume"] = combined["volume"].astype("int64")

    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(combined, schema=SCHEMA, preserve_index=False)
    pq.write_table(table, path, compression="lz4")
    return len(combined)

def already_covered(path: Path, start: date, end: date) -> bool:
    df = load_existing(path)
    if df.empty: return False
    existing_dates = set(df["time"].dt.date)
    chunk_dates = pd.bdate_range(str(start), str(end))
    expected = len(chunk_dates)
    present  = sum(1 for d in chunk_dates if d.date() in existing_dates)
    # If 80% of business days are present, assume data exists
    return expected > 0 and (present / expected) >= 0.80

def get_historical_daily(client: DhanClient, sec_id: str, start: date, end: date) -> list:
    """Uses daily chart endpoint properly."""
    return client.get_historical_daily_candles(
        security_id=sec_id,
        exchange_segment="NSE_EQ",
        instrument="EQUITY",
        from_date=start.strftime("%Y-%m-%d"),
        to_date=end.strftime("%Y-%m-%d"),
        expiry_code=0
    )

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--start", default=str(DEFAULT_START))
    p.add_argument("--end", default=str(date.today()))
    p.add_argument("--force", action="store_true")
    p.add_argument("--limit", type=int, help="Only process first N stocks (for testing)")
    return p.parse_args()

def main():
    args = parse_args()
    start = date.fromisoformat(args.start)
    end   = date.fromisoformat(args.end)

    client = DhanClient(
        os.environ["DHAN_CLIENT_ID"].strip(),
        os.environ["DHAN_ACCESS_TOKEN"].strip(),
    )
    if not client.verify_connection():
        log.error("Dhan connection failed.")
        sys.exit(1)

    if not MAPPING.exists():
        log.error(f"Missing {MAPPING}")
        sys.exit(1)

    with open(MAPPING) as f:
        mapping = json.load(f)

    symbols = list(mapping.keys())
    if args.limit:
        symbols = symbols[:args.limit]

    log.info("=" * 60)
    log.info(f"  NIFTY 500 Equity Downloader (1D / Daily)")
    log.info(f"  Stocks    : {len(symbols)}")
    log.info(f"  Range     : {start} → {end}")
    log.info("=" * 60)

    for i, sym in enumerate(symbols, 1):
        sec_id = mapping[sym]
        log.info(f"\n[{i}/{len(symbols)}] 1D Processing {sym} (ID: {sec_id})")

        out_path = BASE_DIR / sym / "1D.parquet"
        total_new = 0

        chunks = list(date_chunks(start, end, CHUNK_DAYS))

        for j, (cs, ce) in enumerate(chunks, 1):
            if not args.force and already_covered(out_path, cs, ce):
                continue
            
            raw = get_historical_daily(client, sec_id, cs, ce)
            
            # Safe sleep boundary to prevent HTTP 429 errors from Dhan API
            time.sleep(1.2)

            if not raw: continue

            df = candles_to_df(raw)
            if df.empty: continue

            total = merge_and_save(df, out_path)
            total_new += len(df)

        if total_new > 0:
            log.info(f"  ↳ 1D: {total_new:,} new rows saved.")
        else:
            log.info(f"  ↳ 1D: fully up-to-date / no new data.")

if __name__ == "__main__":
    main()
