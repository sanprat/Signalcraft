#!/usr/bin/env python3
"""
Automated database backup script.
Creates timestamped backups and cleans up old backups.

Usage:
    python3 scripts/backup_db.py [--keep-days 30]

Cron example (daily at 2 AM):
    0 2 * * * cd /home/signalcraft && python3 backend/scripts/backup_db.py
"""

import sys
import os
import subprocess
from datetime import datetime, timedelta
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings


def backup_database(keep_days=30):
    """Create database backup and cleanup old backups."""
    
    if settings.DB_TYPE != "postgres":
        print("❌ Error: DB_TYPE must be 'postgres'")
        print(f"   Current DB_TYPE: {settings.DB_TYPE}")
        sys.exit(1)
    
    # Create backups directory
    backup_dir = settings.DATA_DIR.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"signalcraft_backup_{timestamp}.sql"
    
    print("=" * 60)
    print("  SignalCraft - Automated Backup")
    print("=" * 60)
    print()
    print(f"📦 Database: {settings.DB_NAME}")
    print(f"📁 Backup file: {backup_file}")
    print()
    
    # Build pg_dump command
    cmd = [
        "pg_dump",
        "-h", settings.DB_HOST,
        "-p", settings.DB_PORT,
        "-U", settings.DB_USER,
        "-d", settings.DB_NAME,
        "-F", "p",
        "-f", str(backup_file)
    ]
    
    # Set password environment variable
    env = os.environ.copy()
    env["PGPASSWORD"] = settings.DB_PASSWORD
    
    try:
        # Run backup
        print("Creating backup...")
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Backup failed: {result.stderr}")
            sys.exit(1)
        
        # Get file size
        file_size = backup_file.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        print(f"✅ Backup created: {backup_file.name}")
        print(f"📏 Size: {file_size_mb:.2f} MB")
        
        # Cleanup old backups
        print()
        print(f"Cleaning up backups older than {keep_days} days...")
        
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        deleted_count = 0
        
        for file in backup_dir.glob("signalcraft_backup_*.sql"):
            file_mtime = datetime.fromtimestamp(file.stat().st_mtime)
            if file_mtime < cutoff_date:
                file.unlink()
                deleted_count += 1
                print(f"  Deleted: {file.name}")
        
        if deleted_count == 0:
            print("  No old backups to delete")
        else:
            print(f"  Deleted {deleted_count} old backup(s)")
        
        # List current backups
        print()
        print("Current backups:")
        backups = sorted(backup_dir.glob("signalcraft_backup_*.sql"), reverse=True)
        for backup in backups[:10]:  # Show last 10
            size_mb = backup.stat().st_size / (1024 * 1024)
            print(f"  • {backup.name} ({size_mb:.2f} MB)")
        
        if len(backups) > 10:
            print(f"  ... and {len(backups) - 10} more")
        
        print()
        print("=" * 60)
        print("  ✅ Backup Complete!")
        print("=" * 60)
        
    except FileNotFoundError:
        print("❌ Error: pg_dump not found")
        print("   Install: apt install postgresql-client")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Parse command line arguments
    keep_days = 30
    if "--keep-days" in sys.argv:
        try:
            idx = sys.argv.index("--keep-days")
            keep_days = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            print("Warning: Invalid --keep-days value, using default (30 days)")
    
    backup_database(keep_days)
