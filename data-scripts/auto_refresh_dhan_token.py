#!/usr/bin/env python3
"""
auto_refresh_dhan_token.py — Auto-refresh Dhan token every 23 hours.
Runs as a background daemon or via cron.
"""

import sys
import os
import time
import json
import logging
import requests
import pyotp
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Setup logging
LOG_FILE = Path(__file__).parent / "data" / "token_refresh.log"
LOG_FILE.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE)
    ]
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# Dhan API config
# NOTE: b2b.dhan.co was deprecated and causes NameResolutionError on VPS.
# We exclusively stick to RenewToken or require manual re-auth via OAuth if expired.
DHAN_AUTH_URLS = [os.getenv("DHAN_AUTH_URL", "https://api.dhan.co/v2/login")]
REFRESH_INTERVAL_HOURS = 24  # Standard token validity is 24 hours
PROACTIVE_REFRESH_HOURS = 2.0  # Refresh when there are 2 hours or less remaining

def get_current_token_expiry():
    """Decode JWT token to get expiry timestamp."""
    import base64
    
    token = os.getenv("DHAN_ACCESS_TOKEN", "").strip()
    if not token:
        return None
    
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding
        
        payload_json = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_json)
        
        return payload.get('exp')  # Unix timestamp
    except Exception as e:
        logger.error(f"Error decoding token: {e}")
        return None

def generate_new_token():
    """Generate a new Dhan access token using official RenewToken API or TOTP fallback."""
    client_id = os.getenv("DHAN_CLIENT_ID", "").strip()
    password = os.getenv("DHAN_PASSWORD", "").strip()
    totp_secret = os.getenv("DHAN_TOTP_SECRET", "").strip()
    current_token = os.getenv("DHAN_ACCESS_TOKEN", "").strip()
    
    if not all([client_id, password, totp_secret]):
        logger.error("Missing Dhan credentials in .env")
        return None
        
    # --- METHOD 1: Official Dhan RenewToken API ---
    if current_token:
        try:
            logger.info("Attempting to renew token via official API...")
            renew_headers = {
                "access-token": current_token,
                "dhanClientId": client_id
            }
            resp = requests.get("https://api.dhan.co/v2/RenewToken", headers=renew_headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if "token" in data:
                    logger.info("✅ Token renewed successfully via RenewToken API!")
                    return data["token"]
            logger.warning(f"RenewToken failed: {resp.status_code} {resp.text[:100]}")
        except Exception as e:
            logger.error(f"RenewToken request error: {e}")
            
    # --- METHOD 2: Fallback to TOTP Login ---
    try:
        # Generate TOTP
        totp = pyotp.TOTP(totp_secret)
        current_totp = totp.now()
        
        logger.info(f"Generating TOTP for fallback login: {current_totp}")
        
        # Prepare login payload
        payload = {
            "clientId": client_id,
            "password": password,
            "totp": current_totp
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        for auth_url in DHAN_AUTH_URLS:
            try:
                response = requests.post(auth_url, json=payload, headers=headers, timeout=30)
            except Exception as e:
                logger.error(f"Token request failed on {auth_url}: {e}")
                continue

            if response.status_code == 200:
                data = response.json()
                access_token = (data.get("accessToken") or
                               data.get("access_token") or
                               data.get("data", {}).get("accessToken") or
                               data.get("data", {}).get("access_token"))

                if access_token:
                    logger.info(f"✅ New token generated successfully via {auth_url}")
                    return access_token
                logger.error(f"No access token in response from {auth_url}: {data}")
                continue

            logger.error(f"Dhan API error from {auth_url}: {response.status_code} {response.text[:200]}")
        return None
            
    except Exception as e:
        logger.error(f"Token generation failed: {e}")
        return None

def update_env_file(new_token):
    """Update .env file with new token."""
    env_path = Path(__file__).parent.parent / ".env"
    
    if not env_path.exists():
        logger.error(f".env file not found: {env_path}")
        return False
    
    try:
        content = env_path.read_text()
        
        import re
        if re.search(r"^DHAN_ACCESS_TOKEN=.*$", content, flags=re.MULTILINE):
            new_content = re.sub(
                r"^DHAN_ACCESS_TOKEN=.*$",
                f"DHAN_ACCESS_TOKEN={new_token}",
                content,
                flags=re.MULTILINE,
            )
        else:
            suffix = "" if content.endswith("\n") else "\n"
            new_content = f"{content}{suffix}DHAN_ACCESS_TOKEN={new_token}\n"
        
        env_path.write_text(new_content)
        logger.info(f"✅ Updated .env file: {env_path}")
        
        # Also update os.environ for current session
        os.environ["DHAN_ACCESS_TOKEN"] = new_token
        
        return True
    except Exception as e:
        logger.error(f"Error updating .env: {e}")
        return False

def refresh_token():
    """Main token refresh logic."""
    logger.info("="*60)
    logger.info("  DHAN TOKEN AUTO-REFRESH")
    logger.info("="*60)
    
    # Check current token expiry
    expiry_ts = get_current_token_expiry()
    
    if expiry_ts:
        expiry_dt = datetime.fromtimestamp(expiry_ts)
        now = datetime.now()
        hours_remaining = (expiry_dt - now).total_seconds() / 3600
        
        logger.info(f"Current token expires: {expiry_dt}")
        logger.info(f"Hours remaining: {hours_remaining:.1f}")
        
        if hours_remaining > PROACTIVE_REFRESH_HOURS:
            logger.info("Token still valid, skipping refresh")
            return True
    
    # Generate new token
    logger.info("Generating new access token...")
    new_token = generate_new_token()
    
    if new_token:
        # Update .env file
        if update_env_file(new_token):
            logger.info("✅ Token refresh complete!")
            logger.info("="*60)
            return True
    
    logger.error("❌ Token refresh failed")
    logger.info("="*60)
    return False

def run_daemon():
    """Run as background daemon, checking every hour."""
    logger.info("Starting Dhan token refresh daemon...")
    logger.info(f"Refresh interval: {REFRESH_INTERVAL_HOURS} hours")
    
    while True:
        try:
            refresh_token()
        except Exception as e:
            logger.error(f"Daemon error: {e}")
        
        # Sleep for 1 hour
        time.sleep(3600)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Dhan Token Auto-Refresh")
    parser.add_argument("--daemon", action="store_true", help="Run as background daemon")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    
    args = parser.parse_args()
    
    if args.daemon:
        run_daemon()
    else:
        # Run once
        success = refresh_token()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
