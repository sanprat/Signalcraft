import os
import sys
import json
import requests
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

def debug_dhan():
    client_id = os.getenv("DHAN_CLIENT_ID", "").strip()
    access_token = os.getenv("DHAN_ACCESS_TOKEN", "").strip()
    
    print("--- System info ---")
    print(f"Current UTC Time: {datetime.utcnow()}")
    print(f"Local System Time: {datetime.now()}")
    
    print("\n--- .env Verification ---")
    print(f"DHAN_CLIENT_ID: {client_id[:4]}****" if client_id else "DHAN_CLIENT_ID: MISSING")
    print(f"DHAN_ACCESS_TOKEN: {access_token[:10]}...{access_token[-10:]}" if access_token else "DHAN_ACCESS_TOKEN: MISSING")
    
    if not client_id or not access_token:
        print("❌ CRITICAL: Credentials missing from .env")
        return

    print("\n--- API Test: fundlimit ---")
    headers = {
        "access-token": access_token,
        "client-id": client_id,
        "Content-Type": "application/json"
    }
    
    url = "https://api.dhan.co/v2/fundlimit"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.text}")
        
        if resp.status_code == 401:
            print("\n❌ 401 Unauthorized!")
            print("Possible reasons:")
            print("1. The Token is truly expired (Dhan tokens expire daily).")
            print("2. The Client ID in .env does NOT match the account used to generate the token.")
            print("3. The VPS clock is out of sync (check 'Current UTC Time' above).")
        elif resp.status_code == 200:
            print("\n✅ Auth is working for fundlimit! The issue might be specific to chart endpoints.")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    debug_dhan()
