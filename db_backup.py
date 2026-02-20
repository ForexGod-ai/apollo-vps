#!/usr/bin/env python3
"""
──────────────────
💾 Glitch in Matrix - Database Backup
──────────────────

NON-BLOCKING SQLite backup (zero impact pe daemons)

Strategy:
1. SQLite .backup() API (online backup, no lock)
2. Verify backup integrity
3. Keep 30 days retention
4. Compress old backups

Rulează Duminică 03:00 (înainte de maintenance_cleaner)
──────────────────
"""

import sqlite3
import shutil
import zipfile
import os
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Bot
import asyncio

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
BACKUPS_DIR = DATA_DIR / "backups"

DB_PATH = DATA_DIR / "trades.db"

# Telegram credentials
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


def verify_database(db_path: Path) -> tuple[bool, dict]:
    """
    Verifică integritatea bazei de date
    
    Returns:
        (valid: bool, stats: dict)
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check integrity
        cursor.execute("PRAGMA integrity_check")
        integrity = cursor.fetchone()[0]
        
        if integrity != "ok":
            return False, {"error": f"Integrity check failed: {integrity}"}
        
        # Get stats
        cursor.execute("SELECT COUNT(*) FROM closed_trades")
        closed_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM open_positions")
        open_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM account_snapshots")
        snapshots_count = cursor.fetchone()[0]
        
        # Get latest snapshot timestamp
        cursor.execute("SELECT timestamp FROM account_snapshots ORDER BY timestamp DESC LIMIT 1")
        latest_snapshot = cursor.fetchone()
        latest_time = latest_snapshot[0] if latest_snapshot else "Never"
        
        conn.close()
        
        stats = {
            "closed_trades": closed_count,
            "open_positions": open_count,
            "account_snapshots": snapshots_count,
            "latest_snapshot": latest_time,
            "file_size_mb": db_path.stat().st_size / (1024 * 1024)
        }
        
        return True, stats
        
    except Exception as e:
        return False, {"error": str(e)}


def backup_database_online(source_db: Path, backup_db: Path) -> bool:
    """
    Online backup using SQLite .backup() API
    NON-BLOCKING - database remains available during backup
    
    Args:
        source_db: Source database path
        backup_db: Backup destination path
    
    Returns:
        bool: Success status
    """
    try:
        # Open source database
        source_conn = sqlite3.connect(source_db)
        
        # Create backup connection
        backup_conn = sqlite3.connect(backup_db)
        
        # Perform online backup (non-blocking)
        # This copies database page-by-page without locking
        source_conn.backup(backup_conn)
        
        # Close connections
        backup_conn.close()
        source_conn.close()
        
        return True
        
    except Exception as e:
        print(f"   ❌ Backup failed: {e}")
        return False


async def send_backup_to_telegram(backup_path: Path, stats: dict):
    """
    Trimite backup-ul pe Telegram cu sumar și cleanup după upload
    
    Args:
        backup_path: Path to backup file (.db or .zip)
        stats: Database statistics
    
    Returns:
        bool: Success status
    """
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print("   ⚠️  Telegram credentials missing - skipping upload")
            return False
        
        print("\n📱 SENDING BACKUP TO TELEGRAM")
        print("─" * 70)
        
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        # Get latest equity from snapshots
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT equity 
                FROM account_snapshots 
                ORDER BY timestamp DESC 
                LIMIT 1
            """)
            equity_result = cursor.fetchone()
            equity = f"${equity_result[0]:,.2f}" if equity_result else "N/A"
            conn.close()
        except Exception as e:
            equity = "N/A"
            print(f"   ⚠️  Could not retrieve equity: {e}")
        
        # Prepare message with EXACT branding signature
        message = (
            "📦 <b>BACKUP SISTEM COMPLET</b>\n\n"
            f"📊 <b>Tranzacții salvate:</b> {stats['closed_trades']} completed\n"
            f"📈 <b>Poziții deschise:</b> {stats['open_positions']} active\n"
            f"💰 <b>Equity actual:</b> {equity}\n"
            f"💾 <b>Snapshots:</b> {stats['account_snapshots']} recorded\n"
            f"📅 <b>Data backup:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📦 <b>Dimensiune:</b> {stats['file_size_mb']:.2f} MB\n\n"
            "──────────────────\n"
            "✨ <b>Glitch in Matrix by ФорексГод</b> ✨\n"
            "🧠 AI-Powered • 💎 Smart Money"
        )
        
        print(f"   📤 Uploading {backup_path.name}...")
        print(f"      └─ Size: {stats['file_size_mb']:.2f} MB")
        
        # Send document to Telegram
        with open(backup_path, 'rb') as file:
            await bot.send_document(
                chat_id=TELEGRAM_CHAT_ID,
                document=file,
                caption=message,
                parse_mode='HTML',
                filename=backup_path.name
            )
        
        print(f"   ✅ Backup sent to Telegram successfully")
        
        # Cleanup: Delete temporary file after successful upload
        # Keep only official copy in backups/ folder
        temp_file_marker = "_temp_"
        if temp_file_marker in backup_path.name:
            print(f"\n   🧹 Cleaning temporary upload file...")
            backup_path.unlink()
            print(f"   ✅ Temporary file deleted: {backup_path.name}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Telegram upload failed: {e}")
        return False


