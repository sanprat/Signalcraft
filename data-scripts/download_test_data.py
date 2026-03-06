import os
import sys
import json
import time
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv

# Load ENV and set paths
BASE_DIR = Path(__file__).parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")
sys.path.insert(0, str(BASE_DIR / "data-scripts"))

from dhan_client import DhanClient

# Configuration
TEST_SYMBOLS = ["IDEA", "SUZLON", "YESBANK", "RPOWER"]
OUTPUT_BASE = BASE_DIR / "data" / "candles" / "NIFTY500"
MAPPING_FILE = BASE_DIR / "data-scripts" / "nifty500_dhan_mapping.json"
START_DATE = date(2026, 1, 1) # Just 2 months of history for fast test
END_DATE = date.today()

SCHEMA = pa.schema([
    ("time",   pa.timestamp("s", tz="Asia/Kolkata")),
    ("open",   pa.float32()),
    ("high",   pa.float32()),
    ("low",    pa.float32()),
    ("close",  pa.float32()),
    ("volume", pa.int64()),
])

def main():
    if not MAPPING_FILE.exists():
        print(f"Missing mapping file: {MAPPING_FILE}")
        return

    with open(MAPPING_FILE) as f:
        mapping = json.load(f)

    client = DhanClient(
        os.environ["DHAN_CLIENT_ID"].strip(),
        os.environ["DHAN_ACCESS_TOKEN"].strip(),
    )

    for sym in TEST_SYMBOLS:
        if sym not in mapping:
            print(f"Symbol {sym} not in mapping")
            continue
        
        sec_id = mapping[sym]
        print(f"Downloading {sym} (ID: {sec_id})...")
        
        for interval in ["1min", "5min", "15min"]:
            print(f"  -> {interval}")
            raw = client.get_intraday_candles(
                security_id=sec_id,
                exchange_segment="NSE_EQ",
                instrument="EQUITY",
                interval=interval,
                from_datetime=f"{START_DATE} 09:00:00",
                to_datetime=f"{END_DATE} 16:00:00",
            )
            
            if not raw:
                print(f"    No data for {sym} {interval}")
                continue

            df = pd.DataFrame(raw)[["time", "open", "high", "low", "close", "volume"]]
            df["time"] = pd.to_datetime(df["time"], utc=False).dt.tz_localize(None).dt.tz_localize("Asia/Kolkata")
            
            # Cast types
            df["time"]   = df["time"].astype("datetime64[s, Asia/Kolkata]")
            df["open"]   = df["open"].astype("float32")
            df["high"]   = df["high"].astype("float32")
            df["low"]    = df["low"].astype("float32")
            df["close"]  = df["close"].astype("float32")
            df["volume"] = df["volume"].astype("int64")

            out_path = OUTPUT_BASE / sym / f"{interval}.parquet"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            
            table = pa.Table.from_pandas(df, schema=SCHEMA, preserve_index=False)
            pq.write_table(table, out_path, compression="lz4")
            print(f"    Saved {len(df)} rows to {out_path.name}")
            time.sleep(1)

if __name__ == "__main__":
    main()
