"""
Database connection module supporting both SQLite (development) and PostgreSQL (production).
Automatically detects database type from DATABASE_URL environment variable.
"""

import os
import logging
from typing import Optional, Generator, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Get database URL from environment variable
# Default to SQLite for local development
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Check if DATABASE_URL explicitly specifies SQLite
if DATABASE_URL.startswith("sqlite"):
    # SQLite explicitly configured - use it
    pass
elif DATABASE_URL.startswith("postgresql"):
    # PostgreSQL explicitly configured - use it
    pass
elif DATABASE_URL:
    # Unknown format - warn but continue
    logger.warning(f"Unknown DATABASE_URL format: {DATABASE_URL}")
else:
    # No DATABASE_URL set - use config settings
    from app.core.config import settings

    if settings.DB_TYPE == "sqlite":
        db_path = settings.SQLITE_DB_PATH
        db_path.parent.mkdir(parents=True, exist_ok=True)
        DATABASE_URL = f"sqlite:///{db_path}"
    else:
        # Construct PostgreSQL URL from settings
        DATABASE_URL = settings.DATABASE_URL

# Database type detection
IS_SQLITE = DATABASE_URL.startswith("sqlite")
IS_POSTGRESQL = DATABASE_URL.startswith("postgresql")

# ── Engine Configuration ────────────────────────────────────────────────────────

if IS_SQLITE:
    # SQLite configuration
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, Session

    # Import shared Base from db_models
    from app.db_models.base import Base

    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # Required for SQLite
        echo=False,  # Set to True for SQL debugging
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    _psycopg2_available = False
    logger.info(f"SQLite database configured: {DATABASE_URL}")

elif IS_POSTGRESQL:
    # PostgreSQL configuration
    try:
        import psycopg2
        from psycopg2 import pool
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker, Session

        # Import shared Base from db_models
        from app.db_models.base import Base

        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        _psycopg2_available = True
        logger.info(f"PostgreSQL database configured: {DATABASE_URL}")

    except ImportError:
        logger.error(
            "psycopg2 not installed. Install with: pip install psycopg2-binary"
        )
        raise

else:
    raise ValueError(f"Unsupported database type in DATABASE_URL: {DATABASE_URL}")


# ── PostgreSQL Connection Pool ─────────────────────────────────────────────────

_db_pool: Optional[Any] = None


def get_db_pool():
    """Get or create PostgreSQL connection pool."""
    global _db_pool
    if _db_pool is None and IS_POSTGRESQL:
        _db_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
        )
    return _db_pool


def close_db_pool():
    """Close PostgreSQL connection pool."""
    global _db_pool
    if _db_pool:
        _db_pool.closeall()
        _db_pool = None


# ── SQLite SQLAlchemy Session ──────────────────────────────────────────────────


def get_db_session() -> Session:
    """Get SQLAlchemy session for SQLite."""
    return SessionLocal()


# ── Database Session Management ────────────────────────────────────────────────


@contextmanager
def get_db() -> Generator:
    """
    Get database connection/session.
    Use as context manager for automatic cleanup.

    For SQLite: Uses SQLAlchemy ORM session
    For PostgreSQL: Uses psycopg2 raw connection

    Usage:
        with get_db() as db:
            db.execute("SELECT * FROM users")
    """
    if IS_SQLITE:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    else:
        conn = None
        try:
            conn = get_db_pool().getconn()
            yield conn
        finally:
            if conn:
                get_db_pool().putconn(conn)


# ── Database Initialization ────────────────────────────────────────────────────


def init_db():
    """
    Initialize database schema.
    Handles both SQLite (SQLAlchemy) and PostgreSQL (raw SQL).
    """
    if IS_SQLITE:
        # SQLite: Use SQLAlchemy ORM
        Base.metadata.create_all(bind=engine)
        logger.info("SQLite tables created successfully")
    else:
        # PostgreSQL: Use raw SQL
        _init_postgres_schema()


