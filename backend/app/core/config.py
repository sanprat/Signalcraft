"""
SignalCraft Backend Configuration
Loads settings from environment variables with sensible defaults.
Supports both SQLite (development) and PostgreSQL (production).
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Load database configuration from .env.db
load_dotenv(Path(__file__).parent.parent.parent / ".env.db")


class Settings:
    """Application settings loaded from environment variables."""

    # Base directories
    BASE_DIR = Path(__file__).parent.parent.parent
    DATA_DIR = BASE_DIR / "data"

    # Database Configuration
    DB_TYPE = os.getenv("DB_TYPE", "postgres")  # 'sqlite' or 'postgres'
    SQLITE_DB_PATH = Path(os.getenv("SQLITE_DB_PATH", "data/users.db"))

    # PostgreSQL Settings
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_USER = os.getenv("DB_USER", "signalcraft")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "signalcraft_dev_pass")
    DB_NAME = os.getenv("DB_NAME", "signalcraft")
    
    @property
    def DATABASE_URL(self) -> str:
        """Get database connection URL."""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # JWT Settings
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "signalcraft-dev-key-change-in-production")
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
    
    # CORS Settings
    @property
    def CORS_ORIGINS(self) -> List[str]:
        origins_str = os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
        return [origin.strip() for origin in origins_str.split(",")]
    
    # API Settings
    API_TITLE = "SignalCraft API"
    API_VERSION = "2.0"
    API_PORT = 8001
    
    # Market Settings
    MARKET_OPEN_HOUR = 9
    MARKET_OPEN_MINUTE = 15
    MARKET_CLOSE_HOUR = 15
    MARKET_CLOSE_MINUTE = 30
    
    # Broker Configuration (loaded from .env)
    ANGEL1_CLIENT_ID = os.getenv("ANGEL1_CLIENT_ID")
    ANGEL1_API_KEY = os.getenv("ANGEL1_API_KEY")
    ANGEL1_TOTP_SECRET = os.getenv("ANGEL1_TOTP_SECRET")
    ANGEL1_MPIN = os.getenv("ANGEL1_MPIN")
    
    SHOONYA_USER_ID = os.getenv("SHOONYA_USER_ID")
    SHOONYA_PASSWORD = os.getenv("SHOONYA_PASSWORD")
    SHOONYA_API_KEY = os.getenv("SHOONYA_API_KEY")
    SHOONYA_VENDOR_CODE = os.getenv("SHOONYA_VENDOR_CODE")
    SHOONYA_IMEI = os.getenv("SHOONYA_IMEI")
    SHOONYA_TOTP_SECRET = os.getenv("SHOONYA_TOTP_SECRET")
    
    DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
    DHAN_PASSWORD = os.getenv("DHAN_PASSWORD")
    DHAN_TOTP_SECRET = os.getenv("DHAN_TOTP_SECRET")
    DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
    
    # Telegram Configuration
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# Global settings instance
settings = Settings()
