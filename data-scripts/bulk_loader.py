"""
bulk_loader.py — Main entry point for FnO historical data download.

Strategy:
  - Angel Account 1  →  NIFTY  (dedicated)
  - Angel Account 2  →  BANKNIFTY  (dedicated)
  - Shoonya          →  FINNIFTY + all underlying spot indices

All 3 run in parallel threads → total download time ~1 hour.

Usage:
  python bulk_loader.py               # full 2-year download
  python bulk_loader.py --months 3    # last 3 months only (for testing)
  python bulk_loader.py --dry-run     # print job list, no API calls
"""

import argparse
import logging
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

from angel_client import AngelAccount, AngelClient, MAX_DAYS
from shoonya_client import ShoonyaClient
from expiry_calendar import get_weekly_expiries, get_atm_strikes, iter_contracts
from parquet_writer import (
    save_candles, save_underlying,
    load_completed_jobs, mark_job_done, job_key
)

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# Ensure data directory exists before logger tries to create the log file
Path("data").mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/errors.log"),
    ]
)
logger = logging.getLogger(__name__)

INTERVALS = ["1min", "5min", "15min"]
INDICES   = ["NIFTY", "BANKNIFTY", "FINNIFTY"]

# ─── Assignment ──────────────────────────────────────────────────────────────
# Each API handles one index exclusively → true parallel download
API_ASSIGNMENT = {
    "NIFTY":     "angel1",
    "BANKNIFTY": "angel2",
    "FINNIFTY":  "shoonya",
}
UNDERLYING_SOURCE = "shoonya"  # spot data for all 3 indices via Shoonya

# Default ATM spot prices (used when live price unavailable in dry-run/early init)
# Update these to current approximate levels before running
DEFAULT_SPOT = {
    "NIFTY":     22500,
    "BANKNIFTY": 48000,
    "FINNIFTY":  22000,
}
NUM_STRIKES = 10  # ATM ± 10


def parse_args():
    p = argparse.ArgumentParser(description="FnO Historical Data Downloader")
    p.add_argument("--months", type=int, default=24,
                   help="Number of months of history to download (default: 24)")
    p.add_argument("--dry-run", action="store_true",
                   help="Print job list without making API calls")
    p.add_argument("--force", action="store_true",
                   help="Re-download even if already in checkpoint")
    return p.parse_args()


