#!/usr/bin/env python3
"""
generate_nifty500_mapping.py — Generate Dhan security ID mapping for NIFTY500 stocks.

Downloads Dhan's instrument master CSV and extracts security IDs for NIFTY500 symbols.
Outputs: nifty500_dhan_mapping.json
"""

import json
import logging
import sys
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Dhan instrument master CSV URL
DHAN_INSTRUMENT_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"

# NIFTY500 symbols (from CSV or hardcoded)
NIFTY500_CSV = Path(__file__).parent / "nifty500_symbols.csv"


def load_nifty500_symbols():
    """Load NIFTY500 symbols from CSV or return hardcoded list."""
    if NIFTY500_CSV.exists():
        df = pd.read_csv(NIFTY500_CSV)
        if "Symbol" in df.columns:
            symbols = df["Symbol"].tolist()
            logger.info(f"Loaded {len(symbols)} symbols from {NIFTY500_CSV}")
            return symbols
        logger.warning(f"'Symbol' column not found in {NIFTY500_CSV}")
    
    # Fallback: NIFTY500 symbols (common ones)
    logger.warning("Using hardcoded NIFTY500 symbol list")
    return [
        "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "BHARTIARTL", "SBIN", "INFY",
        "LICI", "ITC", "HINDUNILVR", "LT", "BAJFINANCE", "HCLTECH", "MARUTI",
        "SUNPHARMA", "TATAMOTORS", "TATASTEEL", "KOTAKBANK", "TITAN", "NTPC",
        "ULTRACEMCO", "ONGC", "AXISBANK", "WIPRO", "NESTLEIND", "M&M", "POWERGRID",
        "GRASIM", "JSWSTEEL", "ASIANPAINT", "HDFCLIFE", "SBILIFE", "BRITANNIA",
        "EICHERMOT", "APOLLOHOSP", "DIVISLAB", "TATACONSUM", "BAJAJFINSV",
        "HINDALCO", "TECHM", "DRREDDY", "CIPLA", "INDUSINDBK", "ADANIPORTS",
        "ADANIENT", "BPCL", "COALINDIA", "HEROMOTOCO", "UPL", "TATAPOWER",
    ]


def download_instrument_master():
    """Download Dhan's instrument master CSV."""
    logger.info("Downloading Dhan instrument master...")
    try:
        response = requests.get(DHAN_INSTRUMENT_MASTER_URL, timeout=60)
        response.raise_for_status()
        
        # Save to disk
        output_path = Path(__file__).parent / "dhan_instrument_master.csv"
        output_path.write_bytes(response.content)
        logger.info(f"Saved instrument master to {output_path}")
        
        # Load into DataFrame
        df = pd.read_csv(output_path)
        logger.info(f"Instrument master has {len(df)} rows, columns: {df.columns.tolist()}")
        return df
    except Exception as e:
        logger.error(f"Failed to download instrument master: {e}")
        return None


def generate_mapping(master_df, nifty500_symbols):
    """Extract Dhan security IDs for NIFTY500 symbols."""
    mapping = {}
    missing = []
    
    # Filter for NSE EQ segment
    nse_eq = master_df[master_df["Exchange Segment"] == "NSE_EQ"]
    logger.info(f"Found {len(nse_eq)} instruments in NSE_EQ segment")
    
    for symbol in nifty500_symbols:
        # Try exact match
        match = nse_eq[nse_eq["Symbol"] == symbol]
        
        if len(match) > 0:
            # Get the equity instrument
            equity = match[match["Instrument"] == "EQUITY"]
            if len(equity) > 0:
                security_id = str(equity.iloc[0]["Security Id"])
                mapping[symbol] = security_id
                logger.info(f"✓ {symbol:20s} -> {security_id}")
            else:
                missing.append(symbol)
                logger.warning(f"✗ {symbol:20s} -> No EQUITY instrument found")
        else:
            missing.append(symbol)
            logger.warning(f"✗ {symbol:20s} -> Not found in NSE_EQ")
    
    return mapping, missing


def save_mapping(mapping, output_path):
    """Save mapping to JSON file."""
    output_path = Path(__file__).parent / output_path
    with open(output_path, "w") as f:
        json.dump(mapping, f, indent=2)
    
    logger.info(f"\n✅ Mapping saved to {output_path}")
    logger.info(f"   Total symbols: {len(mapping)}")


def main():
    logger.info("=" * 60)
    logger.info("  DHAN NIFTY500 MAPPING GENERATOR")
    logger.info("=" * 60)
    
    # Step 1: Load NIFTY500 symbols
    nifty500_symbols = load_nifty500_symbols()
    logger.info(f"NIFTY500 symbols to map: {len(nifty500_symbols)}")
    
    # Step 2: Download instrument master
    master_df = download_instrument_master()
    if master_df is None:
        logger.error("Failed to download instrument master. Exiting.")
        sys.exit(1)
    
    # Step 3: Generate mapping
    logger.info("\nGenerating Dhan security ID mapping...")
    mapping, missing = generate_mapping(master_df, nifty500_symbols)
    
    # Step 4: Save mapping
    save_mapping(mapping, "nifty500_dhan_mapping.json")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total NIFTY500 symbols: {len(nifty500_symbols)}")
    logger.info(f"Mapped successfully: {len(mapping)}")
    logger.info(f"Missing: {len(missing)}")
    
    if missing:
        logger.warning(f"\nMissing symbols: {', '.join(missing[:10])}")
        if len(missing) > 10:
            logger.warning(f"  ... and {len(missing) - 10} more")


if __name__ == "__main__":
    main()
