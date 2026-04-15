#!/usr/bin/env python3
"""
daily_updater.py — Daily incremental updater for historical OHLCV data.

Detects the last date in each Parquet file and downloads only the gap.
Designed to run once daily after market close (3:45 PM IST) via cron.

Covers:
  1. NIFTY 50 stocks     → data/candles/NIFTY500/{SYMBOL}/{interval}.parquet
  2. Index underlying    → data/underlying/{INDEX}/{interval}.parquet
  3. FnO expired options → data/candles/{INDEX}/{CE|PE}/{interval}/dhan_ec1_*.parquet

Usage:
  python daily_updater.py                 # update everything
  python daily_updater.py --stocks-only   # only NIFTY500 stocks
  python daily_updater.py --indices-only  # only index underlying
  python daily_updater.py --fno-only      # only FnO expired options
  python daily_updater.py --dry-run       # preview without downloading
  python daily_updater.py --limit 5       # test with first 5 stocks

Cron example (run daily at 3:45 PM IST, resample immediately after):
  45 15 * * 1-5 cd /path/to/Pytrader && python3 data-scripts/daily_updater.py >> data/logs/daily_update.log 2>&1 && python3 data-scripts/resample_nifty50.py >> data/logs/resample_nifty50.log 2>&1 && python3 data-scripts/resample_fno.py >> data/logs/resample_fno.log 2>&1
"""

import argparse
import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import date, timedelta, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv

# ── Setup ─────────────────────────────────────────────────────────────────────

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))
from dhan_client import DhanClient

PROJECT_ROOT = Path(__file__).parent.parent
NIFTY500_DIR = PROJECT_ROOT / "data" / "candles" / "NIFTY500"
UNDERLYING_DIR = PROJECT_ROOT / "data" / "underlying"
FNO_DIR = PROJECT_ROOT / "data" / "candles"
MAPPING_FILE = Path(__file__).parent / "nifty50_dhan_mapping.json"

STOCK_INTERVALS = ["1min"]  # 5min/15min/1D derived via resample_nifty500.py
INDEX_INTERVALS = ["1min", "5min", "15min"]
FNO_INTERVALS = ["1min"]  # 5min/15min derived via resample_fno.py
FNO_OFFSETS = list(range(-10, 11))  # ATM-10 to ATM+10
FNO_OPT_TYPES = ["CE", "PE"]

INDICES = {
    "NIFTY": {"id": "13", "segment": "IDX_I", "instrument": "INDEX"},
    "BANKNIFTY": {"id": "25", "segment": "IDX_I", "instrument": "INDEX"},
    "FINNIFTY": {"id": "27", "segment": "IDX_I", "instrument": "INDEX"},
    "GIFTNIFTY": {"id": "5024", "segment": "IDX_I", "instrument": "INDEX"},
}

# NIFTY 50 blue-chip stocks (Deep historical data support)
NIFTY_50 = [
    "RELIANCE",
    "TCS",
    "HDFCBANK",
    "ICICIBANK",
    "BHARTIARTL",
    "SBIN",
    "INFY",
    "LICI",
    "ITC",
    "HINDUNILVR",
    "LT",
    "BAJFINANCE",
    "HCLTECH",
    "MARUTI",
    "SUNPHARMA",
    "TATAMOTORS",
    "TATASTEEL",
    "KOTAKBANK",
    "TITAN",
    "NTPC",
    "ULTRACEMCO",
    "ONGC",
    "AXISBANK",
    "WIPRO",
    "NESTLEIND",
    "M&M",
    "POWERGRID",
    "GRASIM",
    "JSWSTEEL",
    "ASIANPAINT",
    "HDFCLIFE",
    "SBILIFE",
    "BRITANNIA",
    "EICHERMOT",
    "APOLLOHOSP",
    "DIVISLAB",
    "TATACONSUM",
    "BAJAJFINSV",
    "HINDALCO",
    "TECHM",
    "DRREDDY",
    "CIPLA",
    "INDUSINDBK",
    "ADANIPORTS",
    "ADANIENT",
    "BPCL",
    "COALINDIA",
    "HEROMOTOCO",
    "UPL",
    "TATAPOWER",
]

