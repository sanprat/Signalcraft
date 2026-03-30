#!/usr/bin/env python3
"""
download_nifty50_1min_full.py — Download 1-minute data for NIFTY 50 stocks

Fetches 1-min intraday OHLCV from Jan 2021 to current date (Dhan depth limit).
Saves to data/candles/NIFTY500/{SYMBOL}/1min.parquet

Usage:
    python download_nifty50_1min_full.py
    python download_nifty50_1min_full.py --start-date 2021-01-01

To cancel: Press Ctrl+C (progress is saved, can resume later)
"""

import argparse
import json
import logging
import os
import signal
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
MAPPING_FILE = Path(__file__).parent / "nifty50_dhan_mapping.json"
CHUNK_DAYS = 85  # Dhan limit for intraday (using 85 to be safe)

# Date range
DEFAULT_START = date(2021, 1, 1)
DEFAULT_END = date.today()

# NIFTY 50 blue-chip stocks (Deep historical data support)
NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "BHARTIARTL", "SBIN", "INFY", "LICI",
    "ITC", "HINDUNILVR", "LT", "BAJFINANCE", "HCLTECH", "MARUTI", "SUNPHARMA",
    "TATAMOTORS", "TATASTEEL", "KOTAKBANK", "TITAN", "NTPC", "ULTRACEMCO", "ONGC",
    "AXISBANK", "WIPRO", "NESTLEIND", "M&M", "POWERGRID", "GRASIM", "JSWSTEEL",
    "ASIANPAINT", "HDFCLIFE", "SBILIFE", "BRITANNIA", "EICHERMOT", "APOLLOHOSP",
    "DIVISLAB", "TATACONSUM", "BAJAJFINSV", "HINDALCO", "TECHM", "DRREDDY", "CIPLA",
    "INDUSINDBK", "ADANIPORTS", "ADANIENT", "BPCL", "COALINDIA", "HEROMOTOCO", "UPL", "TATAPOWER"
]

# Parquet schema for 1-min data
SCHEMA = pa.schema(
    [
        ("time", pa.timestamp("s")),
        ("open", pa.float64()),
        ("high", pa.float64()),
        ("low", pa.float64()),
        ("close", pa.float64()),
        ("volume", pa.int64()),
    ]
)

# Global flag for graceful shutdown
shutdown_requested = False

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global shutdown_requested
    shutdown_requested = True
    log.warning(
        "\n⚠️  Shutdown requested! Finishing current stock and saving progress..."
    )


# Register signal handler
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def load_mapping() -> dict:
    """Load Dhan security ID mapping."""
    with open(MAPPING_FILE) as f:
        return json.load(f)


def load_nifty50_symbols() -> list:
    """Return the hardcoded NIFTY 50 symbols."""
    return NIFTY_50


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
) -> dict:
    """Download 1-minute data for a single stock."""
    global shutdown_requested

    log.info(f"\n{'=' * 70}")
    log.info(f"Downloading {symbol} (ID: {security_id})")
    log.info(f"Date range: {start} to {end}")
    log.info(f"{'=' * 70}")

    output_path = BASE_DIR / symbol / "1min.parquet"
    stats = {
        "symbol": symbol,
        "requests": 0,
        "candles": 0,
        "errors": 0,
        "status": "success",
    }

    # Check for shutdown
    if shutdown_requested:
        stats["status"] = "cancelled"
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
        # Check for shutdown request
        if shutdown_requested:
            log.warning(f"Shutdown requested, finishing {symbol}...")
            break

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

    if shutdown_requested:
        stats["status"] = "cancelled"

    return stats


