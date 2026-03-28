#!/usr/bin/env python3
"""
Create synthetic OHLCV test data for backtesting
Usage: python create_test_data.py --symbol RELIANCE --days 90
"""

import sys
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os


def create_test_data(symbol: str, days: int = 90):
    """Generate synthetic OHLCV data for testing"""

    # Create date range (trading days only)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    dates = pd.date_range(start=start_date, end=end_date, freq="B")  # Business days

    np.random.seed(42)

    # Generate realistic price movement (random walk)
    returns = np.random.normal(0.001, 0.02, len(dates))  # Mean 0.1%, std 2%
    prices = 2500 * (1 + returns).cumprod()

    # Generate OHLC from close prices
    data = {
        "open": prices * (1 + np.random.normal(0, 0.005, len(dates))),
        "high": prices * (1 + abs(np.random.normal(0.01, 0.005, len(dates)))),
        "low": prices * (1 - abs(np.random.normal(0.01, 0.005, len(dates)))),
        "close": prices,
        "volume": np.random.randint(1000000, 5000000, len(dates)),
    }

    df = pd.DataFrame(data, index=dates)

    # Ensure OHLC logic (high >= max(open, close), low <= min(open, close))
    df["high"] = df[["open", "close", "high"]].max(axis=1)
    df["low"] = df[["open", "close", "low"]].min(axis=1)

    # Save to parquet
    output_dir = f"backend/data/candles/NIFTY500/{symbol}"
    os.makedirs(output_dir, exist_ok=True)

    output_file = f"{output_dir}/1D.parquet"
    df.to_parquet(output_file)

    print(f"✅ Created test data for {symbol}")
    print(f"📊 Candles: {len(df)}")
    print(f"📅 Date range: {df.index[0].date()} to {df.index[-1].date()}")
    print(f"💾 Saved to: {output_file}")
    print(f"\nPrice stats:")
    print(f"  Start: {df['close'].iloc[0]:.2f}")
    print(f"  End: {df['close'].iloc[-1]:.2f}")
    print(f"  High: {df['high'].max():.2f}")
    print(f"  Low: {df['low'].min():.2f}")

    return output_file


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="RELIANCE", help="Stock symbol")
    parser.add_argument("--days", type=int, default=90, help="Number of days")
    args = parser.parse_args()

    create_test_data(args.symbol, args.days)


if __name__ == "__main__":
    main()
