"""SQLAlchemy BrokerCredential model."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from app.db_models.base import Base


class BrokerCredential(Base):
    """Broker credentials model for SQLite ORM operations."""

    __tablename__ = "broker_credentials"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    broker = Column(String(50), nullable=False)
    credentials = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
