#!/usr/bin/env python3
"""
Generate cTrader Access Token using Official OpenApiPy
This will open browser for OAuth authentication
"""

import webbrowser
from ctrader_open_api import Auth, EndPoints
from loguru import logger

# Load credentials
import os
from dotenv import load_dotenv
load_dotenv()

CLIENT_ID = os.getenv('CTRADER_CLIENT_ID')
CLIENT_SECRET = os.getenv('CTRADER_CLIENT_SECRET')
REDIRECT_URI = "http://localhost:5000/callback"  # Must match portal config

logger.info("🔐 cTrader OAuth Token Generator")
logger.info(f"📋 Client ID: {CLIENT_ID[:20]}...")
logger.info(f"🔗 Redirect URI: {REDIRECT_URI}")

# Create Auth instance
auth = Auth(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)

# Get authorization URL
auth_uri = auth.getAuthUri()

logger.info("\n" + "="*60)
logger.info("STEP 1: Authorize Application")
logger.info("="*60)
logger.info(f"\n🌐 Opening browser for authentication...")
logger.info(f"\n{auth_uri}\n")

# Open browser
webbrowser.open_new(auth_uri)

logger.info("📝 After authorizing, you'll be redirected to:")
logger.info(f"   {REDIRECT_URI}?code=XXXXX")
logger.info("\n⚠️  The page will show an error (that's OK!)")
logger.info("📋 COPY the 'code=XXXXX' from the URL bar\n")

# Get auth code from user
auth_code = input("🔑 Paste the authorization code here: ").strip()

if not auth_code:
    logger.error("❌ No code provided!")
    exit(1)

logger.info("\n" + "="*60)
logger.info("STEP 2: Exchange Code for Access Token")
logger.info("="*60)

try:
    # Exchange code for token
    logger.info("🔄 Exchanging authorization code for access token...")
    token = auth.getToken(auth_code)
    
    if 'errorCode' in token:
        logger.error(f"❌ Token error: {token.get('errorCode')}")
        logger.error(f"   Description: {token.get('description')}")
        exit(1)
    
    access_token = token.get('accessToken')
    refresh_token = token.get('refreshToken')
    expires_in = token.get('expiresIn')
    
    logger.success("\n✅ TOKEN RECEIVED!")
    logger.info(f"\n📊 Token Details:")
    logger.info(f"   Access Token: {access_token[:40]}...")
    logger.info(f"   Refresh Token: {refresh_token[:40] if refresh_token else 'N/A'}...")
    logger.info(f"   Expires In: {expires_in / 3600:.1f} hours")
    
    # Update .env file
    logger.info("\n" + "="*60)
    logger.info("STEP 3: Update .env File")
    logger.info("="*60)
    
    env_path = '.env'
    with open(env_path, 'r') as f:
        lines = f.readlines()
    
    with open(env_path, 'w') as f:
        updated = False
        for line in lines:
            if line.startswith('CTRADER_ACCESS_TOKEN='):
                f.write(f'CTRADER_ACCESS_TOKEN={access_token}\n')
                updated = True
            elif line.startswith('CTRADER_REFRESH_TOKEN='):
                f.write(f'CTRADER_REFRESH_TOKEN={refresh_token}\n')
            else:
                f.write(line)
        
        # Add if not exists
        if not updated:
            f.write(f'\nCTRADER_ACCESS_TOKEN={access_token}\n')
            if refresh_token:
                f.write(f'CTRADER_REFRESH_TOKEN={refresh_token}\n')
    
    logger.success(f"✅ Updated {env_path}")
    logger.success("\n🎉 SUCCESS! You can now use OpenApiPy for market data!")
    logger.info("\n🧪 Test with: python3 test_openapi_quick.py")
    
except Exception as e:
    logger.error(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
