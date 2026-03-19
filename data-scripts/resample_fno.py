#!/usr/bin/env python3
"""
resample_fno.py — Resample FnO options 1-minute parquet data to 5min and 15min.

Uses DuckDB for fast SQL-based aggregation directly on parquet files.
Skips strikes/timeframes that are already up to date.

Data layout:
  data/candles/{INDEX}/{CE|PE}/1min/dhan_ec{n}_{strike}.parquet   ← source
  data/candles/{INDEX}/{CE|PE}/5min/dhan_ec{n}_{strike}.parquet   ← generated
  data/candles/{INDEX}/{CE|PE}/15min/dhan_ec{n}_{strike}.parquet  ← generated

Usage:
  python3 data-scripts/resample_fno.py                         # all indices
  python3 data-scripts/resample_fno.py --index NIFTY           # single index
  python3 data-scripts/resample_fno.py --index NIFTY --type CE # specific type
  python3 data-scripts/resample_fno.py --force                 # overwrite all
  python3 data-scripts/resample_fno.py --dry-run               # preview only
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
CANDLES_DIR  = PROJECT_ROOT / "data" / "candles"

# Indices and option types to process
FNO_INDICES   = ["NIFTY", "BANKNIFTY", "FINNIFTY", "GIFTNIFTY"]
OPTION_TYPES  = ["CE", "PE"]

# Only resample to these timeframes (1D rarely useful for options)
RESAMPLE_TARGETS = ["5min", "15min"]

# UTC equivalents of IST market hours (DuckDB reads parquet timestamps as UTC)
# 9:15 AM IST = 3:45 AM UTC = 225 min
# 3:30 PM IST = 10:00 AM UTC = 600 min
MARKET_OPEN_UTC_MIN  = 225
MARKET_CLOSE_UTC_MIN = 600

# PyArrow schema
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
        logging.FileHandler(LOG_DIR / "resample_fno.log"),
    ],
)
log = logging.getLogger(__name__)


# ── DuckDB SQL Aggregation ─────────────────────────────────────────────────────

def resample_with_duckdb(src_path: Path, interval: str) -> pd.DataFrame:
    """Resample a 1min parquet file to the target interval using DuckDB SQL."""
    src = str(src_path)

    if interval == "5min":
        bucket = "INTERVAL 5 MINUTES"
    elif interval == "15min":
        bucket = "INTERVAL 15 MINUTES"
    else:
        raise ValueError(f"Unsupported interval: {interval}")

    sql = f"""
        SELECT
            TIME_BUCKET({bucket}, time::TIMESTAMPTZ) AS time,
            FIRST(open  ORDER BY time) AS open,
            MAX(high)                  AS high,
            MIN(low)                   AS low,
            LAST(close  ORDER BY time) AS close,
            SUM(volume)                AS volume
        FROM read_parquet('{src}')
        WHERE (EXTRACT(HOUR FROM time) * 60 + EXTRACT(MINUTE FROM time))
              BETWEEN {MARKET_OPEN_UTC_MIN} AND {MARKET_CLOSE_UTC_MIN}
        GROUP BY 1
        ORDER BY 1
    """

    con = duckdb.connect()
    df  = con.execute(sql).df()
    con.close()
    return df


# ── Helpers ────────────────────────────────────────────────────────────────────

def is_up_to_date(src_path: Path, dst_path: Path) -> bool:
    """Return True if destination exists and is newer than the source."""
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
    p = argparse.ArgumentParser(description="Resample FnO 1-min options data to 5min/15min")
    p.add_argument("--index",   help="Process a single index (e.g. NIFTY, BANKNIFTY)")
    p.add_argument("--type",    choices=["CE", "PE"], help="Process a single option type")
    p.add_argument("--force",   action="store_true", help="Overwrite existing files")
    p.add_argument("--dry-run", action="store_true", help="Preview without writing")
    return p.parse_args()


def main():
    args = parse_args()

    indices = [args.index.upper()] if args.index else FNO_INDICES
    types   = [args.type]          if args.type  else OPTION_TYPES

    # Collect all 1min source directories
    work_items = []  # list of (index, opt_type, src_1min_dir, strike_file)
    for idx in indices:
        for opt in types:
            src_dir = CANDLES_DIR / idx / opt / "1min"
            if not src_dir.exists():
                log.warning(f"  No 1min data found: {src_dir} — skipping")
                continue
            parquet_files = sorted(
                f for f in src_dir.glob("*.parquet")
                if not f.name.startswith("._")
            )
            for f in parquet_files:
                work_items.append((idx, opt, f))

    total = len(work_items)
    if total == 0:
        log.warning("No FnO 1min parquet files found. Check the data directory.")
        sys.exit(1)

    log.info("=" * 70)
    log.info("  FnO 1-Minute → Resample (5min / 15min)")
    log.info(f"  Indices         : {', '.join(indices)}")
    log.info(f"  Option types    : {', '.join(types)}")
    log.info(f"  Strike files    : {total}")
    log.info(f"  Targets         : {', '.join(RESAMPLE_TARGETS)}")
    log.info(f"  Force overwrite : {args.force}")
    log.info(f"  Dry run         : {args.dry_run}")
    log.info("=" * 70)

    t_start  = time.time()
    updated  = 0
    skipped  = 0
    errors   = 0

    for i, (idx, opt, src_path) in enumerate(work_items, 1):
        fname = src_path.name  # e.g. dhan_ec0_24000.parquet

        file_updated = False
        for interval in RESAMPLE_TARGETS:
            dst_dir  = CANDLES_DIR / idx / opt / interval
            dst_path = dst_dir / fname

            if not args.force and is_up_to_date(src_path, dst_path):
                skipped += 1
                continue

            if args.dry_run:
                log.info(f"  [{i}/{total}] {idx}/{opt}/{interval}/{fname}: would resample")
                continue

            try:
                df = resample_with_duckdb(src_path, interval)
                if df.empty:
                    log.warning(f"  [{i}/{total}] {idx}/{opt}/{interval}/{fname}: empty — skipping")
                    skipped += 1
                    continue

                save_parquet(df, dst_path)
                file_updated = True

            except Exception as e:
                log.error(f"  [{i}/{total}] {idx}/{opt}/{interval}/{fname}: ERROR — {e}")
                errors += 1

        if file_updated:
            updated += 1

        # Progress every 100 files
        if i % 100 == 0:
            elapsed = time.time() - t_start
            pct = i / total * 100
            eta = (elapsed / i) * (total - i)
            log.info(f"  Progress: {i}/{total} ({pct:.0f}%) | ETA: {eta:.0f}s")

    elapsed = time.time() - t_start
    log.info("=" * 70)
    log.info("  FnO RESAMPLE COMPLETE")
    log.info(f"  Strike files updated : {updated}")
    log.info(f"  Skipped              : {skipped}")
    log.info(f"  Errors               : {errors}")
    log.info(f"  Elapsed              : {elapsed / 60:.1f} minutes")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
