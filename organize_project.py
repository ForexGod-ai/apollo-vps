#!/usr/bin/env python3
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🗂️ Glitch in Matrix - Project Organizer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SAFE cleanup - doar mută fișiere (NU șterge!)
Arhivează scripturi legacy și test files în archive_legacy/

⚠️ ZERO IMPACT pe trading logic - doar organization
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

# Base directory
BASE_DIR = Path(__file__).parent
ARCHIVE_DIR = BASE_DIR / "archive_legacy"

# ═══════════════════════════════════════════════════════════════
# LISTA FIȘIERE SAFE DE MUTAT (identificate în PROJECT_ARCHITECTURE_MAP.md)
# ═══════════════════════════════════════════════════════════════

FILES_TO_ARCHIVE = {
    "test_scripts": [
        "test_chart_generation.py",
        "test_telegram_bot.py",
        "test_execution_message.py",
        "test_strategy_detection.py",
        "test_v3_3_continuation.py",
    ],
    
    "legacy_chart_generators": [
        "chart_generator_OLD_BACKUP.py",
        "chart_generator_simple.py",
        "chart_generator_v2.py",
    ],
    
    "deprecated_tools": [
        "check_patterns.py",
        "check_setup_staleness.py",
        "check_setup_status.py",
        "resend_active_setups.py",
        "migrate_to_sqlite.py",
        "oauth_flow_complete.py",
        "setup_telegram.py",
        "spatiotemporal_analyzer.py",
    ],
    
    "backup_files": [
        "notification_manager.py",  # telegram_notifier.py e current
        "money_manager.py",         # risk_manager.py e current
        "view_dashboard_status.py",
    ],
    
    "legacy_data": [
        "trade_history.json",       # Migrated to SQLite
        "backtest_results_v3_vs_v21.json",
    ]
}

# ═══════════════════════════════════════════════════════════════
# CRITICAL FILES - NU ATINGE NICIODATĂ!
# ═══════════════════════════════════════════════════════════════

CRITICAL_FILES = {
    "smc_detector.py",
    "daily_scanner.py",
    "setup_executor_monitor.py",
    "position_monitor.py",
    "ctrader_sync_daemon.py",
    "ctrader_executor.py",
    "ctrader_cbot_client.py",
    "telegram_notifier.py",
    "chart_generator.py",
    "risk_manager.py",
    "service_watchdog.py",
    "system_health_check.py",
}


def verify_critical_files():
    """Verifică că fișierele critice nu sunt în lista de arhivare"""
    all_archive_files = []
    for category_files in FILES_TO_ARCHIVE.values():
        all_archive_files.extend(category_files)
    
    conflicts = set(all_archive_files) & CRITICAL_FILES
    
    if conflicts:
        print(f"❌ EROARE CRITICĂ: Fișiere critice în lista de arhivare: {conflicts}")
        return False
    
    print("✅ Verificare passed: Zero fișiere critice în lista de arhivare")
    return True


def create_archive_structure():
    """Creează structura de foldere pentru arhivă"""
    timestamp = datetime.now().strftime('%Y-%m-%d')
    
    archive_root = ARCHIVE_DIR / timestamp
    
    for category in FILES_TO_ARCHIVE.keys():
        category_dir = archive_root / category
        category_dir.mkdir(parents=True, exist_ok=True)
    
    return archive_root


def move_file_safely(src_file: Path, dest_dir: Path) -> bool:
    """
    Mută fișier SAFE (cu verificări multiple)
    Returns True dacă success, False dacă skip
    """
    if not src_file.exists():
        print(f"   ⚠️  SKIP: {src_file.name} (nu există)")
        return False
    
    # Double-check: nu e fișier critic
    if src_file.name in CRITICAL_FILES:
        print(f"   🚨 BLOCAT: {src_file.name} (fișier CRITIC - protected)")
        return False
    
    # Verifică dacă fișierul e deschis de un proces activ
    try:
        # Pe macOS: lsof nu e disponibil în Python, dar putem testa write access
        with open(src_file, 'a'):
            pass  # Dacă putem append, nu e locked
    except IOError:
        print(f"   ⚠️  SKIP: {src_file.name} (file in use - protected)")
        return False
    
    # Move to archive
    dest_file = dest_dir / src_file.name
    
    try:
        shutil.move(str(src_file), str(dest_file))
        print(f"   ✅ MOVED: {src_file.name} → {dest_dir.relative_to(BASE_DIR)}")
        return True
    except Exception as e:
        print(f"   ❌ FAILED: {src_file.name} - {e}")
        return False


