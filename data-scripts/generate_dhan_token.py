#!/usr/bin/env python3
"""
generate_dhan_token.py — Generate fresh Dhan access token using TOTP.
Uses the correct Dhan API v2 endpoints.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

import requests
import pyotp
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# Dhan API endpoint
DHAN_AUTH_URLS = [os.getenv("DHAN_AUTH_URL", "https://api.dhan.co/v2/login")]

def generate_token():
    client_id = os.getenv("DHAN_CLIENT_ID", "").strip()
    password = os.getenv("DHAN_PASSWORD", "").strip()
    totp_secret = os.getenv("DHAN_TOTP_SECRET", "").strip()
    
    if not all([client_id, password, totp_secret]):
        print("❌ Missing Dhan credentials in .env file")
        return None
    
    # Generate TOTP
    totp = pyotp.TOTP(totp_secret)
    current_totp = totp.now()
    
    print(f"📱 Generating TOTP for client: {client_id[:4]}****")
    print(f"🔑 TOTP Code: {current_totp}")
    
    # Prepare login payload (Dhan web login format)
    payload = {
        "clientId": client_id,
        "password": password,
        "totp": current_totp
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    print("🌐 Requesting access token from Dhan...")
    
    try:
        for auth_url in DHAN_AUTH_URLS:
            print(f"   URL: {auth_url}")
            try:
                response = requests.post(auth_url, json=payload, headers=headers, timeout=30)
            except Exception as e:
                print(f"   Request failed on {auth_url}: {e}")
                continue

            print(f"   Response Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                # Try different response formats
                access_token = (data.get("accessToken") or
                               data.get("access_token") or
                               data.get("data", {}).get("accessToken") or
                               data.get("data", {}).get("access_token"))

                if access_token:
                    print("\n✅ Token generated successfully!")
                    print(f"📝 Access Token: {access_token[:50]}...")
                    print(f"⏰ Expires in: 24 hours")

                    # Update .env file
                    env_path = Path(__file__).parent.parent / ".env"
                    if env_path.exists():
                        content = env_path.read_text()
                        import re
                        if re.search(r"^DHAN_ACCESS_TOKEN=.*$", content, flags=re.MULTILINE):
                            new_content = re.sub(
                                r"^DHAN_ACCESS_TOKEN=.*$",
                                f"DHAN_ACCESS_TOKEN={access_token}",
                                content,
                                flags=re.MULTILINE,
                            )
                        else:
                            suffix = "" if content.endswith("\n") else "\n"
                            new_content = f"{content}{suffix}DHAN_ACCESS_TOKEN={access_token}\n"
                        env_path.write_text(new_content)
                        print(f"\n💾 Updated .env file with new token")

                    return access_token

                print(f"❌ No access token in response from {auth_url}: {data}")
                continue

            print(f"❌ Dhan API error from {auth_url}: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Response: {response.text[:500]}")

        return None
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  DHAN ACCESS TOKEN GENERATOR")
    print("="*60 + "\n")
    
    token = generate_token()
    
    if token:
        print("\n" + "="*60)
        print("  ✅ SUCCESS! Token ready for use")
        print("="*60 + "\n")
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("  ❌ FAILED to generate token")
        print("="*60 + "\n")
        sys.exit(1)
