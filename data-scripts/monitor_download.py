#!/usr/bin/env python3
"""
monitor_download.py — Watch download progress and notify on completion.
"""

import json
import time
from pathlib import Path
from datetime import datetime

PROGRESS_FILE = Path("data/download_progress.json")
TOTAL_JOBS = 13104
CHECK_INTERVAL = 300  # Check every 5 minutes

def get_progress():
    if not PROGRESS_FILE.exists():
        return 0
    try:
        with open(PROGRESS_FILE) as f:
            return len(json.load(f))
    except:
        return 0

def verify_final_data():
    """Verify BANKNIFTY and FINNIFTY data after download."""
    try:
        from pathlib import Path
        import duckdb
        
        BASE = Path('data/candles')
        print('\n' + '='*70)
        print('  FINAL DATA VERIFICATION')
        print('='*70)
        
        for index in ['BANKNIFTY', 'FINNIFTY']:
            print(f'\n  {index}:')
            print('  ' + '-'*68)
            
            total_files = 0
            total_candles = 0
            earliest = None
            latest = None
            
            for opt in ['CE', 'PE']:
                for tf in ['1min', '5min', '15min']:
                    dir_path = BASE / index / opt / tf
                    if dir_path.exists():
                        files = list(dir_path.glob('*.parquet'))
                        total_files += len(files)
                        try:
                            result = duckdb.query(f"""
                                SELECT 
                                    COUNT(*) as candles,
                                    MIN(time) as first,
                                    MAX(time) as last
                                FROM read_parquet('{dir_path}/*.parquet')
                            """).df()
                            if not result.empty and result.iloc[0]['candles'] > 0:
                                total_candles += int(result.iloc[0]['candles'])
                                if result.iloc[0]['first']:
                                    if earliest is None or result.iloc[0]['first'] < earliest:
                                        earliest = result.iloc[0]['first']
                                if result.iloc[0]['last']:
                                    if latest is None or result.iloc[0]['last'] > latest:
                                        latest = result.iloc[0]['last']
                        except:
                            pass
            
            if earliest and latest:
                days_span = (latest - earliest).days
                print(f'  Files: {total_files:,} | Candles: {total_candles:,}')
                print(f'  Date Range: {earliest.strftime("%Y-%m-%d")} → {latest.strftime("%Y-%m-%d")}')
                print(f'  Span: {days_span} days ({days_span/30:.1f} months)')
                
                if days_span >= 300:
                    print(f'  Status: ✅ COMPLETE (1+ year)')
                elif days_span >= 180:
                    print(f'  Status: ⚠ PARTIAL (6+ months)')
                else:
                    print(f'  Status: ✗ INCOMPLETE (< 6 months)')
            else:
                print(f'  Status: ✗ NO DATA')
        
        print('\n' + '='*70 + '\n')
    except Exception as e:
        print(f'Verification error: {e}')

def main():
    print("\n" + "="*70)
    print("  DHAN DOWNLOAD MONITOR")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Target:  {TOTAL_JOBS:,} jobs (BANKNIFTY + FINNIFTY, 52 expiries)")
    print(f"  Checking every {CHECK_INTERVAL//60} minutes...")
    print("="*70 + "\n")
    
    last_progress = 0
    
    while True:
        progress = get_progress()
        pct = (progress / TOTAL_JOBS) * 100 if progress > 0 else 0
        now = datetime.now().strftime('%H:%M:%S')
        
        if progress > 0:
            remaining = max(TOTAL_JOBS - progress, 0)
            est_hours = remaining / 3600
            
            status_line = f"[{now}] {progress:,} / {TOTAL_JOBS:,} jobs ({pct:.1f}%) - Est. remaining: {est_hours:.1f}h"
            
            if progress > last_progress:
                print(status_line)
                last_progress = progress
            
            if progress >= TOTAL_JOBS:
                print("\n" + "="*70)
                print("  ✅ DOWNLOAD COMPLETE!")
                print("="*70)
                print(f"\n  Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  Total jobs: {progress:,}")
                print(f"  Duration: ~{progress/3600:.1f} hours")
                
                # Verify final data
                verify_final_data()
                
                # Terminal bell
                print("\a")
                break
        else:
            print(f"[{now}] Waiting for download to start...")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
