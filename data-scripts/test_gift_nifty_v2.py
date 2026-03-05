"""
test_gift_nifty_v2.py — Test if GIFT NIFTY is accessible via Dhan API.
Uses the same working pattern as dhan_client.py
"""

import os
import sys
from pathlib import Path
from datetime import date
from dotenv import load_dotenv
import requests

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

# Dhan API config
BASE_URL = "https://api.dhan.co/v2"
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "").strip()
CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "").strip()

if not ACCESS_TOKEN or not CLIENT_ID:
    print("❌ Missing DHAN_ACCESS_TOKEN or DHAN_CLIENT_ID in .env")
    sys.exit(1)

headers = {
    "access-token": ACCESS_TOKEN,
    "client-id": CLIENT_ID,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

session = requests.Session()
session.headers.update(headers)

def test_fund_limit():
    """Test connection using fund limit endpoint."""
    try:
        resp = session.get(f"{BASE_URL}/fundlimit", timeout=10)
        if resp.status_code == 200:
            print("✓ Dhan connection verified")
            return True
        print(f"✗ Auth failed: {resp.status_code}")
        print(f"  Response: {resp.text[:300]}")
        return False
    except Exception as e:
        print(f"✗ Connection error: {e}")
        return False

def test_historical(security_id, exchange_segment, instrument, name):
    """Test historical data API."""
    payload = {
        "securityId": security_id,
        "exchangeSegment": exchange_segment,
        "instrument": instrument,
        "expiryCode": 0,
        "fromDate": "2024-01-01",
        "toDate": "2024-01-31",
    }
    
    try:
        resp = session.post(f"{BASE_URL}/charts/historical", json=payload, timeout=15)
        
        print(f"\nTesting: {name}")
        print(f"  securityId={security_id}, exchangeSegment={exchange_segment}, instrument={instrument}")
        print(f"  Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            inner = data.get("data", data)
            timestamps = inner.get("start_Time", inner.get("timestamp", []))
            if timestamps:
                print(f"  ✓ SUCCESS! Got {len(timestamps)} data points")
                # Convert first timestamp to date
                try:
                    from datetime import datetime
                    first_ts = datetime.fromtimestamp(int(timestamps[0])).strftime("%Y-%m-%d")
                    last_ts = datetime.fromtimestamp(int(timestamps[-1])).strftime("%Y-%m-%d")
                    print(f"  Date range: {first_ts} to {last_ts}")
                except:
                    print(f"  Sample timestamps: {timestamps[:3]}")
                return True
            else:
                print(f"  ✗ No data returned (empty response)")
        else:
            print(f"  ✗ Error: {resp.text[:200]}")
        return False
        
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        return False

def test_intraday(security_id, exchange_segment, instrument, name):
    """Test intraday data API."""
    payload = {
        "securityId": security_id,
        "exchangeSegment": exchange_segment,
        "instrument": instrument,
        "interval": "15",
        "oi": False,
        "fromDate": "2024-01-15 09:00:00",
        "toDate": "2024-01-15 15:30:00",
    }
    
    try:
        resp = session.post(f"{BASE_URL}/charts/intraday", json=payload, timeout=15)
        
        print(f"\nTesting Intraday: {name}")
        print(f"  Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            timestamps = data.get("timestamp", [])
            if timestamps:
                print(f"  ✓ SUCCESS! Got {len(timestamps)} intraday candles")
                return True
            else:
                print(f"  ✗ No data returned")
        else:
            print(f"  ✗ Error: {resp.text[:200]}")
        return False
        
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        return False

def main():
    print("=" * 70)
    print("  GIFT NIFTY API AVAILABILITY TEST (v2)")
    print("=" * 70)
    
    # First verify connection
    if not test_fund_limit():
        print("\n❌ Cannot proceed without valid authentication")
        print("   Check your DHAN_ACCESS_TOKEN in .env file")
        sys.exit(1)
    
    print("\n" + "=" * 70)
    print("  TESTING HISTORICAL DATA APIs")
    print("=" * 70)
    
    # Test known working configs first
    print("\n--- Testing KNOWN working indices (baseline) ---")
    test_historical(13, "NSE_EQ", "INDEX", "NIFTY (ID: 13, NSE_EQ)")
    test_historical(25, "NSE_EQ", "INDEX", "BANKNIFTY (ID: 25, NSE_EQ)")
    test_historical(27, "NSE_EQ", "INDEX", "FINNIFTY (ID: 27, NSE_EQ)")
    
    # Now test GIFT NIFTY possibilities
    print("\n--- Testing GIFT NIFTY possibilities ---")
    
    # Based on Dhan docs, IDX_I is for index instruments
    # GIFT NIFTY might be under IDX_I with a different security ID
    test_historical(26000, "IDX_I", "INDEX", "GIFT NIFTY attempt (ID: 26000, IDX_I)")
    test_historical(26009, "IDX_I", "INDEX", "GIFT NIFTY attempt (ID: 26009, IDX_I)")
    test_historical(26037, "IDX_I", "INDEX", "GIFT NIFTY attempt (ID: 26037, IDX_I)")
    
    # Try NSE_IX exchange segment (if supported)
    test_historical(13, "NSE_IX", "INDEX", "NIFTY on NSE_IX (ID: 13)")
    test_historical(26000, "NSE_IX", "INDEX", "GIFT NIFTY on NSE_IX (ID: 26000)")
    
    # Try without exchange segment (some APIs work with just security ID)
    print("\n--- Testing minimal payload (security ID only) ---")
    payload_minimal = {
        "securityId": 26000,
        "fromDate": "2024-01-01",
        "toDate": "2024-01-31",
    }
    try:
        resp = session.post(f"{BASE_URL}/charts/historical", json=payload_minimal, timeout=15)
        print(f"Minimal payload status: {resp.status_code}")
        print(f"Response: {resp.text[:300]}")
    except Exception as e:
        print(f"Minimal payload error: {e}")
    
    print("\n" + "=" * 70)
    print("  TESTING COMPLETE")
    print("=" * 70)
    print("\nConclusion:")
    print("  • If NIFTY/BANKNIFTY/FINNIFTY worked but GIFT NIFTY didn't,")
    print("    then GIFT NIFTY historical data may not be available via API")
    print("  • Contact Dhan support at help@dhan.co for the correct security ID")
    print("  • GIFT NIFTY may only be available for live quotes, not historical OHLC")

if __name__ == "__main__":
    main()
