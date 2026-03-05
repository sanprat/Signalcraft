"""
dhan_bulk_loader.py — Download expired options history via Dhan API.

Speed: uses tight per-expiryCode date windows → 1 API call per job (13x faster).
Data quality: Dhan returns actual absolute strike per candle via 'strike' field.

Usage:
  python dhan_bulk_loader.py               # last 1 year (52 expiries)
  python dhan_bulk_loader.py --dry-run     # preview
  python dhan_bulk_loader.py --expiries 26 # last 6 months
"""

import argparse
import logging
import os
import sys
from collections import defaultdict
from datetime import date, timedelta, datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from dhan_client import DhanClient
from parquet_writer import load_completed_jobs, _save_progress

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
Path("data").mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/dhan_errors.log"),
    ]
)
logger = logging.getLogger(__name__)

INDICES   = ["NIFTY", "BANKNIFTY", "FINNIFTY"]
INTERVALS = ["1min", "5min", "15min"]
OFFSETS   = list(range(-10, 11))   # ATM-10 to ATM+10 = 21 strikes
OPT_TYPES = ["CE", "PE"]
BASE_DIR  = Path("data")


def parse_args():
    p = argparse.ArgumentParser(description="Dhan Expired Options Downloader")
    p.add_argument("--start-expiry", type=int, default=1,
                   help="Expiry code to start from (1 = most recent expiry). Use >52 for older years like 2024.")
    p.add_argument("--expiries", type=int, default=52,
                   help="Number of past weekly expiries to fetch (default: 52 ≈ 1 year)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true",
                   help="Re-download even if checkpoint says done")
    p.add_argument("--indices", nargs="+", default=["NIFTY", "BANKNIFTY", "FINNIFTY"],
                   choices=["NIFTY", "BANKNIFTY", "FINNIFTY"],
                   help="Which indices to download (default: all three)")
    return p.parse_args()


# Expiry weekday per index: NIFTY=Thursday(3), BANKNIFTY=Wednesday(2), FINNIFTY=Tuesday(1)
EXPIRY_WEEKDAY = {"NIFTY": 3, "BANKNIFTY": 2, "FINNIFTY": 1}


def expiry_window(expiry_code: int, index: str) -> tuple[date, date]:
    """
    Estimate the date window for a given expiryCode and index.
    Uses the correct expiry weekday: NIFTY=Thursday, BANKNIFTY=Wednesday, FINNIFTY=Tuesday.
    Window = estimated_expiry - 12 days → estimated_expiry + 1 day (fits in 1 Dhan API call).
    """
    today = date.today()
    target_weekday = EXPIRY_WEEKDAY[index]
    days_since = (today.weekday() - target_weekday) % 7
    if days_since == 0:
        days_since = 7
    last_expiry_day  = today - timedelta(days=days_since)
    estimated_expiry = last_expiry_day - timedelta(weeks=expiry_code - 1)
    return estimated_expiry - timedelta(days=12), estimated_expiry + timedelta(days=1)


def save_dhan_candles(candles: list, index: str, option_type: str,
                      interval: str, expiry_code: int) -> int:
    """
    Group candles by their actual absolute strike price (from Dhan response)
    and write each strike's data to a separate Parquet file.
    Returns total number of rows saved.
    """
    if not candles:
        return 0

    by_strike = defaultdict(list)
    for c in candles:
        by_strike[int(c["strike"])].append(c)

    total = 0
    for strike, rows in by_strike.items():
        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["time"]).dt.tz_localize(None)
        df = (df[["time", "open", "high", "low", "close", "volume"]]
              .drop_duplicates(subset=["time"])
              .sort_values("time")
              .reset_index(drop=True))
        df["time"] = df["time"].astype("datetime64[s]")

        out_dir = BASE_DIR / "candles" / index / option_type / interval
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"dhan_ec{expiry_code}_{strike}.parquet"

        if out_path.exists():
            existing = pd.read_parquet(out_path)
            df = (pd.concat([existing, df])
                  .drop_duplicates(subset=["time"])
                  .sort_values("time")
                  .reset_index(drop=True))

        df.to_parquet(out_path, compression="lz4", index=False)
        total += len(df)
    return total


def dhan_key(index, ec, offset, opt, interval):
    return f"dhan_{index}_ec{ec}_ATM{offset:+d}_{opt}_{interval}"


def main():
    args = parse_args()
    expiry_codes   = list(range(args.start_expiry, args.start_expiry + args.expiries))
    active_indices = args.indices
    total_jobs     = len(expiry_codes) * len(active_indices) * len(OFFSETS) * len(OPT_TYPES) * len(INTERVALS)

    if args.dry_run:
        print(f"\n{'='*60}")
        print(f"  DHAN DRY RUN")
        print(f"{'='*60}")
        print(f"  Expiry codes : {args.start_expiry} to {args.start_expiry + args.expiries - 1} (~{args.expiries} weekly expiries)")
        print(f"  Indices      : {', '.join(active_indices)}")
        print(f"  Strikes      : ATM-10 to ATM+10 (21 per expiry)")
        print(f"  Option types : CE + PE")
        print(f"  Intervals    : {', '.join(INTERVALS)}")
        print(f"  TOTAL jobs   : {total_jobs:,}")
        print(f"  Est. time    : {total_jobs/3600:.1f} hrs @ 1 req/sec (tight windows = 1 call/job)")
        print(f"{'='*60}\n")
        return

    client = DhanClient(
        os.environ["DHAN_CLIENT_ID"].strip(),
        os.environ["DHAN_ACCESS_TOKEN"].strip(),
    )
    if not client.verify_connection():
        logger.error("Dhan connection failed — check DHAN_ACCESS_TOKEN in .env")
        sys.exit(1)

    done = load_completed_jobs() if not args.force else set()
    downloaded = skipped = empty = 0

    jobs = [
        {"index": idx, "ec": ec, "offset": off, "opt": opt, "interval": iv}
        for idx in active_indices
        for ec in expiry_codes
        for off in OFFSETS
        for opt in OPT_TYPES
        for iv in INTERVALS
    ]

    for job in tqdm(jobs, desc="Dhan download", unit="job"):
        idx, ec, off, opt, iv = (
            job["index"], job["ec"], job["offset"], job["opt"], job["interval"]
        )
        key = dhan_key(idx, ec, off, opt, iv)

        if key in done:
            skipped += 1
            continue

        # Tight date window: ~1 Dhan API chunk per job, correct anchor day per index
        start_date, end_date = expiry_window(ec, idx)

        candles = client.get_expired_options_full(
            index=idx,
            strike_offset=off,
            option_type=opt,
            expiry_flag="WEEK",
            expiry_code=ec,
            start=start_date,
            end=end_date,
            interval=iv,
        )

        if candles:
            save_dhan_candles(candles, idx, opt, iv, ec)
            downloaded += 1
        else:
            empty += 1

        done.add(key)

        if (downloaded + empty) % 200 == 0:
            _save_progress(done)
            logger.info(f"Progress: {downloaded} with data | {empty} empty | {skipped} skipped")

    _save_progress(done)
    logger.info("=" * 60)
    logger.info(f"Dhan download complete! {downloaded:,} data | {empty:,} empty | {skipped:,} skipped")
    logger.info("Run verify_data.py to check coverage.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
