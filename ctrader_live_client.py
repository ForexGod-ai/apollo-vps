#!/usr/bin/env python3
"""
cTrader LIVE Connection using Official SDK
Real-time account data sync
"""

import os
import time
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv
import json

# cTrader Open API SDK
from ctrader_open_api import Client, Protobuf, TcpProtocol, Auth, EndPoints
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import *
from ctrader_open_api.messages.OpenApiMessages_pb2 import *
from twisted.internet import reactor

load_dotenv()


class CTraderLiveClient:
    """
    Real LIVE connection to cTrader using official SDK
    """
    
    def __init__(self):
        self.client_id = os.getenv('CTRADER_CLIENT_ID')
        self.client_secret = os.getenv('CTRADER_CLIENT_SECRET')
        self.access_token = os.getenv('CTRADER_ACCESS_TOKEN')
        self.account_id = int(os.getenv('CTRADER_ACCOUNT_ID', '9709773'))
        
        # Connection settings
        self.host = "demo.ctraderapi.com"  # Demo
        # self.host = "live.ctraderapi.com"  # Live
        self.port = 5035
        
        self.client = None
        self.is_connected = False
        self.account_info = None
        
        logger.info("🔌 cTrader LIVE Client initialized (Official SDK)")
        logger.info(f"   Host: {self.host}:{self.port}")
        logger.info(f"   Account: {self.account_id}")
    
    async def connect_and_auth(self):
        """
        Connect to cTrader and authenticate
        """
        try:
            logger.info("🔌 Connecting to cTrader API...")
            
            # Create client
            self.client = Client(self.host, self.port)
            
            # Set up message handler
            self.client.setMessageHandler(self._message_handler)
            
            # Connect
            await self.client.connect()
            
            logger.success("✅ Connected to cTrader!")
            
            # Application authentication
            logger.info("🔐 Authenticating application...")
            
            app_auth_req = ProtoOAApplicationAuthReq()
            app_auth_req.clientId = self.client_id
            app_auth_req.clientSecret = self.client_secret
            
            await self.client.send(app_auth_req)
            
            # Wait for auth response
            await asyncio.sleep(2)
            
            # Account authentication
            logger.info("🔑 Authenticating account...")
            
            account_auth_req = ProtoOAAccountAuthReq()
            account_auth_req.ctidTraderAccountId = self.account_id
            account_auth_req.accessToken = self.access_token
            
            await self.client.send(account_auth_req)
            
            # Wait for auth
            await asyncio.sleep(2)
            
            self.is_connected = True
            logger.success("✅ Fully authenticated!")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Connection/Auth failed: {e}")
            self.is_connected = False
            return False
    
    def _message_handler(self, message):
        """
        Handle incoming messages from cTrader
        """
        try:
            payload_type = message.payloadType
            
            if payload_type == ProtoOAApplicationAuthRes.ID:
                logger.success("✅ Application authenticated")
            
            elif payload_type == ProtoOAAccountAuthRes.ID:
                logger.success("✅ Account authenticated")
            
            elif payload_type == ProtoOATrader.ID:
                # Account info received
                trader = Protobuf.extract(message)
                balance = trader.balance / 100  # cents to dollars
                
                self.account_info = {
                    'account_id': self.account_id,
                    'balance': balance,
                    'equity': balance,  # Will be updated with positions
                    'timestamp': datetime.now().isoformat()
                }
                
                logger.success(f"✅ Account info: Balance=${balance:.2f}")
            
            elif payload_type == ProtoOAErrorRes.ID:
                error = Protobuf.extract(message)
                logger.error(f"❌ API Error: {error.errorCode} - {error.description}")
            
            else:
                logger.debug(f"📥 Message type: {payload_type}")
                
        except Exception as e:
            logger.error(f"❌ Message handler error: {e}")
    
    async def get_account_info(self):
        """
        Request account information
        """
        try:
            if not self.is_connected:
                logger.error("❌ Not connected")
                return None
            
            logger.info("📊 Requesting account info...")
            
            # Request trader (account) info
            trader_req = ProtoOATraderReq()
            trader_req.ctidTraderAccountId = self.account_id
            
            await self.client.send(trader_req)
            
            # Wait for response
            await asyncio.sleep(2)
            
            return self.account_info
            
        except Exception as e:
            logger.error(f"❌ Get account error: {e}")
            return None
    
    async def disconnect(self):
        """
        Disconnect from cTrader
        """
        if self.client:
            await self.client.disconnect()
            self.is_connected = False
            logger.info("🔌 Disconnected")


async def test_live_client():
    """
    Test LIVE client with official SDK
    """
    logger.info("="*70)
    logger.info("🧪 TESTING cTRADER LIVE CLIENT (Official SDK)")
    logger.info("="*70)
    
    client = CTraderLiveClient()
    
    # Connect and authenticate
    connected = await client.connect_and_auth()
    
    if connected:
        # Get account info
        account_info = await client.get_account_info()
        
        if account_info:
            logger.success("✅ LIVE CONNECTION WORKING!")
            logger.info(f"   Account: {account_info['account_id']}")
            logger.info(f"   Balance: ${account_info['balance']:.2f}")
            logger.info(f"   Equity: ${account_info['equity']:.2f}")
            
            # Update .env with live balance
            logger.info("\n📝 Updating .env with LIVE balance...")
            
            with open('.env', 'r') as f:
                env_content = f.read()
            
            import re
            env_content = re.sub(
                r'ACCOUNT_BALANCE=\d+\.?\d*',
                f'ACCOUNT_BALANCE={account_info["balance"]:.2f}',
                env_content
            )
            
            with open('.env', 'w') as f:
                f.write(env_content)
            
            logger.success(f"✅ Updated .env: ACCOUNT_BALANCE={account_info['balance']:.2f}")
            
            # Update trade_history.json
            logger.info("\n📝 Updating trade_history.json...")
            
            try:
                with open('trade_history.json', 'r') as f:
                    trades = json.load(f)
            except FileNotFoundError:
                trades = []
            
            # Calculate from balance
            initial_balance = 1000.0
            total_profit = account_info['balance'] - initial_balance
            
            logger.success(f"✅ Total profit: ${total_profit:.2f}")
            
        # Keep connection for a bit
        await asyncio.sleep(3)
        
        # Disconnect
        await client.disconnect()
    else:
        logger.error("❌ Connection failed")
    
    logger.info("\n" + "="*70)
    logger.info("✅ TEST COMPLETE")
    logger.info("="*70)


if __name__ == "__main__":
    # Run with twisted reactor
    from twisted.internet import asyncioreactor
    asyncioreactor.install()
    
    from twisted.internet import reactor
    
    async def main():
        await test_live_client()
        reactor.stop()
    
    reactor.callWhenRunning(lambda: asyncio.ensure_future(main()))
    reactor.run()