SCHEMA = pa.schema(
    [
        ("time", pa.timestamp("s")),
        ("open", pa.float32()),
        ("high", pa.float32()),
        ("low", pa.float32()),
        ("close", pa.float32()),
        ("volume", pa.int64()),
    ]
)

OPTIONS_SCHEMA = pa.schema(
    [
        ("time", pa.timestamp("s")),
        ("open", pa.float32()),
        ("high", pa.float32()),
        ("low", pa.float32()),
        ("close", pa.float32()),
        ("volume", pa.int64()),
        ("oi", pa.float64()),
        ("iv", pa.float32()),
        ("spot", pa.float32()),
    ]
)

LOG_DIR = PROJECT_ROOT / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
IST = ZoneInfo("Asia/Kolkata")
MARKET_CLOSE_MINUTES_IST = 15 * 60 + 30

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "daily_update.log"),
    ],
)
log = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────


def get_last_date(parquet_path: Path) -> date | None:
    """Read a Parquet file and return the last date present."""
    if not parquet_path.exists():
        return None
    try:
        try:
            df = pd.read_parquet(parquet_path, columns=["time"])
        except Exception:
            df = pd.read_parquet(parquet_path, columns=["time"], engine="fastparquet")
        if df.empty:
            return None
        return pd.to_datetime(df["time"]).max().date()
    except Exception:
        return None


def next_business_day(d: date) -> date:
    """Return the next business day after d."""
    nd = d + timedelta(days=1)
    while nd.weekday() >= 5:  # Skip weekends
        nd += timedelta(days=1)
    return nd


def previous_business_day(d: date) -> date:
    """Return the previous business day before d."""
    pd_ = d - timedelta(days=1)
    while pd_.weekday() >= 5:  # Skip weekends
        pd_ -= timedelta(days=1)
    return pd_


def resolve_effective_end_date(requested_end: date) -> tuple[date, datetime]:
    """
    Resolve the trading date to update based on current IST market session.

    Before IST market close, requesting today's date should fall back to the
    previous business day because the current session's full data is not yet
    available for the daily batch update.
    """
    now_ist = datetime.now(IST)
    ist_today = now_ist.date()
    effective_end = min(requested_end, ist_today)

    if effective_end.weekday() >= 5:
        effective_end = previous_business_day(effective_end)

    now_minutes = now_ist.hour * 60 + now_ist.minute
    if effective_end == ist_today and now_minutes < MARKET_CLOSE_MINUTES_IST:
        effective_end = previous_business_day(effective_end)

    return effective_end, now_ist


def _normalize_time_to_utc_naive(series: pd.Series) -> pd.Series:
    """
    Normalize a timestamp series to naive UTC for stable parquet storage.

    Handles strings, tz-aware timestamps, and legacy tz-naive values that were
    intended to represent Asia/Kolkata wall-clock time.
    """
    parsed = pd.to_datetime(series, errors="coerce")
    if parsed.isna().all():
        raise ValueError("time column could not be parsed as datetimes")

    if parsed.dt.tz is None:
        return (
            parsed.dt.tz_localize("Asia/Kolkata")
            .dt.tz_convert("UTC")
            .dt.tz_localize(None)
        )

    return parsed.dt.tz_convert("UTC").dt.tz_localize(None)


def candles_to_df_intraday(raw: list) -> pd.DataFrame:
    """Convert raw intraday candles to DataFrame with market hours filter."""
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw)[["time", "open", "high", "low", "close", "volume"]]
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce").dt.tz_convert(
        "Asia/Kolkata"
    )
    df = df.dropna(subset=["time"])
    # Filter market hours
    t = df["time"]
    if t.dt.hour.max() > 0:
        df = df[
            ((t.dt.hour > 9) | ((t.dt.hour == 9) & (t.dt.minute >= 15)))
            & ((t.dt.hour < 15) | ((t.dt.hour == 15) & (t.dt.minute <= 30)))
        ]
    return df.drop_duplicates("time").sort_values("time").reset_index(drop=True)


