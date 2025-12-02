"""
Script principal pentru pornirea agentului de trading AI
"""
from webhook_server import start_webhook_server
from loguru import logger
import sys

# Configurare logging
logger.remove()
logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
)
logger.add("trading_agent.log", rotation="1 day", retention="7 days")

if __name__ == "__main__":
    logger.info("🚀 Pornire Trading AI Agent...")
    
    try:
        start_webhook_server()
    except KeyboardInterrupt:
        logger.info("\n⚠️ Oprire agent...")
    except Exception as e:
        logger.error(f"❌ Eroare critică: {e}")
