#!/usr/bin/env python3
"""
Import PostgreSQL database from SQL file.
Usage:
    python3 scripts/import_db.py [input_file]
"""

import sys
import os
import subprocess
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings


def import_database(input_file):
    """Import PostgreSQL database from SQL file."""
    
    if settings.DB_TYPE != "postgres":
        print("❌ Error: DB_TYPE must be 'postgres' to import")
        print(f"   Current DB_TYPE: {settings.DB_TYPE}")
        sys.exit(1)
    
    if not os.path.exists(input_file):
        print(f"❌ Error: File not found: {input_file}")
        sys.exit(1)
    
    print("=" * 60)
    print("  SignalCraft - Database Import")
    print("=" * 60)
    print()
    print(f"📦 Importing to database: {settings.DB_NAME}")
    print(f"📁 Input file: {input_file}")
    print()
    
    # Build psql command
    cmd = [
        "psql",
        "-h", settings.DB_HOST,
        "-p", settings.DB_PORT,
        "-U", settings.DB_USER,
        "-d", settings.DB_NAME,
        "-f", input_file
    ]
    
    # Set password environment variable
    env = os.environ.copy()
    env["PGPASSWORD"] = settings.DB_PASSWORD
    
    try:
        print("Running psql import...")
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            print()
            print("=" * 60)
            print("  ✅ Import Complete!")
            print("=" * 60)
            print()
            print("Database has been successfully imported.")
            print("You can now access the admin panel with your migrated credentials.")
            print()
        else:
            print(f"❌ Import failed: {result.stderr}")
            sys.exit(1)
            
    except FileNotFoundError:
        print("❌ Error: psql not found. Install PostgreSQL client:")
        print("   Ubuntu: sudo apt install postgresql-client")
        print("   Mac: brew install postgresql")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 import_db.py [input_file.sql]")
        print()
        print("Example:")
        print("  python3 import_db.py backups/signalcraft_backup_20260227_120000.sql")
        sys.exit(1)
    
    input_file = sys.argv[1]
    import_database(input_file)