def candles_to_df_daily(raw: list) -> pd.DataFrame:
    """Convert raw daily candles to DataFrame."""
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw)[["time", "open", "high", "low", "close", "volume"]]
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce").dt.tz_convert(
        "Asia/Kolkata"
    )
    df = df.dropna(subset=["time"])
    df["time"] = df["time"].dt.normalize()
    return df.drop_duplicates("time").sort_values("time").reset_index(drop=True)


def merge_and_save(new_df: pd.DataFrame, path: Path, schema: pa.Schema = SCHEMA) -> int:
    """Merge new data with existing Parquet file, dedup, and save.

    Args:
        new_df:  New candle data to append.
        path:    Destination parquet file.
        schema:  Arrow schema to enforce on write (default: SCHEMA with volume;
                 pass OPTIONS_SCHEMA for options which include oi, iv, spot).
    """
    if new_df.empty:
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            try:
                existing = pd.read_parquet(path)
            except Exception:
                existing = pd.read_parquet(path, engine="fastparquet")

            # CRITICAL: Normalize both to naive UTC *before* concat to prevent Pandas
            # from coercing mixed tz-aware and tz-naive arrays into NaTs!
            existing["time"] = _normalize_time_to_utc_naive(existing["time"])
            new_df["time"] = _normalize_time_to_utc_naive(new_df["time"])

            combined = pd.concat([existing, new_df], ignore_index=True)
        except Exception as e:
            log.error(
                f"FATAL ERROR: Could not read existing file {path} ({e}). Attempting to overwrite it will cause permanent historical data loss! Skipping."
            )
            return 0
    else:
        new_df["time"] = _normalize_time_to_utc_naive(new_df["time"])
        combined = new_df

    combined = (
        combined.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    )

    # Cast columns present in the target schema
    combined["time"] = combined["time"].astype("datetime64[s]")
    combined["open"] = combined["open"].astype("float32")
    combined["high"] = combined["high"].astype("float32")
    combined["low"] = combined["low"].astype("float32")
    combined["close"] = combined["close"].astype("float32")
    if "volume" in [f.name for f in schema]:
        combined["volume"] = combined["volume"].astype("int64")

    # Keep only the columns defined in the schema
    cols = [f.name for f in schema]
    combined = combined[[c for c in cols if c in combined.columns]]

    table = pa.Table.from_pandas(combined, schema=schema, preserve_index=False)
    pq.write_table(table, path, compression="lz4")
    return len(combined)


# ── Update Functions ──────────────────────────────────────────────────────────


