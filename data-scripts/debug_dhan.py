#!/usr/bin/env python3
import requests
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv(dotenv_path=Path("/Users/sanim/Downloads/sunny/Python/AIML/Pybankers/Pytrader/.env"))

token = os.getenv("DHAN_ACCESS_TOKEN")
client_id = os.getenv("DHAN_CLIENT_ID")

print(f"Token: {token[:30]}...{token[-20:]}")
print(f"Client ID: {client_id}")

# Test with Session like dhan_client.py
session = requests.Session()
session.headers.update({
    "access-token": token,
    "client-id": client_id,
    "Content-Type": "application/json",
    "Accept": "application/json",
})

print("\n--- Testing with Session ---")
try:
    resp = session.get("https://api.dhan.co/v2/fundlimit", timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:200]}")
except Exception as e:
    print(f"Error: {e}")

print("\n--- Testing without Session (direct) ---")
try:
    resp = requests.get(
        "https://api.dhan.co/v2/fundlimit",
        headers={
            "access-token": token,
            "client-id": client_id,
        },
        timeout=10
    )
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:200]}")
except Exception as e:
    print(f"Error: {e}")
