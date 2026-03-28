import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

import dhan_client
import angel_client

load_dotenv('/Users/sanim/Downloads/sunny/Python/AIML/Pybankers/Pytrader/.env')

def test_angel():
    # Load Angel Accounts
    angel_keys = os.getenv("ANGEL_API_KEYS", "")
    angel_accounts = []
    
    if hasattr(json, 'loads'):
        try:
            angel_accounts = json.loads(angel_keys)
        except:
            pass

    if not angel_accounts:
        print("No Angel accounts found in .env.")
        return

    print("\nLogging into Angel One API...")
    client = angel_client.AngelClient(angel_accounts[:1]) # Just use first account
    try:
        client.login_all()
    except Exception as e:
        print(f"Angel login failed: {e}")
        return
        
    start_time = datetime(2020, 1, 1).replace(hour=9, minute=15, second=0)
    end_time = datetime(2020, 1, 31).replace(hour=15, minute=30, second=0)

    print("\nRequesting BANKNIFTY from Angel (Jan 2020) 15min...")
    # Angle one symbols: Banknifty = '26009'
    try:
        acc = client.accounts[0]
        candles = acc.get_candles(
            token="26009",
            interval="15min",
            from_dt=start_time,
            to_dt=end_time
        )
        print(f"Angel returned {len(candles) if candles else '0'} candles.")
        if candles and len(candles) > 0:
             print(f"Sample: {candles[0]}")
    except Exception as e:
        print(f"Angel Error: {e}")

def test_dhan():
    client_id = os.getenv("DHAN_CLIENT_ID")
    access_token = os.getenv("DHAN_ACCESS_TOKEN")
    
    if not client_id or not access_token:
        print("Dhan credentials missing")
        return

    print("\nLogging into Dhan API...")
    client = dhan_client.DhanClient(client_id, access_token)
    
    start_time = datetime(2020, 1, 1).replace(hour=9, minute=15, second=0)
    end_time = datetime(2020, 1, 31).replace(hour=15, minute=30, second=0)

    print("\nRequesting BANKNIFTY from Dhan (Jan 2020) 15min...")
    
    try:
        # Based on dhan documentation or available functions inside wrapper
        # Let's try to fetch daily instead as a test to see what date it returns
        candles = client.get_intraday_candles(
            security_id="13",  # BANKNIFTY
            exchange_segment="IDX_I",
            instrument_type="INDEX",
            from_date=start_time.strftime("%Y-%m-%d"),
            to_date=end_time.strftime("%Y-%m-%d"),
            interval="15"
        )
        print(f"Dhan returned {len(candles.get('data', {}).get('start_Time', [])) if candles and candles.get('status') == 'success' else '0'} candles.")
    except Exception as e:
        print(f"Dhan Error: {e}")

if __name__ == "__main__":
    test_angel()
    test_dhan()