def update_nifty500_stocks(
    client: DhanClient, end_date: date, dry_run: bool = False, limit: int = None
):
    """Update NIFTY500 stocks with missing data."""
    log.info("=" * 60)
    log.info("  NIFTY 50 STOCKS UPDATE")
    log.info("=" * 60)

    if not MAPPING_FILE.exists():
        log.error(f"Missing {MAPPING_FILE}")
        return

    with open(MAPPING_FILE) as f:
        mapping = json.load(f)

    # Strictly target NIFTY 50 for deep history stability
    symbols = [s for s in NIFTY_50 if s in mapping]
    if limit:
        symbols = symbols[:limit]

    total_symbols = len(symbols)
    start_time = time.time()

    total_updated = 0
    total_skipped = 0
    method_stats = {"daily": 0, "intraday_d": 0, "intraday_1min": 0, "failed": 0}
    failed_symbols = []

    log.info(f"Starting NIFTY 50 update: {total_symbols} symbols")

    for i, sym in enumerate(symbols, 1):
        sec_id = mapping[sym]
        sym_updated = False
        method_used = None
        attempted_1d = False

        for interval in STOCK_INTERVALS:
            out_path = NIFTY500_DIR / sym / f"{interval}.parquet"
            last = get_last_date(out_path)

            if last and last >= end_date:
                total_skipped += 1
                continue

            start = next_business_day(last) if last else end_date
            if start > end_date:
                total_skipped += 1
                continue

            if dry_run:
                log.info(
                    f"  [{i}/{len(symbols)}] {sym} {interval}: would download {start} → {end_date}"
                )
                continue

            # Fetch data
            if interval == "1D":
                # The daily historical endpoint (get_historical_daily_candles) trails by a few days
                # and throws DH-905 for very recent dates.
                # We use it first, but fallback to get_intraday_candles with 'D' interval if needed.
                attempted_1d = True
                raw = client.get_historical_daily_candles(
                    security_id=sec_id,
                    exchange_segment="NSE_EQ",
                    instrument="EQUITY",
                    from_date=start.strftime("%Y-%m-%d"),
                    to_date=end_date.strftime("%Y-%m-%d"),
                    expiry_code=0,
                )
                time.sleep(1.2)

                # Track method: daily endpoint succeeded
                if raw:
                    method_used = "daily"

                # Fallback to intraday endpoint natively supporting 'D' interval up to 90 days
                if not raw:
                    raw = client.get_intraday_candles(
                        security_id=sec_id,
                        exchange_segment="NSE_EQ",
                        instrument="EQUITY",
                        interval="D",
                        from_datetime=f"{start} 09:00:00",
                        to_datetime=f"{end_date} 16:00:00",
                    )
                    time.sleep(1.0)

                    # Track method: intraday D fallback succeeded
                    if raw:
                        method_used = "intraday_d"

                # Secondary fallback: fetch 1-minute data and aggregate it into daily candles
                if not raw:
                    # Track method: 1min aggregation fallback
                    method_used = "intraday_1min"
                    raw_1m = client.get_intraday_candles(
                        security_id=sec_id,
                        exchange_segment="NSE_EQ",
                        instrument="EQUITY",
                        interval="1",
                        from_datetime=f"{start} 09:00:00",
                        to_datetime=f"{end_date} 16:00:00",
                    )
                    time.sleep(1.0)
                    if raw_1m:
                        df_1m = pd.DataFrame(raw_1m)
                        df_1m["time"] = (
                            pd.to_datetime(df_1m["time"])
                            .dt.tz_localize(None)
                            .dt.tz_localize("Asia/Kolkata")
                        )

                        # Apply market hours filter
                        t = df_1m["time"]
                        df_1m = df_1m[
                            ((t.dt.hour > 9) | ((t.dt.hour == 9) & (t.dt.minute >= 15)))
                            & (
                                (t.dt.hour < 15)
                                | ((t.dt.hour == 15) & (t.dt.minute <= 30))
                            )
                        ]

                        if not df_1m.empty:
                            df_1m.set_index("time", inplace=True)
                            df_daily = (
                                df_1m.resample("D")
                                .agg(
                                    {
                                        "open": "first",
                                        "high": "max",
                                        "low": "min",
                                        "close": "last",
                                        "volume": "sum",
                                    }
                                )
                                .dropna()
                                .reset_index()
                            )
                            merge_and_save(df_daily, out_path)
                            sym_updated = True
                            continue  # skip the normal df save

                if raw:
                    df = candles_to_df_daily(raw)
                    if not df.empty:
                        merge_and_save(df, out_path)
                        sym_updated = True
            else:
                interval_str = interval
                raw = client.get_intraday_candles(
                    security_id=sec_id,
                    exchange_segment="NSE_EQ",
                    instrument="EQUITY",
                    interval=interval_str,
                    from_datetime=f"{start} 09:00:00",
                    to_datetime=f"{end_date} 16:00:00",
                )
                time.sleep(1.0)
                if raw:
                    df = candles_to_df_intraday(raw)
                    if not df.empty:
                        merge_and_save(df, out_path)
                        sym_updated = True

        if sym_updated:
            total_updated += 1
            # Track method stats
            if method_used:
                method_stats[method_used] = method_stats.get(method_used, 0) + 1
        else:
            # Mark as failed if we attempted 1D but didn't get any update
            if attempted_1d and not sym_updated:
                method_stats["failed"] = method_stats.get("failed", 0) + 1
                failed_symbols.append(sym)

        # Calculate ETA and log progress for each symbol
        elapsed = time.time() - start_time
        avg_time = elapsed / i
        remaining = total_symbols - i
        eta_seconds = avg_time * remaining
        eta_str = (datetime.now() + timedelta(seconds=eta_seconds)).strftime("%H:%M:%S")

        # Log progress for every symbol (method: ✓ or ✗)
        status_icon = "✓" if sym_updated else "✗"
        method_str = method_used if method_used else "none"
        log.info(
            f"  [{i}/{total_symbols}] {sym:15} {status_icon} ({method_str:12}) | "
            f"ETA: {eta_str} | Avg: {avg_time:.1f}s/symbol"
        )

    # Summary report
    total_elapsed = time.time() - start_time
    log.info("=" * 60)
    log.info("  NIFTY 50 UPDATE COMPLETE")
    log.info("=" * 60)
    log.info(f"  Total symbols:     {total_symbols}")
    log.info(f"  Updated:           {total_updated}")
    log.info(f"  Skipped (up-to-date): {total_skipped}")
    log.info("-" * 60)
    log.info("  Method breakdown:")
    log.info(f"    - daily endpoint:      {method_stats.get('daily', 0)}")
    log.info(f"    - intraday (D):        {method_stats.get('intraday_d', 0)}")
    log.info(f"    - intraday (1min agg): {method_stats.get('intraday_1min', 0)}")
    log.info(f"    - failed:              {method_stats.get('failed', 0)}")
    log.info("-" * 60)
    log.info(f"  Total time:        {timedelta(seconds=int(total_elapsed))}")
    log.info(f"  Avg time/symbol:   {total_elapsed / total_symbols:.1f} seconds")
    if failed_symbols:
        log.warning(f"  Failed symbols: {', '.join(failed_symbols[:10])}")
        if len(failed_symbols) > 10:
            log.warning(f"                    ... and {len(failed_symbols) - 10} more")
    log.info("=" * 60)