def format_time(seconds: float) -> str:
    """Format seconds to readable time."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def main():
    parser = argparse.ArgumentParser(
        description="Download 1-minute data for NIFTY 50 stocks",
        epilog="Press Ctrl+C to cancel gracefully (progress is saved)",
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
        "--limit", type=int, default=None, help="Limit to first N stocks (for testing)"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip stocks that already have complete data",
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

    # Load data
    mapping = load_mapping()
    all_symbols = load_nifty50_symbols()

    # Filter to requested limit
    symbols = all_symbols[: args.limit] if args.limit else all_symbols

    # Filter out stocks without mappings
    missing = [s for s in symbols if s not in mapping]
    if missing:
        log.warning(f"⚠️  Skipping {len(missing)} stocks without Dhan mappings: {missing}")
        symbols = [s for s in symbols if s in mapping]
    
    if not symbols:
        log.error("No stocks with valid mappings found!")
        return

    # Initialize Dhan client
    client_id = os.getenv("DHAN_CLIENT_ID", "").strip()
    access_token = os.getenv("DHAN_ACCESS_TOKEN", "").strip()

    if not client_id or not access_token:
        log.error("DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN not set in environment!")
        return

    client = DhanClient(client_id, access_token)
    if not client.verify_connection():
        log.error("Failed to connect to Dhan API. Check your access token.")
        return

    # Print header
    total_stocks = len(symbols)
    estimated_chunks = sum(1 for _ in date_chunks(start, end, CHUNK_DAYS))
    estimated_requests = total_stocks * estimated_chunks
    estimated_time_hours = (estimated_requests * 1.1) / 3600

    log.info("=" * 70)
    log.info("NIFTY 50 1-Minute Data Download - FULL")
    log.info("=" * 70)
    log.info(f"Stocks to download: {total_stocks}")
    log.info(f"Date range: {start} to {end}")
    log.info(f"API chunks per stock: ~{estimated_chunks}")
    log.info(f"Estimated API requests: ~{estimated_requests:,}")
    log.info(f"Estimated time: ~{estimated_time_hours:.1f} hours")
    log.info(f"Output: {BASE_DIR}")
    log.info("=" * 70)
    log.info("Press Ctrl+C at any time to cancel (progress will be saved)")
    log.info("=" * 70)

    # Download data for each stock
    all_stats = []
    start_time = time.time()
    global shutdown_requested

    for i, symbol in enumerate(symbols, 1):
        if shutdown_requested:
            log.info(f"\n{'=' * 70}")
            log.info("Shutdown requested. Stopping after saving progress...")
            log.info(f"{'=' * 70}")
            break

        # Calculate ETA
        elapsed = time.time() - start_time
        stocks_done = i - 1
        if stocks_done > 0:
            avg_time_per_stock = elapsed / stocks_done
            remaining_stocks = total_stocks - i + 1
            eta_seconds = avg_time_per_stock * remaining_stocks
            eta_str = format_time(eta_seconds)
        else:
            eta_str = "calculating..."

        log.info(f"\n{'=' * 70}")
        log.info(
            f"Stock {i}/{total_stocks} ({i / total_stocks * 100:.1f}%) | ETA: {eta_str}"
        )
        log.info(f"{'=' * 70}")

        security_id = mapping[symbol]
        stats = download_stock_1min(client, symbol, security_id, start, end)
        all_stats.append(stats)

        if stats["status"] == "cancelled":
            break

        # Delay between stocks
        if i < total_stocks and not shutdown_requested:
            time.sleep(2)

    # Print summary
    elapsed = time.time() - start_time
    log.info("\n" + "=" * 70)
    if shutdown_requested:
        log.info("DOWNLOAD PARTIALLY COMPLETE (Cancelled by user)")
    else:
        log.info("DOWNLOAD COMPLETE - SUMMARY")
    log.info("=" * 70)

    successful = sum(1 for s in all_stats if s["status"] == "success")
    cancelled = sum(1 for s in all_stats if s["status"] == "cancelled")
    total_candles = sum(s["candles"] for s in all_stats)
    total_errors = sum(s["errors"] for s in all_stats)
    total_requests = sum(s["requests"] for s in all_stats)

    log.info(f"Stocks processed: {len(all_stats)}/{total_stocks}")
    log.info(f"Successful: {successful}")
    log.info(f"Cancelled: {cancelled}")
    log.info(f"Total API requests: {total_requests:,}")
    log.info(f"Total candles downloaded: {total_candles:,}")
    log.info(f"Total errors: {total_errors}")
    log.info(f"Elapsed time: {format_time(elapsed)}")
    log.info("=" * 70)

    # Show stocks with errors
    error_stocks = [s["symbol"] for s in all_stats if s["errors"] > 0]
    if error_stocks:
        log.info(f"\nStocks with errors ({len(error_stocks)}):")
        for sym in error_stocks[:10]:
            log.info(f"  - {sym}")
        if len(error_stocks) > 10:
            log.info(f"  ... and {len(error_stocks) - 10} more")

    if shutdown_requested:
        log.info("\n✅ Progress saved! To resume, just run the same command again.")
    else:
        log.info("\n✅ All done! Check the data in:")
        log.info(f"   {BASE_DIR}")


if __name__ == "__main__":
    main()
