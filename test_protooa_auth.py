#!/usr/bin/env python3
"""
Test RAPID ProtoOA Authentication
Verifică dacă Client ID/Secret din .env pot autentifica ProtoOA
"""

import os
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

CLIENT_ID = os.getenv('CTRADER_CLIENT_ID')
CLIENT_SECRET = os.getenv('CTRADER_CLIENT_SECRET')
ACCOUNT_ID = os.getenv('CTRADER_ACCOUNT_ID')
ACCESS_TOKEN = os.getenv('CTRADER_ACCESS_TOKEN')

logger.info("🔍 Checking ProtoOA credentials...")
logger.info(f"Client ID: {CLIENT_ID[:20]}..." if CLIENT_ID else "❌ No Client ID")
logger.info(f"Client Secret: {CLIENT_SECRET[:20]}..." if CLIENT_SECRET else "❌ No Client Secret")
logger.info(f"Account ID: {ACCOUNT_ID}")
logger.info(f"Access Token: {ACCESS_TOKEN[:30]}..." if ACCESS_TOKEN else "❌ No Access Token")

# Test ProtoOA connection
try:
    from ctrader_data_client import CTraderProtoOAClient
    
    logger.info("\n🚀 Testing ProtoOA connection...")
    
    client = CTraderProtoOAClient(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        account_id=ACCOUNT_ID,
        access_token=ACCESS_TOKEN
    )
    
    # Try to connect
    import time
    logger.info("⏳ Connecting to demo.ctraderapi.com:5035...")
    
    # Connect and wait for authentication
    from twisted.internet import reactor
    
    def test_auth():
        client.connect()
        reactor.callLater(5, reactor.stop)  # Wait 5 seconds
    
    reactor.callWhenRunning(test_auth)
    reactor.run()
    
    if client.authenticated:
        logger.success("✅ ProtoOA AUTHENTICATION SUCCESS!")
        logger.success("✅ Can fetch UNLIMITED market data for all 21 pairs!")
    else:
        logger.error("❌ ProtoOA authentication FAILED")
        logger.error("❌ Credentials from .env cannot authenticate ProtoOA")
        logger.info("\n💡 SOLUTION:")
        logger.info("1. ForexGod_AI_Bot application may not have ProtoOA scope")
        logger.info("2. Create NEW application on cTrader portal with ProtoOA access")
        logger.info("3. OR use different credentials for ProtoOA")
        
except ImportError as e:
    logger.error(f"❌ Import error: {e}")
    logger.info("💡 Run: pip install ctrader-open-api twisted pyopenssl")
except Exception as e:
    logger.error(f"❌ Test error: {e}")
    import traceback
    traceback.print_exc()
