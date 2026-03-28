#!/usr/bin/env python3
"""
download_intraday_data.py — Download 1-minute intraday OHLCV data from Dhan API

Downloads data for testing ORB (Opening Range Breakout) strategy or any intraday
strategy. Saves data as parquet files compatible with the backtest engine.

Usage:
    python scripts/download_intraday_data.py --symbol RELIANCE --days 5
    python scripts/download_intraday_data.py --symbol TCS --days 10
    python scripts/download_intraday_data.py --symbol RELIANCE --start 2024-01-01 --end 2024-01-31

Output:
    Saves to: backend/data/candles/NIFTY500/{SYMBOL}/1M.parquet

Requirements:
    - DHAN_ACCESS_TOKEN and DHAN_CLIENT_ID in .env file
    - Symbol must exist in data-scripts/nifty500_dhan_mapping.json
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, date
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

# Setup paths
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data" / "candles" / "NIFTY500"
MAPPING_FILE = PROJECT_ROOT / "data-scripts" / "nifty500_dhan_mapping.json"

# Add backend to path for imports
sys.path.insert(0, str(BACKEND_DIR))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Dhan API configuration
BASE_URL = "https://api.dhan.co/v2"
API_DELAY_SECONDS = 1.1  # Rate limiting

# Parquet schema for 1-minute data
PARQUET_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def load_dhan_mapping() -> dict:
    """Load Dhan security ID mapping from JSON file."""
    try:
        with open(MAPPING_FILE) as f:
            mapping = json.load(f)
            logger.info(
                f"Loaded {len(mapping)} symbol mappings from {MAPPING_FILE.name}"
            )
            return mapping
    except FileNotFoundError:
        logger.error(f"Mapping file not found: {MAPPING_FILE}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in mapping file: {e}")
        return {}


def get_dhan_headers() -> dict:
    """Get Dhan API headers from environment."""
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "access-token": os.environ.get("DHAN_ACCESS_TOKEN", ""),
        "client-id": os.environ.get("DHAN_CLIENT_ID", ""),
    }


def verify_credentials() -> bool:
    """Verify Dhan API credentials are set."""
    headers = get_dhan_headers()
    if not headers["access-token"]:
        logger.error("❌ DHAN_ACCESS_TOKEN not set in environment!")
        return False
    if not headers["client-id"]:
        logger.error("❌ DHAN_CLIENT_ID not set in environment!")
        return False
    return True


def verify_connection() -> bool:
    """Test Dhan API connection."""
    try:
        headers = get_dhan_headers()
        response = requests.get(f"{BASE_URL}/fundlimit", headers=headers, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Dhan API connection verified")
            return True
        else:
            logger.error(
                f"❌ Dhan API error: {response.status_code} - {response.text[:200]}"
            )
            return False
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return False


def is_trading_day(dt: datetime) -> bool:
    """Check if date is a weekday (Monday=0 to Friday=4)."""
    return dt.weekday() < 5


def get_trading_dates(start: date, end: date) -> list:
    """Get list of trading days between start and end dates."""
    dates = []
    current = start
    while current <= end:
        dt = datetime.combine(current, datetime.min.time())
        if is_trading_day(dt):
            dates.append(current)
        current += timedelta(days=1)
    return dates


def fetch_intraday_candles(
    security_id: str,
    symbol: str,
    request_date: date,
) -> pd.DataFrame:
    """
    Fetch 1-minute candles for a specific date using Dhan API.

    Args:
        security_id: Dhan security ID (e.g., "2885" for RELIANCE)
        symbol: Symbol name for logging
        request_date: Date to fetch data for

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    headers = get_dhan_headers()
    url = f"{BASE_URL}/charts/intraday"

    # Format dates for Dhan API (YYYY-MM-DD HH:MM:SS)
    from_datetime = request_date.strftime("%Y-%m-%d") + " 09:15:00"
    to_datetime = request_date.strftime("%Y-%m-%d") + " 15:30:00"

    payload = {
        "securityId": security_id,
        "exchangeSegment": "NSE_EQ",  # NSE Equity
        "instrument": "EQUITY",
        "interval": "1",  # 1-minute candles
        "oi": False,
        "fromDate": from_datetime,
        "toDate": to_datetime,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()

            # Check for error response
            if "errorCode" in data or "error" in data:
                logger.error(f"API error: {data}")
                return pd.DataFrame()

            # Handle column-oriented response from Dhan
            if not data:
                logger.debug(f"No data for {symbol} on {request_date}")
                return pd.DataFrame()

            # Dhan returns column-oriented format: {open: [...], high: [...], ...}
            df = pd.DataFrame(data)

            if df.empty:
                logger.debug(f"Empty response for {symbol} on {request_date}")
                return pd.DataFrame()

            # Convert Unix timestamp to datetime (IST)
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
                df["timestamp"] = df["timestamp"].dt.tz_convert("Asia/Kolkata")
                df["timestamp"] = df["timestamp"].dt.tz_localize(None)

            # Filter market hours (9:15 AM - 3:30 PM IST)
            if "timestamp" in df.columns and not df.empty:
                market_start = (
                    df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute >= 555
                )  # 9:15
                market_end = (
                    df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute <= 930
                )  # 15:30
                df = df[market_start & market_end]

            # Select required columns
            df = df[[c for c in PARQUET_COLUMNS if c in df.columns]]

            return df

        elif response.status_code == 429:
            logger.warning(f"Rate limited for {symbol} on {request_date}, waiting...")
            time.sleep(60)
            return fetch_intraday_candles(security_id, symbol, request_date)

        else:
            logger.error(
                f"API error for {symbol} on {request_date}: "
                f"{response.status_code} - {response.text[:200]}"
            )
            return pd.DataFrame()

    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching {symbol} on {request_date}")
        return pd.DataFrame()

    except Exception as e:
        logger.error(f"Exception fetching {symbol} on {request_date}: {e}")
        return pd.DataFrame()


def load_existing_data(symbol: str) -> pd.DataFrame:
    """Load existing parquet file if it exists."""
    output_path = DATA_DIR / symbol / "1M.parquet"
    if output_path.exists():
        try:
            df = pd.read_parquet(output_path)
            logger.info(
                f"Found existing data: {len(df)} candles, latest: {df['timestamp'].max()}"
            )
            return df
        except Exception as e:
            logger.warning(f"Could not load existing {output_path}: {e}")
    return pd.DataFrame()


def save_data(df: pd.DataFrame, symbol: str) -> None:
    """Save DataFrame to parquet file."""
    output_dir = DATA_DIR / symbol
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "1M.parquet"

    df.to_parquet(output_path, index=False)
    logger.info(f"💾 Saved {len(df)} candles to {output_path}")


def download_symbol_data(
    symbol: str,
    security_id: str,
    start_date: date,
    end_date: date,
    skip_existing: bool = True,
) -> dict:
    """
    Download 1-minute data for a symbol over date range.

    Args:
        symbol: Stock symbol (e.g., "RELIANCE")
        security_id: Dhan security ID
        start_date: Start date for download
        end_date: End date for download
        skip_existing: Skip dates that already have data

    Returns:
        Dict with download statistics
    """
    logger.info(f"\n{'=' * 70}")
    logger.info(f"Downloading {symbol} (ID: {security_id})")
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"{'=' * 70}")

    stats = {
        "total_days": 0,
        "success_days": 0,
        "failed_days": 0,
        "total_candles": 0,
    }

    # Load existing data if skipping
    existing_df = load_existing_data(symbol) if skip_existing else pd.DataFrame()
    existing_dates = (
        set(existing_df["timestamp"].dt.date.unique())
        if not existing_df.empty
        else set()
    )

    # Get list of trading days
    trading_dates = get_trading_dates(start_date, end_date)

    for request_date in trading_dates:
        stats["total_days"] += 1

        # Skip if already have data for this date
        if skip_existing and request_date in existing_dates:
            logger.info(
                f"[{stats['total_days']}] {request_date}: Already have data, skipping"
            )
            continue

        logger.info(f"[{stats['total_days']}] {request_date}: Downloading...")

        # Fetch data for this date
        df = fetch_intraday_candles(security_id, symbol, request_date)

        if not df.empty:
            # Append to existing data
            existing_df = pd.concat([existing_df, df], ignore_index=True)
            stats["success_days"] += 1
            stats["total_candles"] += len(df)
            logger.info(f"  ✓ Got {len(df)} candles")
        else:
            stats["failed_days"] += 1
            logger.warning(f"  ⚠ No data for {request_date}")

        # Rate limiting
        time.sleep(API_DELAY_SECONDS)

    # Remove duplicates and sort
    if not existing_df.empty:
        existing_df = (
            existing_df.drop_duplicates("timestamp", keep="last")
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        # Save combined data
        save_data(existing_df, symbol)

        # Print summary
        logger.info(f"\n✅ {symbol} Download Complete!")
        logger.info(f"  Trading days: {stats['total_days']}")
        logger.info(f"  Successful: {stats['success_days']}")
        logger.info(f"  Failed: {stats['failed_days']}")
        logger.info(f"  Total candles: {stats['total_candles']:,}")
        logger.info(
            f"  Date range: {existing_df['timestamp'].min()} to {existing_df['timestamp'].max()}"
        )

    return stats


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Download 1-minute intraday data from Dhan API"
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default="RELIANCE",
        help="Stock symbol (default: RELIANCE)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=5,
        help="Number of trading days to download (default: 5)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Start date (YYYY-MM-DD). Overrides --days if provided.",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="End date (YYYY-MM-DD). Default: today",
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Re-download even if data exists",
    )
    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Test Dhan API connection and exit",
    )
    args = parser.parse_args()

    # Load environment variables (from project root .env)
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        logger.info(f"Loaded environment from {env_path}")
    else:
        logger.warning(
            f".env file not found at {env_path}, checking other locations..."
        )
        # Try backend/.env as fallback
        env_path = BACKEND_DIR / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            logger.info(f"Loaded environment from {env_path}")

    # Test connection if requested
    if args.test_connection:
        if verify_credentials():
            verify_connection()
        return

    # Verify credentials
    if not verify_credentials():
        logger.error(
            "\nPlease set DHAN_ACCESS_TOKEN and DHAN_CLIENT_ID in your .env file"
        )
        return

    # Load symbol mapping
    mapping = load_dhan_mapping()

    # Get security ID
    security_id = mapping.get(args.symbol)
    if not security_id:
        logger.error(f"❌ Symbol '{args.symbol}' not found in mapping file")
        logger.error(f"Available symbols: {len(mapping)}")
        return

    # Calculate date range
    end_date = date.today()
    if args.end:
        try:
            end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"Invalid end date: {args.end}. Use YYYY-MM-DD format.")
            return

    if args.start:
        try:
            start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"Invalid start date: {args.start}. Use YYYY-MM-DD format.")
            return
    else:
        start_date = end_date - timedelta(days=args.days)

    # Verify connection
    if not verify_connection():
        logger.error("\nFailed to connect to Dhan API. Please check your credentials.")
        return

    # Download data
    logger.info("=" * 70)
    logger.info("1-MINUTE INTRADAY DATA DOWNLOAD")
    logger.info("=" * 70)
    logger.info(f"Symbol: {args.symbol} (Dhan ID: {security_id})")
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Output: {DATA_DIR / args.symbol / '1M.parquet'}")
    logger.info(f"Skip existing: {not args.no_skip}")
    logger.info("=" * 70)

    stats = download_symbol_data(
        symbol=args.symbol,
        security_id=security_id,
        start_date=start_date,
        end_date=end_date,
        skip_existing=not args.no_skip,
    )

    # Final verification
    if stats["total_candles"] > 0:
        output_path = DATA_DIR / args.symbol / "1M.parquet"
        df = pd.read_parquet(output_path)
        logger.info(f"\n✅ Verification: {output_path}")
        logger.info(f"   Total rows: {len(df):,}")
        logger.info(
            f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}"
        )
        logger.info(
            f"   Memory: {df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB"
        )


if __name__ == "__main__":
    main()
