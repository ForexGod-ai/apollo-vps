#!/usr/bin/env python3
"""
Refresh cTrader Access Token using Refresh Token
"""

import os
import requests
from dotenv import load_dotenv
from loguru import logger
import re

load_dotenv()

CLIENT_ID = os.getenv('CTRADER_CLIENT_ID')
CLIENT_SECRET = os.getenv('CTRADER_CLIENT_SECRET')
REFRESH_TOKEN = os.getenv('CTRADER_REFRESH_TOKEN')

logger.info("="*70)
logger.info("🔄 Refreshing cTrader Access Token")
logger.info("="*70)

# cTrader OAuth token endpoint
TOKEN_URL = "https://openapi.ctrader.com/apps/token"

# Refresh token request
data = {
    'grant_type': 'refresh_token',
    'refresh_token': REFRESH_TOKEN,
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET
}

logger.info("📡 Requesting new access token...")

try:
    response = requests.post(TOKEN_URL, data=data)
    
    logger.info(f"Response status: {response.status_code}")
    logger.info(f"Response body: {response.text}")
    
    if response.status_code == 200:
        tokens = response.json()
        
        new_access_token = tokens['access_token']
        new_refresh_token = tokens.get('refresh_token', REFRESH_TOKEN)  # Some APIs return new refresh token
        
        logger.success("✅ Token refreshed successfully!")
        logger.info(f"   New Access Token: {new_access_token[:30]}...")
        logger.info(f"   New Refresh Token: {new_refresh_token[:30]}...")
        
        # Update .env file
        logger.info("\n📝 Updating .env file...")
        
        with open('.env', 'r') as f:
            env_content = f.read()
        
        # Update access token
        env_content = re.sub(
            r'CTRADER_ACCESS_TOKEN=.*',
            f'CTRADER_ACCESS_TOKEN={new_access_token}',
            env_content
        )
        
        # Update refresh token if new one provided
        if 'refresh_token' in tokens:
            env_content = re.sub(
                r'CTRADER_REFRESH_TOKEN=.*',
                f'CTRADER_REFRESH_TOKEN={new_refresh_token}',
                env_content
            )
        
        with open('.env', 'w') as f:
            f.write(env_content)
        
        logger.success("✅ .env file updated!")
        logger.info("\n🚀 Ready to connect to cTrader API")
        
    else:
        logger.error(f"❌ Token refresh failed: {response.status_code}")
        logger.error(f"   Response: {response.text}")
        
        logger.warning("\n⚠️  You may need to get new tokens from:")
        logger.warning("   https://connect.spotware.com")

except Exception as e:
    logger.error(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

logger.info("\n" + "="*70)
