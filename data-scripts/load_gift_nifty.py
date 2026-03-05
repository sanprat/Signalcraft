"""
load_gift_nifty.py — Load and display GIFT NIFTY data from parquet files.

Usage:
    python load_gift_nifty.py                    # Show summary
    python load_gift_nifty.py --interval 5min    # Load 5min data
    python load_gift_nifty.py --last 100         # Show last 100 candles
"""

import argparse
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent / "data" / "underlying" / "GIFTNIFTY"

def load_data(interval="15min"):
    """Load GIFT NIFTY data for specified interval."""
    file_path = BASE_DIR / f"{interval}.parquet"
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return None
    
    df = pd.read_parquet(file_path)
    df['date'] = df['time'].dt.date
    df['time_only'] = df['time'].dt.time
    return df

def show_summary(df, interval):
    """Show summary statistics."""
    print("=" * 70)
    print(f"  GIFT NIFTY {interval} Data Summary")
    print("=" * 70)
    print(f"\n📊 Statistics:")
    print(f"  Total candles: {len(df):,}")
    print(f"  Date range: {df['time'].min().date()} → {df['time'].max().date()}")
    print(f"  Price range: {df['low'].min():,.1f} → {df['high'].max():,.1f}")
    print(f"  Latest close: {df.iloc[-1]['close']:,.1f}")
    
    print(f"\n📈 Sample (first 5 rows):")
    print(df[['time', 'open', 'high', 'low', 'close']].head().to_string(index=False))
    
    print(f"\n📉 Sample (last 5 rows):")
    print(df[['time', 'open', 'high', 'low', 'close']].tail().to_string(index=False))
    
    # Daily aggregation
    print(f"\n📅 Trading days: {df['date'].nunique()}")
    
    # Recent performance
    recent = df[df['date'] >= df['date'].max()].tail(5)
    if len(recent) > 0:
        print(f"\n📊 Recent 5-day performance:")
        daily = df.groupby('date')['close'].last()
        print(daily.tail().to_string())

def main():
    parser = argparse.ArgumentParser(description="Load GIFT NIFTY data")
    parser.add_argument("--interval", default="15min", choices=["1min", "5min", "15min"],
                       help="Data interval (default: 15min)")
    parser.add_argument("--last", type=int, default=5, help="Show last N candles")
    parser.add_argument("--export", type=str, help="Export to CSV file")
    args = parser.parse_args()
    
    df = load_data(args.interval)
    if df is None:
        return
    
    show_summary(df, args.interval)
    
    if args.export:
        export_path = Path(args.export)
        df[['time', 'open', 'high', 'low', 'close', 'volume']].to_csv(export_path, index=False)
        print(f"\n✅ Exported to: {export_path}")

if __name__ == "__main__":
    main()
