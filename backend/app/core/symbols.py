"""
symbols.py — Centralized symbol configuration for FnO and NIFTY500.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CSV_PATH = PROJECT_ROOT / "data-scripts" / "nifty500_symbols.csv"
MAPPING_PATH = PROJECT_ROOT / "data-scripts" / "nifty500_dhan_mapping.json"


# ── FnO Symbols Configuration ──────────────────────────────────────────────
# Dhan API uses numeric security IDs for indices
# Note: BANKNIFTY and FINNIFTY intraday data is only available from Jan 2022
FNO_SYMBOLS: Dict[str, Dict[str, str]] = {
    "NIFTY": {
        "id": "13",
        "segment": "IDX_I",
        "instrument": "INDEX",
        "name": "Nifty 50",
        "start_date": "2020-01-01",  # NIFTY available from Jan 2020
    },
    "BANKNIFTY": {
        "id": "25",
        "segment": "IDX_I",
        "instrument": "INDEX",
        "name": "Nifty Bank",
        "start_date": "2022-01-01",  # BANKNIFTY only available from Jan 2022
    },
    "FINNIFTY": {
        "id": "27",
        "segment": "IDX_I",
        "instrument": "INDEX",
        "name": "Nifty Fin Services",
        "start_date": "2022-01-01",  # FINNIFTY only available from Jan 2022
    },
    # GIFTNIFTY - only available on SGX, may have limited data
    # "GIFTNIFTY": {
    #     "id": "442",
    #     "segment": "IDX_I",
    #     "instrument": "INDEX",
    #     "name": "Nifty GIFT",
    #     "start_date": "2022-01-01",
    # },
}

# All FnO index keys for iteration
FNO_INDEX_KEYS = list(FNO_SYMBOLS.keys())


# ── Load NIFTY500 from CSV ────────────────────────────────────────────────
def _load_nifty500_from_csv() -> List[str]:
    """Load NIFTY500 symbols from CSV file."""
    try:
        df = pd.read_csv(CSV_PATH)
        if "Symbol" in df.columns:
            return df["Symbol"].tolist()
        else:
            logger.warning(
                f"CSV doesn't have 'Symbol' column. Columns: {df.columns.tolist()}"
            )
            return []
    except FileNotFoundError:
        logger.warning(f"NIFTY500 CSV not found at {CSV_PATH}")
        return []
    except Exception as e:
        logger.error(f"Error loading NIFTY500 CSV: {e}")
        return []


# ── Load Dhan Mapping from JSON ─────────────────────────────────────────
def _load_dhan_mapping() -> Dict[str, str]:
    """Load Dhan security ID mapping from JSON file."""
    try:
        with open(MAPPING_PATH, "r") as f:
            data = json.load(f)
            # Handle both formats: {"SYMBOL": "12345"} or [{"symbol": "SYMBOL", "dhan_id": "12345"}]
            if isinstance(data, list):
                return {item["symbol"]: item["dhan_id"] for item in data}
            return data
    except FileNotFoundError:
        logger.warning(f"Dhan mapping not found at {MAPPING_PATH}")
        return {}
    except Exception as e:
        logger.error(f"Error loading Dhan mapping: {e}")
        return {}


# ── Initialize at module load ────────────────────────────────────────────
NIFTY500: List[str] = _load_nifty500_from_csv()
DHAN_MAPPING: Dict[str, str] = _load_dhan_mapping()

# Combined list of all tradable symbols
ALL_SYMBOLS: List[str] = FNO_INDEX_KEYS + NIFTY500


# ── Helper Functions ──────────────────────────────────────────────────────


def get_fno_config(symbol: str) -> Optional[Dict[str, str]]:
    """
    Get Dhan API configuration for an FnO symbol.

    Args:
        symbol: FnO symbol (NIFTY, BANKNIFTY, FINNIFTY)

    Returns:
        Dict with keys: id, segment, instrument, name, start_date
        None if symbol not found
    """
    return FNO_SYMBOLS.get(symbol)


def get_fno_start_date(symbol: str) -> Optional[datetime]:
    """
    Get the earliest available date for an FnO symbol's historical data.

    Args:
        symbol: FnO symbol (NIFTY, BANKNIFTY, FINNIFTY)

    Returns:
        datetime object for the earliest available date, or None if not found
    """
    config = FNO_SYMBOLS.get(symbol)
    if config and "start_date" in config:
        return datetime.strptime(config["start_date"], "%Y-%m-%d")
    return None


def get_dhan_id(symbol: str) -> Optional[str]:
    """
    Get Dhan security ID for a symbol.

    Args:
        symbol: Stock symbol

    Returns:
        Dhan security ID as string, or None if not found
    """
    # Check FnO first
    if symbol in FNO_SYMBOLS:
        return FNO_SYMBOLS[symbol]["id"]

    # Check NIFTY500 mapping
    return DHAN_MAPPING.get(symbol)


def get_symbol_info(symbol: str) -> Dict:
    """
    Get comprehensive information about a symbol.

    Args:
        symbol: Stock symbol

    Returns:
        Dict with symbol details
    """
    info = {
        "symbol": symbol,
        "dhan_id": get_dhan_id(symbol),
        "is_fno": symbol in FNO_INDEX_KEYS,
        "is_nifty500": symbol in NIFTY500,
    }

    # Add FnO details if applicable
    if symbol in FNO_SYMBOLS:
        info.update(FNO_SYMBOLS[symbol])

    return info


def is_tradable(symbol: str) -> bool:
    """
    Check if a symbol is tradable (exists in our system).

    Args:
        symbol: Stock symbol

    Returns:
        True if tradable, False otherwise
    """
    return symbol in ALL_SYMBOLS


def get_all_nifty500() -> List[str]:
    """Get list of all NIFTY500 symbols."""
    return NIFTY500.copy()


def get_all_fno() -> List[str]:
    """Get list of all FnO index symbols."""
    return FNO_INDEX_KEYS.copy()


def get_missing_dhan_ids() -> List[str]:
    """
    Get list of NIFTY500 symbols that don't have Dhan ID mapping.

    Returns:
        List of symbols missing mapping
    """
    return [s for s in NIFTY500 if s not in DHAN_MAPPING]


# ── Timeframe Configuration ────────────────────────────────────────────────
INTERVAL_MAP = {
    "1min": "1 minute",
    "5min": "5 minutes",
    "15min": "15 minutes",
    "30min": "30 minutes",
    "1hour": "1 hour",
    "1D": "1 day",
    "1W": "1 week",
    "1M": "1 month",
}


if __name__ == "__main__":
    # Print summary when run directly
    print("=" * 60)
    print("SYMBOL CONFIGURATION SUMMARY")
    print("=" * 60)

    print(f"\nFnO Indices: {len(FNO_SYMBOLS)}")
    for symbol, config in FNO_SYMBOLS.items():
        print(f"  {symbol}: ID={config['id']}")

    print(f"\nNIFTY500: {len(NIFTY500)} symbols")
    print(f"Dhan Mapped: {len(DHAN_MAPPING)} symbols")
    print(f"Missing Mapping: {len(get_missing_dhan_ids())} symbols")

    print(f"\nAll Tradable: {len(ALL_SYMBOLS)} symbols")

    print("\n" + "=" * 60)
    print("INTERVAL MAPPING")
    print("=" * 60)
    for tf, interval in INTERVAL_MAP.items():
        print(f"  {tf} -> {interval}")
