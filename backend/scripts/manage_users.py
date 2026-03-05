#!/usr/bin/env python3
"""
Manage users in SignalCraft database.
List, delete, update users from command line.

Usage:
    python3 scripts/manage_users.py list              # List all users
    python3 scripts/manage_users.py delete <id>       # Delete user by ID
    python3 scripts/manage_users.py delete --email user@example.com
    python3 scripts/manage_users.py role <id> admin   # Change user role to admin
    python3 scripts/manage_users.py role <id> user    # Change user role to user
    python3 scripts/manage_users.py activate <id>     # Activate user
    python3 scripts/manage_users.py deactivate <id>   # Deactivate user
"""

import sys
import os
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
from app.core.database import (
    init_db, 
    get_user_by_id, 
    get_user_by_email, 
    get_all_users,
    update_user, 
    delete_user
)


def list_users():
    """List all users in the database."""
    print("\n" + "=" * 80)
    print("  SignalCraft - All Users")
    print("=" * 80)
    
    users = get_all_users(limit=100, offset=0)
    
    if not users:
        print("\n  No users found in database.")
        return
    
    print(f"\n  {'ID':<5} {'Email':<35} {'Name':<20} {'Role':<8} {'Active':<8} {'Created':<20}")
    print("  " + "-" * 96)
    
    for user in users:
        email = user['email'][:33] + '..' if len(user['email']) > 35 else user['email']
        name = (user.get('full_name') or 'N/A')[:18] + '..' if len(user.get('full_name') or '') > 20 else (user.get('full_name') or 'N/A')
        role = user.get('role', 'user')
        is_active = 'Yes' if user.get('is_active', True) else 'No'
        created = str(user.get('created_at', 'N/A'))[:19]
        
        print(f"  {user['id']:<5} {email:<35} {name:<20} {role:<8} {is_active:<8} {created:<20}")
    
    print("\n" + "=" * 80)
    print(f"  Total users: {len(users)}")
    print("=" * 80 + "\n")


def delete_user_by_id(user_id: int):
    """Delete a user by ID."""
    user = get_user_by_id(user_id)
    
    if not user:
        print(f"\n  ❌ Error: User with ID {user_id} not found!")
        return False
    
    print("\n" + "=" * 60)
    print("  ⚠️  Confirm Deletion")
    print("=" * 60)
    print(f"\n  Email:  {user['email']}")
    print(f"  Name:   {user.get('full_name', 'N/A')}")
    print(f"  Role:   {user.get('role', 'user')}")
    print(f"  ID:     {user_id}")
    print()
    
    confirm = input("  Are you sure you want to delete this user? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("\n  ❌ Deletion cancelled.")
        return False
    
    # Try to delete, handle foreign key constraint
    from app.core.database import get_db
    
    try:
        with get_db() as conn:
            if settings.DB_TYPE == "postgres":
                cursor = conn.cursor()
                
                # First, delete admin logs where this user is the admin
                cursor.execute("DELETE FROM admin_logs WHERE admin_id = %s", (user_id,))
                
                # Then delete admin logs where this user is the target
                cursor.execute("DELETE FROM admin_logs WHERE target_user_id = %s", (user_id,))
                
                conn.commit()
                cursor.close()
            else:
                conn.execute("DELETE FROM admin_logs WHERE admin_id = ?", (user_id,))
                conn.execute("DELETE FROM admin_logs WHERE target_user_id = ?", (user_id,))
                conn.commit()
        
        # Now delete the user
        success = delete_user(user_id)
        
        if success:
            print("\n  ✅ User and related logs deleted successfully!")
        else:
            print("\n  ❌ Failed to delete user.")
        
        print("=" * 60 + "\n")
        return success
        
    except Exception as e:
        print(f"\n  ❌ Error deleting user: {e}")
        print("=" * 60 + "\n")
        return False


def delete_user_by_email(email: str):
    """Delete a user by email."""
    user = get_user_by_email(email)
    
    if not user:
        print(f"\n  ❌ Error: User with email '{email}' not found!")
        return False
    
    return delete_user_by_id(user['id'])


def change_role(user_id: int, new_role: str):
    """Change user's role."""
    if new_role not in ['admin', 'user']:
        print(f"\n  ❌ Error: Invalid role '{new_role}'. Must be 'admin' or 'user'.")
        return False
    
    user = get_user_by_id(user_id)
    
    if not user:
        print(f"\n  ❌ Error: User with ID {user_id} not found!")
        return False
    
    old_role = user.get('role', 'user')
    
    print(f"\n  Changing role for {user['email']}...")
    print(f"  Old role: {old_role}")
    print(f"  New role: {new_role}")
    
    success = update_user(user_id, role=new_role)
    
    if success:
        print(f"  ✅ Role updated successfully!")
    else:
        print(f"  ❌ Failed to update role.")
    
    return success


def set_active_status(user_id: int, active: bool):
    """Set user's active status."""
    user = get_user_by_id(user_id)
    
    if not user:
        print(f"\n  ❌ Error: User with ID {user_id} not found!")
        return False
    
    status_str = "activate" if active else "deactivate"
    
    print(f"\n  {status_str.capitalize()} user {user['email']}...")
    
    success = update_user(user_id, is_active=active)
    
    if success:
        print(f"  ✅ User {status_str}d successfully!")
    else:
        print(f"  ❌ Failed to {status_str} user.")
    
    return success


def print_usage():
    """Print usage instructions."""
    print("\n" + "=" * 60)
    print("  SignalCraft User Management")
    print("=" * 60)
    print("\n  Usage:")
    print("    python3 scripts/manage_users.py <command> [arguments]")
    print("\n  Commands:")
    print("    list                      - List all users")
    print("    delete <id>               - Delete user by ID")
    print("    delete --email <email>    - Delete user by email")
    print("    role <id> <admin|user>    - Change user role")
    print("    activate <id>             - Activate user account")
    print("    deactivate <id>           - Deactivate user account")
    print("    reset-password <id>       - Reset password for user by ID")
    print("    reset-password --email <email> - Reset password by email")
    print("\n  Examples:")
    print("    python3 scripts/manage_users.py list")
    print("    python3 scripts/manage_users.py delete 3")
    print("    python3 scripts/manage_users.py delete --email test@example.com")
    print("    python3 scripts/manage_users.py role 3 admin")
    print("    python3 scripts/manage_users.py activate 3")
    print("    python3 scripts/manage_users.py deactivate 3")
    print("    python3 scripts/manage_users.py reset-password 3")
    print("    python3 scripts/manage_users.py reset-password --email user@example.com")
    print("\n" + "=" * 60 + "\n")


def reset_password(user_id: int = None, email: str = None):
    """Reset a user's password interactively."""
    from getpass import getpass
    
    # Get user
    if email:
        user = get_user_by_email(email)
        if not user:
            print(f"\n  ❌ Error: User with email '{email}' not found!")
            return False
    elif user_id:
        user = get_user_by_id(user_id)
        if not user:
            print(f"\n  ❌ Error: User with ID {user_id} not found!")
            return False
    else:
        print("\n  ❌ Error: Must provide user ID or email!")
        return False
    
    print("\n" + "=" * 60)
    print(f"  Reset Password for: {user['email']}")
    print("=" * 60)
    print()
    
    # Get new password
    while True:
        new_password = getpass("  New Password: ")
        if len(new_password) < 6:
            print("  ❌ Password must be at least 6 characters!")
            continue
        
        confirm_password = getpass("  Confirm Password: ")
        if new_password != confirm_password:
            print("  ❌ Passwords do not match!")
            continue
        break
    
    # Hash the new password
    import hashlib
    import secrets
    
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac('sha256', new_password.encode(), salt.encode(), 100000)
    password_hash = f'{salt}${key.hex()}'
    
    # Update password in database
    from app.core.database import get_db
    
    try:
        with get_db() as conn:
            if settings.DB_TYPE == "postgres":
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET password_hash = %s WHERE id = %s",
                    (password_hash, user['id'])
                )
                conn.commit()
                cursor.close()
            else:
                conn.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (password_hash, user['id'])
                )
                conn.commit()
        
        print("\n  ✅ Password reset successfully!")
        print("=" * 60 + "\n")
        return True
        
    except Exception as e:
        print(f"\n  ❌ Error resetting password: {e}")
        print("=" * 60 + "\n")
        return False


