import os
from fastapi import APIRouter, HTTPException
import logging

router = APIRouter(prefix="/api/stocks", tags=["stocks"])
logger = logging.getLogger(__name__)

# Fallback list of common NIFTY 500 stocks
FALLBACK_STOCKS = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "HINDUNILVR", "ITC",
    "KOTAKBANK", "LT", "SBIN", "AXISBANK", "ASIANPAINT", "NESTLEIND", "MARUTI",
    "BAJFINANCE", "HDFC", "ADANIPORTS", "BRITANNIA", "TITAN", "ULTRACEMCO",
    "WIPRO", "SUNPHARMA", "BAJAJFINSV", "POWERGRID", "NTPC", "ONGC", "TATASTEEL",
    "JSWSTEEL", "HCLTECH", "TECHM", "ADANIENT", "APOLLOHOSP", "CIPLA", "M&M",
    "EICHERMOT", "COALINDIA", "GRASIM", "HEROMOTOCO", "DRREDDY", "BPCL", "IOC",
    "SHRIRAMFIN", "INDUSINDBK", "ADANIGREEN", "BAJAJ-AUTO", "BEL", "BHEL",
    "DIVISLAB", "GODREJCP", "HAVELLS", "HINDALCO", "JINDALSTEL", "LUPIN",
    "MOTHERSON", "NHPC", "NMDC", "OIL", "PIDILITIND", "RECLTD", "SBILIFE",
    "SIEMENS", "TATACONSUM", "TATAMOTORS", "TATAPOWER", "VOLTAS", "ZOMATO",
    "ZYDUSWELL", "POLICYBZR", "PAYTM", "NYKAA", "IREDA", "IRFC", "RVNL",
]

@router.get("")
def get_stock_list():
    """
    Returns a list of all available Nifty 500 stock symbols based on the
    subdirectories in data/candles/NIFTY500.
    Falls back to a predefined list if the directory doesn't exist or is empty.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    nifty500_dir = os.path.join(base_dir, "data", "candles", "NIFTY500")

    symbols = []

    if os.path.exists(nifty500_dir):
        try:
            # Get all subdirectories in the NIFTY500 folder
            symbols = [
                d for d in os.listdir(nifty500_dir)
                if os.path.isdir(os.path.join(nifty500_dir, d))
            ]
            symbols.sort()
            logger.info(f"Found {len(symbols)} symbols in NIFTY500 directory")
        except Exception as e:
            logger.error(f"Error listing NIFTY500 symbols: {e}")
            # Fall through to fallback list

    # If no symbols found or directory doesn't exist, use fallback
    if not symbols:
        logger.warning(f"NIFTY500 directory empty or not found, using {len(FALLBACK_STOCKS)} fallback stocks")
        symbols = FALLBACK_STOCKS

    return {"stocks": symbols}
