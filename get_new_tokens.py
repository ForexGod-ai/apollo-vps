#!/usr/bin/env python3
"""
Generate cTrader OAuth URL for getting NEW tokens
"""

import os
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

CLIENT_ID = os.getenv('CTRADER_CLIENT_ID')

# OAuth authorization URL
auth_url = f"https://openapi.ctrader.com/apps/auth?client_id={CLIENT_ID}&redirect_uri=http://localhost:8080/callback&scope=trading&response_type=code"

logger.info("="*70)
logger.info("🔐 cTrader OAuth Token Generation")
logger.info("="*70)
logger.info("\n📋 STEPS:")
logger.info("1. Open this URL in your browser:")
logger.info(f"\n   {auth_url}\n")
logger.info("2. Login with your cTrader account")
logger.info("3. Authorize the app")
logger.info("4. You'll be redirected to a page with a 'code' parameter")
logger.info("5. Copy the entire URL and paste it here\n")
logger.info("="*70)

print("\n\nOpen this link:\n")
print(auth_url)
print("\n\n")
