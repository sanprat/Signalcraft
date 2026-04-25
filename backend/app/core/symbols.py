"""
symbols.py — Centralized symbol configuration for Nifty50 stocks.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, TypedDict

import pandas as pd
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAPPING_PATH = PROJECT_ROOT / "data-scripts" / "nifty50_dhan_mapping.json"


# ── FnO Symbols Configuration ──────────────────────────────────────────────
# Kept for reference/compatibility, but not actively used in strategy flows
# Dhan API uses numeric security IDs for indices
FNO_SYMBOLS: Dict[str, Dict[str, str]] = {
    "NIFTY": {
        "id": "13",
        "segment": "IDX_I",
        "instrument": "INDEX",
        "name": "Nifty 50",
        "start_date": "2020-01-01",
    },
    "BANKNIFTY": {
        "id": "25",
        "segment": "IDX_I",
        "instrument": "INDEX",
        "name": "Nifty Bank",
        "start_date": "2022-01-01",
    },
    "FINNIFTY": {
        "id": "27",
        "segment": "IDX_I",
        "instrument": "INDEX",
        "name": "Nifty Fin Services",
        "start_date": "2022-01-01",
    },
}

FNO_INDEX_KEYS = list(FNO_SYMBOLS.keys())


# ── Load Nifty50 from JSON ────────────────────────────────────────────────
def _load_nifty50_from_json() -> List[str]:
    """Load Nifty50 symbols from JSON file."""
    try:
        with open(MAPPING_PATH, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return [item["symbol"] for item in data]
            return list(data.keys())
    except FileNotFoundError:
        logger.warning(f"Nifty50 mapping not found at {MAPPING_PATH}")
        return []
    except Exception as e:
        logger.error(f"Error loading Nifty50 mapping: {e}")
        return []


# ── Load Dhan Mapping from JSON ─────────────────────────────────────────
def _load_dhan_mapping() -> Dict[str, str]:
    """Load Dhan security ID mapping from JSON file."""
    try:
        with open(MAPPING_PATH, "r") as f:
            data = json.load(f)
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
NIFTY50: List[str] = _load_nifty50_from_json()
DHAN_MAPPING: Dict[str, str] = _load_dhan_mapping()

# Nifty50 stocks only (FnO indices excluded from active flows)
ALL_SYMBOLS: List[str] = NIFTY50.copy()


def _normalize_symbol_text(value: str) -> str:
    """Normalize free text for symbol alias matching."""
    normalized = value.upper().strip()
    normalized = normalized.replace("&", " AND ")
    normalized = normalized.replace("-", " ")
    normalized = normalized.replace(".", " ")
    normalized = " ".join(normalized.split())
    for suffix in (" LIMITED", " LTD", " CORPORATION", " CORP", " COMPANY", " CO"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
    return normalized


# Canonical company-name aliases for the currently supported Nifty50 universe.
SYMBOL_ALIASES: Dict[str, List[str]] = {
    "RELIANCE": ["RELIANCE", "RELIANCE INDUSTRIES", "RIL"],
    "TCS": ["TCS", "TATA CONSULTANCY", "TATA CONSULTANCY SERVICES"],
    "HDFCBANK": ["HDFCBANK", "HDFC BANK"],
    "ICICIBANK": ["ICICIBANK", "ICICI BANK"],
    "BHARTIARTL": ["BHARTIARTL", "BHARTI AIRTEL", "AIRTEL"],
    "SBIN": ["SBIN", "SBI", "STATE BANK", "STATE BANK OF INDIA"],
    "INFY": ["INFY", "INFOSYS", "INFOSYS TECHNOLOGIES"],
    "LICI": ["LICI", "LIC", "LIFE INSURANCE CORPORATION", "LIFE INSURANCE CORPORATION OF INDIA"],
    "ITC": ["ITC", "ITC INDIA"],
    "HINDUNILVR": ["HINDUNILVR", "HINDUSTAN UNILEVER", "HUL"],
    "LT": ["LT", "L AND T", "LARSEN AND TOUBRO", "LARSEN TOUBRO"],
    "BAJFINANCE": ["BAJFINANCE", "BAJAJ FINANCE"],
    "HCLTECH": ["HCLTECH", "HCL", "HCL TECH", "HCL TECHNOLOGIES"],
    "MARUTI": ["MARUTI", "MARUTI SUZUKI", "MARUTI SUZUKI INDIA"],
    "SUNPHARMA": ["SUNPHARMA", "SUN PHARMA", "SUN PHARMACEUTICAL", "SUN PHARMACEUTICAL INDUSTRIES"],
    "TATAMOTORS": ["TATAMOTORS", "TATA MOTORS"],
    "TATASTEEL": ["TATASTEEL", "TATA STEEL"],
    "KOTAKBANK": ["KOTAKBANK", "KOTAK", "KOTAK BANK", "KOTAK MAHINDRA BANK"],
    "TITAN": ["TITAN", "TITAN COMPANY", "TITAN COMPANY INDIA"],
    "NTPC": ["NTPC", "NATIONAL THERMAL POWER", "NTPC INDIA"],
    "ULTRACEMCO": ["ULTRACEMCO", "ULTRACEM", "ULTRATECH", "ULTRATECH CEMENT"],
    "ONGC": ["ONGC", "OIL AND NATURAL GAS", "OIL AND NATURAL GAS CORPORATION"],
    "AXISBANK": ["AXISBANK", "AXIS BANK"],
    "WIPRO": ["WIPRO"],
    "NESTLEIND": ["NESTLEIND", "NESTLE", "NESTLE INDIA"],
    "M&M": ["M&M", "M AND M", "MAHINDRA", "MAHINDRA AND MAHINDRA"],
    "POWERGRID": ["POWERGRID", "POWER GRID", "POWER GRID CORPORATION", "POWER GRID CORPORATION OF INDIA"],
    "GRASIM": ["GRASIM", "GRASIM INDUSTRIES"],
    "JSWSTEEL": ["JSWSTEEL", "JSW STEEL"],
    "ASIANPAINT": ["ASIANPAINT", "ASIAN PAINT", "ASIAN PAINTS"],
    "HDFCLIFE": ["HDFCLIFE", "HDFC LIFE", "HDFC LIFE INSURANCE"],
    "SBILIFE": ["SBILIFE", "SBI LIFE", "SBI LIFE INSURANCE"],
    "BRITANNIA": ["BRITANNIA", "BRITANNIA INDUSTRIES"],
    "EICHERMOT": ["EICHERMOT", "EICHER", "EICHER MOTORS"],
    "APOLLOHOSP": ["APOLLOHOSP", "APOLLO HOSPITAL", "APOLLO HOSPITALS"],
    "DIVISLAB": ["DIVISLAB", "DIVIS", "DIVIS LAB", "DIVIS LABORATORIES"],
    "TATACONSUM": ["TATACONSUM", "TATA CONSUM", "TATA CONSUMER", "TATA CONSUMER PRODUCTS"],
    "BAJAJFINSV": ["BAJAJFINSV", "BAJAJ FINSERV"],
    "HINDALCO": ["HINDALCO", "HINDALCO INDUSTRIES"],
    "TECHM": ["TECHM", "TECH MAHINDRA"],
    "DRREDDY": ["DRREDDY", "DR REDDY", "DR REDDYS", "DR REDDYS LABORATORIES"],
    "CIPLA": ["CIPLA"],
    "INDUSINDBK": ["INDUSINDBK", "INDUSIND", "INDUSIND BANK"],
    "ADANIPORTS": ["ADANIPORTS", "ADANI PORTS", "ADANI PORTS AND SEZ"],
    "ADANIENT": ["ADANIENT", "ADANI ENTERPRISES", "ADANI ENTERPRISE"],
    "BPCL": ["BPCL", "BHARAT PETROLEUM", "BHARAT PETROLEUM CORPORATION"],
    "COALINDIA": ["COALINDIA", "COAL INDIA"],
    "HEROMOTOCO": ["HEROMOTOCO", "HERO", "HERO MOTOCORP", "HERO MOTORS"],
    "UPL": ["UPL", "UNITED PHOSPHORUS"],
    "TATAPOWER": ["TATAPOWER", "TATA POWER"],
}

NORMALIZED_SYMBOL_ALIASES: Dict[str, List[str]] = {
    symbol: [_normalize_symbol_text(alias) for alias in aliases]
    for symbol, aliases in SYMBOL_ALIASES.items()
}

ALIAS_TO_SYMBOL: Dict[str, str] = {}
for symbol, aliases in NORMALIZED_SYMBOL_ALIASES.items():
    for alias in aliases:
        ALIAS_TO_SYMBOL[alias] = symbol

ALL_SYMBOL_SEARCH_TERMS: List[str] = sorted(ALIAS_TO_SYMBOL.keys(), key=len, reverse=True)


class SymbolMatch(TypedDict):
    input: str
    matched_alias: str
    symbol: str
    confidence: int


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
    # Check FnO first (kept for reference)
    if symbol in FNO_SYMBOLS:
        return FNO_SYMBOLS[symbol]["id"]

    # Check Nifty50 mapping
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
        "is_nifty50": symbol in NIFTY50,
    }

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


def resolve_symbol_alias(query: str, min_score: int = 88) -> Optional[str]:
    """
    Resolve a ticker or company-name alias to a canonical symbol.
    """
    normalized = _normalize_symbol_text(query)
    if not normalized:
        return None

    if normalized in ALIAS_TO_SYMBOL:
        return ALIAS_TO_SYMBOL[normalized]

    match = process.extractOne(
        normalized,
        ALL_SYMBOL_SEARCH_TERMS,
        scorer=fuzz.token_set_ratio,
    )
    if not match or match[1] < min_score:
        return None
    return ALIAS_TO_SYMBOL.get(match[0])


def extract_symbols_from_text(query: str) -> List[str]:
    """
    Extract canonical symbols from free text using exact alias containment first,
    then fuzzy phrase resolution on comma/and-separated chunks.
    """
    normalized = _normalize_symbol_text(query)
    if not normalized:
        return []

    positioned_matches: List[tuple[int, str]] = []
    bounded_query = f" {normalized} "
    for alias in ALL_SYMBOL_SEARCH_TERMS:
        needle = f" {alias} "
        position = bounded_query.find(needle)
        if position != -1:
            symbol = ALIAS_TO_SYMBOL[alias]
            positioned_matches.append((position, symbol))

    if positioned_matches:
        ordered: List[str] = []
        for _, symbol in sorted(positioned_matches, key=lambda item: item[0]):
            if symbol not in ordered:
                ordered.append(symbol)
        return ordered

    matches: List[str] = []
    chunks = re.split(r",|\bAND\b|&", normalized)
    for chunk in chunks:
        symbol = resolve_symbol_alias(chunk.strip())
        if symbol and symbol not in matches:
            matches.append(symbol)
    return matches


def extract_symbol_matches_from_text(query: str) -> List[SymbolMatch]:
    """
    Return detailed alias matches in the order they appear in the text.
    """
    normalized = _normalize_symbol_text(query)
    if not normalized:
        return []

    positioned_matches: List[tuple[int, SymbolMatch]] = []
    bounded_query = f" {normalized} "
    for alias in ALL_SYMBOL_SEARCH_TERMS:
        needle = f" {alias} "
        start = 0
        while True:
            position = bounded_query.find(needle, start)
            if position == -1:
                break
            symbol = ALIAS_TO_SYMBOL[alias]
            positioned_matches.append(
                (
                    position,
                    {
                        "input": alias.title(),
                        "matched_alias": alias.title(),
                        "symbol": symbol,
                        "confidence": 100,
                    },
                )
            )
            start = position + len(needle)

    if positioned_matches:
        ordered: List[SymbolMatch] = []
        seen_symbols: set[str] = set()
        for _, match in sorted(positioned_matches, key=lambda item: item[0]):
            if match["symbol"] not in seen_symbols:
                ordered.append(match)
                seen_symbols.add(match["symbol"])
        return ordered

    results: List[SymbolMatch] = []
    seen_symbols: set[str] = set()
    chunks = re.split(r",|\bAND\b|&", normalized)
    for chunk in chunks:
        clean_chunk = chunk.strip()
        if not clean_chunk:
            continue
        match = process.extractOne(
            clean_chunk,
            ALL_SYMBOL_SEARCH_TERMS,
            scorer=fuzz.token_set_ratio,
        )
        if not match or match[1] < 88:
            continue
        symbol = ALIAS_TO_SYMBOL[match[0]]
        if symbol in seen_symbols:
            continue
        results.append(
            {
                "input": clean_chunk.title(),
                "matched_alias": match[0].title(),
                "symbol": symbol,
                "confidence": int(match[1]),
            }
        )
        seen_symbols.add(symbol)
    return results


def get_all_nifty50() -> List[str]:
    """Get list of all Nifty50 symbols."""
    return NIFTY50.copy()


def get_all_fno() -> List[str]:
    """Get list of all FnO index symbols."""
    return FNO_INDEX_KEYS.copy()


def get_missing_dhan_ids() -> List[str]:
    """
    Get list of Nifty50 symbols that don't have Dhan ID mapping.

    Returns:
        List of symbols missing mapping
    """
    return [s for s in NIFTY50 if s not in DHAN_MAPPING]


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

    print(f"\nFnO Indices: {len(FNO_SYMBOLS)} (reference only)")
    for symbol, config in FNO_SYMBOLS.items():
        print(f"  {symbol}: ID={config['id']}")

    print(f"\nNifty50: {len(NIFTY50)} symbols")
    print(f"Dhan Mapped: {len(DHAN_MAPPING)} symbols")
    print(f"Missing Mapping: {len(get_missing_dhan_ids())} symbols")

    print(f"\nAll Tradable: {len(ALL_SYMBOLS)} symbols")

    print("\n" + "=" * 60)
    print("INTERVAL MAPPING")
    print("=" * 60)
    for tf, interval in INTERVAL_MAP.items():
        print(f"  {tf} -> {interval}")
