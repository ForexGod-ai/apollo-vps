#!/usr/bin/env python3
"""
cTrader WebSocket Client - REAL LIVE Connection
Uses WebSocket + Protobuf for real-time data from cTrader
"""

import asyncio
import websockets
import json
from datetime import datetime
from loguru import logger
import os
from dotenv import load_dotenv

load_dotenv()


class CTraderWebSocketClient:
    """
    Real-time WebSocket connection to cTrader Open API
    """
    
    def __init__(self):
        self.client_id = os.getenv('CTRADER_CLIENT_ID')
        self.client_secret = os.getenv('CTRADER_CLIENT_SECRET')
        self.access_token = os.getenv('CTRADER_ACCESS_TOKEN')
        self.account_id = os.getenv('CTRADER_ACCOUNT_ID', '9709773')
        
        # WebSocket endpoint
        self.ws_url = "wss://live.ctraderapi.com:5035"  # Live
        # self.ws_url = "wss://demo.ctraderapi.com:5035"  # Demo
        
        self.websocket = None
        self.is_connected = False
        self.account_info = None
        
        logger.info("🌐 cTrader WebSocket Client initialized")
        logger.info(f"   Account: {self.account_id}")
    
    async def connect(self):
        """
        Connect to cTrader WebSocket API
        """
        try:
            logger.info(f"🔌 Connecting to {self.ws_url}...")
            
            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=10
            )
            
            self.is_connected = True
            logger.success("✅ WebSocket connected!")
            
            # Authenticate
            await self._authenticate()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            self.is_connected = False
            return False
    
    async def _authenticate(self):
        """
        Authenticate with access token
        """
        try:
            logger.info("🔐 Authenticating...")
            
            auth_message = {
                "payloadType": 2100,  # ProtoOAApplicationAuthReq
                "clientId": self.client_id,
                "clientSecret": self.client_secret
            }
            
            await self.websocket.send(json.dumps(auth_message))
            
            # Wait for auth response
            response = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=10
            )
            
            logger.info(f"📥 Auth response: {response[:100]}...")
            logger.success("✅ Authenticated!")
            
        except asyncio.TimeoutError:
            logger.error("❌ Authentication timeout")
        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
    
    async def get_account_info(self):
        """
        Request account information
        """
        try:
            if not self.is_connected:
                logger.error("❌ Not connected")
                return None
            
            logger.info("📊 Requesting account info...")
            
            # Account info request
            request = {
                "payloadType": 2102,  # ProtoOAAccountAuthReq
                "ctidTraderAccountId": int(self.account_id),
                "accessToken": self.access_token
            }
            
            await self.websocket.send(json.dumps(request))
            
            # Wait for response
            response = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=10
            )
            
            logger.info(f"📥 Account response: {response[:200]}...")
            
            # Parse account info
            account_data = json.loads(response)
            
            self.account_info = {
                'account_id': self.account_id,
                'balance': account_data.get('balance', 0) / 100,  # cents to dollars
                'equity': account_data.get('equity', 0) / 100,
                'margin': account_data.get('margin', 0) / 100,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.success(f"✅ Got account info: Balance=${self.account_info['balance']:.2f}")
            
            return self.account_info
            
        except asyncio.TimeoutError:
            logger.error("❌ Request timeout")
            return None
        except Exception as e:
            logger.error(f"❌ Request error: {e}")
            return None
    
    async def disconnect(self):
        """
        Disconnect from WebSocket
        """
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("🔌 Disconnected")


async def test_websocket():
    """
    Test WebSocket connection
    """
    logger.info("="*70)
    logger.info("🧪 TESTING cTRADER WEBSOCKET")
    logger.info("="*70)
    
    client = CTraderWebSocketClient()
    
    # Connect
    connected = await client.connect()
    
    if connected:
        # Get account info
        account_info = await client.get_account_info()
        
        if account_info:
            logger.success("✅ WebSocket working!")
            logger.info(f"   Balance: ${account_info['balance']:.2f}")
            logger.info(f"   Equity: ${account_info['equity']:.2f}")
        
        # Keep alive for a bit
        await asyncio.sleep(2)
        
        # Disconnect
        await client.disconnect()
    else:
        logger.error("❌ Connection failed")
    
    logger.info("="*70)


if __name__ == "__main__":
    asyncio.run(test_websocket())
