#!/usr/bin/env python3
"""
download_fno_historical.py

Download historical 1-minute FnO data from 2020-01-01 to 2026-03-13.
Uses Dhan's /v2/charts/intraday endpoint.

Usage:
    python scripts/download_fno_historical.py

Output:
    Downloads 1-minute OHLCV data to DuckDB (data/candles.db)
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import from our modules
from app.core.symbols import FNO_SYMBOLS, get_fno_config, get_fno_start_date
from app.core.candle_store import (
    init_database,
    insert_candles,
    get_latest_timestamp,
    get_symbol_count,
)

# Date range for historical download
START_DATE = datetime(2020, 1, 1)
END_DATE = datetime(2026, 3, 13)

# Rate limiting
API_DELAY_SECONDS = 1.0  # Delay between API calls


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
                # Check if it's an error response
                if "errorCode" in data or "error" in data:
                    logger.error(f"API error for {symbol} on {date.date()}: {data}")
                    return pd.DataFrame()
                # Check if it's column-oriented data (arrays for each column)
                elif "open" in data and isinstance(data["open"], list):
                    # Column-oriented format: {open: [...], high: [...], ...}
                    df = pd.DataFrame(data)
                # Check for data key
                elif "data" in data:
                    df = pd.DataFrame(data["data"])
                else:
                    # Log the actual response for debugging
                    logger.warning(
                        f"Unexpected dict response for {symbol}: {list(data.keys())}"
                    )
                    logger.debug(f"Response content: {data}")
                    return pd.DataFrame()
            else:
                logger.warning(f"Unexpected response format for {symbol}: {type(data)}")
                return pd.DataFrame()

            # Add symbol column
            df["symbol"] = symbol

            # Handle timestamp - Dhan returns Unix timestamps in seconds
            if "timestamp" in df.columns:
                # Convert Unix timestamp (seconds) to datetime
                # Dhan returns timestamps as integers (Unix epoch seconds)
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)

                # Convert to IST (Asia/Kolkata timezone)
                df["timestamp"] = df["timestamp"].dt.tz_convert("Asia/Kolkata")

                # Validate timestamps - filter out invalid dates (pre-2020 or far future)
                valid_mask = (df["timestamp"].dt.year >= 2020) & (
                    df["timestamp"].dt.year <= 2030
                )
                invalid_count = (~valid_mask).sum()
                if invalid_count > 0:
                    logger.warning(
                        f"Filtering out {invalid_count} invalid timestamps for {symbol} on {date.date()}"
                    )
                    df = df[valid_mask].copy()

                # Remove timezone info for storage (DuckDB stores naive timestamps)
                df["timestamp"] = df["timestamp"].dt.tz_localize(None)

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
            # Wait and retry
            import time

            time.sleep(60)
            return fetch_intraday_candles(symbol, config, date)

        else:
            logger.error(
                f"API error for {symbol} on {date.date()}: {response.status_code} - {response.text[:200]}"
            )
            return pd.DataFrame()

    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching {symbol} on {date.date()}")
        return pd.DataFrame()

    except Exception as e:
        logger.error(f"Exception fetching {symbol} on {date.date()}: {e}")
        return pd.DataFrame()


def is_trading_day(date: datetime) -> bool:
    """Check if date is a weekday (Monday-Friday)."""
    return date.weekday() < 5  # Monday=0, Friday=4


def download_symbol(
    symbol: str,
    config: Dict[str, str],
    start_date: datetime,
    end_date: datetime,
    skip_existing: bool = True,
) -> Dict[str, int]:
    """
    Download all historical 1-min data for a symbol.

    Args:
        symbol: Symbol name
        config: Dict with keys: id, segment, instrument, name, start_date
        start_date: Global start date for download
        end_date: End date for download
        skip_existing: If True, skip dates that already have data

    Returns:
        Dict with statistics: total_days, success_days, total_candles
    """
    logger.info(f"\n{'=' * 70}")
    logger.info(f"Downloading {symbol} ({config.get('name', symbol)})")
    logger.info(f"Date range: {start_date.date()} to {end_date.date()}")
    logger.info(f"{'=' * 70}")

    # Get symbol-specific start date (Dhan API limitation)
    symbol_start_date = get_fno_start_date(symbol)
    if symbol_start_date:
        # Use the later of global start_date or symbol's available start_date
        actual_start_date = max(start_date, symbol_start_date)
        if actual_start_date != start_date:
            logger.info(
                f"Note: {symbol} data available from {symbol_start_date.date()}, using that instead"
            )
    else:
        actual_start_date = start_date

    stats = {
        "total_days": 0,
        "success_days": 0,
        "failed_days": 0,
        "total_candles": 0,
    }

    # Check latest date in database
    if skip_existing:
        latest = get_latest_timestamp(symbol)
        if latest:
            logger.info(f"Latest data in DB: {latest}")
            current_date = latest + timedelta(days=1)
        else:
            current_date = actual_start_date
    else:
        current_date = actual_start_date

    # Iterate through dates
    while current_date <= end_date:
        # Skip weekends
        if not is_trading_day(current_date):
            current_date += timedelta(days=1)
            continue

        stats["total_days"] += 1

        # Fetch data for this date
        df = fetch_intraday_candles(symbol, config, current_date)

        if not df.empty:
            # Insert into database
            inserted = insert_candles(df)
            stats["success_days"] += 1
            stats["total_candles"] += len(df)

            logger.info(
                f"[{stats['total_days']}] {current_date.date()}: {len(df)} candles (Total: {stats['total_candles']})"
            )
        else:
            stats["failed_days"] += 1
            logger.warning(f"[{stats['total_days']}] {current_date.date()}: No data")

        # Rate limiting
        import time

        time.sleep(API_DELAY_SECONDS)

        current_date += timedelta(days=1)

    logger.info(f"\n{symbol} Complete!")
    logger.info(f"  Trading days: {stats['total_days']}")
    logger.info(f"  Successful: {stats['success_days']}")
    logger.info(f"  Failed: {stats['failed_days']}")
    logger.info(f"  Total candles: {stats['total_candles']:,}")

    return stats


def main():
    """Main function to download all FnO historical data."""
    logger.info("=" * 70)
    logger.info("FnO Historical 1-Minute Data Download")
    logger.info("=" * 70)
    logger.info(f"Period: {START_DATE.date()} to {END_DATE.date()}")
    logger.info(f"Symbols: {list(FNO_SYMBOLS.keys())}")
    logger.info("=" * 70)

    # Initialize database
    logger.info("\nInitializing database...")
    init_database()

    # Verify Dhan API credentials
    headers = get_dhan_headers()
    if not headers["access-token"]:
        logger.error("DHAN_ACCESS_TOKEN not set in environment!")
        return

    # Download each FnO symbol
    all_stats = {}

    for symbol in FNO_SYMBOLS.keys():
        config = get_fno_config(symbol)
        if not config:
            logger.error(f"No config found for {symbol}")
            continue

        try:
            stats = download_symbol(
                symbol=symbol,
                config=config,
                start_date=START_DATE,
                end_date=END_DATE,
                skip_existing=True,
            )
            all_stats[symbol] = stats

        except Exception as e:
            logger.error(f"Error downloading {symbol}: {e}")

        # Longer delay between symbols
        import time

        time.sleep(5)

    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("DOWNLOAD COMPLETE - SUMMARY")
    logger.info("=" * 70)

    total_candles = 0
    for symbol, stats in all_stats.items():
        logger.info(
            f"{symbol}: {stats['total_candles']:,} candles ({stats['success_days']}/{stats['total_days']} days)"
        )
        total_candles += stats["total_candles"]

    logger.info(f"\nTotal candles downloaded: {total_candles:,}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
