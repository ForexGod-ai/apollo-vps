#!/usr/bin/env python3
"""
Setup Telegram Bot - Get Your Bot Token and Chat ID
"""

from loguru import logger

logger.info("="*70)
logger.info("📱 TELEGRAM BOT SETUP GUIDE")
logger.info("="*70)

logger.info("\n🤖 STEP 1: Create Telegram Bot")
logger.info("   1. Open Telegram and search for @BotFather")
logger.info("   2. Send command: /newbot")
logger.info("   3. Choose a name: ForexGod AI Trading Bot")
logger.info("   4. Choose username: forexgod_trading_bot")
logger.info("   5. BotFather will give you a TOKEN like:")
logger.info("      123456789:ABCdefGHIjklMNOpqrsTUVwxyz")

logger.info("\n💬 STEP 2: Get Your Chat ID")
logger.info("   1. Send a message to your bot (any message)")
logger.info("   2. Open browser: https://api.telegram.org/bot<TOKEN>/getUpdates")
logger.info("   3. Look for \"chat\":{\"id\":123456789}")
logger.info("   4. That number is your CHAT_ID")

logger.info("\n📝 STEP 3: Update .env file")
logger.info("   TELEGRAM_BOT_TOKEN=your_token_here")
logger.info("   TELEGRAM_CHAT_ID=your_chat_id_here")

logger.info("\n" + "="*70)
logger.info("❓ DO YOU ALREADY HAVE TELEGRAM BOT TOKEN?")
logger.info("="*70)

print("\nIf YES, paste your token here and I'll test it!")
print("If NO, follow steps above to create bot.")
