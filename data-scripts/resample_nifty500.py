#!/usr/bin/env python3
"""
resample_nifty500.py — Resample NIFTY500 1-minute parquet data to 5min, 15min, and 1D.

Uses DuckDB for fast SQL-based aggregation directly on parquet files.
Skips stocks/timeframes that are already up to date.

Data layout:
  data/candles/NIFTY500/{SYMBOL}/1min.parquet   ← source
  data/candles/NIFTY500/{SYMBOL}/5min.parquet   ← generated
  data/candles/NIFTY500/{SYMBOL}/15min.parquet  ← generated
  data/candles/NIFTY500/{SYMBOL}/1D.parquet     ← generated

Usage:
  python3 data-scripts/resample_nifty500.py                 # resample all stocks
  python3 data-scripts/resample_nifty500.py --symbol RELIANCE  # single stock
  python3 data-scripts/resample_nifty500.py --force         # overwrite existing files
  python3 data-scripts/resample_nifty500.py --dry-run       # preview only
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# ── Config ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
NIFTY500_DIR = PROJECT_ROOT / "data" / "candles" / "NIFTY500"

# Target timeframes to generate from 1-minute source
RESAMPLE_TARGETS = ["5min", "15min", "1D"]

# Market hours IST (used to filter 1D aggregation to intraday hours only)
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"

# PyArrow schema for all output files
SCHEMA = pa.schema([
    ("time",   pa.timestamp("s", tz="Asia/Kolkata")),
    ("open",   pa.float32()),
    ("high",   pa.float32()),
    ("low",    pa.float32()),
    ("close",  pa.float32()),
    ("volume", pa.int64()),
])

LOG_DIR = PROJECT_ROOT / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "resample_nifty500.log"),
    ],
)
log = logging.getLogger(__name__)


# ── DuckDB SQL Aggregation ─────────────────────────────────────────────────────

def resample_with_duckdb(src_path: Path, interval: str) -> pd.DataFrame:
    """
    Read a 1min parquet file and resample to the target interval using DuckDB SQL.
    Returns a pandas DataFrame with columns: time, open, high, low, close, volume.
    """
    src = str(src_path)

    if interval == "5min":
        bucket = "INTERVAL 5 MINUTES"
    elif interval == "15min":
        bucket = "INTERVAL 15 MINUTES"
    elif interval == "1D":
        bucket = "INTERVAL 1 DAY"
    else:
        raise ValueError(f"Unsupported interval: {interval}")

    if interval == "1D":
        # For daily, group by calendar date (timestamps already in IST in parquet)
        # Filter to market hours: 09:15 to 15:30 IST
        sql = f"""
            SELECT
                date_trunc('day', time)::TIMESTAMPTZ AS time,
                FIRST(open  ORDER BY time) AS open,
                MAX(high)                  AS high,
                MIN(low)                   AS low,
                LAST(close  ORDER BY time) AS close,
                SUM(volume)                AS volume
            FROM read_parquet('{src}')
            WHERE TIME(time) >= TIME '09:15:00'
              AND TIME(time) <= TIME '15:30:00'
            GROUP BY 1
            ORDER BY 1
        """
    else:
        # For intraday, preserve market hours naturally (data is already filtered)
        sql = f"""
            SELECT
                TIME_BUCKET({bucket}, time::TIMESTAMPTZ, 'Asia/Kolkata') AS time,
                FIRST(open  ORDER BY time) AS open,
                MAX(high)                  AS high,
                MIN(low)                   AS low,
                LAST(close  ORDER BY time) AS close,
                SUM(volume)                AS volume
            FROM read_parquet('{src}')
            GROUP BY 1
            ORDER BY 1
        """

    con = duckdb.connect()
    df = con.execute(sql).df()
    con.close()
    return df


# ── Helpers ────────────────────────────────────────────────────────────────────

def is_up_to_date(src_path: Path, dst_path: Path) -> bool:
    """Return True if destination file exists and is newer than the source."""
    if not dst_path.exists():
        return False
    return dst_path.stat().st_mtime >= src_path.stat().st_mtime


def save_parquet(df: pd.DataFrame, path: Path):
    """Cast types and save as a compressed parquet file."""
    df["time"]   = pd.to_datetime(df["time"], utc=True).dt.tz_convert("Asia/Kolkata")
    df["time"]   = df["time"].astype("datetime64[s, Asia/Kolkata]")
    df["open"]   = df["open"].astype("float32")
    df["high"]   = df["high"].astype("float32")
    df["low"]    = df["low"].astype("float32")
    df["close"]  = df["close"].astype("float32")
    df["volume"] = df["volume"].astype("int64")

    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, schema=SCHEMA, preserve_index=False)
    pq.write_table(table, path, compression="lz4")


# ── Main ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Resample NIFTY500 1-min data to 5min/15min/1D")
    p.add_argument("--symbol",  help="Process a single stock symbol (e.g. RELIANCE)")
    p.add_argument("--force",   action="store_true", help="Overwrite existing files")
    p.add_argument("--dry-run", action="store_true", help="Preview without writing")
    return p.parse_args()


def main():
    args = parse_args()

    if not NIFTY500_DIR.exists():
        log.error(f"NIFTY500 data directory not found: {NIFTY500_DIR}")
        sys.exit(1)

    # Collect symbols to process
    if args.symbol:
        sym_dirs = [NIFTY500_DIR / args.symbol.upper()]
        if not sym_dirs[0].exists():
            log.error(f"Symbol directory not found: {sym_dirs[0]}")
            sys.exit(1)
    else:
        sym_dirs = sorted([d for d in NIFTY500_DIR.iterdir() if d.is_dir()])

    total = len(sym_dirs)
    log.info("=" * 70)
    log.info("  NIFTY500 1-Minute → Resample (5min / 15min / 1D)")
    log.info(f"  Stocks to process : {total}")
    log.info(f"  Targets           : {', '.join(RESAMPLE_TARGETS)}")
    log.info(f"  Force overwrite   : {args.force}")
    log.info(f"  Dry run           : {args.dry_run}")
    log.info("=" * 70)

    t_start = time.time()
    updated = 0
    skipped = 0
    errors  = 0

    for i, sym_dir in enumerate(sym_dirs, 1):
        sym = sym_dir.name
        src_path = sym_dir / "1min.parquet"

        if not src_path.exists():
            log.warning(f"  [{i}/{total}] {sym}: No 1min.parquet — skipping")
            skipped += 1
            continue

        sym_updated = False

        for interval in RESAMPLE_TARGETS:
            dst_path = sym_dir / f"{interval}.parquet"

            # Skip if already up to date and not forcing
            if not args.force and is_up_to_date(src_path, dst_path):
                skipped += 1
                continue

            if args.dry_run:
                log.info(f"  [{i}/{total}] {sym} {interval}: would resample")
                continue

            try:
                df = resample_with_duckdb(src_path, interval)
                if df.empty:
                    log.warning(f"  [{i}/{total}] {sym} {interval}: Empty result — skipping")
                    skipped += 1
                    continue

                save_parquet(df, dst_path)
                log.info(
                    f"  [{i}/{total}] {sym} {interval}: "
                    f"{len(df):,} candles | "
                    f"{df['time'].min().date()} → {df['time'].max().date()}"
                )
                sym_updated = True

            except Exception as e:
                log.error(f"  [{i}/{total}] {sym} {interval}: ERROR — {e}")
                errors += 1

        if sym_updated:
            updated += 1

    elapsed = time.time() - t_start
    log.info("=" * 70)
    log.info("  RESAMPLE COMPLETE")
    log.info(f"  Stocks updated : {updated}")
    log.info(f"  Skipped        : {skipped}")
    log.info(f"  Errors         : {errors}")
    log.info(f"  Elapsed        : {elapsed / 60:.1f} minutes")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
