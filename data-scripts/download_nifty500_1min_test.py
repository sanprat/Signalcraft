#!/usr/bin/env python3
"""
download_nifty500_1min_test.py — Test download for 20 NIFTY 500 stocks (1-minute data)

Tests the infrastructure before full 500-stock download.
Saves to data/candles/NIFTY500/{SYMBOL}/1min.parquet

Usage:
    python download_nifty500_1min_test.py
    python download_nifty500_1min_test.py --start-date 2024-01-01
    python download_nifty500_1min_test.py --dry-run
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))
from dhan_client import DhanClient

# Configuration
BASE_DIR = Path(__file__).parent.parent / "data" / "candles" / "NIFTY500"
MAPPING_FILE = Path(__file__).parent / "nifty500_dhan_mapping.json"
CHUNK_DAYS = 85  # Dhan limit for intraday (using 85 to be safe)

# Test with 20 diverse stocks
TEST_STOCKS = [
    "RELIANCE",
    "TCS",
    "HDFCBANK",
    "INFY",
    "ICICIBANK",
    "HINDUNILVR",
    "SBIN",
    "BHARTIARTL",
    "ITC",
    "KOTAKBANK",
    "LT",
    "HCLTECH",
    "BAJFINANCE",
    "SUNPHARMA",
    "MARUTI",
    "TITAN",
    "ADANIENT",
    "ULTRACEMCO",
    "WIPRO",
    "NESTLEIND",
]

# Date range
DEFAULT_START = date(2020, 1, 1)
DEFAULT_END = date.today()

# Parquet schema for 1-min data
SCHEMA = pa.schema(
    [
        ("time", pa.timestamp("s", tz="Asia/Kolkata")),
        ("open", pa.float64()),
        ("high", pa.float64()),
        ("low", pa.float64()),
        ("close", pa.float64()),
        ("volume", pa.int64()),
    ]
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def load_mapping() -> dict:
    """Load Dhan security ID mapping."""
    with open(MAPPING_FILE) as f:
        return json.load(f)


def date_chunks(start: date, end: date, chunk_days: int):
    """Generate date chunks for API requests."""
    cur = start
    while cur <= end:
        yield cur, min(cur + timedelta(days=chunk_days - 1), end)
        cur += timedelta(days=chunk_days)


def candles_to_df(raw: list) -> pd.DataFrame:
    """Convert raw candles to DataFrame with market hours filtering."""
    if not raw:
        return pd.DataFrame()

    df = pd.DataFrame(raw)
    df["time"] = pd.to_datetime(df["time"], utc=False)
    df["time"] = df["time"].dt.tz_localize(None).dt.tz_localize("Asia/Kolkata")

    # Filter market hours (9:15 AM - 3:30 PM IST)
    t = df["time"]
    df = df[
        ((t.dt.hour > 9) | ((t.dt.hour == 9) & (t.dt.minute >= 15)))
        & ((t.dt.hour < 15) | ((t.dt.hour == 15) & (t.dt.minute <= 30)))
    ]

    return df.drop_duplicates("time").sort_values("time").reset_index(drop=True)


def load_existing(path: Path) -> pd.DataFrame:
    """Load existing parquet file if it exists."""
    if path.exists():
        try:
            return pd.read_parquet(path)
        except Exception as e:
            log.warning(f"Could not load existing {path}: {e}")
    return pd.DataFrame()


def merge_and_save(new_df: pd.DataFrame, path: Path):
    """Merge new data with existing and save."""
    existing = load_existing(path)

    if not existing.empty:
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    combined = (
        combined.drop_duplicates("time", keep="last")
        .sort_values("time")
        .reset_index(drop=True)
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(combined, schema=SCHEMA, preserve_index=False)
    pq.write_table(table, path)

    return len(combined)


def download_stock_1min(
    client: DhanClient,
    symbol: str,
    security_id: str,
    start: date,
    end: date,
    dry_run: bool = False,
) -> dict:
    """Download 1-minute data for a single stock."""
    log.info(f"\n{'=' * 60}")
    log.info(f"Downloading {symbol} (ID: {security_id})")
    log.info(f"Date range: {start} to {end}")
    log.info(f"{'=' * 60}")

    output_path = BASE_DIR / symbol / "1min.parquet"
    stats = {
        "symbol": symbol,
        "requests": 0,
        "candles": 0,
        "errors": 0,
    }

    if dry_run:
        log.info(f"[DRY RUN] Would download {symbol}")
        return stats

    # Check existing data
    existing_df = load_existing(output_path)
    if not existing_df.empty:
        latest = existing_df["time"].max()
        log.info(f"Existing data found, latest: {latest}")
        start = max(start, latest.date() + timedelta(days=1))
        if start > end:
            log.info(f"{symbol}: Already up to date")
            return stats

    all_candles = []
    total_chunks = sum(1 for _ in date_chunks(start, end, CHUNK_DAYS))
    chunk_num = 0

    for chunk_start, chunk_end in date_chunks(start, end, CHUNK_DAYS):
        chunk_num += 1
        log.info(f"  [{chunk_num}/{total_chunks}] {chunk_start} to {chunk_end}")

        from_dt = f"{chunk_start} 09:15:00"
        to_dt = f"{chunk_end} 15:30:00"

        try:
            raw = client.get_intraday_candles(
                security_id=security_id,
                exchange_segment="NSE_EQ",
                instrument="EQUITY",
                interval="1min",
                from_datetime=from_dt,
                to_datetime=to_dt,
            )

            stats["requests"] += 1

            if raw:
                df = candles_to_df(raw)
                if not df.empty:
                    all_candles.append(df)
                    log.info(f"    ✓ Got {len(df)} candles")
                else:
                    log.warning(f"    ⚠ No candles after market hours filter")
            else:
                log.warning(f"    ⚠ No data from API")

        except Exception as e:
            log.error(f"    ✗ Error: {e}")
            stats["errors"] += 1

        # Rate limiting
        time.sleep(1.1)

    # Save combined data
    if all_candles:
        combined_df = pd.concat(all_candles, ignore_index=True)
        total_rows = merge_and_save(combined_df, output_path)
        stats["candles"] = len(combined_df)
        log.info(
            f"✓ {symbol}: Saved {stats['candles']} candles (total in file: {total_rows})"
        )
    else:
        log.warning(f"⚠ {symbol}: No candles downloaded")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Download 1-min data for 20 test NIFTY 500 stocks"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Start date (YYYY-MM-DD), default: 2020-01-01",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End date (YYYY-MM-DD), default: today",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without downloading",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Limit to first N stocks (for testing)"
    )
    args = parser.parse_args()

    # Parse dates
    start = (
        datetime.strptime(args.start_date, "%Y-%m-%d").date()
        if args.start_date
        else DEFAULT_START
    )
    end = (
        datetime.strptime(args.end_date, "%Y-%m-%d").date()
        if args.end_date
        else DEFAULT_END
    )

    log.info("=" * 70)
    log.info("NIFTY 500 1-Minute Data Download - TEST (20 Stocks)")
    log.info("=" * 70)
    log.info(f"Date range: {start} to {end}")
    log.info(f"Stocks: {args.limit or len(TEST_STOCKS)} of {len(TEST_STOCKS)}")
    log.info(f"Output: {BASE_DIR}")
    log.info("=" * 70)

    # Load mapping
    mapping = load_mapping()

    # Get test stocks
    stocks = TEST_STOCKS[: args.limit] if args.limit else TEST_STOCKS

    # Verify all have mappings
    missing = [s for s in stocks if s not in mapping]
    if missing:
        log.error(f"Missing Dhan mappings for: {missing}")
        return

    # Initialize Dhan client
    client_id = os.getenv("DHAN_CLIENT_ID", "")
    access_token = os.getenv("DHAN_ACCESS_TOKEN", "")

    if not client_id or not access_token:
        log.error("DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN not set in environment!")
        return

    client = DhanClient(client_id, access_token)

    if not args.dry_run:
        if not client.verify_connection():
            log.error("Failed to connect to Dhan API")
            return

    # Download data for each stock
    all_stats = []
    start_time = time.time()

    for i, symbol in enumerate(stocks, 1):
        log.info(f"\n{'=' * 70}")
        log.info(f"Stock {i}/{len(stocks)}: {symbol}")
        log.info(f"{'=' * 70}")

        security_id = mapping[symbol]
        stats = download_stock_1min(
            client, symbol, security_id, start, end, args.dry_run
        )
        all_stats.append(stats)

        # Delay between stocks
        if i < len(stocks) and not args.dry_run:
            time.sleep(2)

    # Print summary
    elapsed = time.time() - start_time
    log.info("\n" + "=" * 70)
    log.info("TEST DOWNLOAD COMPLETE - SUMMARY")
    log.info("=" * 70)

    total_candles = sum(s["candles"] for s in all_stats)
    total_errors = sum(s["errors"] for s in all_stats)

    for stats in all_stats:
        log.info(
            f"{stats['symbol']:15s}: {stats['candles']:>8,} candles, {stats['requests']:>2} requests, {stats['errors']} errors"
        )

    log.info("-" * 70)
    log.info(f"Total: {total_candles:,} candles, {total_errors} errors")
    log.info(f"Elapsed: {elapsed / 60:.1f} minutes")
    log.info("=" * 70)

    if not args.dry_run:
        log.info("\n✅ Test complete! Check the data quality above.")
        log.info(f"Data saved to: {BASE_DIR}")
        log.info("\nTo verify data:")
        log.info(f"  ls -la {BASE_DIR}/*")
        log.info("\nIf satisfied, you can proceed with full 500-stock download.")


if __name__ == "__main__":
    main()
