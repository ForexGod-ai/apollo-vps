#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🛡️ TELEGRAM BACKUP - Quick Commands
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ✨ Glitch in Matrix by ФорексГод ✨
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

PYTHON=".venv/bin/python"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🛡️  TELEGRAM BACKUP SYSTEM - Quick Commands"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Choose an option:"
echo ""
echo "  1️⃣  Create backup + Send to Telegram"
echo "  2️⃣  Create backup (local only, no Telegram)"
echo "  3️⃣  List available backups"
echo "  4️⃣  Restore from backup"
echo "  5️⃣  Check Launchd job status"
echo "  6️⃣  View backup logs"
echo "  7️⃣  Manual trigger (run backup NOW)"
echo "  8️⃣  Test Telegram connection"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

read -p "Enter option (1-8): " choice

case $choice in
    1)
        echo ""
        echo "📱 Creating backup and sending to Telegram..."
        echo ""
        $PYTHON db_backup.py --create --telegram
        ;;
    2)
        echo ""
        echo "💾 Creating local backup only..."
        echo ""
        $PYTHON db_backup.py --create --no-create
        ;;
    3)
        echo ""
        echo "📋 Available backups:"
        echo ""
        $PYTHON db_backup.py --list
        ;;
    4)
        echo ""
        echo "📋 Available backups:"
        $PYTHON db_backup.py --list
        echo ""
        read -p "Enter backup filename to restore: " filename
        echo ""
        echo "⚠️  WARNING: This will OVERWRITE current database!"
        read -p "Are you sure? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            $PYTHON db_backup.py --restore "$filename"
        else
            echo "❌ Restore cancelled"
        fi
        ;;
    5)
        echo ""
        echo "🔍 Launchd job status:"
        echo ""
        launchctl list | grep forexgod.dbbackup
        if [ $? -eq 0 ]; then
            echo "✅ Job is loaded and active"
        else
            echo "❌ Job NOT loaded"
        fi
        ;;
    6)
        echo ""
        echo "📄 Backup logs (last 50 lines):"
        echo ""
        tail -50 logs/db_backup.log
        ;;
    7)
        echo ""
        echo "▶️  Triggering backup manually..."
        echo ""
        launchctl start com.forexgod.dbbackup
        sleep 5
        echo ""
        echo "📄 Check logs:"
        tail -20 logs/db_backup.log
        ;;
    8)
        echo ""
        echo "📱 Testing Telegram connection..."
        echo ""
        $PYTHON -c "
from telegram import Bot
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()
token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

if not token or not chat_id:
    print('❌ Telegram credentials missing in .env')
    exit(1)

bot = Bot(token=token)

async def test():
    await bot.send_message(
        chat_id=chat_id,
        text='🛡️ <b>Telegram Backup System TEST</b>\n\n✅ Connection successful!\n━━━━━━━━━━━━━━━━━━━━\n✨ <b>Glitch in Matrix by ФорексГод</b> ✨',
        parse_mode='HTML'
    )

asyncio.run(test())
print('✅ Test message sent to Telegram!')
"
        ;;
    *)
        echo "❌ Invalid option"
        exit 1
        ;;
esac

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ Glitch in Matrix by ФорексГод ✨"
echo "🛡️ Your $2,500+ profit is secured!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
