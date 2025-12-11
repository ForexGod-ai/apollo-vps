#!/usr/bin/env python3
"""
Exchange authorization code for access token (MANUAL)
Paste the authorization code from browser URL
"""

import os
import requests
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv('CTRADER_CLIENT_ID')
CLIENT_SECRET = os.getenv('CTRADER_CLIENT_SECRET')
REDIRECT_URI = "http://localhost:5000/callback"
TOKEN_URL = "https://openapi.ctrader.com/apps/token"

logger.info("="*70)
logger.info("🔐 Exchange Authorization Code for Access Token")
logger.info("="*70)

# Paste your authorization code here (from URL after ?code=)
AUTH_CODE = input("\n📋 Paste authorization code from browser URL: ").strip()

if not AUTH_CODE:
    logger.error("❌ No code provided!")
    exit(1)

logger.info(f"\n🔄 Exchanging code: {AUTH_CODE[:30]}...")

# Exchange code for tokens
data = {
    'grant_type': 'authorization_code',
    'code': AUTH_CODE,
    'redirect_uri': REDIRECT_URI,
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET
}

try:
    response = requests.post(
        TOKEN_URL,
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=10
    )
    
    if response.status_code == 200:
        token_data = response.json()
        
        access_token = token_data.get('access_token', '')
        refresh_token = token_data.get('refresh_token', '')
        expires_in = token_data.get('expires_in', 0)
        
        logger.success("\n" + "="*70)
        logger.success("✅ SUCCESS! Tokens received")
        logger.success("="*70)
        if access_token:
            logger.success(f"Access Token: {access_token[:40]}...")
        if refresh_token:
            logger.success(f"Refresh Token: {refresh_token[:40]}...")
        logger.success(f"Expires in: {expires_in / 3600:.1f} hours")
        logger.success("="*70)
        
        # Update .env file
        env_path = '.env'
        with open(env_path, 'r') as f:
            lines = f.readlines()
        
        with open(env_path, 'w') as f:
            for line in lines:
                if line.startswith('CTRADER_ACCESS_TOKEN='):
                    f.write(f'CTRADER_ACCESS_TOKEN={access_token}\n')
                elif line.startswith('CTRADER_REFRESH_TOKEN='):
                    f.write(f'CTRADER_REFRESH_TOKEN={refresh_token}\n')
                else:
                    f.write(line)
        
        logger.success("\n✅ Updated .env with new tokens!")
        logger.info("\n🎉 Ready to test ProtoOA!")
        logger.info("Run: python3 test_protooa_simple.py\n")
        
    else:
        logger.error(f"\n❌ Token exchange failed: {response.status_code}")
        logger.error(f"Response: {response.text}")
        
except Exception as e:
    logger.error(f"\n❌ Error: {e}")
