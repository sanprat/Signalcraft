"""
dhan_auth.py — Dhan authentication service for generating fresh access tokens.
"""

import logging
import os
import re
import json
import base64
from pathlib import Path

import requests
import pyotp

logger = logging.getLogger(__name__)

# Keep root resolution centralized; this file is backend/app/core/dhan_auth.py
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = PROJECT_ROOT / ".env"

# Dhan login endpoint — b2b.dhan.co is deprecated and unresolvable in Docker
DHAN_AUTH_URLS = [os.getenv("DHAN_AUTH_URL", "https://api.dhan.co/v2/login")]
DHAN_VALIDATE_URLS = [
    "https://api.dhan.co/v2/fundlimit",
    "https://api.dhan.co/fundlimit",
]
PROACTIVE_REFRESH_HOURS = int(os.getenv("DHAN_PROACTIVE_REFRESH_HOURS", "2"))


def _extract_access_token(payload: dict) -> str:
    """Handle response shape variations safely."""
    return (
        payload.get("accessToken")
        or payload.get("access_token")
        or payload.get("data", {}).get("accessToken")
        or payload.get("data", {}).get("access_token")
        or ""
    )


def _persist_access_token(access_token: str) -> bool:
    """Persist the token in project-root .env."""
    if not access_token:
        return False
    try:
        if ENV_PATH.exists():
            content = ENV_PATH.read_text()
            if re.search(r"^DHAN_ACCESS_TOKEN=.*$", content, flags=re.MULTILINE):
                updated = re.sub(
                    r"^DHAN_ACCESS_TOKEN=.*$",
                    f"DHAN_ACCESS_TOKEN={access_token}",
                    content,
                    flags=re.MULTILINE,
                )
            else:
                suffix = "" if content.endswith("\n") else "\n"
                updated = f"{content}{suffix}DHAN_ACCESS_TOKEN={access_token}\n"
        else:
            updated = f"DHAN_ACCESS_TOKEN={access_token}\n"
        ENV_PATH.write_text(updated)
        return True
    except Exception as e:
        logger.warning(f"Could not update .env file at {ENV_PATH}: {e}")
        return False


def _token_hours_remaining(access_token: str) -> float | None:
    """Decode JWT payload exp claim (without signature validation)."""
    if not access_token:
        return None
    try:
        parts = access_token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1] + ("=" * ((4 - len(parts[1]) % 4) % 4))
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload.get("exp")
        if not exp:
            return None
        import time
        return (float(exp) - time.time()) / 3600.0
    except Exception:
        return None


def generate_dhan_token(client_id: str = None, password: str = None, totp_secret: str = None) -> dict:
    """
    Generate a fresh Dhan access token.
    Tries RenewToken API first (fast, no TOTP needed), then falls back to TOTP login.
    
    Returns:
        dict: {
            "success": bool,
            "access_token": str (if successful),
            "expires_in": int (seconds),
            "message": str
        }
    """
    client_id = client_id or os.getenv("DHAN_CLIENT_ID", "").strip()
    password = password or os.getenv("DHAN_PASSWORD", "").strip()
    totp_secret = totp_secret or os.getenv("DHAN_TOTP_SECRET", "").strip()
    current_token = os.getenv("DHAN_ACCESS_TOKEN", "").strip()
    
    if not client_id:
        return {
            "success": False,
            "message": "Missing DHAN_CLIENT_ID in environment variables"
        }
    
    # ── METHOD 1: RenewToken API (fast, works if current token exists) ──
    if current_token:
        try:
            logger.info("Attempting token renewal via RenewToken API...")
            renew_headers = {
                "access-token": current_token,
                "dhanClientId": client_id
            }
            resp = requests.get("https://api.dhan.co/v2/RenewToken", headers=renew_headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if "token" in data:
                    access_token = data["token"]
                    os.environ["DHAN_ACCESS_TOKEN"] = access_token
                    _persist_access_token(access_token)
                    logger.info("Token renewed successfully via RenewToken API")
                    return {
                        "success": True,
                        "access_token": access_token,
                        "expires_in": 86400,
                        "message": "Token renewed via RenewToken API",
                    }
            logger.warning(f"RenewToken failed: {resp.status_code} {resp.text[:100]}")
        except Exception as e:
            logger.warning(f"RenewToken request error: {e}")
    
    # ── METHOD 2: TOTP Login (fallback) ──
    if not password or not totp_secret:
        return {
            "success": False,
            "message": "RenewToken failed and TOTP credentials missing for fallback login"
        }
    
    try:
        # Generate TOTP
        totp = pyotp.TOTP(totp_secret)
        current_totp = totp.now()
        
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
        
        logger.info(f"Requesting Dhan token for client: {client_id}")
        
        endpoint_errors = []
        for auth_url in DHAN_AUTH_URLS:
            try:
                response = requests.post(auth_url, json=payload, headers=headers, timeout=30)
            except requests.exceptions.RequestException as e:
                endpoint_errors.append(f"{auth_url}: {e}")
                continue

            if response.status_code == 200:
                data = response.json()
                access_token = _extract_access_token(data)
                if access_token:
                    # Keep current process env in sync.
                    os.environ["DHAN_ACCESS_TOKEN"] = access_token
                    # Persist to project .env so scripts and backend stay aligned.
                    _persist_access_token(access_token)
                    return {
                        "success": True,
                        "access_token": access_token,
                        "expires_in": 86400,  # Typically ~24h
                        "message": f"Token generated successfully via {auth_url}",
                    }
                endpoint_errors.append(f"{auth_url}: no access token in response")
                continue

            try:
                error_data = response.json()
                msg = error_data.get("message") or error_data.get("errorMessage") or "Unknown error"
            except Exception:
                msg = response.text[:300] or "Unknown error"
            endpoint_errors.append(f"{auth_url}: HTTP {response.status_code} - {msg}")

        return {
            "success": False,
            "message": " | ".join(endpoint_errors) if endpoint_errors else "Token request failed",
        }
            
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": "Dhan API request timed out"
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": f"Request failed: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Authentication failed: {str(e)}"
        }


