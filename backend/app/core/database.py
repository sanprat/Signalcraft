"""
Database connection module supporting PostgreSQL exclusively.
"""
from contextlib import contextmanager
from typing import Optional, Generator
import psycopg2
from psycopg2 import pool
from datetime import datetime

from app.core.config import settings


# PostgreSQL connection pool (initialized on first use)
_db_pool: Optional[pool.SimpleConnectionPool] = None


def get_db_pool():
    """Get or create PostgreSQL connection pool."""
    global _db_pool
    if _db_pool is None:
        _db_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )
    return _db_pool


def close_db_pool():
    """Close PostgreSQL connection pool."""
    global _db_pool
    if _db_pool:
        _db_pool.closeall()
        _db_pool = None


@contextmanager
def get_db():
    """
    Get PostgreSQL database connection.
    Use as context manager for automatic cleanup.
    
    Usage:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
    """
    conn = None
    try:
        conn = get_db_pool().getconn()
        yield conn
    finally:
        if conn:
            get_db_pool().putconn(conn)


def init_db():
    """
    Initialize database schema in PostgreSQL.
    """
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
            # Drop old constraints if they exist (Postgres auto-names them usually like table_column_fkey)
            cursor.execute("ALTER TABLE admin_logs DROP CONSTRAINT IF EXISTS admin_logs_admin_id_fkey")
            cursor.execute("ALTER TABLE admin_logs DROP CONSTRAINT IF EXISTS admin_logs_target_user_id_fkey")
        except Exception as e:
            print(f"Note: Constraint update skipped or failed (might already be updated): {e}")
            
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_live_strategies_user ON live_strategies(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_live_strategies_status ON live_strategies(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_strategy ON positions(live_strategy_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trading_logs_strategy ON trading_logs(live_strategy_id)")

        cursor.execute("COMMIT")
        cursor.close()


# ── User Database Functions (Database Agnostic) ──────────────────────────────

def create_user(email: str, password_hash: str, full_name: Optional[str] = None) -> Optional[int]:
    """Create a new user and return their ID."""
    with get_db() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (email, password_hash, full_name) 
                VALUES (%s, %s, %s) 
                RETURNING id
                """,
                (email, password_hash, full_name)
            )
            user_id = cursor.fetchone()[0]
            cursor.execute("COMMIT")
            cursor.close()
            return user_id
        except Exception as e:
            print(f"Error creating user: {e}")
            return None


def get_user_by_email(email: str) -> Optional[dict]:
    """Get user by email address."""
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
                "created_at": str(row[6]) if row[6] else None
            }
        return None


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Get user by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, email, full_name, role, is_active, created_at 
            FROM users WHERE id = %s
            """, 
            (user_id,)
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
                "created_at": str(row[5]) if row[5] else None
            }
        return None


def get_all_users(limit: int = 100, offset: int = 0) -> list:
    """Get all users with pagination."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, email, full_name, role, is_active, created_at 
            FROM users ORDER BY created_at DESC LIMIT %s OFFSET %s
            """,
            (limit, offset)
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
                "created_at": str(row[5]) if row[5] else None
            }
            for row in rows
        ]


def update_user(user_id: int, **kwargs) -> bool:
    """Update user fields. Returns True if successful."""
    if not kwargs:
        return True
    
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
            print(f"Error updating user: {e}")
            return False


def delete_user(user_id: int) -> bool:
    """Delete user by ID. Returns True if successful."""
    with get_db() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            cursor.execute("COMMIT")
            cursor.close()
            return True
        except Exception as e:
            print(f"Error deleting user: {e}")
            return False


# ── Admin Logs Functions ──────────────────────────────────────────────────────

def log_admin_action(admin_id: int, action: str, target_user_id: Optional[int] = None, details: Optional[str] = None):
    """Log an admin action to the audit log."""
    with get_db() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO admin_logs (admin_id, action, target_user_id, details)
                VALUES (%s, %s, %s, %s)
                """,
                (admin_id, action, target_user_id, details)
            )
            cursor.execute("COMMIT")
            cursor.close()
        except Exception as e:
            print(f"Error logging admin action: {e}")


def get_admin_logs(limit: int = 50) -> list:
    """Get recent admin logs."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, admin_id, action, target_user_id, details, created_at 
            FROM admin_logs ORDER BY created_at DESC LIMIT %s
            """,
            (limit,)
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
                "created_at": str(row[5]) if row[5] else None
            }
            for row in rows
        ]


# ── Stats Functions ───────────────────────────────────────────────────────────

def get_user_stats() -> dict:
    """Get user statistics."""
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
# ── Broker Credentials Functions ─────────────────────────────────────────────

def save_broker_credentials(user_id: int, broker: str, credentials_dict: dict) -> bool:
    with get_db() as conn:
        try:
            import json
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO broker_credentials (user_id, broker, credentials, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, broker) 
                DO UPDATE SET credentials = EXCLUDED.credentials, updated_at = CURRENT_TIMESTAMP
            """, (user_id, broker, json.dumps(credentials_dict)))
            cursor.execute("COMMIT")
            cursor.close()
            return True
        except Exception as e:
            print(f"Error saving broker credentials: {e}")
            return False

def get_broker_credentials(user_id: int, broker: str) -> Optional[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT credentials FROM broker_credentials WHERE user_id = %s AND broker = %s AND is_active = TRUE", (user_id, broker))
        row = cursor.fetchone()
        cursor.close()
        if row:
            import json
            return row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return None