def update_index_underlying(client: DhanClient, end_date: date, dry_run: bool = False):
    """Update index underlying data with missing candles."""
    log.info("=" * 60)
    log.info("  INDEX UNDERLYING UPDATE")
    log.info("=" * 60)

    total_updated = 0

    for index, cfg in INDICES.items():
        for interval in INDEX_INTERVALS:
            out_path = UNDERLYING_DIR / index / f"{interval}.parquet"
            last = get_last_date(out_path)

            if last and last >= end_date:
                log.info(f"  {index} {interval}: already up-to-date ({last})")
                continue

            start = next_business_day(last) if last else end_date
            if start > end_date:
                continue

            if dry_run:
                log.info(f"  {index} {interval}: would download {start} → {end_date}")
                continue

            raw = client.get_intraday_candles(
                security_id=cfg["id"],
                exchange_segment=cfg["segment"],
                instrument=cfg["instrument"],
                interval=interval,
                from_datetime=f"{start} 09:00:00",
                to_datetime=f"{end_date} 16:00:00",
            )
            time.sleep(1.0)

            if raw:
                df = candles_to_df_intraday(raw)
                if not df.empty:
                    total = merge_and_save(df, out_path)
                    log.info(
                        f"  {index} {interval}: +{len(df)} candles (total: {total:,})"
                    )
                    total_updated += 1
            else:
                log.warning(f"  {index} {interval}: no data for {start} → {end_date}")

    log.info(f"  Index underlying done: {total_updated} intervals updated")


