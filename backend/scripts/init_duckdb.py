#!/usr/bin/env python3
"""
init_duckdb.py

One-time initialization script for DuckDB candle storage.
Creates the database file, tables, and indexes.

Usage:
    python scripts/init_duckdb.py
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import from our modules
from app.core.candle_store import init_database, get_fno_stats, DB_PATH
from app.core.symbols import FNO_SYMBOLS


def verify_api_connection():
    """Verify Dhan API connection."""
    import requests

    headers = {
        "Content-Type": "application/json",
        "access-token": os.environ.get("DHAN_ACCESS_TOKEN", ""),
        "client-id": os.environ.get("DHAN_CLIENT_ID", ""),
    }

    if not headers["access-token"]:
        logger.warning("DHAN_ACCESS_TOKEN not set in environment")
        return False

    try:
        response = requests.get(
            "https://api.dhan.co/v2/fundlimit", headers=headers, timeout=10
        )

        if response.status_code == 200:
            logger.info("✓ Dhan API connection verified")
            return True
        else:
            logger.warning(f"Dhan API returned status {response.status_code}")
            return False

    except Exception as e:
        logger.warning(f"Dhan API connection failed: {e}")
        return False


def main():
    """Main initialization function."""
    logger.info("=" * 70)
    logger.info("DuckDB Initialization")
    logger.info("=" * 70)

    # Show configuration
    logger.info(f"Database path: {DB_PATH}")
    logger.info(f"FnO symbols: {list(FNO_SYMBOLS.keys())}")

    # Initialize database
    logger.info("\nInitializing database...")
    init_database()
    logger.info("✓ Database tables created")

    # Verify API connection
    logger.info("\nVerifying Dhan API connection...")
    api_ok = verify_api_connection()

    # Show current status
    logger.info("\nCurrent data status:")
    stats = get_fno_stats()

    for symbol in FNO_SYMBOLS.keys():
        data = stats.get(symbol, {})
        candles = data.get("total_candles", 0)
        print(f"  {symbol}: {candles:,} candles")

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("INITIALIZATION COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Database: {DB_PATH}")
    logger.info(f"API: {'✓ Connected' if api_ok else '⚠ Not configured'}")
    logger.info("\nNext steps:")
    logger.info("  1. Download historical data:")
    logger.info(
        "     docker exec signalcraft-backend python3 scripts/download_fno_historical.py"
    )
    logger.info("\n  2. Or run daily update:")
    logger.info(
        "     docker exec signalcraft-backend python3 scripts/daily_fno_updater.py"
    )
    logger.info("\n  3. Check data status:")
    logger.info(
        "     docker exec signalcraft-backend python3 scripts/fno_data_manager.py status"
    )
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
