#!/bin/bash
# cleanup_system.sh - Curățenie sistem trading Glitch v2.1
# Data: 2025-12-29

cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

echo "🧹 GLITCH v2.1 - SYSTEM CLEANUP"
echo "================================"
echo ""

# PAS 1: BACKUP
echo "📦 PAS 1: Creez backup complet..."
BACKUP_FILE="../trading-ai-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
tar -czf "$BACKUP_FILE" .
echo "✅ Backup creat: $BACKUP_FILE"
ls -lh "$BACKUP_FILE"
echo ""

# PAS 2: ȘTERGERE
echo "🗑️  PAS 2: Șterg fișiere nefolosite..."
echo ""

# 1. Folder _deprecated/ complet
echo "  - Șterg folder _deprecated/ (79 fișiere)..."
rm -rf _deprecated/

# 2. Backup files
echo "  - Șterg backup files..."
rm -f news_calendar_monitor_backup.py
rm -f PythonSignalExecutor_backup.cs
rm -f .env.backup

# 3. Output files vechi
echo "  - Șterg output files vechi..."
rm -f backtest_output.txt
rm -f backtest_usd_output.txt
rm -f full_scan_results.txt
rm -f daily_scan_results.txt
rm -f scan_log.txt
rm -f COMMIT_MESSAGE.txt

# 4. HTML debug ForexFactory
echo "  - Șterg HTML debug files..."
rm -f forexfactory_after_render.html
rm -f forexfactory_fresh.html
rm -f forexfactory_selenium.html
rm -f forexfactory_visible_browser.html
rm -f forexfactory_screenshot.png

# 5. PNG screenshots test
echo "  - Șterg PNG screenshots test..."
rm -f test_*.png
rm -f btc_with_login_session.png
rm -f tradingview_homepage_check.png

# 6. Python scripts NEFOLOSITE
echo "  - Șterg Python scripts nefolosite..."
rm -f forex_news_telegram.py
rm -f setup_live_data.py
rm -f forexgod_ai_report.py
rm -f start_bot.py
rm -f webhook_server.py
rm -f signal_processor.py
rm -f telegram_bot.py
rm -f tradingview_webhook.py
rm -f realtime_4h_scanner.py
rm -f setup_monitor.py
rm -f run_daily_scan.py
rm -f smc_algorithm.py
rm -f price_action_analyzer.py

# 7. Windows files
echo "  - Șterg Windows batch/PS1 files..."
rm -f *.bat
rm -f *.ps1

# 8. Scripturi shell vechi
echo "  - Șterg scripturi shell vechi..."
rm -f cleanup_old_folder.sh
rm -f remove_alpha_vantage.sh
rm -f audit_system.sh
rm -f check_status.sh

# 9. Log files din root
echo "  - Șterg log files din root (ar trebui în logs/)..."
rm -f *.log

echo ""
echo "✅ Curățenie completă!"
echo ""

# PAS 3: VERIFICARE
echo "🔍 PAS 3: Verificare fișiere importante..."
echo ""
echo "Fișiere CORE (ar trebui să fie toate prezente):"
ls -la main.py smc_detector.py spatiotemporal_analyzer.py daily_scanner.py \
       trade_monitor.py position_monitor.py realtime_monitor.py \
       ctrader_cbot_client.py ctrader_executor.py 2>/dev/null | grep -v "^total" | wc -l
echo "  (Ar trebui să fie 9 fișiere)"
echo ""

echo "Spațiu total folder:"
du -sh .
echo ""

# PAS 4: GIT STATUS
echo "📊 PAS 4: Git status..."
git status --short | head -30
echo ""
echo "Total fișiere modificate/șterse:"
git status --short | wc -l

echo ""
echo "================================"
echo "✅ CLEANUP FINALIZAT!"
echo "================================"
echo ""
echo "📝 URMĂTORII PAȘI:"
echo "1. Verifică că sistemul rulează: ps aux | grep 'python3.*monitor'"
echo "2. Testează daily_scanner: python3 daily_scanner.py"
echo "3. Dacă totul e OK, commit changes: git add -A && git commit -m 'Cleanup: removed deprecated files'"
echo ""
