#!/usr/bin/env python3
"""
Export PostgreSQL database to SQL file for migration.
Usage:
    python3 scripts/export_db.py [output_file]
"""

import sys
import os
import subprocess
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings


def export_database(output_file=None):
    """Export PostgreSQL database to SQL file."""
    
    if settings.DB_TYPE != "postgres":
        print("❌ Error: DB_TYPE must be 'postgres' to export")
        print(f"   Current DB_TYPE: {settings.DB_TYPE}")
        sys.exit(1)
    
    if not output_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"backups/signalcraft_backup_{timestamp}.sql"
    
    # Ensure backups directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    print("=" * 60)
    print("  SignalCraft - Database Export")
    print("=" * 60)
    print()
    print(f"📦 Exporting database: {settings.DB_NAME}")
    print(f"📁 Output file: {output_file}")
    print()
    
    # Build pg_dump command
    cmd = [
        "pg_dump",
        "-h", settings.DB_HOST,
        "-p", settings.DB_PORT,
        "-U", settings.DB_USER,
        "-d", settings.DB_NAME,
        "-F", "p",  # Plain text format
        "-f", output_file
    ]
    
    # Set password environment variable
    env = os.environ.copy()
    env["PGPASSWORD"] = settings.DB_PASSWORD
    
    try:
        print("Running pg_dump...")
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Get file size
            file_size = os.path.getsize(output_file)
            file_size_mb = file_size / (1024 * 1024)
            
            print()
            print("=" * 60)
            print("  ✅ Export Complete!")
            print("=" * 60)
            print()
            print(f"📊 Backup file: {output_file}")
            print(f"📏 File size: {file_size_mb:.2f} MB")
            print()
            print("To import on VPS:")
            print(f"  1. Copy file: scp {output_file} user@vps-ip:/home/")
            print(f"  2. Import: psql -U {settings.DB_USER} -d {settings.DB_NAME} -f /home/{os.path.basename(output_file)}")
            print()
        else:
            print(f"❌ Export failed: {result.stderr}")
            sys.exit(1)
            
    except FileNotFoundError:
        print("❌ Error: pg_dump not found. Install PostgreSQL client:")
        print("   Ubuntu: sudo apt install postgresql-client")
        print("   Mac: brew install postgresql")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    output_file = sys.argv[1] if len(sys.argv) > 1 else None
    export_database(output_file)