def main():
    """Main entry point."""
    print("\n📦 Initializing database...")
    init_db()
    print("✅ Database ready!\n")
    
    if len(sys.argv) < 2:
        print_usage()
        return
    
    command = sys.argv[1].lower()
    
    if command == 'list':
        list_users()
    
    elif command == 'delete':
        if len(sys.argv) < 3:
            print("\n  ❌ Error: Missing user ID or email!")
            print_usage()
            return
        
        if sys.argv[2] == '--email':
            if len(sys.argv) < 4:
                print("\n  ❌ Error: Missing email address!")
                print_usage()
                return
            delete_user_by_email(sys.argv[3])
        else:
            try:
                user_id = int(sys.argv[2])
                delete_user_by_id(user_id)
            except ValueError:
                print("\n  ❌ Error: Invalid user ID!")
                print_usage()
    
    elif command == 'role':
        if len(sys.argv) < 4:
            print("\n  ❌ Error: Missing user ID or role!")
            print_usage()
            return
        
        try:
            user_id = int(sys.argv[2])
            new_role = sys.argv[3].lower()
            change_role(user_id, new_role)
        except ValueError:
            print("\n  ❌ Error: Invalid user ID!")
            print_usage()
    
    elif command == 'activate':
        if len(sys.argv) < 3:
            print("\n  ❌ Error: Missing user ID!")
            print_usage()
            return
        
        try:
            user_id = int(sys.argv[2])
            set_active_status(user_id, True)
        except ValueError:
            print("\n  ❌ Error: Invalid user ID!")
            print_usage()
    
    elif command == 'deactivate':
        if len(sys.argv) < 3:
            print("\n  ❌ Error: Missing user ID!")
            print_usage()
            return

        try:
            user_id = int(sys.argv[2])
            set_active_status(user_id, False)
        except ValueError:
            print("\n  ❌ Error: Invalid user ID!")
            print_usage()

    elif command == 'reset-password':
        if len(sys.argv) < 3:
            print("\n  ❌ Error: Missing user ID or email!")
            print_usage()
            return

        if sys.argv[2] == '--email':
            if len(sys.argv) < 4:
                print("\n  ❌ Error: Missing email address!")
                print_usage()
                return
            reset_password(email=sys.argv[3])
        else:
            try:
                user_id = int(sys.argv[2])
                reset_password(user_id=user_id)
            except ValueError:
                print("\n  ❌ Error: Invalid user ID!")
                print_usage()

    else:
        print(f"\n  ❌ Unknown command: {command}")
        print_usage()


if __name__ == "__main__":
    main()
