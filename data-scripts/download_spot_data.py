"""
download_spot_data.py — Download Index Spot OHLCV from Dhan API.

Saves to:
  data/underlying/{INDEX}/1min.parquet
  data/underlying/{INDEX}/5min.parquet
  data/underlying/{INDEX}/15min.parquet

Usage:
  python download_spot_data.py                     # 2020/2022 → today
  python download_spot_data.py --start 2023-01-01  # custom start date
  python download_spot_data.py --intervals 5min 15min
  python download_spot_data.py --indices NIFTY BANKNIFTY
  python download_spot_data.py --force             # redownload everything

Dhan intraday data limits:
  NIFTY: Available from Jan 2020
  BANKNIFTY/FINNIFTY: Available from Jan 2022
"""

import argparse
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))
from dhan_client import DhanClient

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent.parent / "data" / "underlying"
CHUNK_DAYS    = 85          # safe under Dhan's 88-day limit
INTERVALS     = ["1min", "5min", "15min"]

INDICES = {
    "NIFTY":     {"id": "13", "start": date(2020, 1, 1)},
    "BANKNIFTY": {"id": "25", "start": date(2022, 1, 1)},
    "FINNIFTY":  {"id": "27", "start": date(2022, 1, 1)},
    "GIFTNIFTY": {"id": "5024", "start": date(2023, 10, 1)},  # GIFT NIFTY (NSE IX - GIFT City)
}

SCHEMA = pa.schema([
    ("time",   pa.timestamp("s", tz="Asia/Kolkata")),
    ("open",   pa.float32()),
    ("high",   pa.float32()),
    ("low",    pa.float32()),
    ("close",  pa.float32()),
    ("volume", pa.int64()),
])

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(BASE_DIR.parent / "logs" / "spot_download.log"
                            if (BASE_DIR.parent / "logs").exists()
                            else "/tmp/spot_download.log"),
    ]
)
log = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def date_chunks(start: date, end: date, chunk_days: int):
    """Yield (chunk_start, chunk_end) pairs covering [start, end]."""
    cur = start
    while cur <= end:
        yield cur, min(cur + timedelta(days=chunk_days - 1), end)
        cur += timedelta(days=chunk_days)


def candles_to_df(raw: list) -> pd.DataFrame:
    """Convert DhanClient normalized candle list to a clean DataFrame."""
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw)[["time", "open", "high", "low", "close", "volume"]]
    df["time"] = pd.to_datetime(df["time"], utc=False).dt.tz_localize(
        None).dt.tz_localize("Asia/Kolkata")
    # Keep only market hours 9:15 → 15:30
    t = df["time"]
    df = df[
        ((t.dt.hour > 9) | ((t.dt.hour == 9) & (t.dt.minute >= 15))) &
        ((t.dt.hour < 15) | ((t.dt.hour == 15) & (t.dt.minute <= 30)))
    ]
    return df.drop_duplicates("time").sort_values("time").reset_index(drop=True)


def load_existing(path: Path) -> pd.DataFrame:
    if path.exists():
        try:
            return pd.read_parquet(path)
        except Exception:
            pass
    return pd.DataFrame()


def merge_and_save(new_df: pd.DataFrame, path: Path):
    """Merge with existing file, deduplicate, write back."""
    existing = load_existing(path)
    if not existing.empty:
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    combined = (combined
                .drop_duplicates("time")
                .sort_values("time")
                .reset_index(drop=True))

    # Cast to schema-compatible types
    combined["time"]   = combined["time"].astype("datetime64[s, Asia/Kolkata]")
    combined["open"]   = combined["open"].astype("float32")
    combined["high"]   = combined["high"].astype("float32")
    combined["low"]    = combined["low"].astype("float32")
    combined["close"]  = combined["close"].astype("float32")
    combined["volume"] = combined["volume"].astype("int64")

    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(combined, schema=SCHEMA, preserve_index=False)
    pq.write_table(table, path, compression="lz4")
    return len(combined)