def update_fno_options(client: DhanClient, end_date: date, dry_run: bool = False):
    """Update FnO expired options data for the most recent expiry."""
    log.info("=" * 60)
    log.info("  FnO EXPIRED OPTIONS UPDATE")
    log.info("=" * 60)

    # Expiry code 1 = most recently expired weekly
    expiry_code = 1
    fno_indices = ["NIFTY", "BANKNIFTY", "FINNIFTY"]

    total_jobs = (
        len(fno_indices) * len(FNO_OFFSETS) * len(FNO_OPT_TYPES) * len(FNO_INTERVALS)
    )

    if dry_run:
        log.info(f"  Would download {total_jobs} jobs (expiry_code={expiry_code})")
        return

    downloaded = 0
    empty = 0

    for idx in fno_indices:
        for opt in FNO_OPT_TYPES:
            for interval in FNO_INTERVALS:
                for offset in FNO_OFFSETS:
                    # Build date window for this expiry
                    EXPIRY_WEEKDAY = {"NIFTY": 3, "BANKNIFTY": 2, "FINNIFTY": 1}
                    today = date.today()
                    target_wd = EXPIRY_WEEKDAY[idx]
                    days_since = (today.weekday() - target_wd) % 7
                    if days_since == 0:
                        days_since = 7
                    estimated_expiry = today - timedelta(days=days_since)
                    start_date = estimated_expiry - timedelta(days=12)
                    end_dt = estimated_expiry + timedelta(days=1)

                    candles = client.get_expired_options_full(
                        index=idx,
                        strike_offset=offset,
                        option_type=opt,
                        expiry_flag="WEEK",
                        expiry_code=expiry_code,
                        start=start_date,
                        end=end_dt,
                        interval=interval,
                    )

                    if candles:
                        # Group by strike and save
                        by_strike = defaultdict(list)
                        for c in candles:
                            by_strike[int(c["strike"])].append(c)

                        for strike, rows in by_strike.items():
                            df = pd.DataFrame(rows)
                            df["time"] = pd.to_datetime(df["time"]).dt.tz_localize(None)
                            # Include oi, iv, spot when available
                            cols = ["time", "open", "high", "low", "close", "volume"]
                            if "oi" in df.columns:
                                cols.extend(["oi", "iv", "spot"])
                            df = (
                                df[cols]
                                .drop_duplicates(subset=["time"])
                                .sort_values("time")
                                .reset_index(drop=True)
                            )
                            df["time"] = df["time"].dt.tz_localize("Asia/Kolkata")

                            out_dir = FNO_DIR / idx / opt / interval
                            out_dir.mkdir(parents=True, exist_ok=True)
                            out_path = (
                                out_dir / f"dhan_ec{expiry_code}_{strike}.parquet"
                            )

                            schema = OPTIONS_SCHEMA if "oi" in df.columns else SCHEMA
                            merge_and_save(df, out_path, schema=schema)

                        downloaded += 1
                    else:
                        empty += 1

                    if (downloaded + empty) % 100 == 0:
                        log.info(f"  FnO progress: {downloaded} data | {empty} empty")

    log.info(f"  FnO done: {downloaded} with data | {empty} empty")


