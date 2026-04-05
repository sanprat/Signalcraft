"""SQLAlchemy User model."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime

from app.db_models.base import Base
from app.db_models.timestamps import utc_now_naive


class User(Base):
    """User model for SQLite ORM operations."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=False), default=utc_now_naive)
