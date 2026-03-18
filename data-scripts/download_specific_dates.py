#!/usr/bin/env python3
"""
download_specific_dates.py — Download 1-minute data for specific dates

Usage:
    python download_specific_dates.py --dates 2026-03-17 2026-03-18
    python download_specific_dates.py --dates 2026-03-17 --stocks-only
    python download_specific_dates.py --dates 2026-03-17 --indices-only
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
NIFTY500_DIR = Path(__file__).parent.parent / "data" / "candles" / "NIFTY500"
INDICES_DIR = Path(__file__).parent.parent / "data" / "candles"
MAPPING_FILE = Path(__file__).parent / "nifty500_dhan_mapping.json"

# Indices configuration
INDICES = {
    "NIFTY": {"id": "13", "segment": "IDX_I", "instrument": "INDEX"},
    "BANKNIFTY": {"id": "25", "segment": "IDX_I", "instrument": "INDEX"},
    "FINNIFTY": {"id": "27", "segment": "IDX_I", "instrument": "INDEX"},
    "GIFTNIFTY": {"id": "5024", "segment": "IDX_I", "instrument": "INDEX"},
}

# Schema for NIFTY 500 parquet files
NIFTY500_SCHEMA = pa.schema(
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
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def load_mapping() -> dict:
    """Load Dhan security ID mapping."""
    with open(MAPPING_FILE) as f:
        return json.load(f)


def load_nifty500_symbols() -> list:
    """Load NIFTY 500 symbols from CSV."""
    csv_path = Path(__file__).parent / "nifty500_symbols.csv"
    df = pd.read_csv(csv_path)
    return df["Symbol"].tolist()


def is_trading_day(d: date) -> bool:
    """Check if date is a weekday (Mon-Fri)."""
    return d.weekday() < 5


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


def load_existing_parquet(path: Path) -> pd.DataFrame:
    """Load existing parquet file if it exists."""
    if path.exists():
        try:
            return pd.read_parquet(path)
        except Exception:
            pass
    return pd.DataFrame()


def save_to_parquet(new_df: pd.DataFrame, path: Path):
    """Merge new data with existing and save to parquet."""
    existing = load_existing_parquet(path)

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
    table = pa.Table.from_pandas(combined, schema=NIFTY500_SCHEMA, preserve_index=False)
    pq.write_table(table, path)

    return len(combined)


def download_nifty500_stock(
    client: DhanClient, symbol: str, security_id: str, target_date: date
) -> int:
    """Download 1-minute data for a single NIFTY 500 stock for specific date."""
    if not is_trading_day(target_date):
        log.info(f"  {target_date} is not a trading day, skipping")
        return 0

    output_path = NIFTY500_DIR / symbol / "1min.parquet"

    # Check if data for this date already exists
    existing_df = load_existing_parquet(output_path)
    if not existing_df.empty:
        date_start = datetime.combine(target_date, datetime.min.time())
        date_end = datetime.combine(
            target_date + timedelta(days=1), datetime.min.time()
        )
        existing_for_date = existing_df[
            (existing_df["time"] >= date_start) & (existing_df["time"] < date_end)
        ]
        if len(existing_for_date) > 0:
            log.info(
                f"  {symbol}: Data for {target_date} already exists ({len(existing_for_date)} candles)"
            )
            return 0

    from_dt = f"{target_date} 09:15:00"
    to_dt = f"{target_date} 15:30:00"

    try:
        raw = client.get_intraday_candles(
            security_id=security_id,
            exchange_segment="NSE_EQ",
            instrument="EQUITY",
            interval="1min",
            from_datetime=from_dt,
            to_datetime=to_dt,
        )

        if raw:
            df = candles_to_df(raw)
            if not df.empty:
                total_rows = save_to_parquet(df, output_path)
                log.info(f"  ✓ {symbol}: {len(df)} candles for {target_date}")
                return len(df)
            else:
                log.warning(
                    f"  ⚠ {symbol}: No candles after filtering for {target_date}"
                )
        else:
            log.warning(f"  ⚠ {symbol}: No data from API for {target_date}")

    except Exception as e:
        log.error(f"  ✗ {symbol}: Error - {e}")

    return 0


def download_index_to_duckdb(
    client: DhanClient, symbol: str, config: dict, target_date: date
) -> int:
    """Download 1-minute data for an index to DuckDB."""
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
    from app.core.candle_store import get_connection, insert_candles

    if not is_trading_day(target_date):
        log.info(f"  {target_date} is not a trading day, skipping")
        return 0

    from_dt = f"{target_date} 09:15:00"
    to_dt = f"{target_date} 15:30:00"

    try:
        raw = client.get_intraday_candles(
            security_id=config["id"],
            exchange_segment=config["segment"],
            instrument=config["instrument"],
            interval="1min",
            from_datetime=from_dt,
            to_datetime=to_dt,
        )

        if raw:
            df = candles_to_df(raw)
            if not df.empty:
                df["symbol"] = symbol
                df = df.rename(columns={"time": "timestamp"})
                df["timestamp"] = df["timestamp"].dt.tz_localize(None)
                inserted = insert_candles(df)
                log.info(f"  ✓ {symbol}: {inserted} candles for {target_date}")
                return inserted
            else:
                log.warning(
                    f"  ⚠ {symbol}: No candles after filtering for {target_date}"
                )
        else:
            log.warning(f"  ⚠ {symbol}: No data from API for {target_date}")

    except Exception as e:
        log.error(f"  ✗ {symbol}: Error - {e}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Download 1-minute data for specific dates"
    )
    parser.add_argument(
        "--dates",
        nargs="+",
        required=True,
        help="Dates to download (YYYY-MM-DD format)",
    )
    parser.add_argument(
        "--stocks-only", action="store_true", help="Only download NIFTY 500 stocks"
    )
    parser.add_argument(
        "--indices-only", action="store_true", help="Only download indices"
    )
    args = parser.parse_args()

    # Parse dates
    target_dates = []
    for d in args.dates:
        try:
            target_dates.append(datetime.strptime(d, "%Y-%m-%d").date())
        except ValueError:
            log.error(f"Invalid date format: {d}. Use YYYY-MM-DD")
            return

    log.info("=" * 70)
    log.info("Download 1-Minute Data for Specific Dates")
    log.info("=" * 70)
    log.info(f"Dates: {[d.strftime('%Y-%m-%d') for d in target_dates]}")
    log.info(f"Stocks: {'Yes' if not args.indices_only else 'No'}")
    log.info(f"Indices: {'Yes' if not args.stocks_only else 'No'}")
    log.info("=" * 70)

    # Initialize Dhan client
    client_id = os.getenv("DHAN_CLIENT_ID", "").strip()
    access_token = os.getenv("DHAN_ACCESS_TOKEN", "").strip()

    if not client_id or not access_token:
        log.error("DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN not set!")
        return

    client = DhanClient(client_id, access_token)
    if not client.verify_connection():
        log.error("Failed to connect to Dhan API")
        return

    total_candles = 0

    # Download NIFTY 500 stocks
    if not args.indices_only:
        log.info("\n" + "=" * 70)
        log.info("NIFTY 500 Stocks")
        log.info("=" * 70)

        mapping = load_mapping()
        symbols = load_nifty500_symbols()
        symbols = [s for s in symbols if s in mapping]  # Skip stocks without mappings

        log.info(f"Total stocks: {len(symbols)}")

        for target_date in target_dates:
            log.info(f"\n📅 Date: {target_date}")

            for i, symbol in enumerate(symbols, 1):
                security_id = mapping[symbol]
                candles = download_nifty500_stock(
                    client, symbol, security_id, target_date
                )
                total_candles += candles

                # Progress every 50 stocks
                if i % 50 == 0:
                    log.info(f"  Progress: {i}/{len(symbols)} stocks processed")

                # Rate limiting
                time.sleep(0.5)

    # Download indices
    if not args.stocks_only:
        log.info("\n" + "=" * 70)
        log.info("Indices")
        log.info("=" * 70)

        for target_date in target_dates:
            log.info(f"\n📅 Date: {target_date}")

            for symbol, config in INDICES.items():
                candles = download_index_to_duckdb(client, symbol, config, target_date)
                total_candles += candles
                time.sleep(0.5)

    # Summary
    log.info("\n" + "=" * 70)
    log.info("DOWNLOAD COMPLETE")
    log.info("=" * 70)
    log.info(f"Total candles downloaded: {total_candles:,}")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
