import os
from fastapi import APIRouter, HTTPException
import logging

router = APIRouter(prefix="/api/stocks", tags=["stocks"])
logger = logging.getLogger(__name__)

@router.get("")
def get_stock_list():
    """
    Returns a list of all available Nifty 500 stock symbols based on the 
    subdirectories in data/candles/NIFTY500.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    nifty500_dir = os.path.join(base_dir, "data", "candles", "NIFTY500")
    
    if not os.path.exists(nifty500_dir):
        logger.error(f"NIFTY500 directory not found: {nifty500_dir}")
        return {"stocks": []}
    
    try:
        # Get all subdirectories in the NIFTY500 folder
        symbols = [
            d for d in os.listdir(nifty500_dir) 
            if os.path.isdir(os.path.join(nifty500_dir, d))
        ]
        symbols.sort()
        return {"stocks": symbols}
    except Exception as e:
        logger.error(f"Error listing NIFTY500 symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))