def already_covered(path: Path, start: date, end: date) -> bool:
    """Return True if the parquet file already has data for this date range."""
    df = load_existing(path)
    if df.empty:
        return False
    existing_dates = set(df["time"].dt.date)
    # Check if at least 80% of expected trading days are present
    chunk_dates = pd.bdate_range(str(start), str(end))
    expected = len(chunk_dates)
    present  = sum(1 for d in chunk_dates if d.date() in existing_dates)
    return expected > 0 and (present / expected) >= 0.80


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Download Index Spot OHLCV from Dhan")
    p.add_argument("--start", type=str,
                   help="Start date YYYY-MM-DD (overrides index defaults)")
    p.add_argument("--end", default=str(date.today()),
                   help="End date YYYY-MM-DD (default: today)")
    p.add_argument("--indices", nargs="+", default=list(INDICES.keys()),
                   choices=list(INDICES.keys()),
                   help="Indices to download (default: all three)")
    p.add_argument("--intervals", nargs="+", default=INTERVALS,
                   choices=INTERVALS,
                   help="Intervals to download (default: all three)")
    p.add_argument("--force", action="store_true",
                   help="Re-download even if chunk already covered")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be downloaded without calling API")
    return p.parse_args()


def main():
    args = parse_args()
    end_date = date.fromisoformat(args.end)

    client = DhanClient(
        os.environ["DHAN_CLIENT_ID"].strip(),
        os.environ["DHAN_ACCESS_TOKEN"].strip(),
    )

    if not args.dry_run:
        if not client.verify_connection():
            log.error("Dhan connection failed — check .env credentials")
            sys.exit(1)

    log.info("=" * 60)
    log.info(f"  F&O Spot Intraday Downloader")
    log.info(f"  Indices   : {', '.join(args.indices)}")
    log.info(f"  Intervals : {', '.join(args.intervals)}")
    log.info(f"  End Date  : {end_date}")
    log.info(f"  Dry run   : {args.dry_run}")
    log.info("=" * 60)

    for index in args.indices:
        idx_cfg = INDICES[index]
        start_date = date.fromisoformat(args.start) if args.start else idx_cfg["start"]
        
        log.info(f"\n{"="*40}")
        log.info(f"  Processing {index} from {start_date}")
        log.info(f"{"="*40}")

        for interval in args.intervals:
            out_path = BASE_DIR / index / f"{interval}.parquet"
            log.info(f"\n── Interval: {interval}  →  {out_path}")

            total_new = 0
            chunks = list(date_chunks(start_date, end_date, CHUNK_DAYS))
            for i, (cs, ce) in enumerate(chunks, 1):
                log.info(f"  Chunk {i}/{len(chunks)}: {cs} → {ce}")

                if not args.force and already_covered(out_path, cs, ce):
                    log.info(f"    ↳ Already covered, skipping")
                    continue

                if args.dry_run:
                    log.info(f"    ↳ [dry-run] would call /intraday {cs} → {ce}")
                    continue

                raw = client.get_intraday_candles(
                    security_id=idx_cfg["id"],
                    exchange_segment="IDX_I",
                    instrument="INDEX",
                    interval=interval,
                    from_datetime=f"{cs} 09:00:00",
                    to_datetime=f"{ce} 16:00:00",
                )

                if not raw:
                    log.warning(f"    ↳ No data returned for {cs} → {ce}")
                    continue

                df = candles_to_df(raw)
                if df.empty:
                    log.warning(f"    ↳ Empty after filtering for {cs} → {ce}")
                    continue

                total = merge_and_save(df, out_path)
                total_new += len(df)
                log.info(f"    ↳ {len(df)} new candles  |  file total: {total:,} rows")

            log.info(f"  Done {index} {interval}: {total_new:,} new candles written → {out_path}")

    log.info("\n" + "=" * 60)
    log.info("  Spot Download complete!")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
