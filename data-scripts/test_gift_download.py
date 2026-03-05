#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"

print(f"Loading .env from: {env_path.absolute()}")
print(f"Exists: {env_path.exists()}")

load_dotenv(dotenv_path=env_path)

client_id = os.getenv("DHAN_CLIENT_ID", "")
access_token = os.getenv("DHAN_ACCESS_TOKEN", "")

print(f"Client ID: {client_id}")
print(f"Access Token: {access_token[:30]}...{access_token[-20:]}")
print(f"Token Length: {len(access_token)}")

# Now test the download
if access_token and client_id:
    sys.path.insert(0, str(project_root / "data-scripts"))
    from dhan_client import DhanClient
    
    client = DhanClient(client_id, access_token)
    if client.verify_connection():
        print("\n✓ Connection successful!")
        
        # Test GIFT NIFTY data fetch
        print("\nTesting GIFT NIFTY data fetch...")
        candles = client.get_intraday_candles(
            security_id="5024",
            exchange_segment="IDX_I",
            instrument="INDEX",
            interval="15min",
            from_datetime="2024-01-15 09:15:00",
            to_datetime="2024-01-15 15:30:00",
            oi=False,
        )
        print(f"Got {len(candles)} candles for Jan 15, 2024")
        if candles:
            print(f"First candle: {candles[0]}")
    else:
        print("\n✗ Connection failed!")
else:
    print("\n✗ Missing credentials!")
