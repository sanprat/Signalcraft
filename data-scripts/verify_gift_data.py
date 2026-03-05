#!/usr/bin/env python3
import pandas as pd
from pathlib import Path

base_dir = Path("/Users/sanim/Downloads/sunny/Python/AIML/Pybankers/Pytrader/data/underlying/GIFTNIFTY")

print("=" * 70)
print("  GIFT NIFTY PARQUET DATA SUMMARY")
print("=" * 70)

for interval in ["1min", "5min", "15min"]:
    file_path = base_dir / f"{interval}.parquet"
    if file_path.exists():
        df = pd.read_parquet(file_path)
        print(f"\n{interval}:")
        print(f"  File: {file_path}")
        print(f"  Total candles: {len(df):,}")
        print(f"  Date range: {df['time'].min()} → {df['time'].max()}")
        print(f"  Columns: {df.columns.tolist()}")
        print(f"  First candle: {df.iloc[0].to_dict()}")
        print(f"  Last candle: {df.iloc[-1].to_dict()}")
        print(f"  File size: {file_path.stat().st_size / 1024 / 1024:.2f} MB")
    else:
        print(f"\n{interval}: FILE NOT FOUND")

print("\n" + "=" * 70)
