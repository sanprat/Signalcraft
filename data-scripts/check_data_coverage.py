#!/usr/bin/env python3
"""Check the last date of data across all Parquet files."""
import os
import pandas as pd
from pathlib import Path

BASE = Path(__file__).parent.parent / "data"

# 1. NIFTY500 stocks - sample check
nifty500_dir = BASE / "candles" / "NIFTY500"
if nifty500_dir.exists():
    symbols = sorted([d.name for d in nifty500_dir.iterdir() if d.is_dir()])
    sample = symbols[:3] + symbols[len(symbols)//2:len(symbols)//2+3] + symbols[-3:]
    sample = list(dict.fromkeys(sample))
else:
    symbols = []
    sample = []

print(f"NIFTY500: {len(symbols)} symbols")
print(f"{'Symbol':20s} {'Interval':10s} {'First':12s} {'Last':12s} {'Rows':>8s}")
print("-" * 65)

for sym in sample:
    sym_dir = nifty500_dir / sym
    for pq in sorted(sym_dir.glob("*.parquet")):
        if pq.name.startswith('._'):
            continue
        try:
            try:
                df = pd.read_parquet(pq)
            except Exception:
                df = pd.read_parquet(pq, engine='fastparquet')
            if 'time' in df.columns:
                times = pd.to_datetime(df['time'], utc=True, errors='coerce')
                print(f"{sym:20s} {pq.stem:10s} {str(times.min())[:10]:12s} {str(times.max())[:10]:12s} {len(df):8,d}")
        except Exception as e:
            print(f"{sym:20s} {pq.stem:10s} ERROR: {e}")

# 2. Aggregate: check ALL symbols for last date (just 1D files)
print(f"\n{'='*60}")
print(f"  AGGREGATE: Last date across ALL NIFTY500 stocks (1D)")
print(f"{'='*60}")
last_dates = []
for sym in symbols:
    pq_1d = nifty500_dir / sym / "1D.parquet"
    if pq_1d.exists():
        try:
            try:
                df = pd.read_parquet(pq_1d)
            except Exception:
                df = pd.read_parquet(pq_1d, engine='fastparquet')
            if 'time' in df.columns:
                last_dates.append(pd.to_datetime(df['time'], utc=True, errors='coerce').max())
        except:
            pass

if last_dates:
    s = pd.Series(last_dates)
    print(f"  Min last date : {s.min()}")
    print(f"  Max last date : {s.max()}")
    print(f"  Median        : {s.median()}")
    print(f"  Stocks checked: {len(last_dates)}")

# 3. Index underlying
print(f"\n{'='*60}")
print(f"  INDEX UNDERLYING")
print(f"{'='*60}")
underlying = BASE / "underlying"
if underlying.exists():
    for idx in sorted(underlying.iterdir()):
        if idx.is_dir():
            for pq in sorted(idx.glob("*.parquet")):
                if pq.name.startswith('._'):
                    continue
                try:
                    try:
                        df = pd.read_parquet(pq)
                    except Exception:
                        df = pd.read_parquet(pq, engine='fastparquet')
                    if 'time' in df.columns:
                        times = pd.to_datetime(df['time'], utc=True, errors='coerce')
                        print(f"  {idx.name:15s} {pq.stem:10s} {str(times.min())[:10]} → {str(times.max())[:19]}  ({len(df):,} rows)")
                except Exception as e:
                    print(f"  {idx.name:15s} {pq.stem:10s} ERROR: {e}")

# 4. FnO candles
print(f"\n{'='*60}")
print(f"  FnO OPTIONS DATA")
print(f"{'='*60}")
candles_dir = BASE / "candles"
for idx in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
    idx_dir = candles_dir / idx
    if idx_dir.exists():
        for opt_dir in sorted(idx_dir.iterdir()):
            if opt_dir.is_dir():
                for iv_dir in sorted(opt_dir.iterdir()):
                    if iv_dir.is_dir():
                        pq_files = list(iv_dir.glob("*.parquet"))
                        if pq_files:
                            # Find date range across the most recent files
                            latest = sorted(pq_files, key=lambda f: f.stat().st_mtime, reverse=True)[:5]
                            max_d = None
                            for pq in latest:
                                try:
                                    try:
                                        df = pd.read_parquet(pq, engine='fastparquet')
                                    except Exception:
                                        df = pd.read_parquet(pq)
                                    if 'time' in df.columns:
                                        times = pd.to_datetime(df['time'], utc=True, errors='coerce')
                                        d = times.max()
                                        if pd.notna(d):
                                            if max_d is None or d > max_d:
                                                max_d = d
                                except Exception:
                                    pass
                            print(f"  {idx:10s} {opt_dir.name:4s} {iv_dir.name:8s} {len(pq_files):5d} files  latest → {str(max_d)[:10] if max_d else 'N/A'}")
    else:
        print(f"  {idx}: No FnO data directory found")

# 5. data-scripts FnO data check  
ds_candles = Path(__file__).parent / "data" / "candles"
if ds_candles.exists():
    print(f"\n{'='*60}")
    print(f"  FnO OPTIONS DATA (data-scripts/data/)")
    print(f"{'='*60}")
    for idx in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
        idx_dir = ds_candles / idx
        if idx_dir.exists():
            for opt_dir in sorted(idx_dir.iterdir()):
                if opt_dir.is_dir():
                    for iv_dir in sorted(opt_dir.iterdir()):
                        if iv_dir.is_dir():
                            pq_files = list(iv_dir.glob("*.parquet"))
                            if pq_files:
                                latest = sorted(pq_files, key=lambda f: f.stat().st_mtime, reverse=True)[:5]
                                max_d = None
                                for pq in latest:
                                    try:
                                        try:
                                            df = pd.read_parquet(pq, engine='fastparquet')
                                        except Exception:
                                            df = pd.read_parquet(pq)
                                        if 'time' in df.columns:
                                            times = pd.to_datetime(df['time'], utc=True, errors='coerce')
                                            d = times.max()
                                            if pd.notna(d):
                                                if max_d is None or d > max_d:
                                                    max_d = d
                                    except Exception:
                                        pass
                                print(f"  {idx:10s} {opt_dir.name:4s} {iv_dir.name:8s} {len(pq_files):5d} files  latest → {str(max_d)[:10] if max_d else 'N/A'}")
