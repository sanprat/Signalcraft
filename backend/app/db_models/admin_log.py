"""SQLAlchemy AdminLog model."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from app.db_models.base import Base


class AdminLog(Base):
    """Admin audit log model for SQLite ORM operations."""

    __tablename__ = "admin_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    admin_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action = Column(String(100), nullable=False)
    target_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    details = Column(Text, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