def update_fno_live_options(client: DhanClient, end_date: date, dry_run: bool = False):
    """Update current-week (ec0) options using active instrument resolution.

    This replaces the old expiry_code=0 approach which now returns DH-905.
    Flow:
      1. Discover current active weekly expiry via get_expiry_list()
      2. Get ATM strike from underlying data
      3. Generate strike list: ATM-10 to ATM+10
      4. Resolve active instrument IDs via resolve_active_weekly_options()
      5. Fetch intraday candles via get_active_option_intraday()
      6. Write to dhan_ec0_{strike}.parquet

    Files saved as: data/candles/{INDEX}/{CE|PE}/{interval}/dhan_ec0_{strike}.parquet
    (separate from expired ec1_* files to avoid mixing live vs settled prices)
    """
    log.info("=" * 60)
    log.info("  FnO LIVE (CURRENT-WEEK) OPTIONS UPDATE  [Active Instruments]")
    log.info("=" * 60)

    fno_indices = ["NIFTY", "BANKNIFTY", "FINNIFTY"]

    if dry_run:
        for idx in fno_indices:
            expiry_list = client.get_expiry_list(idx)
            if not expiry_list:
                log.info(f"  {idx}: would skip (no expiry list)")
                continue

            today_date = date.today()
            valid_expiries = [
                e for e in expiry_list if pd.to_datetime(e).date() >= today_date
            ]
            if not valid_expiries:
                log.info(f"  {idx}: would skip (no valid expiry)")
                continue

            current_expiry = valid_expiries[0]

            strikes = [25000 + offset * 100 for offset in FNO_OFFSETS]
            contracts_ce = client.resolve_active_weekly_options(
                idx, current_expiry, strikes, "CE"
            )
            contracts_pe = client.resolve_active_weekly_options(
                idx, current_expiry, strikes, "PE"
            )

            log.info(
                f"  {idx}: would resolve {len(contracts_ce)} CE + {len(contracts_pe)} PE "
                f"for expiry {current_expiry}"
            )

        total = (
            len(fno_indices)
            * len(FNO_OFFSETS)
            * len(FNO_OPT_TYPES)
            * len(FNO_INTERVALS)
        )
        log.info(f"  Would download up to {total} live jobs (active instrument path)")
        return

    downloaded = 0
    empty = 0
    unresolved = 0

    for idx in fno_indices:
        expiry_list = client.get_expiry_list(idx)
        if not expiry_list:
            log.warning(f"  {idx}: could not get expiry list, skipping")
            continue

        today_date = date.today()
        valid_expiries = [
            e for e in expiry_list if pd.to_datetime(e).date() >= today_date
        ]
        if not valid_expiries:
            log.warning(f"  {idx}: no valid future expiry found, skipping")
            continue

        current_expiry = valid_expiries[0]
        log.info(f"  {idx}: current expiry = {current_expiry}")

        underlying_path = UNDERLYING_DIR / idx / "1min.parquet"
        atm_strike = None
        if underlying_path.exists():
            try:
                df = pd.read_parquet(underlying_path, columns=["time", "close"])
                if not df.empty:
                    last_close = df["close"].iloc[-1]
                    atm_strike = int(round(last_close / 100) * 100)
            except Exception as e:
                log.warning(f"  {idx}: could not read ATM from underlying: {e}")

        if not atm_strike:
            atm_strike = {"NIFTY": 25000, "BANKNIFTY": 52000, "FINNIFTY": 22000}.get(
                idx, 25000
            )
            log.warning(f"  {idx}: using fallback ATM = {atm_strike}")

        strikes = [atm_strike + offset * 100 for offset in FNO_OFFSETS]
        log.info(
            f"  {idx}: strikes {strikes[0]} → {strikes[-1]} ({len(strikes)} strikes)"
        )

        expiry_dt = pd.to_datetime(current_expiry)
        week_start = expiry_dt - timedelta(days=expiry_dt.weekday())
        week_start_date = week_start.date()

        if week_start_date > end_date:
            log.info(f"  {idx}: week starts {week_start_date} > {end_date}, skipping")
            continue

        for opt in FNO_OPT_TYPES:
            contracts = client.resolve_active_weekly_options(
                index=idx,
                expiry_date=current_expiry,
                strikes=strikes,
                option_type=opt,
            )

            if not contracts:
                log.warning(
                    f"  {idx} {opt}: no contracts resolved for {current_expiry}"
                )
                unresolved += len(strikes)
                continue

            log.info(f"  {idx} {opt}: resolved {len(contracts)} contracts")

            for interval in FNO_INTERVALS:
                for contract in contracts:
                    candles = client.get_active_option_intraday(
                        security_id=contract["security_id"],
                        exchange_segment=contract["exchange_segment"],
                        instrument=contract["instrument"],
                        interval=interval,
                        start_dt=f"{week_start_date} 09:15:00",
                        end_dt=f"{end_date} 15:30:00",
                        oi=True,
                    )

                    if candles:
                        df = pd.DataFrame(candles)
                        df["time"] = _normalize_time_to_utc_naive(df["time"])

                        cols = ["time", "open", "high", "low", "close", "volume"]
                        if "oi" in df.columns:
                            cols.append("oi")

                        df = (
                            df[cols]
                            .drop_duplicates(subset=["time"])
                            .sort_values("time")
                            .reset_index(drop=True)
                        )

                        out_dir = FNO_DIR / idx / opt / interval
                        out_dir.mkdir(parents=True, exist_ok=True)
                        out_path = out_dir / f"dhan_ec0_{contract['strike']}.parquet"

                        merge_and_save(df, out_path, schema=SCHEMA)
                        downloaded += 1
                    else:
                        empty += 1

                    if (downloaded + empty) % 50 == 0:
                        log.info(
                            f"  Live FnO progress: {downloaded} data | {empty} empty | {unresolved} unresolved"
                        )

    log.info(
        f"  Live FnO done: {downloaded} with data | {empty} empty | {unresolved} unresolved"
    )


