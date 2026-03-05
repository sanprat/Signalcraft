"""
verify_data.py — Check downloaded Parquet files for completeness and gaps.
Prints a coverage report for all instruments and timeframes.
"""

import logging
from pathlib import Path

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)
BASE_DIR = Path("data")

INTERVALS = ["1min", "5min", "15min"]
INDICES   = ["NIFTY", "BANKNIFTY", "FINNIFTY"]

# Expected candles per trading day per interval (approx, 9:15–15:30 = 375 min)
EXPECTED_PER_DAY = {
    "1min":  375,
    "5min":  75,
    "15min": 25,
}


def check_underlying():
    print("\n=== UNDERLYING SPOT DATA ===")
    for idx in INDICES:
        for interval in INTERVALS:
            path = BASE_DIR / "underlying" / idx / f"{interval}.parquet"
            if not path.exists():
                print(f"  ✗ {idx} {interval}: FILE MISSING")
                continue
            try:
                result = duckdb.query(
                    f"SELECT COUNT(*) as n, MIN(time) as first, MAX(time) as last "
                    f"FROM read_parquet('{path}')"
                ).df()
                n, first, last = result.iloc[0]["n"], result.iloc[0]["first"], result.iloc[0]["last"]
                print(f"  ✓ {idx} {interval}: {n:,} candles  |  {first} → {last}")
            except Exception as e:
                print(f"  ✗ {idx} {interval}: ERROR — {e}")


def check_options():
    print("\n=== OPTIONS DATA ===")
    summary = {}

    for idx in INDICES:
        for opt in ["CE", "PE"]:
            for interval in INTERVALS:
                dir_path = BASE_DIR / "candles" / idx / opt / interval
                if not dir_path.exists():
                    print(f"  ✗ {idx}/{opt}/{interval}: DIRECTORY MISSING")
                    continue

                parquet_files = list(dir_path.glob("*.parquet"))
                if not parquet_files:
                    print(f"  ✗ {idx}/{opt}/{interval}: NO FILES")
                    continue

                try:
                    result = duckdb.query(
                        f"SELECT COUNT(*) as n, COUNT(DISTINCT strftime(time, '%Y-%m-%d')) as days "
                        f"FROM read_parquet('{dir_path}/*.parquet')"
                    ).df()
                    n    = int(result.iloc[0]["n"])
                    days = int(result.iloc[0]["days"])
                    files = len(parquet_files)
                    print(f"  ✓ {idx}/{opt}/{interval}: {files} contracts | {n:,} candles | {days} trading days")
                    summary[f"{idx}/{opt}/{interval}"] = {"files": files, "candles": n, "days": days}
                except Exception as e:
                    print(f"  ✗ {idx}/{opt}/{interval}: ERROR — {e}")

    return summary


def check_gaps(idx: str, opt: str, interval: str, sample_files: int = 3):
    """Check timestamp gaps in a sample of files."""
    dir_path = BASE_DIR / "candles" / idx / opt / interval
    if not dir_path.exists():
        return

    files = sorted(dir_path.glob("*.parquet"))[:sample_files]
    for f in files:
        try:
            df = pd.read_parquet(f).sort_values("time")
            expected_gap = pd.Timedelta(minutes=int(interval.replace("min", "")))
            diffs = df["time"].diff().dropna()
            big_gaps = diffs[diffs > expected_gap * 2]
            if not big_gaps.empty:
                print(f"  ⚠  Gap in {f.name}: {len(big_gaps)} missing candles")
        except Exception:
            pass


def check_progress():
    import json
    progress_file = BASE_DIR / "download_progress.json"
    if progress_file.exists():
        with open(progress_file) as f:
            done = json.load(f)
        print(f"\n=== CHECKPOINT ===")
        print(f"  Completed jobs: {len(done):,}")
    else:
        print("\n=== CHECKPOINT ===")
        print("  No checkpoint file found — download not started yet.")


def main():
    print("=" * 60)
    print("  FnO DATA VERIFICATION REPORT")
    print("=" * 60)

    check_progress()
    check_underlying()
    check_options()

    # Spot-check gaps for NIFTY CE 1min
    print("\n=== GAP CHECK (NIFTY CE 1min — sample 3 files) ===")
    check_gaps("NIFTY", "CE", "1min", sample_files=3)

    print("\n" + "=" * 60)
    print("  Run 'python bulk_loader.py' to start or resume download.")
    print("=" * 60)


if __name__ == "__main__":
    main()
