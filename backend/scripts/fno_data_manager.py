#!/usr/bin/env python3
"""
fno_data_manager.py

Utility script for managing FnO candle data.

Usage:
    python scripts/fno_data_manager.py status          # Show data statistics
    python scripts/fno_data_manager.py verify         # Verify data integrity
    python scripts/fno_data_manager.py delete NIFTY  # Delete symbol data
    python scripts/fno_data_manager.py sample NIFTY   # Show sample data
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import logging
from datetime import datetime, timedelta

import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import from our modules
from app.core.symbols import FNO_SYMBOLS
from app.core.candle_store import (
    init_database,
    get_fno_stats,
    get_all_symbols,
    get_symbol_count,
    get_latest_timestamp,
    get_earliest_timestamp,
    get_candles_1min,
    delete_symbol_data,
    aggregate_to_timeframe,
    DB_PATH,
)


def show_status():
    """Show current data statistics for all FnO symbols."""
    logger.info("\n" + "=" * 70)
    logger.info("FnO DATA STATUS")
    logger.info("=" * 70)

    stats = get_fno_stats()

    total_candles = 0

    for symbol in FNO_SYMBOLS.keys():
        data = stats.get(symbol, {})
        candles = data.get("total_candles", 0)
        earliest = data.get("earliest")
        latest = data.get("latest")

        total_candles += candles

        print(f"\n{symbol} ({FNO_SYMBOLS[symbol].get('name', symbol)}):")
        print(f"  Total candles: {candles:,}")

        if earliest:
            print(f"  Earliest: {earliest[:19]}")
        else:
            print(f"  Earliest: N/A")

        if latest:
            print(f"  Latest:   {latest[:19]}")
        else:
            print(f"  Latest:   N/A")

        # Show expected vs actual
        if candles > 0:
            # Rough estimate: ~375 candles per trading day
            expected_days = 1550  # ~6 years of trading days
            days_of_data = candles / 375 if candles > 0 else 0
            coverage = (days_of_data / expected_days) * 100
            print(f"  Coverage: ~{days_of_data:.0f} days ({coverage:.1f}%)")

    print("\n" + "=" * 70)
    print(f"Total candles in database: {total_candles:,}")
    print(f"Database file: {DB_PATH}")
    print("=" * 70)


def verify_data(symbol: str = None):
    """Verify data integrity for FnO symbols."""
    logger.info("\n" + "=" * 70)
    logger.info("VERIFYING DATA INTEGRITY")
    logger.info("=" * 70)

    symbols_to_check = [symbol] if symbol else list(FNO_SYMBOLS.keys())

    all_ok = True

    for sym in symbols_to_check:
        count = get_symbol_count(sym)
        latest = get_latest_timestamp(sym)
        earliest = get_earliest_timestamp(sym)

        print(f"\n{sym}:")
        print(f"  Candles: {count:,}")
        print(f"  Date range: {earliest} to {latest}")

        # Check for gaps
        if count > 0:
            # Sample a recent date to verify data
            if latest:
                check_date = min(datetime.now() - timedelta(days=5), latest)
                df = get_candles_1min(
                    sym,
                    check_date.replace(hour=9, minute=15),
                    check_date.replace(hour=15, minute=30),
                )

                if df.empty:
                    print(f"  ⚠ Warning: No data for recent date {check_date.date()}")
                    all_ok = False
                else:
                    print(
                        f"  ✓ Sample data OK ({len(df)} candles for {check_date.date()})"
                    )

    print("\n" + "=" * 70)
    if all_ok:
        print("✓ All data verified successfully")
    else:
        print("⚠ Some issues detected")
    print("=" * 70)


def show_sample(symbol: str, days: int = 5):
    """Show sample data for a symbol."""
    logger.info("\n" + "=" * 70)
    logger.info(f"SAMPLE DATA FOR {symbol} (Last {days} days)")
    logger.info("=" * 70)

    if symbol not in FNO_SYMBOLS:
        logger.error(f"{symbol} is not a valid FnO symbol")
        return

    latest = get_latest_timestamp(symbol)
    if not latest:
        logger.warning(f"No data for {symbol}")
        return

    # Get last N days of data
    from_date = latest - timedelta(days=days)
    to_date = latest

    df = get_candles_1min(symbol, from_date, to_date)

    if df.empty:
        logger.warning(f"No data found for {symbol}")
        return

    print(f"\nTotal candles: {len(df)}")
    print(f"\nFirst 5 candles:")
    print(df.head().to_string(index=False))

    print(f"\nLast 5 candles:")
    print(df.tail().to_string(index=False))

    # Show aggregated sample
    print(f"\n--- 5-minute aggregation sample ---")
    df_5min = aggregate_to_timeframe(symbol, "5 minutes", from_date, to_date)
    if not df_5min.empty:
        print(df_5min.head(10).to_string(index=False))

    print("\n" + "=" * 70)


def delete_data(symbol: str, confirm: bool = False):
    """Delete all data for a symbol."""
    if not confirm:
        response = input(f"Delete all data for {symbol}? Type 'yes' to confirm: ")
        if response.lower() != "yes":
            logger.info("Cancelled")
            return

    count = delete_symbol_data(symbol)
    logger.info(f"Deleted {count} candles for {symbol}")


def list_symbols():
    """List all symbols in the database."""
    symbols = get_all_symbols()

    print("\n" + "=" * 70)
    print("SYMBOLS IN DATABASE")
    print("=" * 70)

    if not symbols:
        print("No symbols in database")
    else:
        for sym in sorted(symbols):
            count = get_symbol_count(sym)
            print(f"  {sym}: {count:,} candles")

    print("=" * 70)


def aggregate_sample(symbol: str, timeframe: str):
    """Show aggregated data sample."""
    logger.info("\n" + "=" * 70)
    logger.info(f"AGGREGATED DATA FOR {symbol} ({timeframe})")
    logger.info("=" * 70)

    # Get last 30 days
    latest = get_latest_timestamp(symbol)
    if not latest:
        logger.warning(f"No data for {symbol}")
        return

    from_date = latest - timedelta(days=30)
    to_date = latest

    df = aggregate_to_timeframe(symbol, timeframe, from_date, to_date)

    if df.empty:
        logger.warning(f"No aggregated data found")
        return

    print(f"\nTotal candles: {len(df)}")
    print(f"\nData:")
    print(df.to_string(index=False))

    print("\n" + "=" * 70)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="FnO Data Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Status command
    subparsers.add_parser("status", help="Show data statistics")

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify data integrity")
    verify_parser.add_argument("--symbol", type=str, help="Specific symbol to verify")

    # Sample command
    sample_parser = subparsers.add_parser("sample", help="Show sample data")
    sample_parser.add_argument("symbol", type=str, help="Symbol to sample")
    sample_parser.add_argument("--days", type=int, default=5, help="Number of days")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete symbol data")
    delete_parser.add_argument("symbol", type=str, help="Symbol to delete")
    delete_parser.add_argument("--force", action="store_true", help="Skip confirmation")

    # List command
    subparsers.add_parser("list", help="List all symbols in database")

    # Aggregate command
    agg_parser = subparsers.add_parser("aggregate", help="Show aggregated data")
    agg_parser.add_argument("symbol", type=str, help="Symbol")
    agg_parser.add_argument(
        "timeframe", type=str, help="Timeframe (5min, 15min, 1hour, 1day)"
    )

    args = parser.parse_args()

    # Initialize database
    init_database()

    # Run command
    if args.command == "status":
        show_status()
    elif args.command == "verify":
        verify_data(args.symbol if hasattr(args, "symbol") else None)
    elif args.command == "sample":
        show_sample(args.symbol, args.days)
    elif args.command == "delete":
        delete_data(args.symbol, args.force)
    elif args.command == "list":
        list_symbols()
    elif args.command == "aggregate":
        aggregate_sample(args.symbol, args.timeframe)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