# ── Main ──────────────────────────────────────────────────────────────────────


def parse_args():
    p = argparse.ArgumentParser(description="Daily Incremental Data Updater")
    p.add_argument(
        "--end",
        default=str(datetime.now(IST).date()),
        help="End date for update in YYYY-MM-DD (default: current IST date)",
    )
    p.add_argument(
        "--respect-market-session",
        action="store_true",
        default=True,
        help="Before IST market open, fall back to the previous business day",
    )
    p.add_argument("--dry-run", action="store_true", help="Preview without downloading")
    p.add_argument(
        "--stocks-only", action="store_true", help="Only update NIFTY500 stocks"
    )
    p.add_argument(
        "--indices-only", action="store_true", help="Only update index underlying"
    )
    p.add_argument(
        "--fno-only",
        action="store_true",
        help="Only update FnO expired options (expiry_code=1)",
    )
    p.add_argument(
        "--fno-live-only",
        action="store_true",
        help="Only update current-week live options (expiry_code=0)",
    )
    p.add_argument(
        "--limit", type=int, help="Process first N stocks only (for testing)"
    )
    return p.parse_args()


def main():
    args = parse_args()
    requested_end_date = date.fromisoformat(args.end)
    now_ist = datetime.now(IST)
    if args.respect_market_session:
        end_date, now_ist = resolve_effective_end_date(requested_end_date)
    else:
        end_date = requested_end_date
    do_all = not (
        args.stocks_only or args.indices_only or args.fno_only or args.fno_live_only
    )

    client = DhanClient(
        os.environ["DHAN_CLIENT_ID"].strip(),
        os.environ["DHAN_ACCESS_TOKEN"].strip(),
    )

    if not args.dry_run:
        if not client.verify_connection():
            log.error("Dhan connection failed — check DHAN_ACCESS_TOKEN in .env")
            sys.exit(1)

    mode = (
        "ALL"
        if do_all
        else "stocks"
        if args.stocks_only
        else "indices"
        if args.indices_only
        else "fno-live"
        if args.fno_live_only
        else "fno"
    )
    log.info("=" * 60)
    log.info("  DAILY INCREMENTAL UPDATER")
    log.info(f"  Requested end date : {requested_end_date}")
    log.info(f"  Effective end date : {end_date}")
    log.info(f"  Current IST        : {now_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    log.info(f"  Dry run  : {args.dry_run}")
    log.info(f"  Mode     : {mode}")
    log.info("=" * 60)

    start_time = time.time()

    if do_all or args.indices_only:
        update_index_underlying(client, end_date, args.dry_run)

    if do_all or args.stocks_only:
        update_nifty500_stocks(client, end_date, args.dry_run, args.limit)

    if do_all or args.fno_only:
        update_fno_options(client, end_date, args.dry_run)

    if do_all or args.fno_live_only:
        update_fno_live_options(client, end_date, args.dry_run)

    elapsed = time.time() - start_time
    log.info("=" * 60)
    log.info(f"  DAILY UPDATE COMPLETE in {elapsed / 60:.1f} minutes")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
