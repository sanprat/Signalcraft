import json
import logging
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO)
STORE = Path("strategies")
DATA_DIR = Path("data/candles/NIFTY500")

def get_latest_prices(asset_type: str, symbols: list[str]) -> dict:
    prices = {}
    if asset_type == "EQUITY":
        for sym in symbols:
            pfile = DATA_DIR / sym / "1D.parquet"
            if pfile.exists():
                try:
                    df = pd.read_parquet(pfile)
                    if not df.empty:
                        prices[sym] = float(df.iloc[-1]["close"])
                except Exception as e:
                    logging.error(f"Error reading {pfile}: {e}")
    return prices

for f in STORE.glob("*.json"):
    try:
        data = json.loads(f.read_text())
        if "creation_prices" not in data or not data["creation_prices"]:
            asset_type = data.get("asset_type", "EQUITY")
            symbols = data.get("symbols", [])
            if not symbols and data.get("symbol"):
                symbols = [data["symbol"]]
            
            prices = get_latest_prices(asset_type, symbols)
            if prices:
                data["creation_prices"] = prices
                f.write_text(json.dumps(data, indent=2))
                logging.info(f"Backfilled prices for {f.name}: {prices}")
    except Exception as e:
        logging.error(f"Failed on {f.name}: {e}")
