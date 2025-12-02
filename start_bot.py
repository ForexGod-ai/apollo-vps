"""
Start both Telegram bot listener and Flask webhook server
"""
import threading
from loguru import logger
import sys
from telegram_bot import TelegramBot
from webhook_server import start_webhook_server

# Configurare logging
logger.remove()
logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
)
logger.add("bot.log", rotation="1 day", retention="7 days")


def run_telegram_bot():
    """Run Telegram bot in separate thread"""
    try:
        logger.info("🤖 Starting Telegram bot listener...")
        bot = TelegramBot()
        bot.start()
    except Exception as e:
        logger.error(f"❌ Telegram bot error: {e}")


def run_webhook_server():
    """Run Flask webhook server in separate thread"""
    try:
        logger.info("🌐 Starting webhook server...")
        start_webhook_server()
    except Exception as e:
        logger.error(f"❌ Webhook server error: {e}")


if __name__ == "__main__":
    logger.info("🚀 Starting ForexGod - Glitch in Matrix Bot...")
    logger.info("=" * 60)
    
    try:
        # Start Telegram bot in background thread
        telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
        telegram_thread.start()
        
        # Start webhook server in main thread (blocks)
        run_webhook_server()
        
    except KeyboardInterrupt:
        logger.info("\n⚠️ Shutting down bot...")
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")
