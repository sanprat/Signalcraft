import asyncio
import sys
import os

# Add the backend directory to sys.path so we can import app modules
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from app.core.notifications import send_telegram_message

async def main():
    print("🚀 Sending test Telegram message...")
    message = (
        "🔔 *SignalCraft Test Notification*\n"
        "Your Telegram bot integration is working correctly!\n"
        "Status: ✅ Online\n"
        "System: Pytrader Live Trading v2.0"
    )
    await send_telegram_message(message)
    print("✅ Test message sent. Please check your Telegram app.")

if __name__ == "__main__":
    asyncio.run(main())
