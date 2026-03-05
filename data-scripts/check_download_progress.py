#!/usr/bin/env python3
"""
check_download_progress.py — Monitor Dhan bulk download progress.
Usage: python check_download_progress.py
"""

import json
import time
from pathlib import Path
from datetime import datetime

PROGRESS_FILE = Path("data/download_progress.json")
TOTAL_JOBS = 13104  # BANKNIFTY + FINNIFTY, 52 expiries

def main():
    print("\n" + "="*70)
    print("  DHAN DOWNLOAD PROGRESS MONITOR")
    print(f"  Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    if not PROGRESS_FILE.exists():
        print("\n  ⏳ Download not started yet (no checkpoint file found)")
        print("="*70 + "\n")
        return
    
    try:
        with open(PROGRESS_FILE) as f:
            done = json.load(f)
    except:
        print("\n  ⚠ Could not read progress file")
        print("="*70 + "\n")
        return
    
    current = len(done)
    pct = min((current / TOTAL_JOBS) * 100, 100)
    remaining = max(TOTAL_JOBS - current, 0)
    
    # Estimate time based on rate (assume ~1 job/sec = 3600 jobs/hour)
    est_hours_remaining = remaining / 3600
    
    print(f"\n  Progress: {current:,} / {TOTAL_JOBS:,} jobs ({pct:.1f}%)")
    print(f"  Completed: {current:,} jobs")
    print(f"  Remaining: {remaining:,} jobs")
    print(f"  Est. Time Remaining: {est_hours_remaining:.1f} hours")
    
    if pct >= 100:
        print("\n  ✅ DOWNLOAD COMPLETE!")
    elif pct >= 75:
        print("\n  🔄 Download in final stretch...")
    elif pct >= 50:
        print("\n  🔄 Download过半 - Keep running...")
    elif pct >= 25:
        print("\n  🔄 Download progressing...")
    else:
        print("\n  🔄 Download started - This will take several hours...")
    
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    main()
