import os
import pandas as pd
from pathlib import Path

BASE = Path("/home/signalcraft/data")

print("\n--- Checking NIFTY500 '1D' sample ---")
nifty500_dir = BASE / "candles" / "NIFTY500"
if nifty500_dir.exists():
    symbols = sorted([d.name for d in nifty500_dir.iterdir() if d.is_dir()])
    sample = ["HDFC", "RELIANCE", "TCS", "INFY", "ITC"] # Known major symbols
    
    for sym in sample:
        pq = nifty500_dir / sym / "1D.parquet"
        if pq.exists():
            try:
                # Read without pyarrow string inference directly
                df = pd.read_parquet(pq, engine='fastparquet')
                if 'time' in df.columns:
                    # Treat time as pure strings to absolutely avoid timezone bugs
                    times = df['time'].astype(str)
                    print(f"{sym:15s}  Max Date = {times.max()[:10]}")
            except Exception as e:
                print(f"{sym:15s}  ERROR: {e}")
                
print("\n--- Checking Indices ---")
underlying = BASE / "underlying"
if underlying.exists():
    for idx in sorted(underlying.iterdir()):
        if idx.is_dir():
            for pq_name in ["1min.parquet", "1D.parquet"]:
                pq = idx / pq_name
                if pq.exists():
                    try:
                        df = pd.read_parquet(pq, engine='fastparquet')
                        if 'time' in df.columns:
                            times = df['time'].astype(str)
                            print(f"{idx.name:15s} | {pq_name:12s} | Max Date = {times.max()[:10]}")
                    except Exception as e:
                        pass
