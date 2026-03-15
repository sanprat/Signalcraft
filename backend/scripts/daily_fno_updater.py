#!/usr/bin/env python3
"""
daily_fno_updater.py

Daily incremental updater for FnO 1-minute data.
Should be run after market close (4:30 PM IST) to capture today's data.

Usage:
    python scripts/daily_fno_updater.py              # Updates yesterday
    python scripts/daily_fno_updater.py --date 2026-03-13  # Specific date
    python scripts/daily_fno_updater.py --dry-run    # Test without saving
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import from our modules
from app.core.symbols import FNO_SYMBOLS, get_fno_config
from app.core.candle_store import (
    init_database,
    insert_candles,
    get_latest_timestamp,
    get_symbol_count,
)

# Rate limiting
API_DELAY_SECONDS = 1.0


def get_dhan_headers() -> Dict[str, str]:
    """Get Dhan API headers from environment."""
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "access-token": os.environ.get("DHAN_ACCESS_TOKEN", ""),
        "client-id": os.environ.get("DHAN_CLIENT_ID", ""),
    }


def fetch_intraday_candles(
    symbol: str, config: Dict[str, str], date: datetime
) -> pd.DataFrame:
    """
    Fetch 1-minute intraday candles for a specific date using Dhan API.

    Args:
        symbol: Symbol name (e.g., 'NIFTY')
        config: Dict with keys: id, segment, instrument
        date: Date to fetch

    Returns:
        DataFrame with columns: symbol, timestamp, open, high, low, close, volume
    """
    headers = get_dhan_headers()
    url = "https://api.dhan.co/v2/charts/intraday"

    # Format dates for Dhan API (YYYY-MM-DD HH:MM:SS)
    from_date = date.strftime("%Y-%m-%d") + " 09:15:00"
    to_date = date.strftime("%Y-%m-%d") + " 15:30:00"

    payload = {
        "securityId": config["id"],
        "exchangeSegment": config["segment"],
        "instrument": config["instrument"],
        "interval": "1",  # 1-minute candles
        "oi": False,
        "fromDate": from_date,
        "toDate": to_date,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()

            if not data:
                logger.debug(f"No data for {symbol} on {date.date()}")
                return pd.DataFrame()

            # Handle response - Dhan returns column-oriented dict
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                # Check if it's column-oriented data (arrays for each column)
                if "open" in data and isinstance(data["open"], list):
                    # Column-oriented format: {open: [...], high: [...], ...}
                    df = pd.DataFrame(data)
                elif "data" in data:
                    df = pd.DataFrame(data["data"])
                else:
                    logger.warning(
                        f"Unexpected response format for {symbol}: {type(data)}"
                    )
                    return pd.DataFrame()
            else:
                logger.warning(f"Unexpected response format for {symbol}: {type(data)}")
                return pd.DataFrame()

            # Add symbol column
            df["symbol"] = symbol

            # Ensure timestamp is datetime
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])

            # Select and order required columns
            required_cols = [
                "symbol",
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
            df = df[[c for c in required_cols if c in df.columns]]

            return df

        elif response.status_code == 429:
            logger.warning(f"Rate limited for {symbol} on {date.date()}")
            import time

            time.sleep(60)
            return fetch_intraday_candles(symbol, config, date)

        else:
            logger.error(
                f"API error for {symbol} on {date.date()}: {response.status_code}"
            )
            return pd.DataFrame()

    except Exception as e:
        logger.error(f"Exception fetching {symbol} on {date.date()}: {e}")
        return pd.DataFrame()


def is_trading_day(date: datetime) -> bool:
    """Check if date is a weekday (Monday-Friday)."""
    return date.weekday() < 5  # Monday=0, Friday=4


def update_symbol(
    symbol: str, config: Dict[str, str], date: datetime, dry_run: bool = False
) -> Dict:
    """
    Update data for a single symbol on a specific date.

    Args:
        symbol: Symbol name
        config: Dict with keys: id, segment, instrument
        date: Date to update
        dry_run: If True, don't save to database

    Returns:
        Dict with update statistics
    """
    stats = {
        "symbol": symbol,
        "date": date.date(),
        "candles": 0,
        "saved": False,
        "skipped": False,
        "error": None,
    }

    # Check if already exists
    latest = get_latest_timestamp(symbol)
    if latest and latest.date() == date.date():
        logger.info(f"{symbol}: Already up to date for {date.date()}")
        stats["skipped"] = True
        return stats

    # Fetch data
    df = fetch_intraday_candles(symbol, config, date)

    if df.empty:
        logger.warning(f"{symbol}: No data for {date.date()}")
        return stats

    stats["candles"] = len(df)

    # Save to database (unless dry run)
    if not dry_run:
        try:
            insert_candles(df)
            stats["saved"] = True
            logger.info(f"{symbol}: ✓ Saved {len(df)} candles for {date.date()}")
        except Exception as e:
            stats["error"] = str(e)
            logger.error(f"{symbol}: Error saving data: {e}")
    else:
        logger.info(
            f"{symbol}: [DRY RUN] Would save {len(df)} candles for {date.date()}"
        )
        stats["saved"] = True  # Pretend we saved for dry run

    return stats


def update_all_fno(date: datetime, dry_run: bool = False) -> List[Dict]:
    """
    Update all FnO symbols for a specific date.

    Args:
        date: Date to update
        dry_run: If True, don't save to database

    Returns:
        List of update statistics
    """
    results = []

    for symbol in FNO_SYMBOLS.keys():
        config = get_fno_config(symbol)
        if not config:
            logger.error(f"No config for {symbol}")
            continue

        stats = update_symbol(symbol, config, date, dry_run)
        results.append(stats)

        # Rate limiting between symbols
        import time

        time.sleep(API_DELAY_SECONDS)

    return results


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Daily FnO 1-minute data updater")
    parser.add_argument(
        "--date", type=str, help="Date to update (YYYY-MM-DD). Defaults to yesterday."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Test run without saving to database"
    )

    args = parser.parse_args()

    # Determine date
    if args.date:
        try:
            update_date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
            return
    else:
        # Default to yesterday
        update_date = datetime.now() - timedelta(days=1)

    # Skip weekends
    if not is_trading_day(update_date):
        logger.info(f"Skipping {update_date.date()} - weekend")
        return

    logger.info("=" * 60)
    logger.info(f"Daily FnO Update - {update_date.date()}")
    if args.dry_run:
        logger.info("*** DRY RUN MODE - No data will be saved ***")
    logger.info("=" * 60)

    # Initialize database
    init_database()

    # Verify credentials
    headers = get_dhan_headers()
    if not headers["access-token"]:
        logger.error("DHAN_ACCESS_TOKEN not set in environment!")
        return

    # Update all FnO symbols
    results = update_all_fno(update_date, dry_run=args.dry_run)

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("UPDATE SUMMARY")
    logger.info("=" * 60)

    total_candles = 0
    saved_count = 0
    skipped_count = 0

    for r in results:
        status = "✓" if r["saved"] else ("⊘" if r["skipped"] else "✗")
        logger.info(f"{status} {r['symbol']}: {r['candles']} candles")

        total_candles += r["candles"]
        if r["saved"]:
            saved_count += 1
        elif r["skipped"]:
            skipped_count += 1

    logger.info(f"\nTotal: {total_candles:,} candles")
    logger.info(f"Saved: {saved_count}, Skipped: {skipped_count}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
