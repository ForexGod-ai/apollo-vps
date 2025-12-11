#!/usr/bin/env python3
"""
Test ProtoOA Application Auth ONLY - fără account access token
Verificăm dacă Client ID + Secret funcționează pentru app authentication
"""

import os
import sys
import time
from dotenv import load_dotenv
from loguru import logger

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ctrader_official'))

from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
from ctrader_open_api.messages import OpenApiMessages_pb2 as proto_msg
from twisted.internet import reactor

load_dotenv()

CLIENT_ID = os.getenv('CTRADER_CLIENT_ID')
CLIENT_SECRET = os.getenv('CTRADER_CLIENT_SECRET')

logger.info("="*70)
logger.info("🧪 Testing ProtoOA Application Authentication")
logger.info("="*70)
logger.info(f"Client ID: {CLIENT_ID[:20]}...")
logger.info(f"Host: demo.ctraderapi.com:5035")

app_authenticated = False

def on_connected(client):
    """WebSocket connected - send app auth"""
    logger.success("✅ WebSocket connected!")
    logger.info("🔐 Sending application authentication...")
    
    auth_req = proto_msg.ProtoOAApplicationAuthReq()
    auth_req.clientId = CLIENT_ID
    auth_req.clientSecret = CLIENT_SECRET
    client.send(auth_req)

def on_message(client, message):
    """Handle ProtoOA messages"""
    global app_authenticated
    
    payload_type = message.payloadType
    logger.info(f"📥 Message type: {payload_type}")
    
    # Application auth response
    if payload_type == 2101:  # ProtoOAApplicationAuthRes
        app_authenticated = True
        logger.success("="*70)
        logger.success("✅ APPLICATION AUTHENTICATED!")
        logger.success("="*70)
        logger.success("ProtoOA connection works!")
        logger.success("Client ID + Secret are VALID")
        logger.success("="*70)
        
        logger.info("\n💡 Next step: Account authentication requires valid ACCESS_TOKEN")
        logger.info("   Current token may be expired or invalid for ProtoOA")
        logger.info("   Solution: Refresh token with OAuth flow\n")
        
        # Stop test
        reactor.callLater(1, reactor.stop)
    
    # Error response
    elif payload_type == 2142:  # ProtoOAErrorRes
        error = Protobuf.extract(message)
        logger.error("="*70)
        logger.error(f"❌ ProtoOA Error: {error.errorCode}")
        logger.error("="*70)
        
        if hasattr(error, 'description'):
            logger.error(f"Description: {error.description}")
        
        if error.errorCode == "CH_CLIENT_AUTH_FAILURE":
            logger.error("\n🚨 CLIENT_ID or CLIENT_SECRET is INVALID!")
            logger.error("Check .env credentials for ForexGod_AI_Bot application\n")
        
        reactor.callLater(1, reactor.stop)

def on_disconnected(client, reason):
    """Disconnected"""
    logger.warning(f"Disconnected: {reason}")
    reactor.stop()

# Create client
client = Client(EndPoints.PROTOBUF_DEMO_HOST, EndPoints.PROTOBUF_PORT, TcpProtocol)
client.setConnectedCallback(on_connected)
client.setMessageReceivedCallback(on_message)
client.setDisconnectedCallback(on_disconnected)

# Start
logger.info("\n🚀 Starting ProtoOA connection test...\n")
client.startService()
reactor.run()

# Summary
logger.info("\n" + "="*70)
if app_authenticated:
    logger.success("✅ TEST PASSED: ProtoOA application auth works!")
    logger.info("Next: Get fresh access token for account authentication")
else:
    logger.error("❌ TEST FAILED: Check credentials in .env")
logger.info("="*70)
