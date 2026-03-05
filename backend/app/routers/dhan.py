"""
dhan_router.py — Dhan authentication endpoints.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.core.dhan_auth import generate_dhan_token, validate_token, refresh_token_if_needed

router = APIRouter(prefix="/api/dhan", tags=["dhan"])


class TokenRefreshRequest(BaseModel):
    client_id: Optional[str] = None
    password: Optional[str] = None
    totp_secret: Optional[str] = None


class TokenValidateRequest(BaseModel):
    access_token: Optional[str] = None
    client_id: Optional[str] = None


@router.post("/refresh")
def refresh_token(body: Optional[TokenRefreshRequest] = None):
    """
    Generate a fresh Dhan access token.
    
    If no credentials provided in request body, uses environment variables.
    Successfully generated tokens are automatically saved to .env file.
    
    **Credentials needed:**
    - DHAN_CLIENT_ID
    - DHAN_PASSWORD  
    - DHAN_TOTP_SECRET
    
    These can be provided in the request or via environment variables.
    """
    try:
        if body:
            result = generate_dhan_token(
                client_id=body.client_id,
                password=body.password,
                totp_secret=body.totp_secret
            )
        else:
            result = generate_dhan_token()
        
        if result["success"]:
            return {
                "status": "success",
                "message": result["message"],
                "data": {
                    "access_token": result["access_token"],
                    "expires_in": result.get("expires_in", 86400),
                    "expires_in_hours": result.get("expires_in", 86400) // 3600
                }
            }
        else:
            raise HTTPException(status_code=400, detail=result["message"])
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
def validate_existing_token(body: Optional[TokenValidateRequest] = None):
    """
    Validate if the current Dhan access token is still valid.
    """
    try:
        if body and body.access_token:
            result = validate_token(body.access_token, body.client_id)
        else:
            import os
            result = validate_token(
                os.getenv("DHAN_ACCESS_TOKEN", ""),
                os.getenv("DHAN_CLIENT_ID", "")
            )
        
        return {
            "status": "success",
            "valid": result["valid"],
            "message": result["message"]
        }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto-refresh")
def auto_refresh_token():
    """
    Automatically refresh token if expired.
    
    Checks if current token is valid, if not generates a new one.
    Updates both environment variable and .env file.
    """
    try:
        result = refresh_token_if_needed()
        
        return {
            "status": "success" if result["success"] else "error",
            "refreshed": result["refreshed"],
            "message": result["message"]
        }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
def get_dhan_status():
    """
    Get current Dhan connection status.
    """
    import os
    
    client_id = os.getenv("DHAN_CLIENT_ID", "").strip()
    access_token = os.getenv("DHAN_ACCESS_TOKEN", "").strip()
    
    has_creds = bool(client_id and access_token)
    
    return {
        "status": "configured" if has_creds else "not_configured",
        "client_id": client_id[:4] + "****" if client_id else None,
        "token_present": bool(access_token),
        "token_length": len(access_token) if access_token else 0
    }
