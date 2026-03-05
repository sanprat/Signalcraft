#!/usr/bin/env python3
"""
Create the first admin user for SignalCraft.
Works with both SQLite and PostgreSQL.

Usage:
    python3 scripts/create_admin.py
"""

import sys
import os
from getpass import getpass
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env and .env.db
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
load_dotenv(project_root / ".env")
load_dotenv(project_root / ".env.db")

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings
from app.core.database import init_db, get_user_by_email, create_user, get_db


def get_password_hash(password: str) -> str:
    """Hash password using the same method as auth router."""
    import hashlib
    import secrets
    
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"{salt}${key.hex()}"


def create_first_admin():
    """Create the first admin user interactively."""
    
    print("=" * 60)
    print("  SignalCraft - Create First Admin User")
    print("=" * 60)
    print()
    
    # Show database type
    db_type = settings.DB_TYPE
    if db_type == "postgres":
        print(f"📦 Database: PostgreSQL ({settings.DB_NAME})")
        print(f"   Host: {settings.DB_HOST}:{settings.DB_PORT}")
    else:
        print(f"📦 Database: SQLite ({settings.SQLITE_DB_PATH})")
    print()
    
    # Initialize database (creates tables if they don't exist)
    print("📦 Initializing database...")
    init_db()
    print("✅ Database ready!")
    print()
    
    # Get admin details
    print("Enter admin details:")
    print()
    
    while True:
        email = input("  Email: ").strip()
        if not email:
            print("  ❌ Email cannot be empty!")
            continue
        if "@" not in email:
            print("  ❌ Please enter a valid email address!")
            continue
        break
    
    while True:
        password = getpass("  Password: ")
        if len(password) < 6:
            print("  ❌ Password must be at least 6 characters!")
            continue
        password_confirm = getpass("  Confirm Password: ")
        if password != password_confirm:
            print("  ❌ Passwords do not match!")
            continue
        break
    
    full_name = input("  Full Name (optional): ").strip()
    
    print()
    print("Creating admin account...")
    
    # Check if user already exists
    existing_user = get_user_by_email(email)
    if existing_user:
        print(f"❌ Error: User with email '{email}' already exists!")
        
        # Check if already admin
        if existing_user.get('role') == 'admin':
            print(f"ℹ️  This user is already an admin.")
        else:
            print(f"ℹ️  This user has role: {existing_user.get('role', 'user')}")
            upgrade = input("  Would you like to upgrade them to admin? (y/n): ").strip().lower()
            if upgrade == 'y':
                from app.core.database import update_user
                success = update_user(existing_user['id'], role='admin')
                if success:
                    print(f"✅ User '{email}' is now an admin!")
                else:
                    print(f"❌ Failed to upgrade user.")
            else:
                print("❌ Admin creation cancelled.")
        return
    
    # Create admin user
    password_hash = get_password_hash(password)
    user_id = create_user(email, password_hash, full_name or None)
    
    if user_id:
        # Set role to admin
        from app.core.database import update_user
        update_user(user_id, role='admin')
        
        print()
        print("=" * 60)
        print("  ✅ Admin User Created Successfully!")
        print("=" * 60)
        print()
        print(f"  ID:        {user_id}")
        print(f"  Email:     {email}")
        print(f"  Name:      {full_name or 'N/A'}")
        print(f"  Role:      admin")
        print()
        print("  You can now login at: http://localhost:3000/admin/login")
        print()
        print("  ⚠️  IMPORTANT: Remember these credentials!")
        print("  Store them in a secure password manager.")
        print("=" * 60)
    else:
        print()
        print("❌ Error creating admin user. Check logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    create_first_admin()
