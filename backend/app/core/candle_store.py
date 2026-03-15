"""
candle_store.py — DuckDB-based candle storage for 1-minute OHLCV data.
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import pandas as pd
import duckdb

logger = logging.getLogger(__name__)

# Database file path (in project data directory)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = PROJECT_ROOT / "data" / "candles.db"


def get_connection() -> duckdb.DuckDBPyConnection:
    """
    Get DuckDB connection.
    Creates the database file and directory if they don't exist.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH))


def init_database():
    """
    Initialize database with tables and indexes.
    Creates candles_1min table with primary key on (symbol, timestamp).
    """
    con = get_connection()

    try:
        # Create candles_1min table
        con.execute("""
            CREATE TABLE IF NOT EXISTS candles_1min (
                symbol VARCHAR,
                timestamp TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                PRIMARY KEY (symbol, timestamp)
            )
        """)

        # Create index for fast queries on symbol and timestamp
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_symbol_timestamp 
            ON candles_1min(symbol, timestamp)
        """)

        logger.info(f"DuckDB initialized at {DB_PATH}")

    finally:
        con.close()


def insert_candles(df: pd.DataFrame, batch_size: int = 1000) -> int:
    """
    Insert candles DataFrame into candles_1min table.
    Uses batch processing for large datasets.

    Args:
        df: DataFrame with columns [symbol, timestamp, open, high, low, close, volume]
        batch_size: Number of rows to insert per batch

    Returns:
        Number of rows inserted
    """
    if df.empty:
        return 0

    con = get_connection()
    total_inserted = 0

    try:
        # Process in batches
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i : i + batch_size].copy()

            # Ensure correct column order and types
            batch = batch[
                ["symbol", "timestamp", "open", "high", "low", "close", "volume"]
            ]
            batch["timestamp"] = pd.to_datetime(batch["timestamp"])

            # Register as temporary table and insert
            con.register("batch", batch)
            con.execute("""
                INSERT OR REPLACE INTO candles_1min 
                SELECT symbol, timestamp, open, high, low, close, volume 
                FROM batch
            """)

            total_inserted += len(batch)

            if i % (batch_size * 10) == 0:
                logger.info(f"Inserted {total_inserted}/{len(df)} candles...")

        logger.info(f"Inserted {total_inserted} candles into DuckDB")
        return total_inserted

    finally:
        con.close()


def get_candles_1min(
    symbol: str, from_date: datetime, to_date: datetime
) -> pd.DataFrame:
    """
    Get 1-minute candles for a symbol within a date range.

    Args:
        symbol: Stock symbol (e.g., 'NIFTY', 'BANKNIFTY')
        from_date: Start datetime
        to_date: End datetime

    Returns:
        DataFrame with OHLCV data
    """
    con = get_connection()

    try:
        result = con.execute(
            """
            SELECT symbol, timestamp, open, high, low, close, volume
            FROM candles_1min
            WHERE symbol = ?
            AND timestamp >= ?
            AND timestamp <= ?
            ORDER BY timestamp
        """,
            [symbol, from_date, to_date],
        ).fetchdf()

        return result

    finally:
        con.close()


def get_latest_timestamp(symbol: str) -> Optional[datetime]:
    """
    Get the latest timestamp for a symbol in the database.

    Args:
        symbol: Stock symbol

    Returns:
        Latest timestamp or None if no data exists
    """
    con = get_connection()

    try:
        result = con.execute(
            """
            SELECT MAX(timestamp) 
            FROM candles_1min 
            WHERE symbol = ?
        """,
            [symbol],
        ).fetchone()

        return result[0] if result and result[0] else None

    finally:
        con.close()


def get_earliest_timestamp(symbol: str) -> Optional[datetime]:
    """
    Get the earliest timestamp for a symbol in the database.

    Args:
        symbol: Stock symbol

    Returns:
        Earliest timestamp or None if no data exists
    """
    con = get_connection()

    try:
        result = con.execute(
            """
            SELECT MIN(timestamp) 
            FROM candles_1min 
            WHERE symbol = ?
        """,
            [symbol],
        ).fetchone()

        return result[0] if result and result[0] else None

    finally:
        con.close()


def get_symbol_count(symbol: str) -> int:
    """
    Get total candle count for a symbol.

    Args:
        symbol: Stock symbol

    Returns:
        Number of candles
    """
    con = get_connection()

    try:
        result = con.execute(
            """
            SELECT COUNT(*) 
            FROM candles_1min 
            WHERE symbol = ?
        """,
            [symbol],
        ).fetchone()

        return result[0] if result else 0

    finally:
        con.close()


def get_all_symbols() -> list:
    """
    Get list of all symbols in the database.

    Returns:
        List of symbol strings
    """
    con = get_connection()

    try:
        result = con.execute("""
            SELECT DISTINCT symbol 
            FROM candles_1min 
            ORDER BY symbol
        """).fetchdf()

        return result["symbol"].tolist()

    finally:
        con.close()


def get_fno_stats() -> dict:
    """
    Get statistics for all FnO symbols.

    Returns:
        Dictionary with symbol statistics
    """
    from .symbols import FNO_SYMBOLS

    con = get_connection()

    try:
        stats = {}

        for symbol in FNO_SYMBOLS.keys():
            result = con.execute(
                """
                SELECT 
                    COUNT(*) as total_candles,
                    MIN(timestamp) as earliest,
                    MAX(timestamp) as latest
                FROM candles_1min
                WHERE symbol = ?
            """,
                [symbol],
            ).fetchone()

            stats[symbol] = {
                "total_candles": result[0] if result[0] else 0,
                "earliest": str(result[1]) if result[1] else None,
                "latest": str(result[2]) if result[2] else None,
            }

        return stats

    finally:
        con.close()


def delete_symbol_data(symbol: str) -> int:
    """
    Delete all data for a symbol.

    Args:
        symbol: Stock symbol to delete

    Returns:
        Number of rows deleted
    """
    con = get_connection()

    try:
        result = con.execute(
            """
            DELETE FROM candles_1min WHERE symbol = ?
        """,
            [symbol],
        )

        logger.info(f"Deleted all data for {symbol}")
        return result.rowcount

    finally:
        con.close()


def aggregate_to_timeframe(
    symbol: str,
    interval: str,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Aggregate 1-minute data to higher timeframes using DuckDB time_bucket.

    Args:
        symbol: Stock symbol
        interval: Timeframe interval ('5 minutes', '15 minutes', '1 hour', '1 day')
        from_date: Start date (optional)
        to_date: End date (optional)

    Returns:
        DataFrame with aggregated OHLCV data
    """
    con = get_connection()

    try:
        # Build query with optional date filters
        query = f"""
            SELECT 
                time_bucket(INTERVAL '{interval}', timestamp, TIMESTAMP '2020-01-01 09:15:00') as time,
                first(open ORDER BY timestamp) as open,
                max(high) as high,
                min(low) as low,
                last(close ORDER BY timestamp) as close,
                sum(volume) as volume
            FROM candles_1min
            WHERE symbol = ?
        """

        params = [symbol]

        if from_date:
            query += " AND timestamp >= ?"
            params.append(from_date)

        if to_date:
            query += " AND timestamp <= ?"
            params.append(to_date)

        query += """
            GROUP BY 1
            ORDER BY 1
        """

        result = con.execute(query, params).fetchdf()
        return result

    finally:
        con.close()


if __name__ == "__main__":
    # Initialize database when run directly
    logging.basicConfig(level=logging.INFO)
    init_database()

    # Show stats
    stats = get_fno_stats()
    print("\n" + "=" * 60)
    print("FnO DATA STATS")
    print("=" * 60)

    for symbol, data in stats.items():
        print(f"\n{symbol}:")
        print(f"  Total candles: {data['total_candles']:,}")
        print(f"  Earliest: {data['earliest']}")
        print(f"  Latest: {data['latest']}")