def validate_token(access_token: str, client_id: str = None) -> dict:
    """
    Validate if the current access token is still valid.
    
    Returns:
        dict: {
            "valid": bool,
            "message": str
        }
    """
    client_id = client_id or os.getenv("DHAN_CLIENT_ID", "").strip()
    
    if not access_token:
        return {"valid": False, "message": "No access token provided"}
    
    try:
        headers = {
            "Content-Type": "application/json",
            "access-token": access_token,
            "client-id": client_id,
            "Accept": "application/json"
        }
        
        failures = []
        for validate_url in DHAN_VALIDATE_URLS:
            try:
                response = requests.get(validate_url, headers=headers, timeout=10)
            except Exception as e:
                failures.append(f"{validate_url}: {e}")
                continue

            if response.status_code == 200:
                return {"valid": True, "message": f"Token is valid ({validate_url})"}
            if response.status_code == 401:
                return {"valid": False, "message": "Token has expired or is invalid"}

            failures.append(f"{validate_url}: HTTP {response.status_code}")

        return {
            "valid": False,
            "message": "Validation failed: " + (" | ".join(failures) if failures else "unknown error"),
        }
            
    except Exception as e:
        return {"valid": False, "message": f"Validation error: {str(e)}"}


def refresh_token_if_needed() -> dict:
    """
    Check if current token is valid, if not generate a new one.
    Updates the environment variable and .env file if successful.
    
    Returns:
        dict: {
            "success": bool,
            "refreshed": bool,
            "message": str
        }
    """
    current_token = os.getenv("DHAN_ACCESS_TOKEN", "").strip()
    client_id = os.getenv("DHAN_CLIENT_ID", "").strip()
    hours_remaining = _token_hours_remaining(current_token)
    force_refresh = hours_remaining is not None and hours_remaining <= PROACTIVE_REFRESH_HOURS
    
    if force_refresh:
        logger.info(
            f"Token has {hours_remaining:.2f}h remaining (<= {PROACTIVE_REFRESH_HOURS}h), refreshing proactively..."
        )
    else:
        # Validate current token
        validation = validate_token(current_token, client_id)
        if validation["valid"]:
            return {
                "success": True,
                "refreshed": False,
                "message": "Current token is still valid"
            }

        # If validation failed due transient network and token still has runway, don't force rotate.
        if (
            hours_remaining is not None
            and hours_remaining > PROACTIVE_REFRESH_HOURS
            and "HTTPSConnectionPool" in validation.get("message", "")
        ):
            return {
                "success": True,
                "refreshed": False,
                "message": (
                    f"Validation endpoint unreachable; token has ~{hours_remaining:.2f}h remaining, "
                    "skipping refresh for now"
                ),
            }

    # Token invalid or proactively expiring, generate new one
    logger.info("Generating new Dhan token...")
    result = generate_dhan_token()
    
    if result["success"]:
        os.environ["DHAN_ACCESS_TOKEN"] = result["access_token"]
        _persist_access_token(result["access_token"])
        return {
            "success": True,
            "refreshed": True,
            "access_token": result["access_token"],
            "message": "Token refreshed successfully"
        }
    else:
        return {
            "success": False,
            "refreshed": False,
            "message": result["message"]
        }
