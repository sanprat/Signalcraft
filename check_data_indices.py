import pandas as pd
import os
from pathlib import Path

base_dir = Path(__file__).parent / 'data' / 'underlying'
indices = ['NIFTY', 'BANKNIFTY', 'FINNIFTY']
timeframes = ['1min.parquet', '5min.parquet', '15min.parquet']

print("--- Underlying Indices Data Dates ---")
for index in indices:
    print(f"\n[{index}]")
    index_dir = os.path.join(base_dir, index)
    if not os.path.exists(index_dir):
        print("  Directory not found.")
        continue
    
    for tf in timeframes:
        file_path = os.path.join(index_dir, tf)
        if os.path.exists(file_path):
            try:
                df = pd.read_parquet(file_path)
                if df.empty:
                    print(f"  {tf}: Empty File")
                else:
                    if 'time' in df.columns:
                        start_date = df['time'].min().strftime('%Y-%m-%d')
                        end_date = df['time'].max().strftime('%Y-%m-%d')
                        print(f"  {tf}: {len(df)} rows | {start_date} to {end_date}")
                    else:
                        print(f"  {tf}: 'time' column missing. Columns: {df.columns}")
            except Exception as e:
                print(f"  {tf}: Error reading file - {e}")
        else:
            print(f"  {tf}: Missing")