def organize_project(dry_run: bool = False):
    """
    Main organizer function
    
    Args:
        dry_run: If True, doar printează ce ar face (nu mută nimic)
    """
    print("\n" + "═" * 70)
    print("🗂️  GLITCH IN MATRIX - PROJECT ORGANIZER")
    print("═" * 70)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 Base: {BASE_DIR}")
    print(f"🎯 Mode: {'DRY RUN (simulation)' if dry_run else 'LIVE (will move files)'}")
    print("═" * 70 + "\n")
    
    # Step 1: Safety check
    print("🔒 STEP 1: Safety Verification")
    print("─" * 70)
    if not verify_critical_files():
        print("\n❌ ABORTAT: Conflict cu fișiere critice detectat!")
        return False
    print()
    
    # Step 2: Create archive structure
    print("📁 STEP 2: Create Archive Structure")
    print("─" * 70)
    
    if dry_run:
        print(f"   [DRY RUN] Would create: {ARCHIVE_DIR / datetime.now().strftime('%Y-%m-%d')}")
    else:
        archive_root = create_archive_structure()
        print(f"   ✅ Created: {archive_root.relative_to(BASE_DIR)}")
    print()
    
    # Step 3: Move files by category
    print("📦 STEP 3: Archive Legacy Files")
    print("─" * 70)
    
    moved_count = 0
    skipped_count = 0
    
    for category, files in FILES_TO_ARCHIVE.items():
        print(f"\n📂 Category: {category} ({len(files)} files)")
        
        category_dir = archive_root / category if not dry_run else Path("archive_legacy") / category
        
        for filename in files:
            src_file = BASE_DIR / filename
            
            if dry_run:
                if src_file.exists():
                    print(f"   [DRY RUN] Would move: {filename} → {category}/")
                    moved_count += 1
                else:
                    print(f"   [DRY RUN] Would skip: {filename} (not found)")
                    skipped_count += 1
            else:
                if move_file_safely(src_file, category_dir):
                    moved_count += 1
                else:
                    skipped_count += 1
    
    # Step 4: Summary
    print("\n" + "═" * 70)
    print("📊 SUMMARY:")
    print("═" * 70)
    print(f"✅ Files Moved: {moved_count}")
    print(f"⚠️  Files Skipped: {skipped_count}")
    
    if not dry_run:
        print(f"\n📂 Archive Location: {archive_root.relative_to(BASE_DIR)}")
        print("\n💡 NOTE: Fișierele pot fi restaurate oricând din archive_legacy/")
    
    print("\n" + "═" * 70)
    print("━━━━━━━━━━━━━━━━━━━━")
    print("✨ Glitch in Matrix by ФорексГод ✨")
    print("🗂️  Safe Organization • Zero Trading Impact")
    print("━━━━━━━━━━━━━━━━━━━━")
    print()
    
    return True


def restore_file(filename: str, archive_date: str = None):
    """
    Utility function: Restore file from archive
    
    Args:
        filename: Name of file to restore
        archive_date: Date folder (default: latest)
    """
    if not archive_date:
        # Find latest archive
        archive_dirs = sorted(ARCHIVE_DIR.glob("*"), reverse=True)
        if not archive_dirs:
            print("❌ No archives found!")
            return False
        archive_root = archive_dirs[0]
    else:
        archive_root = ARCHIVE_DIR / archive_date
    
    # Search in all categories
    for category_dir in archive_root.iterdir():
        if category_dir.is_dir():
            archived_file = category_dir / filename
            if archived_file.exists():
                dest_file = BASE_DIR / filename
                shutil.move(str(archived_file), str(dest_file))
                print(f"✅ Restored: {filename} from {category_dir.name}/")
                return True
    
    print(f"❌ File not found in archive: {filename}")
    return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Organize Glitch in Matrix project")
    parser.add_argument('--dry-run', action='store_true',
                        help='Simulation mode - show what would be moved')
    parser.add_argument('--restore', type=str,
                        help='Restore file from archive (filename)')
    parser.add_argument('--archive-date', type=str,
                        help='Archive date for restore (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    if args.restore:
        restore_file(args.restore, args.archive_date)
    else:
        organize_project(dry_run=args.dry_run)