def build_date_range(months: int) -> tuple[date, date]:
    end = date.today()
    start = date(end.year - (months // 12), end.month - (months % 12) or 1, 1)
    if months == 24:
        start = date(2024, 1, 1)
    return start, end


def build_jobs(start: date, end: date) -> list[dict]:
    """Build full list of (index, expiry, strike, option_type, interval) jobs."""
    strikes = {idx: get_atm_strikes(DEFAULT_SPOT[idx], idx, NUM_STRIKES) for idx in INDICES}
    contracts = list(iter_contracts(INDICES, start, end, strikes))
    jobs = []
    for c in contracts:
        for interval in INTERVALS:
            jobs.append({**c, "interval": interval})
    return jobs


def download_contract_angel(
    client: AngelClient,
    contract: dict,
    start: date,
    end: date,
    done: set,
    lock: threading.Lock,
) -> bool:
    """Download one contract's candles via a dedicated AngelAccount."""
    idx        = contract["index"]
    expiry     = contract["expiry"]
    strike     = contract["strike"]
    opt        = contract["option_type"]
    interval   = contract["interval"]

    key = job_key(idx, expiry, strike, opt, interval)
    with lock:
        if key in done:
            return True  # already downloaded

    # Look up token
    from datetime import datetime as dt
    expiry_dt = dt.combine(expiry, dt.min.time())
    token = client.get_token(idx, expiry_dt, strike, opt)
    if not token:
        logger.warning(f"Token not found: {idx} {expiry} {strike} {opt}")
        return False

    # Date range for this contract: from (expiry - 8 days) to expiry
    contract_start = dt.combine(max(expiry - timedelta(days=8), start), dt.min.time()).replace(hour=9, minute=15)
    contract_end   = dt.combine(expiry, dt.min.time()).replace(hour=15, minute=30)

    acc = client.accounts[0]  # dedicated single account per index
    candles = acc.get_candles(token, interval, contract_start, contract_end)

    if candles:
        save_candles(candles, idx, opt, interval, expiry, strike)

    with lock:
        mark_job_done(done, idx, expiry, strike, opt, interval)
    return True


def download_contract_shoonya(
    client: ShoonyaClient,
    contract: dict,
    start: date,
    end: date,
    done: set,
    lock: threading.Lock,
) -> bool:
    """Download one contract's candles via Shoonya."""
    idx      = contract["index"]
    expiry   = contract["expiry"]
    strike   = contract["strike"]
    opt      = contract["option_type"]
    interval = contract["interval"]

    key = job_key(idx, expiry, strike, opt, interval)
    with lock:
        if key in done:
            return True

    from datetime import datetime as dt
    expiry_dt = dt.combine(expiry, dt.min.time())
    token = client.get_token(idx, expiry_dt, strike, opt)
    if not token:
        logger.warning(f"Shoonya token not found: {idx} {expiry} {strike} {opt}")
        return False

    contract_start = dt.combine(max(expiry - timedelta(days=8), start), dt.min.time()).replace(hour=9, minute=15)
    contract_end   = dt.combine(expiry, dt.min.time()).replace(hour=15, minute=30)

    raw = client._fetch_chunk(token, interval, contract_start, contract_end)
    if raw:
        normalized = ShoonyaClient.normalize_candles(raw)
        save_candles(normalized, idx, opt, interval, expiry, strike)

    with lock:
        mark_job_done(done, idx, expiry, strike, opt, interval)
    return True


def download_underlying_shoonya(client: ShoonyaClient, start: date, end: date):
    """Download spot index candles for NIFTY, BANKNIFTY, FINNIFTY via Shoonya."""
    # Shoonya index tokens (NSE segment)
    SPOT_TOKENS = {
        "NIFTY":     "26000",
        "BANKNIFTY": "26009",
        "FINNIFTY":  "26037",
    }
    from datetime import datetime as dt

    for idx, token in SPOT_TOKENS.items():
        for interval in INTERVALS:
            logger.info(f"Downloading underlying spot: {idx} {interval}")
            chunk_start = dt.combine(start, dt.min.time()).replace(hour=9, minute=15)
            chunk_end   = dt.combine(end, dt.min.time()).replace(hour=15, minute=30)

            raw = client.get_candles_full(token, interval, chunk_start, chunk_end)
            if raw:
                normalized = ShoonyaClient.normalize_candles(raw)
                save_underlying(normalized, idx, interval)
                logger.info(f"  ✓ {idx} {interval}: {len(normalized)} candles saved")
            else:
                logger.warning(f"  ✗ {idx} {interval}: no data received")


def run_worker(
    source: str,
    jobs: list[dict],
    angel_client: AngelClient | None,
    shoonya: ShoonyaClient | None,
    start: date,
    end: date,
    done: set,
    lock: threading.Lock,
):
    """
    Worker function for each thread (one per API).
    angel_client and shoonya are pre-initialized — NOT recreated per job.
    """
    desc = {"angel1": "Angel1/NIFTY", "angel2": "Angel2/BANKNIFTY", "shoonya": "Shoonya/FINNIFTY"}[source]

    for job in tqdm(jobs, desc=desc, unit="job", position={"angel1": 0, "angel2": 1, "shoonya": 2}[source]):
        if source in ("angel1", "angel2"):
            download_contract_angel(angel_client, job, start, end, done, lock)
        else:
            download_contract_shoonya(shoonya, job, start, end, done, lock)


def main():
    args = parse_args()
    start, end = build_date_range(args.months)
    logger.info(f"Download range: {start} → {end}")

    all_jobs = build_jobs(start, end)

    # Split jobs by API assignment
    jobs_angel1  = [j for j in all_jobs if j["index"] == "NIFTY"]
    jobs_angel2  = [j for j in all_jobs if j["index"] == "BANKNIFTY"]
    jobs_shoonya = [j for j in all_jobs if j["index"] == "FINNIFTY"]

    total = len(all_jobs)
    logger.info(f"Total jobs: {total}  |  Angel1 (NIFTY): {len(jobs_angel1)}  |  Angel2 (BNKN): {len(jobs_angel2)}  |  Shoonya (FINN): {len(jobs_shoonya)}")

    if args.dry_run:
        logger.info("DRY RUN — no API calls made.")
        print(f"\n{'='*60}")
        print(f"  DRY RUN SUMMARY")
        print(f"{'='*60}")
        print(f"  Date range    : {start}  →  {end}")
        print(f"  Timeframes    : {', '.join(INTERVALS)}")
        print(f"  Angel1/NIFTY  : {len(jobs_angel1):,} jobs")
        print(f"  Angel2/BANKNIFTY: {len(jobs_angel2):,} jobs")
        print(f"  Shoonya/FINNIFTY: {len(jobs_shoonya):,} jobs")
        print(f"  TOTAL         : {total:,} jobs")
        estimated_hrs = total / (6 * 3600)
        print(f"  Est. time     : {estimated_hrs:.1f} hours (parallel)")
        print(f"{'='*60}\n")
        return

    # Load credentials from .env
    angel1 = AngelAccount(
        client_id   = os.environ["ANGEL1_CLIENT_ID"],
        api_key     = os.environ["ANGEL1_API_KEY"],
        mpin        = os.environ["ANGEL1_MPIN"],
        totp_secret = os.environ["ANGEL1_TOTP_SECRET"],
    )
    angel2 = AngelAccount(
        client_id   = os.environ["ANGEL2_CLIENT_ID"],
        api_key     = os.environ["ANGEL2_API_KEY"],
        mpin        = os.environ["ANGEL2_MPIN"],
        totp_secret = os.environ["ANGEL2_TOTP_SECRET"],
    )
    shoonya = ShoonyaClient(
        user_id      = os.environ["SHOONYA_USER_ID"],
        password     = os.environ["SHOONYA_PASSWORD"],
        api_key      = os.environ["SHOONYA_API_KEY"],
        vendor_code  = os.environ["SHOONYA_VENDOR_CODE"],
        imei         = os.environ["SHOONYA_IMEI"],
        totp_secret  = os.environ["SHOONYA_TOTP_SECRET"],
    )

    # Login all accounts
    logger.info("Logging in to all API accounts...")
    angel1.login()
    angel2.login()
    shoonya.login()
    logger.info("All accounts logged in ✓")

    # Load scrip masters (shared, thread-safe read after load)
    master_client = AngelClient([])
    master_client.load_scrip_master()
    # Make it available to both angel clients
    angel1_client = AngelClient([])
    angel1_client.accounts = [angel1]
    angel1_client._scrip_master = master_client._scrip_master

    angel2_client = AngelClient([])
    angel2_client.accounts = [angel2]
    angel2_client._scrip_master = master_client._scrip_master

    done = load_completed_jobs() if not args.force else set()
    lock = threading.Lock()

    # Download underlying spot data via Shoonya first (fast)
    logger.info("Downloading underlying spot candles via Shoonya...")
    download_underlying_shoonya(shoonya, start, end)

    # Run 3 parallel threads — one per API (clients built ONCE here, reused across all jobs)
    logger.info("Starting parallel download: Angel1/NIFTY | Angel2/BANKNIFTY | Shoonya/FINNIFTY")
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(run_worker, "angel1",  jobs_angel1,  angel1_client, None,    start, end, done, lock): "Angel1/NIFTY",
            executor.submit(run_worker, "angel2",  jobs_angel2,  angel2_client, None,    start, end, done, lock): "Angel2/BANKNIFTY",
            executor.submit(run_worker, "shoonya", jobs_shoonya, None,          shoonya, start, end, done, lock): "Shoonya/FINNIFTY",
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
                logger.info(f"✓ {name} download complete")
            except Exception as e:
                logger.error(f"✗ {name} failed: {e}", exc_info=True)

    logger.info("=" * 60)
    logger.info("Download complete! Run verify_data.py to check coverage.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
