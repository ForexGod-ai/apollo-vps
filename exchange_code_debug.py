#!/usr/bin/env python3
"""
Exchange authorization code - DEBUG VERSION
"""

import os
import requests
from loguru import logger
from dotenv import load_dotenv
import json

load_dotenv()

CLIENT_ID = os.getenv('CTRADER_CLIENT_ID')
CLIENT_SECRET = os.getenv('CTRADER_CLIENT_SECRET')
REDIRECT_URI = "http://localhost:5000/callback"
TOKEN_URL = "https://openapi.ctrader.com/apps/token"

logger.info("="*70)
logger.info("🔐 Exchange Authorization Code for Access Token (DEBUG)")
logger.info("="*70)

AUTH_CODE = input("\n📋 Paste authorization code: ").strip()

if not AUTH_CODE:
    logger.error("❌ No code provided!")
    exit(1)

logger.info(f"\n🔄 Exchanging code: {AUTH_CODE[:30]}...")

data = {
    'grant_type': 'authorization_code',
    'code': AUTH_CODE,
    'redirect_uri': REDIRECT_URI,
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET
}

logger.info(f"\nRequest data:")
logger.info(f"  grant_type: authorization_code")
logger.info(f"  redirect_uri: {REDIRECT_URI}")
logger.info(f"  client_id: {CLIENT_ID[:20]}...")
logger.info(f"  code: {AUTH_CODE[:30]}...")

try:
    response = requests.post(
        TOKEN_URL,
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=10
    )
    
    logger.info(f"\nResponse status: {response.status_code}")
    logger.info(f"Response headers: {dict(response.headers)}")
    logger.info(f"\nResponse body:")
    
    try:
        response_json = response.json()
        logger.info(json.dumps(response_json, indent=2))
        
        if response.status_code == 200:
            access_token = response_json.get('access_token')
            refresh_token = response_json.get('refresh_token')
            
            if access_token:
                logger.success(f"\n✅ Access Token: {access_token}")
                logger.success(f"✅ Refresh Token: {refresh_token}")
                
                # Save to .env
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
                
                logger.success("\n✅ Saved to .env!")
                logger.info("\n🎉 Ready to test ProtoOA:")
                logger.info("python3 test_protooa_simple.py\n")
            else:
                logger.error("❌ No access_token in response!")
        else:
            logger.error(f"\n❌ Token exchange failed!")
            
    except Exception as e:
        logger.error(f"Response text: {response.text}")
        logger.error(f"Parse error: {e}")
        
except Exception as e:
    logger.error(f"\n❌ Request error: {e}")
