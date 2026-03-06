#!/usr/bin/env python3
"""
generate_and_verify_token.py — Force fresh token via v2 and test immediately.
"""

import os
import sys
import json
import requests
import pyotp
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

def run_test():
    client_id = os.getenv("DHAN_CLIENT_ID", "").strip()
    password = os.getenv("DHAN_PASSWORD", "").strip()
    totp_secret = os.getenv("DHAN_TOTP_SECRET", "").strip()
    
    if not all([client_id, password, totp_secret]):
        print("❌ Credentials missing in .env")
        return

    # 1. Generate TOTP
    totp = pyotp.TOTP(totp_secret)
    current_totp = totp.now()
    print(f"📱 Generated TOTP: {current_totp}")

    # 2. Authenticate via v2
    login_url = "https://api.dhan.co/v2/login"
    payload = {
        "clientId": client_id,
        "password": password,
        "totp": current_totp
    }
    
    print(f"🌐 Logging in to {login_url}...")
    try:
        r = requests.post(login_url, json=payload, timeout=30)
        print(f"Login Status: {r.status_code}")
        
        if r.status_code != 200:
            print(f"❌ Login failed: {r.text}")
            return
            
        data = r.json()
        # Different fields depending on response version
        token = data.get("accessToken") or data.get("access_token") or data.get("data", {}).get("accessToken")
        
        if not token:
            print(f"❌ No token in response: {data}")
            return
            
        print("✅ Fresh token received!")
        
        # 3. VERIFY IMMEDIATELY
        print("\n🔍 Verifying token immediately via /v2/fundlimit...")
        headers = {
            "access-token": token,
            "client-id": client_id,
            "Content-Type": "application/json"
        }
        
        v_url = "https://api.dhan.co/v2/fundlimit"
        v_r = requests.get(v_url, headers=headers, timeout=15)
        
        print(f"Verification Status: {v_r.status_code}")
        if v_r.status_code == 200:
            print("🎉 SUCCESS! This token is valid for Trade API.")
            
            # 4. Save to .env
            env_file = BASE_DIR / ".env"
            with open(env_file, 'r') as f:
                lines = f.readlines()
            
            new_lines = []
            found = False
            for line in lines:
                if line.startswith("DHAN_ACCESS_TOKEN="):
                    new_lines.append(f"DHAN_ACCESS_TOKEN={token}\n")
                    found = True
                else:
                    new_lines.append(line)
            
            if not found:
                new_lines.append(f"DHAN_ACCESS_TOKEN={token}\n")
                
            with open(env_file, 'w') as f:
                f.writelines(new_lines)
            
            print(f"💾 Updated {env_file} with the fresh working token.")
        else:
            print(f"❌ Token generated but still got 401 on verification: {v_r.text}")
            print("This usually means the Client ID or Account is restricted or doesn't match.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_test()
