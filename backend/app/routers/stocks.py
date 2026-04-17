import os
from fastapi import APIRouter, HTTPException
import logging

router = APIRouter(prefix="/api/stocks", tags=["stocks"])
logger = logging.getLogger(__name__)

# Fallback list of common Nifty50 stocks (used if data directory is unavailable)
FALLBACK_STOCKS = [
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

MIN_EXPECTED_STOCKS = 40


@router.get("")
def get_stock_list():
    """
    Returns a list of all available Nifty50 stock symbols.
    Falls back to a predefined list if the directory doesn't exist.
    """
    from app.core.symbols import get_all_nifty50, NIFTY50

    # Try to get from symbols module first
    nifty50_symbols = get_all_nifty50()
    if nifty50_symbols and len(nifty50_symbols) >= MIN_EXPECTED_STOCKS:
        logger.info(
            f"Returning {len(nifty50_symbols)} Nifty50 symbols from symbols module"
        )
        return {"stocks": nifty50_symbols}

    # Fall back to directory-based approach
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    nifty50_dir = os.path.join(base_dir, "data", "candles", "NIFTY500")

    symbols = []

    if os.path.exists(nifty50_dir):
        try:
            symbols = [
                d
                for d in os.listdir(nifty50_dir)
                if os.path.isdir(os.path.join(nifty50_dir, d))
            ]
            symbols.sort()
            logger.info(f"Found {len(symbols)} symbols in NIFTY500 directory")

            if len(symbols) < MIN_EXPECTED_STOCKS:
                logger.warning(f"Only {len(symbols)} stocks found, using fallback")
                symbols = FALLBACK_STOCKS
        except Exception as e:
            logger.error(f"Error listing symbols: {e}")
            symbols = FALLBACK_STOCKS

    if not symbols:
        logger.warning("No symbols found, using fallback")
        symbols = FALLBACK_STOCKS

    return {"stocks": symbols}
