"""
test_gift_nifty.py — Test if GIFT NIFTY is accessible via Dhan API.

According to Dhan's announcements, GIFT NIFTY is available on their platform.
This script tests different possible security IDs and exchange segments.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

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

# Possible configurations for GIFT NIFTY
# Based on research:
# - GIFT NIFTY trades on NSE International Exchange (NSE IX) in GIFT City
# - Possible exchange segments: NSE_IX, NSE_IFSC, IFSC, IDX_I
# - Possible security IDs: need to discover

TEST_CONFIGS = [
    # Try as INDEX instrument on various exchange segments
    {"security_id": "26000", "exchange": "NSE_IX", "instrument": "INDEX", "name": "NSE_IX INDEX (26000)"},
    {"security_id": "26000", "exchange": "NSE_IFSC", "instrument": "INDEX", "name": "NSE_IFSC INDEX (26000)"},
    {"security_id": "26000", "exchange": "IFSC", "instrument": "INDEX", "name": "IFSC INDEX (26000)"},
    {"security_id": "26000", "exchange": "IDX_I", "instrument": "INDEX", "name": "IDX_I INDEX (26000) - like NIFTY"},
    
    # Try different possible security IDs
    {"security_id": "13", "exchange": "NSE_IX", "instrument": "INDEX", "name": "NSE_IX NIFTY ID (13)"},
    {"security_id": "13", "exchange": "NSE_IFSC", "instrument": "INDEX", "name": "NSE_IFSC NIFTY ID (13)"},
    
    # GIFT NIFTY might have its own security ID
    {"security_id": "26050", "exchange": "NSE_IX", "instrument": "INDEX", "name": "NSE_IX (26050)"},
    {"security_id": "26050", "exchange": "IDX_I", "instrument": "INDEX", "name": "IDX_I (26050)"},
]

def test_historical_data(config):
    """Test historical data API for a given config."""
    payload = {
        "securityId": config["security_id"],
        "exchangeSegment": config["exchange"],
        "instrument": config["instrument"],
        "expiryCode": 0,
        "fromDate": "2024-01-01",
        "toDate": "2024-01-31",
    }
    
    try:
        resp = requests.post(
            f"{BASE_URL}/charts/historical",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        result = {
            "config": config["name"],
            "status_code": resp.status_code,
            "success": resp.status_code == 200,
        }
        
        if resp.status_code == 200:
            data = resp.json()
            inner = data.get("data", data)
            timestamps = inner.get("start_Time", inner.get("timestamp", []))
            result["data_points"] = len(timestamps) if timestamps else 0
            if timestamps:
                result["sample"] = {
                    "first": timestamps[0],
                    "last": timestamps[-1] if len(timestamps) > 1 else timestamps[0],
                }
        else:
            result["error"] = resp.text[:200]
            
        return result
        
    except Exception as e:
        return {
            "config": config["name"],
            "success": False,
            "error": str(e),
        }

def test_intraday_data(config):
    """Test intraday data API for a given config."""
    payload = {
        "securityId": config["security_id"],
        "exchangeSegment": config["exchange"],
        "instrument": config["instrument"],
        "interval": "15",
        "oi": False,
        "fromDate": "2024-01-15 09:00:00",
        "toDate": "2024-01-15 15:30:00",
    }
    
    try:
        resp = requests.post(
            f"{BASE_URL}/charts/intraday",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        result = {
            "config": config["name"],
            "status_code": resp.status_code,
            "success": resp.status_code == 200,
        }
        
        if resp.status_code == 200:
            data = resp.json()
            timestamps = data.get("timestamp", [])
            result["data_points"] = len(timestamps) if timestamps else 0
        else:
            result["error"] = resp.text[:200]
            
        return result
        
    except Exception as e:
        return {
            "config": config["name"],
            "success": False,
            "error": str(e),
        }

def main():
    print("=" * 70)
    print("  GIFT NIFTY API AVAILABILITY TEST")
    print("=" * 70)
    print()
    
    print("Testing Historical Data API (Daily candles)...")
    print("-" * 70)
    
    successful_configs = []
    
    for config in TEST_CONFIGS:
        result = test_historical_data(config)
        status = "✓" if result["success"] else "✗"
        print(f"{status} {result['config']}")
        
        if result["success"]:
            print(f"    Status: {result.get('status_code')} | Data points: {result.get('data_points', 0)}")
            if result.get("sample"):
                print(f"    Sample: {result['sample']}")
            successful_configs.append(config)
        else:
            print(f"    Error: {result.get('error', 'Unknown')[:100]}")
        print()
    
    if successful_configs:
        print("=" * 70)
        print("  ✓ SUCCESSFUL CONFIGURATIONS FOUND!")
        print("=" * 70)
        for cfg in successful_configs:
            print(f"  • {cfg['name']}")
            print(f"    securityId: {cfg['security_id']}, exchangeSegment: {cfg['exchange']}, instrument: {cfg['instrument']}")
        
        print()
        print("Testing Intraday Data API for successful configs...")
        print("-" * 70)
        
        for config in successful_configs:
            result = test_intraday_data(config)
            status = "✓" if result["success"] else "✗"
            print(f"{status} {result['config']}")
            if result["success"]:
                print(f"    Status: {result.get('status_code')} | Data points: {result.get('data_points', 0)}")
            else:
                print(f"    Error: {result.get('error', 'Unknown')[:100]}")
            print()
    else:
        print("=" * 70)
        print("  ✗ NO SUCCESSFUL CONFIGURATIONS FOUND")
        print("=" * 70)
        print()
        print("Possible reasons:")
        print("  1. GIFT NIFTY is not available via Dhan API for historical data")
        print("  2. The security ID or exchange segment is different from tested values")
        print("  3. GIFT NIFTY may only be available for live quotes, not historical OHLC")
        print()
        print("Recommendations:")
        print("  • Contact Dhan support at help@dhan.co for the correct security ID")
        print("  • Check if GIFT NIFTY is only available via live feed, not historical API")
        print("  • Try accessing via NSE IFSC exchange segment if supported")

if __name__ == "__main__":
    main()
