#!/usr/bin/env python3
"""
cTrader REST API Direct Connection
Using Playground tokens directly
"""

import os
import requests
from dotenv import load_dotenv
from loguru import logger
import json

load_dotenv()

ACCESS_TOKEN = os.getenv('CTRADER_ACCESS_TOKEN')
ACCOUNT_ID = os.getenv('CTRADER_ACCOUNT_ID', '9709773')

# cTrader REST API endpoint
BASE_URL = "https://api.spotware.com/connect"

logger.info("="*70)
logger.info("🧪 Testing cTrader REST API with Playground Token")
logger.info("="*70)

# Request account info using REST API
headers = {
    'Authorization': f'Bearer {ACCESS_TOKEN}',
    'Content-Type': 'application/json'
}

logger.info(f"Account ID: {ACCOUNT_ID}")
logger.info(f"Token: {ACCESS_TOKEN[:30]}...")

# Try to get account info
logger.info("\n📊 Requesting account info via REST API...")

try:
    # Try accounts endpoint
    url = f"{BASE_URL}/tradingaccounts"
    logger.info(f"URL: {url}")
    
    response = requests.get(url, headers=headers)
    
    logger.info(f"Status: {response.status_code}")
    logger.info(f"Response: {response.text[:500]}")
    
    if response.status_code == 200:
        data = response.json()
        logger.success("✅ REST API works!")
        logger.info(json.dumps(data, indent=2))
    else:
        logger.warning("⚠️  REST API endpoint not available")
        
        # Try alternative: Direct protobuf connection without app auth
        logger.info("\n🔄 Trying alternative: Account-only auth...")
        
        # Import SDK
        from ctrader_open_api import Client, Protobuf, TcpProtocol
        from ctrader_open_api.messages import OpenApiMessages_pb2 as msg
        from twisted.internet import reactor
        
        class DirectAuthClient:
            def __init__(self):
                self.client = None
                self.connected = False
            
            def message_handler(self, client, message):
                payloadType = message.payloadType
                logger.info(f"📥 Message: {payloadType}")
                
                if payloadType == 2101:  # Account auth success
                    logger.success("✅ Account authenticated!")
                    
                    # Request balance
                    request = msg.ProtoOATraderReq()
                    request.ctidTraderAccountId = int(ACCOUNT_ID)
                    client.send(request)
                
                elif payloadType == 2121:  # Trader response
                    trader_res = Protobuf.extract(message)
                    trader = trader_res.trader
                    balance = trader.balance / 100
                    
                    logger.success("="*70)
                    logger.success(f"💰 BALANCE: ${balance:.2f}")
                    logger.success("="*70)
                    
                    reactor.stop()
                
                elif payloadType == 2142:  # Error
                    error = Protobuf.extract(message)
                    logger.error(f"❌ Error: {error.errorCode}")
                    reactor.stop()
            
            def on_connect(self, client):
                logger.success("✅ Connected!")
                
                # Try direct account auth (skip app auth)
                logger.info("🔑 Authenticating account directly...")
                request = msg.ProtoOAAccountAuthReq()
                request.ctidTraderAccountId = int(ACCOUNT_ID)
                request.accessToken = ACCESS_TOKEN
                client.send(request)
            
            def on_disconnect(self, client, reason):
                logger.info(f"🔌 Disconnected: {reason}")
                if reactor.running:
                    reactor.stop()
            
            def connect(self):
                self.client = Client("demo.ctraderapi.com", 5035, TcpProtocol)
                self.client.setConnectedCallback(self.on_connect)
                self.client.setDisconnectedCallback(self.on_disconnect)
                self.client.setMessageReceivedCallback(self.message_handler)
                
                self.client.startService()
                reactor.run()
        
        logger.info("🔌 Connecting to cTrader...")
        client = DirectAuthClient()
        client.connect()
        
except Exception as e:
    logger.error(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

logger.info("\n" + "="*70)
