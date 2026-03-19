from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

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

    clear_adapter_cache(body.broker, user_id)
    return {"status": "success", "message": f"Credentials for {body.broker} securely updated."}


# ── Telegram Endpoints ─────────────────────────────────────────────────────────

class TelegramConfigReq(BaseModel):
    bot_token: str
    chat_id: str


@router.get("/telegram")
def get_telegram_config(current_user: UserResponse = Depends(get_current_user)):
    """Return Telegram config for this user. Falls back to env vars if no DB entry yet."""
    from app.core.config import settings

    creds = get_broker_credentials(current_user.id, "telegram") or {}
    bot_token = creds.get("bot_token") or settings.TELEGRAM_BOT_TOKEN or ""
    chat_id = creds.get("chat_id") or settings.TELEGRAM_CHAT_ID or ""

    return {
        "bot_token": "********" if bot_token else "",
        "chat_id": chat_id,
        "configured": bool(bot_token and chat_id),
        "source": "database" if creds else ("env" if bot_token else "none"),
    }


@router.post("/telegram")
def save_telegram_config(body: TelegramConfigReq, current_user: UserResponse = Depends(get_current_user)):
    """Save Telegram bot token + chat ID for this user in the DB."""
    from app.core.config import settings

    existing = get_broker_credentials(current_user.id, "telegram") or {}

    # Keep existing token if the frontend sent back the masked placeholder
    bot_token = body.bot_token
    if bot_token == "********":
        bot_token = existing.get("bot_token") or settings.TELEGRAM_BOT_TOKEN or ""

    success = save_broker_credentials(current_user.id, "telegram", {
        "bot_token": bot_token,
        "chat_id": body.chat_id,
    })
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save Telegram config")

    return {"status": "success", "message": "Telegram configuration saved."}


@router.get("/telegram/lookup")
async def lookup_telegram_chat_id(current_user: UserResponse = Depends(get_current_user)):
    """
    Call the bot's getUpdates to return a list of Telegram users who've
    messaged the bot. The user can pick themselves from the list.
    Requires them to have sent at least one message to @Pytradersc_bot first.
    """
    import httpx
    from app.core.config import settings

    creds = get_broker_credentials(current_user.id, "telegram") or {}
    bot_token = creds.get("bot_token") or settings.TELEGRAM_BOT_TOKEN or ""

    if not bot_token:
        raise HTTPException(status_code=400, detail="No bot token configured.")

    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
        data = resp.json()
        if not data.get("ok"):
            raise HTTPException(status_code=400, detail="Telegram API error: " + str(data.get("description", "")))

        seen = {}
        for update in data.get("result", []):
            msg = update.get("message") or update.get("channel_post") or {}
            chat = msg.get("chat", {})
            cid = chat.get("id")
            if cid and cid not in seen:
                seen[cid] = {
                    "chat_id": str(cid),
                    "name": f"{chat.get('first_name', '')} {chat.get('last_name', '')}".strip() or chat.get("title", "Unknown"),
                    "type": chat.get("type", "private"),
                }

        if not seen:
            raise HTTPException(
                status_code=404,
                detail="No messages found. Please send any message to the bot on Telegram first, then try again."
            )

        return {"users": list(seen.values())}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reach Telegram: {str(e)}")


@router.post("/telegram/test")
async def test_telegram(current_user: UserResponse = Depends(get_current_user)):
    """Send a test message via Telegram using this user's saved credentials."""
    import httpx
    from app.core.config import settings

    creds = get_broker_credentials(current_user.id, "telegram") or {}
    bot_token = creds.get("bot_token") or settings.TELEGRAM_BOT_TOKEN or ""
    chat_id = creds.get("chat_id") or settings.TELEGRAM_CHAT_ID or ""

    if not bot_token:
        raise HTTPException(status_code=400, detail="Bot token not configured. Save your Telegram settings first.")
    if not chat_id:
        raise HTTPException(status_code=400, detail="Chat ID not set. Enter your Chat ID and save first.")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": (
            "✅ *SignalCraft Connected!*\n\n"
            "Telegram notifications are working. You'll receive alerts here for:\n"
            "• 🟢 Trade entries\n• 🔴 Trade exits\n• 🛑 Stop-loss hits\n• ⚠️ Risk limit alerts"
        ),
        "parse_mode": "Markdown",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code == 200:
            return {"status": "success", "message": "Test message sent! Check your Telegram."}
        else:
            detail = resp.json().get("description", "Unknown Telegram API error")
            raise HTTPException(status_code=400, detail=f"Telegram API error: {detail}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not reach Telegram: {str(e)}")
