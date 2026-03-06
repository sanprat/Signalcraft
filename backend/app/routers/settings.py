from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.routers.auth import get_current_user, UserResponse
from app.core.database import get_broker_credentials, save_broker_credentials
from app.core.brokers import clear_adapter_cache

router = APIRouter(prefix="/api/settings", tags=["Settings"])


class BrokerCredentialsReq(BaseModel):
    broker: str
    credentials: Dict[str, Any]


@router.get("/broker/{broker}")
def retrieve_broker_credentials(broker: str, current_user: UserResponse = Depends(get_current_user)):
    user_id = current_user.id
    creds = get_broker_credentials(user_id, broker)
    if not creds:
        return {"status": "not_found", "broker": broker, "credentials": {}}
    
    # Sanitize secrets before sending back
    sanitized_creds = {}
    for k, v in creds.items():
        k_lower = k.lower()
        if "secret" in k_lower or "password" in k_lower or "token" in k_lower or "pin" in k_lower:
            sanitized_creds[k] = "********" if v else ""
        else:
            sanitized_creds[k] = v
            
    return {"status": "success", "broker": broker, "credentials": sanitized_creds}


@router.post("/broker")
def update_broker_credentials(body: BrokerCredentialsReq, current_user: UserResponse = Depends(get_current_user)):
    user_id = current_user.id
    
    # If the user sends generic obscured masked passwords (********), fetch the old ones to merge
    existing = get_broker_credentials(user_id, body.broker) or {}
    updated_creds = {}
    
    for k, new_v in body.credentials.items():
        if isinstance(new_v, str) and new_v == "********":
            updated_creds[k] = existing.get(k, "")
        else:
            updated_creds[k] = new_v
            
    success = save_broker_credentials(user_id, body.broker, updated_creds)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save broker credentials")
    
    # Clear the broker cache for this user so new adapter connections are created
    clear_adapter_cache(body.broker, user_id)
    
    return {"status": "success", "message": f"Credentials for {body.broker} securely updated."}
