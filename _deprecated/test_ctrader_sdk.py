#!/usr/bin/env python3
"""
Test cTrader Official SDK Connection
Simple working example
"""

import os
from dotenv import load_dotenv
from loguru import logger

from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
from ctrader_open_api.messages import OpenApiMessages_pb2 as msg
from ctrader_open_api.messages import OpenApiCommonMessages_pb2 as common
from twisted.internet import reactor

load_dotenv()

# Your credentials
CLIENT_ID = os.getenv('CTRADER_CLIENT_ID')
CLIENT_SECRET = os.getenv('CTRADER_CLIENT_SECRET')
ACCESS_TOKEN = os.getenv('CTRADER_ACCESS_TOKEN')
ACCOUNT_ID = int(os.getenv('CTRADER_ACCOUNT_ID', '9709773'))

# Demo host
HOST = "demo.ctraderapi.com"
PORT = 5035

logger.info("="*70)
logger.info("🧪 Testing cTrader Official SDK")
logger.info("="*70)
logger.info(f"Host: {HOST}:{PORT}")
logger.info(f"Account: {ACCOUNT_ID}")
logger.info(f"Client ID: {CLIENT_ID[:20]}...")


def onMessageReceived(client, message):
    """
    Handle all messages from cTrader
    """
    try:
        payloadType = message.payloadType
        
        logger.info(f"📥 Message type: {payloadType}")
        
        # Try to extract and show payload
        try:
            payload = Protobuf.extract(message)
            logger.info(f"   Payload type: {type(payload).__name__}")
        except:
            payload = None
        
        # Application authentication response (2100)
        if payloadType == 2100:
            logger.success("✅ Application authenticated!")
            
            # Now authenticate account
            logger.info("🔑 Authenticating account...")
            request = msg.ProtoOAAccountAuthReq()
            request.ctidTraderAccountId = ACCOUNT_ID
            request.accessToken = ACCESS_TOKEN
            client.send(request)
        
        # Error response (2142)
        elif payloadType == 2142:
            error = Protobuf.extract(message)
            logger.error(f"❌ API Error: {error.errorCode}")
            if hasattr(error, 'description'):
                logger.error(f"   Description: {error.description}")
            reactor.stop()
        
        # Account authentication response (2101)
        elif payloadType == 2101:
            logger.success("✅ Account authenticated!")
            
            # Request account info
            logger.info("📊 Requesting account balance...")
            request = msg.ProtoOATraderReq()
            request.ctidTraderAccountId = ACCOUNT_ID
            client.send(request)
        
        # Account (Trader) info response (check exact ID)
        elif payloadType == 2121 or 'Trader' in type(payload).__name__ if payload else False:
            trader_res = Protobuf.extract(message)
            trader = trader_res.trader
            balance = trader.balance / 100  # Convert cents to dollars
            
            logger.success("="*70)
            logger.success("💰 LIVE ACCOUNT DATA RECEIVED!")
            logger.success("="*70)
            logger.success(f"Account ID: {ACCOUNT_ID}")
            logger.success(f"Balance: ${balance:.2f}")
            logger.success(f"Deposit Asset ID: {trader.depositAssetId}")
            logger.success("="*70)
            
            # Save to file
            import json
            result = {
                'account_id': ACCOUNT_ID,
                'balance': balance,
                'timestamp': str(trader.registrationTimestamp),
                'deposit_asset': trader.depositAssetId
            }
            
            with open('ctrader_live_data.json', 'w') as f:
                json.dump(result, f, indent=2)
            
            logger.info("✅ Saved to ctrader_live_data.json")
            
            # Disconnect
            logger.info("\n🔌 Disconnecting...")
            client.disconnect()
            reactor.stop()
        
        
        # Error response (already handled above as 2142)
        elif payloadType == 2102:
            error = Protobuf.extract(message)
            logger.error(f"❌ API Error 2102: {error.errorCode}")
            logger.error(f"   Description: {error.description}")
            reactor.stop()
        
        else:
            logger.debug(f"📥 Unhandled message: {payloadType}")
    
    except Exception as e:
        logger.error(f"❌ Message handler error: {e}")
        import traceback
        traceback.print_exc()


def onConnect(client):
    """
    Called when connected to cTrader
    """
    logger.success("✅ Connected to cTrader!")
    
    # Authenticate application
    logger.info("🔐 Authenticating application...")
    request = msg.ProtoOAApplicationAuthReq()
    request.clientId = CLIENT_ID
    request.clientSecret = CLIENT_SECRET
    client.send(request)


def onDisconnect(client, reason):
    """
    Called when disconnected
    """
    logger.info(f"🔌 Disconnected: {reason}")
    reactor.stop()


def onError(failure):
    """
    Called on error
    """
    logger.error(f"❌ Connection error: {failure}")
    reactor.stop()


# Create client
client = Client(HOST, PORT, TcpProtocol)
client.setConnectedCallback(onConnect)
client.setDisconnectedCallback(onDisconnect)
client.setMessageReceivedCallback(onMessageReceived)

# Start connection
logger.info("🔌 Connecting...")
client.startService()

# Run reactor
reactor.run()