def _init_postgres_schema():
    """Initialize PostgreSQL schema with raw SQL."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                role VARCHAR(50) DEFAULT 'user',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Admin logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_logs (
                id SERIAL PRIMARY KEY,
                admin_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                action VARCHAR(100) NOT NULL,
                target_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Ensure existing constraints have ON DELETE clauses
        try:
            cursor.execute(
                "ALTER TABLE admin_logs DROP CONSTRAINT IF EXISTS admin_logs_admin_id_fkey"
            )
            cursor.execute(
                "ALTER TABLE admin_logs DROP CONSTRAINT IF EXISTS admin_logs_target_user_id_fkey"
            )
        except Exception as e:
            logger.debug(f"Constraint update skipped (might already be updated): {e}")

        cursor.execute("COMMIT")

        # --- Live Trading Module Tables ---

        # Broker Credentials
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS broker_credentials (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                broker VARCHAR(50) NOT NULL,
                credentials JSONB,
                is_active BOOLEAN DEFAULT TRUE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, broker)
            )
        """)

        # Active live strategies configuration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS live_strategies (
                id SERIAL PRIMARY KEY,
                strategy_id VARCHAR(100) NOT NULL,
                name VARCHAR(255),
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                broker VARCHAR(50) NOT NULL,
                status VARCHAR(50) DEFAULT 'ACTIVE',
                symbols JSONB,
                risk_settings JSONB,
                entry_conditions JSONB,
                exit_conditions JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Open and closed positions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id SERIAL PRIMARY KEY,
                live_strategy_id INTEGER REFERENCES live_strategies(id) ON DELETE CASCADE,
                symbol VARCHAR(50) NOT NULL,
                exchange VARCHAR(20) DEFAULT 'NSE',
                entry_price DECIMAL(15,2) NOT NULL,
                quantity INTEGER NOT NULL,
                product_type VARCHAR(20) DEFAULT 'INTRADAY',
                stoploss DECIMAL(15,2),
                target DECIMAL(15,2),
                status VARCHAR(50) DEFAULT 'OPEN',
                entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                exit_time TIMESTAMP,
                exit_price DECIMAL(15,2),
                pnl DECIMAL(15,2),
                pnl_pct DECIMAL(10,2),
                exit_reason VARCHAR(100),
                broker_order_id VARCHAR(100),
                broker_exit_order_id VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Audit logs for automated trading events
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trading_logs (
                id SERIAL PRIMARY KEY,
                live_strategy_id INTEGER REFERENCES live_strategies(id) ON DELETE CASCADE,
                position_id INTEGER REFERENCES positions(id) ON DELETE SET NULL,
                event_type VARCHAR(100) NOT NULL,
                details TEXT,
                event_data JSONB,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes for performance
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_live_strategies_user ON live_strategies(user_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_live_strategies_status ON live_strategies(status)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_positions_strategy ON positions(live_strategy_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_trading_logs_strategy ON trading_logs(live_strategy_id)"
        )

        cursor.execute("COMMIT")
        cursor.close()
        logger.info("PostgreSQL tables created successfully")


# ── User Database Functions (Database Agnostic) ───────────────────────────────


def create_user(
    email: str, password_hash: str, full_name: Optional[str] = None
) -> Optional[int]:
    """Create a new user and return their ID."""
    if IS_SQLITE:
        from app.db_models.user import User

        db = SessionLocal()
        try:
            user = User(email=email, password_hash=password_hash, full_name=full_name)
            db.add(user)
            db.commit()
            db.refresh(user)
            return user.id
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            db.rollback()
            return None
        finally:
            db.close()
    else:
        with get_db() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO users (email, password_hash, full_name)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (email, password_hash, full_name),
                )
                user_id = cursor.fetchone()[0]
                cursor.execute("COMMIT")
                cursor.close()
                return user_id
            except Exception as e:
                logger.error(f"Error creating user: {e}")
                return None


def get_user_by_email(email: str) -> Optional[dict]:
    """Get user by email address."""
    if IS_SQLITE:
        from app.db_models.user import User

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == email).first()
            if user:
                return {
                    "id": user.id,
                    "email": user.email,
                    "password_hash": user.password_hash,
                    "full_name": user.full_name,
                    "role": user.role,
                    "is_active": user.is_active,
                    "created_at": str(user.created_at) if user.created_at else None,
                }
            return None
        finally:
            db.close()
    else:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            row = cursor.fetchone()
            cursor.close()
            if row:
                return {
                    "id": row[0],
                    "email": row[1],
                    "password_hash": row[2],
                    "full_name": row[3],
                    "role": row[4],
                    "is_active": row[5],
                    "created_at": str(row[6]) if row[6] else None,
                }
            return None


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Get user by ID."""
    if IS_SQLITE:
        from app.db_models.user import User

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                return {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role,
                    "is_active": user.is_active,
                    "created_at": str(user.created_at) if user.created_at else None,
                }
            return None
        finally:
            db.close()
    else:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, email, full_name, role, is_active, created_at
                FROM users WHERE id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            cursor.close()
            if row:
                return {
                    "id": row[0],
                    "email": row[1],
                    "full_name": row[2],
                    "role": row[3],
                    "is_active": row[4],
                    "created_at": str(row[5]) if row[5] else None,
                }
            return None


def get_all_users(limit: int = 100, offset: int = 0) -> list:
    """Get all users with pagination."""
    if IS_SQLITE:
        from app.db_models.user import User

        db = SessionLocal()
        try:
            users = (
                db.query(User)
                .order_by(User.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": u.id,
                    "email": u.email,
                    "full_name": u.full_name,
                    "role": u.role,
                    "is_active": u.is_active,
                    "created_at": str(u.created_at) if u.created_at else None,
                }
                for u in users
            ]
        finally:
            db.close()
    else:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, email, full_name, role, is_active, created_at
                FROM users ORDER BY created_at DESC LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [
                {
                    "id": row[0],
                    "email": row[1],
                    "full_name": row[2],
                    "role": row[3],
                    "is_active": row[4],
                    "created_at": str(row[5]) if row[5] else None,
                }
                for row in rows
            ]


# Allowed columns for dynamic update - prevents SQL injection
ALLOWED_USER_UPDATE_COLUMNS = frozenset(
    {"email", "full_name", "role", "is_active", "password_hash"}
)


def update_user(user_id: int, **kwargs) -> bool:
    """Update user fields. Returns True if successful."""
    if not kwargs:
        return True

    # Validate that only allowed columns are being updated
    invalid_columns = set(kwargs.keys()) - ALLOWED_USER_UPDATE_COLUMNS
    if invalid_columns:
        logger.error(f"Error updating user: Invalid columns: {invalid_columns}")
        return False

    if IS_SQLITE:
        from app.db_models.user import User

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            for key, value in kwargs.items():
                setattr(user, key, value)
            db.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    else:
        with get_db() as conn:
            try:
                set_clause = ", ".join([f"{k} = %s" for k in kwargs.keys()])
                values = list(kwargs.values()) + [user_id]
                cursor = conn.cursor()
                cursor.execute(f"UPDATE users SET {set_clause} WHERE id = %s", values)
                cursor.execute("COMMIT")
                cursor.close()
                return True
            except Exception as e:
                logger.error(f"Error updating user: {e}")
                return False


def delete_user(user_id: int) -> bool:
    """Delete user by ID. Returns True if successful."""
    if IS_SQLITE:
        from app.db_models.user import User

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                db.delete(user)
                db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    else:
        with get_db() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                cursor.execute("COMMIT")
                cursor.close()
                return True
            except Exception as e:
                logger.error(f"Error deleting user: {e}")
                return False


# ── Admin Logs Functions ──────────────────────────────────────────────────────


def log_admin_action(
    admin_id: int,
    action: str,
    target_user_id: Optional[int] = None,
    details: Optional[str] = None,
):
    """Log an admin action to the audit log."""
    if IS_SQLITE:
        from app.db_models.admin_log import AdminLog

        db = SessionLocal()
        try:
            log = AdminLog(
                admin_id=admin_id,
                action=action,
                target_user_id=target_user_id,
                details=details,
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.error(f"Error logging admin action: {e}")
            db.rollback()
        finally:
            db.close()
    else:
        with get_db() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO admin_logs (admin_id, action, target_user_id, details)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (admin_id, action, target_user_id, details),
                )
                cursor.execute("COMMIT")
                cursor.close()
            except Exception as e:
                logger.error(f"Error logging admin action: {e}")


def get_admin_logs(limit: int = 50) -> list:
    """Get recent admin logs."""
    if IS_SQLITE:
        from app.db_models.admin_log import AdminLog

        db = SessionLocal()
        try:
            logs = (
                db.query(AdminLog)
                .order_by(AdminLog.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": log.id,
                    "admin_id": log.admin_id,
                    "action": log.action,
                    "target_user_id": log.target_user_id,
                    "details": log.details,
                    "created_at": str(log.created_at) if log.created_at else None,
                }
                for log in logs
            ]
        finally:
            db.close()
    else:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, admin_id, action, target_user_id, details, created_at
                FROM admin_logs ORDER BY created_at DESC LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [
                {
                    "id": row[0],
                    "admin_id": row[1],
                    "action": row[2],
                    "target_user_id": row[3],
                    "details": row[4],
                    "created_at": str(row[5]) if row[5] else None,
                }
                for row in rows
            ]


# ── Stats Functions ───────────────────────────────────────────────────────────


def get_user_stats() -> dict:
    """Get user statistics."""
    if IS_SQLITE:
        from app.db_models.user import User

        db = SessionLocal()
        try:
            total = db.query(User).count()
            active = db.query(User).filter(User.is_active == True).count()
            admin = db.query(User).filter(User.role == "admin").count()
            return {
                "total_users": total,
                "active_users": active,
                "admin_users": admin,
                "inactive_users": total - active,
            }
        finally:
            db.close()
    else:
        with get_db() as conn:
            cursor = conn.cursor()
            stats = {}

            cursor.execute("SELECT COUNT(*) FROM users")
            stats["total_users"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
            stats["active_users"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            stats["admin_users"] = cursor.fetchone()[0]

            stats["inactive_users"] = stats["total_users"] - stats["active_users"]

            cursor.close()
            return stats


# ── Broker Credentials Functions ──────────────────────────────────────────────


def save_broker_credentials(user_id: int, broker: str, credentials_dict: dict) -> bool:
    """Save broker credentials for a user."""
    import json

    if IS_SQLITE:
        from app.db_models.broker import BrokerCredential

        db = SessionLocal()
        try:
            # Check if exists
            cred = (
                db.query(BrokerCredential)
                .filter(
                    BrokerCredential.user_id == user_id,
                    BrokerCredential.broker == broker,
                )
                .first()
            )
            if cred:
                cred.credentials = json.dumps(credentials_dict)
            else:
                cred = BrokerCredential(
                    user_id=user_id,
                    broker=broker,
                    credentials=json.dumps(credentials_dict),
                )
                db.add(cred)
            db.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving broker credentials: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    else:
        with get_db() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO broker_credentials (user_id, broker, credentials, updated_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id, broker)
                    DO UPDATE SET credentials = EXCLUDED.credentials, updated_at = CURRENT_TIMESTAMP
                """,
                    (user_id, broker, json.dumps(credentials_dict)),
                )
                cursor.execute("COMMIT")
                cursor.close()
                return True
            except Exception as e:
                logger.error(f"Error saving broker credentials: {e}")
                return False


def get_broker_credentials(user_id: int, broker: str) -> Optional[dict]:
    """Get broker credentials for a user."""
    import json

    if IS_SQLITE:
        from app.db_models.broker import BrokerCredential

        db = SessionLocal()
        try:
            cred = (
                db.query(BrokerCredential)
                .filter(
                    BrokerCredential.user_id == user_id,
                    BrokerCredential.broker == broker,
                    BrokerCredential.is_active == True,
                )
                .first()
            )
            if cred:
                cred_data = cred.credentials
                if isinstance(cred_data, str):
                    return json.loads(cred_data)
                return cred_data
            return None
        finally:
            db.close()
    else:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT credentials FROM broker_credentials WHERE user_id = %s AND broker = %s AND is_active = TRUE",
                (user_id, broker),
            )
            row = cursor.fetchone()
            cursor.close()
            if row:
                return row[0] if isinstance(row[0], dict) else json.loads(row[0])
            return None