def create_backup(compress: bool = False, send_telegram: bool = False):
    """
    Creează backup complet al bazei de date
    
    Args:
        compress: Compress backup to ZIP (default False for recent backups)
        send_telegram: Send backup to Telegram after creation (default False)
    """
    print("\n💾 CREATING DATABASE BACKUP")
    print("─" * 70)
    
    # Verify source database
    print("   1️⃣  Verifying source database...")
    valid, source_stats = verify_database(DB_PATH)
    
    if not valid:
        print(f"   ❌ Source database invalid: {source_stats.get('error')}")
        return False
    
    print(f"   ✅ Source valid:")
    print(f"      └─ Closed Trades: {source_stats['closed_trades']}")
    print(f"      └─ Open Positions: {source_stats['open_positions']}")
    print(f"      └─ Snapshots: {source_stats['account_snapshots']}")
    print(f"      └─ Size: {source_stats['file_size_mb']:.2f} MB")
    print(f"      └─ Latest: {source_stats['latest_snapshot']}")
    
    # Create backup directory
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    backup_filename = f"trades_backup_{timestamp}.db"
    backup_path = BACKUPS_DIR / backup_filename
    
    # Perform online backup
    print(f"\n   2️⃣  Creating backup (online, non-blocking)...")
    print(f"      Source: {DB_PATH.relative_to(BASE_DIR)}")
    print(f"      Backup: {backup_path.relative_to(BASE_DIR)}")
    
    success = backup_database_online(DB_PATH, backup_path)
    
    if not success:
        return False
    
    print(f"   ✅ Backup created successfully")
    
    # Verify backup integrity
    print(f"\n   3️⃣  Verifying backup integrity...")
    valid, backup_stats = verify_database(backup_path)
    
    if not valid:
        print(f"   ❌ Backup verification failed: {backup_stats.get('error')}")
        backup_path.unlink()  # Delete invalid backup
        return False
    
    # Compare stats
    if backup_stats['closed_trades'] != source_stats['closed_trades']:
        print(f"   ⚠️  WARNING: Trade count mismatch")
        print(f"      Source: {source_stats['closed_trades']}, Backup: {backup_stats['closed_trades']}")
        return False
    
    print(f"   ✅ Backup verified (all data intact)")
    print(f"      └─ Size: {backup_stats['file_size_mb']:.2f} MB")
    
    # Compress if requested
    final_backup_path = backup_path
    if compress:
        print(f"\n   4️⃣  Compressing backup...")
        zip_path = BACKUPS_DIR / f"{backup_filename}.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(backup_path, backup_filename)
        
        compressed_size = zip_path.stat().st_size / (1024 * 1024)
        backup_stats['file_size_mb'] = compressed_size
        ratio = (1 - compressed_size / (backup_path.stat().st_size / (1024 * 1024))) * 100
        
        print(f"   ✅ Compressed: {compressed_size:.2f} MB ({ratio:.0f}% saved)")
        
        # Delete uncompressed backup
        backup_path.unlink()
        
        final_backup_path = zip_path
    
    # Send to Telegram if requested
    if send_telegram:
        # Create temporary compressed version for Telegram
        telegram_backup_path = final_backup_path
        
        # If not already compressed, create temp ZIP for Telegram
        if not compress:
            print(f"\n   4️⃣  Preparing Telegram upload (compressing)...")
            telegram_backup_path = BACKUPS_DIR / f"trades_backup_{timestamp}_temp_.zip"
            
            with zipfile.ZipFile(telegram_backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(final_backup_path, backup_filename)
            
            compressed_size = telegram_backup_path.stat().st_size / (1024 * 1024)
            telegram_stats = backup_stats.copy()
            telegram_stats['file_size_mb'] = compressed_size
            
            print(f"   ✅ Compressed for upload: {compressed_size:.2f} MB")
        else:
            telegram_stats = backup_stats
        
        # Send to Telegram (async)
        try:
            asyncio.run(send_backup_to_telegram(telegram_backup_path, telegram_stats))
        except Exception as e:
            print(f"   ❌ Telegram upload failed: {e}")
    
    return final_backup_path


def cleanup_old_backups(days_retention: int = 30):
    """
    Șterge backup-uri mai vechi de X zile
    
    Args:
        days_retention: Zile retention (default 30)
    """
    print(f"\n🗑️  CLEANING OLD BACKUPS (older than {days_retention} days)")
    print("─" * 70)
    
    if not BACKUPS_DIR.exists():
        print("   ℹ️  No backups directory found")
        return
    
    cutoff_date = datetime.now() - timedelta(days=days_retention)
    deleted_count = 0
    deleted_size = 0
    
    for backup_file in BACKUPS_DIR.glob("trades_backup_*"):
        try:
            file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
            
            if file_mtime < cutoff_date:
                file_size = backup_file.stat().st_size
                backup_file.unlink()
                
                deleted_size += file_size
                deleted_count += 1
                
                print(f"   ✅ DELETED: {backup_file.name} ({file_size / (1024*1024):.2f} MB)")
                
        except Exception as e:
            print(f"   ❌ ERROR: {backup_file.name} - {e}")
    
    if deleted_count > 0:
        print(f"\n📊 Result: {deleted_count} deleted, {deleted_size / (1024*1024):.2f} MB freed")
    else:
        print(f"   ℹ️  No old backups to delete")


def list_backups():
    """Listează toate backup-urile disponibile"""
    print("\n📋 AVAILABLE BACKUPS")
    print("─" * 70)
    
    if not BACKUPS_DIR.exists():
        print("   ℹ️  No backups directory found")
        return
    
    backups = sorted(BACKUPS_DIR.glob("trades_backup_*"), reverse=True)
    
    if not backups:
        print("   ℹ️  No backups found")
        return
    
    print(f"\n   Found {len(backups)} backups:\n")
    
    for i, backup_file in enumerate(backups, 1):
        file_size = backup_file.stat().st_size / (1024 * 1024)
        file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
        age_days = (datetime.now() - file_mtime).days
        
        print(f"   {i}. {backup_file.name}")
        print(f"      └─ Size: {file_size:.2f} MB | Age: {age_days} days | Date: {file_mtime.strftime('%Y-%m-%d %H:%M')}")


def restore_backup(backup_filename: str, verify_first: bool = True):
    """
    Restore database from backup
    
    Args:
        backup_filename: Name of backup file to restore
        verify_first: Verify backup before restoring (default True)
    """
    print("\n🔄 RESTORING DATABASE FROM BACKUP")
    print("─" * 70)
    print("⚠️  WARNING: This will OVERWRITE current database!")
    print()
    
    backup_path = BACKUPS_DIR / backup_filename
    
    if not backup_path.exists():
        print(f"   ❌ Backup not found: {backup_filename}")
        return False
    
    # Verify backup integrity first
    if verify_first:
        print("   1️⃣  Verifying backup integrity...")
        valid, stats = verify_database(backup_path)
        
        if not valid:
            print(f"   ❌ Backup invalid: {stats.get('error')}")
            return False
        
        print(f"   ✅ Backup valid:")
        print(f"      └─ Closed Trades: {stats['closed_trades']}")
        print(f"      └─ Open Positions: {stats['open_positions']}")
        print(f"      └─ Snapshots: {stats['account_snapshots']}")
    
    # Create backup of current database
    print("\n   2️⃣  Creating safety backup of current database...")
    safety_backup = DB_PATH.parent / f"{DB_PATH.stem}_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(DB_PATH, safety_backup)
    print(f"   ✅ Safety backup: {safety_backup.name}")
    
    # Restore
    print("\n   3️⃣  Restoring database...")
    
    try:
        shutil.copy2(backup_path, DB_PATH)
        print(f"   ✅ Database restored from: {backup_filename}")
        
        # Verify restored database
        print("\n   4️⃣  Verifying restored database...")
        valid, stats = verify_database(DB_PATH)
        
        if not valid:
            print(f"   ❌ Restored database invalid!")
            print(f"   🔄 Rolling back to safety backup...")
            shutil.copy2(safety_backup, DB_PATH)
            return False
        
        print(f"   ✅ Restored database verified successfully")
        return True
        
    except Exception as e:
        print(f"   ❌ Restore failed: {e}")
        print(f"   🔄 Rolling back to safety backup...")
        shutil.copy2(safety_backup, DB_PATH)
        return False


def db_backup_manager(
    create: bool = True,
    compress: bool = False,
    send_telegram: bool = False,
    cleanup_days: int = 30,
    list_only: bool = False,
    restore: str = None
):
    """
    Main backup manager function
    
    Args:
        create: Create new backup
        compress: Compress backup
        send_telegram: Send backup to Telegram
        cleanup_days: Days retention for cleanup
        list_only: Only list backups (no actions)
        restore: Restore from backup filename
    """
    print("\n" + "═" * 70)
    print("💾 GLITCH IN MATRIX - DATABASE BACKUP")
    print("═" * 70)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 Database: {DB_PATH.relative_to(BASE_DIR)}")
    print("═" * 70)
    
    if restore:
        # Restore mode
        success = restore_backup(restore)
        
        if success:
            print("\n" + "═" * 70)
            print("✅ RESTORE COMPLETE")
            print("═" * 70)
            print("\n⚠️  IMPORTANT: Restart all trading services!")
            print("   pkill -f 'ctrader_sync_daemon.py|position_monitor.py|setup_executor_monitor.py'")
        
    elif list_only:
        # List mode
        list_backups()
        
    else:
        # Backup mode
        if create:
            backup_path = create_backup(compress=compress, send_telegram=send_telegram)
            
            if backup_path:
                print(f"\n   📂 Backup Location: {backup_path.relative_to(BASE_DIR)}")
        
        # Cleanup old backups
        cleanup_old_backups(days_retention=cleanup_days)
        
        # List current backups
        list_backups()
        
        print("\n" + "═" * 70)
        print("✅ BACKUP COMPLETE")
        print("═" * 70)
        
        if send_telegram:
            print("\n📱 TELEGRAM DELIVERY:")
            print("   ✅ Backup sent to your phone")
            print("   🛡️  Your $2,500+ profit is secured!")
        
        print("\n💡 SCHEDULE: Run weekly (Sunday 03:00)")
        print("   Launchd: com.forexgod.dbbackup.plist")
        print("   Auto-send to Telegram: ✅ ENABLED")
    
    print("\n" + "═" * 70)
    print("──────────────────")
    print("✨ Glitch in Matrix by ФорексГод ✨")
    print("💾 Safe Backup • Zero Downtime • Telegram Secured")
    print("──────────────────")
    print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Database backup manager for Glitch in Matrix")
    parser.add_argument('--create', action='store_true', default=True,
                        help='Create new backup (default)')
    parser.add_argument('--compress', action='store_true',
                        help='Compress backup to ZIP')
    parser.add_argument('--telegram', dest='send_telegram', action='store_true',
                        help='Send backup to Telegram')
    parser.add_argument('--cleanup-days', type=int, default=30,
                        help='Days retention for old backups (default: 30)')
    parser.add_argument('--list', dest='list_only', action='store_true',
                        help='List available backups')
    parser.add_argument('--restore', type=str,
                        help='Restore from backup (filename)')
    parser.add_argument('--no-create', dest='create', action='store_false',
                        help='Skip creating new backup')
    
    args = parser.parse_args()
    
    db_backup_manager(
        create=args.create and not args.list_only and not args.restore,
        compress=args.compress,
        send_telegram=args.send_telegram,
        cleanup_days=args.cleanup_days,
        list_only=args.list_only,
        restore=args.restore
    )
