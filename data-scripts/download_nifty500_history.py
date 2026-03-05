"""
download_nifty500_history.py — Download NIFTY 500 Historical Equity Data

Fetches intraday OHLCV for 500 stocks from Dhan API.
Saves to data/candles/NIFTY500/{SYMBOL}/{interval}.parquet

Usage:
  python download_nifty500_history.py
  python download_nifty500_history.py --intervals 15min 1D
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
sys.path.insert(0, str(Path(__file__).parent))
from dhan_client import DhanClient

BASE_DIR   = Path(__file__).parent.parent / "data" / "candles" / "NIFTY500"
MAPPING    = Path(__file__).parent / "nifty500_dhan_mapping.json"
CHUNK_DAYS = 85

# NIFTY 500 Dhan data safely available from Jan 2020
DEFAULT_START = date(2020, 1, 1)
INTERVALS     = ["15min", "5min"]  # 1D throws DH-905 errors on Dhan's intraday endpoint

SCHEMA = pa.schema([
    ("time",   pa.timestamp("s", tz="Asia/Kolkata")),
    ("open",   pa.float32()),
    ("high",   pa.float32()),
    ("low",    pa.float32()),
    ("close",  pa.float32()),
    ("volume", pa.int64()),
])

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(BASE_DIR.parent.parent / "logs" / "nifty500_download.log"
                            if (BASE_DIR.parent.parent / "logs").exists()
                            else "/tmp/nifty500_download.log"),
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
    
    # Filter market hours for intraday
    t = df["time"]
    if t.dt.hour.max() > 0:  # Intraday
        df = df[
            ((t.dt.hour > 9) | ((t.dt.hour == 9) & (t.dt.minute >= 15))) &
            ((t.dt.hour < 15) | ((t.dt.hour == 15) & (t.dt.minute <= 30)))
        ]
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
    return expected > 0 and (present / expected) >= 0.80


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--start", default=str(DEFAULT_START))
    p.add_argument("--end", default=str(date.today()))
    p.add_argument("--intervals", nargs="+", default=INTERVALS)
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
    log.info(f"  NIFTY 500 Equity Downloader")
    log.info(f"  Stocks    : {len(symbols)}")
    log.info(f"  Range     : {start} → {end}")
    log.info("=" * 60)

    for i, sym in enumerate(symbols, 1):
        sec_id = mapping[sym]
        log.info(f"\n[{i}/{len(symbols)}] Processing {sym} (ID: {sec_id})")

        for interval in args.intervals:
            out_path = BASE_DIR / sym / f"{interval}.parquet"
            total_new = 0

            # Dhan Daily interval needs 'D' as the interval string.
            # CRITICAL: Even for Daily data, Dhan /intraday endpoint limits queries to 90 days max!
            interval_str = "D" if interval == "1D" else interval
            chunks = list(date_chunks(start, end, CHUNK_DAYS))

            for j, (cs, ce) in enumerate(chunks, 1):
                if not args.force and already_covered(out_path, cs, ce):
                    continue

                raw = client.get_intraday_candles(
                    security_id=sec_id,
                    exchange_segment="NSE_EQ",
                    instrument="EQUITY",
                    interval=interval_str,
                    from_datetime=f"{cs} 09:00:00",
                    to_datetime=f"{ce} 16:00:00",
                )
                
                time.sleep(1.0)

                if not raw: continue

                df = candles_to_df(raw)
                if df.empty: continue

                total = merge_and_save(df, out_path)
                total_new += len(df)

            if total_new > 0:
                log.info(f"  ↳ {interval}: {total_new:,} new rows saved.")
            else:
                log.info(f"  ↳ {interval}: fully up-to-date / no new data.")

if __name__ == "__main__":
    main()
