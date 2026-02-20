#!/usr/bin/env python3
"""
──────────────────
🧹 Glitch in Matrix - Maintenance Cleaner
──────────────────

Log rotation și cleanup EXTERN (zero impact pe daemons)

SAFE operations:
- Comprimă log-uri > 7 zile (ZIP)
- Șterge log-uri > 30 zile
- NU atinge log-uri active (in use)
- Curăță charts > 7 zile

Rulează săptămânal (Duminică 03:00)
──────────────────
"""

import os
import zipfile
import psutil
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
CHARTS_DIR = BASE_DIR / "charts"
ARCHIVE_LOGS_DIR = LOGS_DIR / "archive"


def is_file_in_use(filepath: Path) -> bool:
    """
    Verifică dacă fișierul este deschis de un proces activ
    CRITICAL: Nu atingem log-uri care sunt folosite de daemons
    """
    try:
        # Method 1: Check if any process has this file open
        for proc in psutil.process_iter(['pid', 'name', 'open_files']):
            try:
                for item in proc.info.get('open_files', []) or []:
                    if item.path == str(filepath):
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Method 2: Try to open with exclusive write (will fail if in use)
        # But don't actually write - just test
        try:
            with open(filepath, 'a') as f:
                pass
            return False
        except IOError:
            return True
            
    except Exception as e:
        # If we can't determine, assume it's in use (SAFE approach)
        print(f"   ⚠️  Cannot determine status of {filepath.name}, assuming IN USE")
        return True


def compress_old_logs(days_threshold: int = 7):
    """
    Comprimă log-uri mai vechi de X zile în ZIP
    
    Args:
        days_threshold: Zile vechime pentru comprimare (default 7)
    """
    print(f"\n📦 COMPRESSING LOGS (older than {days_threshold} days)")
    print("─" * 70)
    
    if not LOGS_DIR.exists():
        print("   ⚠️  Logs directory not found")
        return
    
    # Create archive directory
    ARCHIVE_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    cutoff_date = datetime.now() - timedelta(days=days_threshold)
    compressed_count = 0
    skipped_count = 0
    
    for log_file in LOGS_DIR.glob("*.log"):
        try:
            # Check file modification time
            file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            
            if file_mtime < cutoff_date:
                # Check if file is in use
                if is_file_in_use(log_file):
                    print(f"   🔒 SKIP: {log_file.name} (IN USE - protected)")
                    skipped_count += 1
                    continue
                
                # Create ZIP archive with date
                archive_date = file_mtime.strftime('%Y-%m-%d')
                zip_filename = f"{log_file.stem}_{archive_date}.zip"
                zip_path = ARCHIVE_LOGS_DIR / zip_filename
                
                # Compress
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(log_file, log_file.name)
                
                # Get compression ratio
                original_size = log_file.stat().st_size
                compressed_size = zip_path.stat().st_size
                ratio = (1 - compressed_size / original_size) * 100
                
                print(f"   ✅ COMPRESSED: {log_file.name}")
                print(f"      └─ {original_size / 1024:.1f} KB → {compressed_size / 1024:.1f} KB ({ratio:.0f}% saved)")
                
                # Delete original
                log_file.unlink()
                compressed_count += 1
                
        except Exception as e:
            print(f"   ❌ ERROR: {log_file.name} - {e}")
            skipped_count += 1
    
    print(f"\n📊 Result: {compressed_count} compressed, {skipped_count} skipped")


def delete_old_archives(days_threshold: int = 30):
    """
    Șterge arhive ZIP mai vechi de X zile
    
    Args:
        days_threshold: Zile vechime pentru ștergere (default 30)
    """
    print(f"\n🗑️  DELETING OLD ARCHIVES (older than {days_threshold} days)")
    print("─" * 70)
    
    if not ARCHIVE_LOGS_DIR.exists():
        print("   ℹ️  No archive directory found")
        return
    
    cutoff_date = datetime.now() - timedelta(days=days_threshold)
    deleted_count = 0
    deleted_size = 0
    
    for zip_file in ARCHIVE_LOGS_DIR.glob("*.zip"):
        try:
            file_mtime = datetime.fromtimestamp(zip_file.stat().st_mtime)
            
            if file_mtime < cutoff_date:
                file_size = zip_file.stat().st_size
                zip_file.unlink()
                
                deleted_size += file_size
                deleted_count += 1
                
                print(f"   ✅ DELETED: {zip_file.name} ({file_size / 1024:.1f} KB)")
                
        except Exception as e:
            print(f"   ❌ ERROR: {zip_file.name} - {e}")
    
    print(f"\n📊 Result: {deleted_count} deleted, {deleted_size / (1024*1024):.2f} MB freed")


