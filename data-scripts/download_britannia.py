#!/usr/bin/env python3
"""
Download historical data for BRITANNIA stock only.
"""

import os
import sys
import time
from pathlib import Path
from datetime import date, timedelta

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
from dhan_client import DhanClient

# ── Configuration ─────────────────────────────────────────────────────────────

SYMBOL = "BRITANNIA"
DHAN_SYMBOL = "BRITANNIA"  # May need to adjust based on mapping
START_DATE = date(2015, 1, 1)
END_DATE = date.today()
CHUNK_DAYS = 365

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "candles" / "NIFTY500" / SYMBOL
OUTPUT_FILE = OUTPUT_DIR / "1D.parquet"

SCHEMA = pa.schema([
    ("time",   pa.timestamp("s", tz="Asia/Kolkata")),
    ("open",   pa.float32()),
    ("high",   pa.float32()),
    ("low",    pa.float32()),
    ("close",  pa.float32()),
    ("volume", pa.int64()),
])

# ── Helpers ───────────────────────────────────────────────────────────────────

def date_chunks(start: date, end: date, chunk_days: int):
    """Generate date ranges in chunks."""
    cur = start
    while cur <= end:
        yield cur, min(cur + timedelta(days=chunk_days - 1), end)
        cur += timedelta(days=chunk_days)

def candles_to_df(raw: list) -> pd.DataFrame:
    """Convert raw API response to DataFrame."""
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw)[["time", "open", "high", "low", "close", "volume"]]
    df["time"] = pd.to_datetime(df["time"], utc=False).dt.tz_localize(
        None).dt.tz_localize("Asia/Kolkata")
    df["time"] = df["time"].dt.normalize()
    return df.drop_duplicates("time").sort_values("time").reset_index(drop=True)

def merge_and_save(new_df: pd.DataFrame, path: Path):
    """Merge new data with existing and save to parquet."""
    existing = pd.DataFrame()
    if path.exists():
        try:
            existing = pd.read_parquet(path)
        except Exception:
            pass
    
    if not existing.empty:
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

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from datetime import timedelta
    
    print(f"🚀 Downloading historical data for {SYMBOL}...")
    
    # Load Dhan credentials
    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
    
    client_id = os.environ.get("DHAN_CLIENT_ID", "").strip()
    access_token = os.environ.get("DHAN_ACCESS_TOKEN", "").strip()
    
    if not client_id or not access_token:
        print("❌ Error: DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN not set in .env")
        sys.exit(1)
    
    client = DhanClient(client_id, access_token)
    
    if not client.verify_connection():
        print("❌ Error: Failed to connect to Dhan API")
        sys.exit(1)
    
    print("✅ Connected to Dhan API")
    
    # Fetch data in chunks
    all_candles = []
    
    for chunk_start, chunk_end in date_chunks(START_DATE, END_DATE, CHUNK_DAYS):
        print(f"  📥 Fetching {chunk_start} to {chunk_end}...")
        
        try:
            candles = client.get_historical_daily_candles(
                security_id=DHAN_SYMBOL,
                exchange_segment="NSE_EQ",
                instrument="EQUITY",
                from_date=chunk_start.strftime("%Y-%m-%d"),
                to_date=chunk_end.strftime("%Y-%m-%d"),
                expiry_code=0
            )
            
            if candles:
                all_candles.extend(candles)
                print(f"     Got {len(candles)} candles")
            else:
                print(f"     No data returned")
                
        except Exception as e:
            print(f"     ❌ Error: {e}")
        
        # Rate limit delay
        time.sleep(0.5)
    
    if all_candles:
        df = candles_to_df(all_candles)
        total = merge_and_save(df, OUTPUT_FILE)
        print(f"\n✅ Successfully saved {total} candles to {OUTPUT_FILE}")
        print(f"   Date range: {df['time'].min()} to {df['time'].max()}")
    else:
        print("\n❌ No data retrieved for BRITANNIA")
