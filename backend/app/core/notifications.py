import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_telegram_message(message: str):
    """
    Sends a message to the configured Telegram chat.
    Safe to call even if Telegram is not configured (will just log).
    """
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        logger.info(f"Telegram not configured. Log: {message}")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                logger.error(f"Failed to send Telegram message: {response.text}")
            else:
                logger.debug("Telegram message sent successfully.")
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")
