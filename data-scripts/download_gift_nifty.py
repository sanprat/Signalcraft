"""
download_gift_nifty.py — Download GIFT NIFTY historical intraday data from Dhan API.

GIFT NIFTY Trading Started: July 3, 2023
Data Available: July 2023 → Present

Saves to:
  data/underlying/GIFTNIFTY/1min.parquet
  data/underlying/GIFTNIFTY/5min.parquet
  data/underlying/GIFTNIFTY/15min.parquet

Usage:
  python download_gift_nifty.py                     # Download all available data
  python download_gift_nifty.py --start 2024-01-01  # Custom start date
  python download_gift_nifty.py --intervals 5min 15min
  python download_gift_nifty.py --force             # Re-download everything
"""

import argparse
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv

# Add parent directory to path for dhan_client import
sys.path.insert(0, str(Path(__file__).parent))
from dhan_client import DhanClient

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent.parent / "data" / "underlying" / "GIFTNIFTY"
CHUNK_DAYS    = 85          # Safe under Dhan's 88-day limit
INTERVALS     = ["1min", "5min", "15min"]

# GIFT NIFTY started trading on July 3, 2023
LAUNCH_DATE   = date(2023, 7, 3)

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
        logging.FileHandler(BASE_DIR.parent / "logs" / "gift_nifty_download.log"
                            if (BASE_DIR.parent / "logs").exists()
                            else "/tmp/gift_nifty_download.log"),
    ]
)
log = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def date_chunks(start: date, end: date, chunk_days: int):
    """Yield (chunk_start, chunk_end) pairs covering [start, end]."""
    cur = start
    while cur <= end:
        yield cur, min(cur + timedelta(days=chunk_days - 1), end)
        cur += timedelta(days=chunk_days)


def candles_to_df(raw: list) -> pd.DataFrame:
    """Convert DhanClient normalized candle list to a clean DataFrame."""
    if not raw:
        return pd.DataFrame()
    
    df = pd.DataFrame(raw)[["time", "open", "high", "low", "close", "volume"]]
    df["time"] = pd.to_datetime(df["time"], utc=False).dt.tz_localize(
        None).dt.tz_localize("Asia/Kolkata")
    
    # Keep only market hours 9:15 → 15:30 (regular session)
    # GIFT NIFTY also trades in night session, but we'll focus on regular hours
    t = df["time"]
    df = df[
        ((t.dt.hour > 9) | ((t.dt.hour == 9) & (t.dt.minute >= 15))) &
        ((t.dt.hour < 15) | ((t.dt.hour == 15) & (t.dt.minute <= 30)))
    ]
    
    return df.drop_duplicates("time").sort_values("time").reset_index(drop=True)


def load_existing(path: Path) -> pd.DataFrame:
    """Load existing parquet file if it exists."""
    if path.exists():
        try:
            return pd.read_parquet(path)
        except Exception:
            pass
    return pd.DataFrame()


def merge_and_save(new_df: pd.DataFrame, path: Path):
    """Merge with existing file, deduplicate, write back."""
    existing = load_existing(path)
    if not existing.empty:
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    combined = (combined
                .drop_duplicates("time")
                .sort_values("time")
                .reset_index(drop=True))

    # Cast to schema-compatible types
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
    """Return True if the parquet file already has data for this date range."""
    df = load_existing(path)
    if df.empty:
        return False
    existing_dates = set(df["time"].dt.date)
    # Check if at least 80% of expected trading days are present
    chunk_dates = pd.bdate_range(str(start), str(end))
    expected = len(chunk_dates)
    present  = sum(1 for d in chunk_dates if d.date() in existing_dates)
    return expected > 0 and (present / expected) >= 0.80


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Download GIFT NIFTY historical intraday data from Dhan API"
    )
    p.add_argument(
        "--start", type=str,
        help=f"Start date YYYY-MM-DD (default: {LAUNCH_DATE}, GIFT NIFTY launch)"
    )
    p.add_argument(
        "--end", default=str(date.today()),
        help="End date YYYY-MM-DD (default: today)"
    )
    p.add_argument(
        "--intervals", nargs="+", default=INTERVALS,
        choices=INTERVALS,
        help="Intervals to download (default: all three)"
    )
    p.add_argument(
        "--force", action="store_true",
        help="Re-download even if chunk already covered"
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be downloaded without calling API"
    )
    return p.parse_args()


