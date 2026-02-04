"""
Start Telegram Bot Handler in Background
Integrates interactive commands with trading system
"""

import sys
import time
from loguru import logger
from telegram_bot_handler import TradingBotHandler

# Configure logger
logger.remove()
logger.add(
    "logs/telegram_bot.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    rotation="10 MB",
    retention="30 days",
    level="INFO"
)
logger.add(sys.stdout, level="INFO")


def main():
    """Start Telegram bot in background thread"""
    try:
        logger.info("="*60)
        logger.info("🤖 Starting Telegram Bot Handler...")
        logger.info("="*60)
        
        # Initialize bot
        bot = TradingBotHandler()
        logger.success("✅ Bot initialized successfully")
        
        # Start in background thread
        bot_thread = bot.run_background()
        logger.success("✅ Bot running in background thread")
        
        logger.info("💡 Bot is now listening for commands:")
        logger.info("   /status - Account overview")
        logger.info("   /summary - Weekly performance")
        logger.info("   /positions - Open positions")
        logger.info("   /balance - Account balance")
        logger.info("   /setups - Monitoring setups")
        logger.info("   /news - High-impact news")
        logger.info("   /help - Show all commands")
        
        logger.info("="*60)
        logger.info("✅ Bot is ONLINE - Press Ctrl+C to stop")
        logger.info("="*60)
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.warning("\n⏹️  Stopping Telegram bot...")
            sys.exit(0)
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
