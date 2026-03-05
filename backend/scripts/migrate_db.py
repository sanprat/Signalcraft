#!/usr/bin/env python3
"""
Migrate existing database to add admin panel support.
Adds role column and admin_logs table.

Usage:
    python3 migrate_db.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings
import sqlite3


def migrate_database():
    """Add role column and admin_logs table to existing database."""
    
    print("=" * 60)
    print("  SignalCraft - Database Migration")
    print("=" * 60)
    print()
    
    db_path = settings.DATABASE_PATH
    print(f"📦 Database path: {db_path}")
    
    if not db_path.exists():
        print("❌ Database not found. Run create_admin.py first to initialize.")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if role column already exists
    print()
    print("Checking schema...")
    
    columns = [row[1] for row in cursor.execute("PRAGMA table_info(users)")]
    
    if 'role' not in columns:
        print("  ⚠️  'role' column not found. Adding...")
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
            print("  ✅ Added 'role' column to users table")
        except sqlite3.OperationalError as e:
            print(f"  ⚠️  Could not add role column: {e}")
    else:
        print("  ✅ 'role' column already exists")
    
    if 'is_active' not in columns:
        print("  ⚠️  'is_active' column not found. Adding...")
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
            print("  ✅ Added 'is_active' column to users table")
        except sqlite3.OperationalError as e:
            print(f"  ⚠️  Could not add is_active column: {e}")
    else:
        print("  ✅ 'is_active' column already exists")
    
    # Check if admin_logs table exists
    tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    
    if 'admin_logs' not in tables:
        print("  ⚠️  'admin_logs' table not found. Creating...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                target_user_id INTEGER,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (admin_id) REFERENCES users(id),
                FOREIGN KEY (target_user_id) REFERENCES users(id)
            )
        """)
        print("  ✅ Created 'admin_logs' table")
    else:
        print("  ✅ 'admin_logs' table already exists")
    
    conn.commit()
    
    # Show current users
    print()
    print("Current users in database:")
    print("-" * 60)
    
    users = cursor.execute("SELECT id, email, role, is_active FROM users").fetchall()
    
    if users:
        for user in users:
            role = user[2] or 'user'
            status = "Active" if user[3] else "Inactive"
            print(f"  ID: {user[0]} | Email: {user[1]} | Role: {role} | Status: {status}")
    else:
        print("  (No users found)")
    
    print("-" * 60)
    
    # Upgrade existing users to admin if they want
    print()
    if users:
        print("💡 Tip: To make an existing user an admin, run:")
        print(f"   UPDATE users SET role = 'admin' WHERE email = 'YOUR_EMAIL';")
        print()
        print("   Or use this Python command:")
        if users:
            first_email = users[0][1]
            print(f"   python3 -c \"import sqlite3; conn = sqlite3.connect('{db_path}'); conn.execute(\"UPDATE users SET role = 'admin' WHERE email = '{first_email}'\"); conn.commit(); conn.close()\"")
    
    conn.close()
    
    print()
    print("=" * 60)
    print("  ✅ Migration Complete!")
    print("=" * 60)
    print()
    print("You can now:")
    print("  1. Create first admin: python3 backend/scripts/create_admin.py")
    print("  2. Access admin panel: http://localhost:3000/admin/login")
    print()


if __name__ == "__main__":
    migrate_database()