def main():
    args = parse_args()
    
    # Validate start date
    if args.start:
        start_date = date.fromisoformat(args.start)
        if start_date < LAUNCH_DATE:
            log.warning(f"⚠ Start date {start_date} is before GIFT NIFTY launch ({LAUNCH_DATE})")
            log.warning(f"  Using launch date {LAUNCH_DATE} instead")
            start_date = LAUNCH_DATE
    else:
        start_date = LAUNCH_DATE
    
    end_date = date.fromisoformat(args.end)
    
    if start_date > end_date:
        log.error(f"Start date {start_date} is after end date {end_date}")
        sys.exit(1)

    # Load credentials
    client_id = os.getenv("DHAN_CLIENT_ID", "").strip()
    access_token = os.getenv("DHAN_ACCESS_TOKEN", "").strip()
    
    if not client_id or not access_token:
        log.error("Missing DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN in .env")
        sys.exit(1)

    # Initialize client
    client = DhanClient(client_id, access_token)

    if not args.dry_run:
        if not client.verify_connection():
            log.error("Dhan connection failed — check .env credentials")
            sys.exit(1)

    log.info("=" * 70)
    log.info("  GIFT NIFTY Historical Data Downloader")
    log.info("=" * 70)
    log.info(f"  Date Range : {start_date} → {end_date}")
    log.info(f"  Intervals  : {', '.join(args.intervals)}")
    log.info(f"  Dry run    : {args.dry_run}")
    log.info(f"  Force      : {args.force}")
    log.info("=" * 70)

    # GIFT NIFTY configuration
    SECURITY_ID = "5024"
    EXCHANGE_SEGMENT = "IDX_I"
    INSTRUMENT = "INDEX"

    for interval in args.intervals:
        out_path = BASE_DIR / f"{interval}.parquet"
        log.info(f"\n{'='*60}")
        log.info(f"  Interval: {interval}  →  {out_path}")
        log.info(f"{'='*60}")

        total_new = 0
        chunks = list(date_chunks(start_date, end_date, CHUNK_DAYS))
        
        for i, (cs, ce) in enumerate(chunks, 1):
            log.info(f"\n  Chunk {i}/{len(chunks)}: {cs} → {ce}")

            if not args.force and already_covered(out_path, cs, ce):
                log.info(f"    ↳ Already covered, skipping")
                continue

            if args.dry_run:
                log.info(f"    ↳ [dry-run] would call /intraday {cs} → {ce}")
                continue

            # Fetch intraday candles
            raw = client.get_intraday_candles(
                security_id=SECURITY_ID,
                exchange_segment=EXCHANGE_SEGMENT,
                instrument=INSTRUMENT,
                interval=interval,
                from_datetime=f"{cs} 09:00:00",
                to_datetime=f"{ce} 16:00:00",
                oi=False,
            )

            if not raw:
                log.warning(f"    ↳ No data returned for {cs} → {ce}")
                continue

            df = candles_to_df(raw)
            if df.empty:
                log.warning(f"    ↳ Empty after filtering for {cs} → {ce}")
                continue

            total = merge_and_save(df, out_path)
            total_new += len(df)
            log.info(f"    ↳ {len(df)} new candles  |  file total: {total:,} rows")

        log.info(f"\n  Done {interval}: {total_new:,} new candles written → {out_path}")

    log.info("\n" + "=" * 70)
    log.info("  ✓ GIFT NIFTY Download complete!")
    log.info("=" * 70)
    
    # Print summary
    log.info("\n  Summary:")
    for interval in args.intervals:
        out_path = BASE_DIR / f"{interval}.parquet"
        if out_path.exists():
            df = load_existing(out_path)
            log.info(f"    {interval}: {len(df):,} candles ({df['time'].min().date()} → {df['time'].max().date()})")


if __name__ == "__main__":
    main()