def cleanup_old_charts(days_threshold: int = 7):
    """
    Șterge charts PNG mai vechi de X zile
    
    Args:
        days_threshold: Zile vechime pentru ștergere (default 7)
    """
    print(f"\n🖼️  CLEANING CHARTS (older than {days_threshold} days)")
    print("─" * 70)
    
    if not CHARTS_DIR.exists():
        print("   ℹ️  Charts directory not found")
        return
    
    cutoff_date = datetime.now() - timedelta(days=days_threshold)
    deleted_count = 0
    deleted_size = 0
    
    for chart_file in CHARTS_DIR.glob("*.png"):
        try:
            file_mtime = datetime.fromtimestamp(chart_file.stat().st_mtime)
            
            if file_mtime < cutoff_date:
                file_size = chart_file.stat().st_size
                chart_file.unlink()
                
                deleted_size += file_size
                deleted_count += 1
                
        except Exception as e:
            print(f"   ❌ ERROR: {chart_file.name} - {e}")
    
    if deleted_count > 0:
        print(f"   ✅ DELETED: {deleted_count} charts ({deleted_size / (1024*1024):.2f} MB freed)")
    else:
        print(f"   ℹ️  No old charts to delete")


def get_disk_usage():
    """Raportează dimensiunile directoarelor"""
    print("\n💾 DISK USAGE REPORT")
    print("─" * 70)
    
    directories = {
        'logs/': LOGS_DIR,
        'logs/archive/': ARCHIVE_LOGS_DIR,
        'charts/': CHARTS_DIR,
        'data/': BASE_DIR / 'data',
    }
    
    for name, dir_path in directories.items():
        if dir_path.exists():
            total_size = sum(f.stat().st_size for f in dir_path.rglob('*') if f.is_file())
            file_count = len(list(dir_path.rglob('*')))
            print(f"   📂 {name:<20} {total_size / (1024*1024):>8.2f} MB ({file_count} files)")
        else:
            print(f"   📂 {name:<20} {'N/A':>8}")


def maintenance_cleaner(
    compress_days: int = 7,
    delete_days: int = 30,
    charts_days: int = 7,
    dry_run: bool = False
):
    """
    Main maintenance function
    
    Args:
        compress_days: Zile până la comprimare logs
        delete_days: Zile până la ștergere archives
        charts_days: Zile până la ștergere charts
        dry_run: Simulation mode
    """
    print("\n" + "═" * 70)
    print("🧹 GLITCH IN MATRIX - MAINTENANCE CLEANER")
    print("═" * 70)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Mode: {'DRY RUN (simulation)' if dry_run else 'LIVE (will clean)'}")
    print("═" * 70)
    
    if dry_run:
        print("\n⚠️  DRY RUN MODE - No files will be modified")
    
    # Step 1: Disk usage BEFORE
    get_disk_usage()
    
    if not dry_run:
        # Step 2: Compress old logs
        compress_old_logs(days_threshold=compress_days)
        
        # Step 3: Delete very old archives
        delete_old_archives(days_threshold=delete_days)
        
        # Step 4: Clean old charts
        cleanup_old_charts(days_threshold=charts_days)
        
        # Step 5: Disk usage AFTER
        get_disk_usage()
    else:
        print("\n[DRY RUN] Would perform:")
        print(f"  - Compress logs older than {compress_days} days")
        print(f"  - Delete archives older than {delete_days} days")
        print(f"  - Delete charts older than {charts_days} days")
    
    # Summary
    print("\n" + "═" * 70)
    print("✅ MAINTENANCE COMPLETE")
    print("═" * 70)
    print("\n💡 SCHEDULE: Run weekly (Sunday 03:00)")
    print("   Launchd: com.forexgod.maintenance.plist")
    print("\n" + "═" * 70)
    print("──────────────────")
    print("✨ Glitch in Matrix by ФорексГод ✨")
    print("🧹 Smart Cleanup • Zero Service Impact")
    print("──────────────────")
    print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Maintenance cleaner for Glitch in Matrix")
    parser.add_argument('--compress-days', type=int, default=7,
                        help='Days before compressing logs (default: 7)')
    parser.add_argument('--delete-days', type=int, default=30,
                        help='Days before deleting archives (default: 30)')
    parser.add_argument('--charts-days', type=int, default=7,
                        help='Days before deleting charts (default: 7)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Simulation mode - show what would be cleaned')
    
    args = parser.parse_args()
    
    maintenance_cleaner(
        compress_days=args.compress_days,
        delete_days=args.delete_days,
        charts_days=args.charts_days,
        dry_run=args.dry_run
    )
