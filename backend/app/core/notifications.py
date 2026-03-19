import httpx
import logging
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_telegram_message(message: str):
    """
    Send to the globally configured Telegram chat (env vars).
    Safe to call even if Telegram is not configured.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        logger.info(f"Telegram not configured (global). Log: {message}")
        return

    await _send(token, chat_id, message)


async def send_user_telegram_message(user_id: int, message: str):
    """
    Send a Telegram message to a specific user's configured chat.
    Looks up the user's saved bot token + chat_id from the DB.
    Falls back to env-var globals if not set for that user.
    """
    token: Optional[str] = None
    chat_id: Optional[str] = None

    try:
        from app.core.database import get_broker_credentials
        creds = get_broker_credentials(user_id, "telegram") or {}
        token = creds.get("bot_token") or settings.TELEGRAM_BOT_TOKEN or ""
        chat_id = creds.get("chat_id") or settings.TELEGRAM_CHAT_ID or ""
    except Exception as e:
        logger.warning(f"Could not load Telegram credentials for user {user_id}: {e}")
        token = settings.TELEGRAM_BOT_TOKEN or ""
        chat_id = settings.TELEGRAM_CHAT_ID or ""

    if not token or not chat_id:
        logger.info(f"Telegram not configured for user {user_id}. Log: {message}")
        return

    await _send(token, chat_id, message)


async def _send(token: str, chat_id: str, message: str):
    """Low-level Telegram sendMessage call."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                logger.error(f"Failed to send Telegram message: {response.text}")
            else:
                logger.debug("Telegram message sent successfully.")
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")
