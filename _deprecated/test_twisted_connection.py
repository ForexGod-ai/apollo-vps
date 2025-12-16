"""
Test FAZA 1 - cTrader ProtoOA cu Twisted (biblioteca oficială)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ctrader_official'))

from twisted.internet import reactor
from loguru import logger
from dotenv import load_dotenv
from ctrader_open_api import Client, TcpProtocol, Protobuf, EndPoints
from ctrader_open_api.messages import OpenApiMessages_pb2 as msg
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import *

load_dotenv()

class cTraderTest:
    def __init__(self):
        self.client_id = os.getenv('CTRADER_CLIENT_ID')
        self.client_secret = os.getenv('CTRADER_CLIENT_SECRET')
        self.access_token = os.getenv('CTRADER_ACCESS_TOKEN')
        self.account_id = int(os.getenv('CTRADER_ACCOUNT_ID', '9709773'))
        
        self.client = None
        self.authenticated = False
        
    def start(self):
        """Start connection"""
        logger.info("=" * 80)
        logger.info("🧪 TEST FAZA 1: CONEXIUNE + AUTENTIFICARE (Twisted)")
        logger.info("=" * 80)
        logger.info(f"Client ID: {self.client_id[:20]}...")
        logger.info(f"Account: {self.account_id}")
        
        # Create client - Try alternative DEMO host
        logger.info("🔌 Creating cTrader client...")
        logger.info("   Host: demo.ctraderapi.com:5035")
        self.client = Client("demo.ctraderapi.com", 5035, TcpProtocol)
        
        # Set callbacks
        self.client.setConnectedCallback(self.on_connected)
        self.client.setDisconnectedCallback(self.on_disconnected)
        self.client.setMessageReceivedCallback(self.on_message)
        
        # Start service
        logger.info("🔌 Starting WebSocket connection...")
        self.client.startService()
        
        # Run reactor for 10 seconds then stop
        reactor.callLater(10, self.stop)
    
    def on_connected(self, client):
        """Called when WebSocket connects"""
        logger.success("✅ WebSocket connected!")
        logger.info("🔐 Authenticating application...")
        logger.debug(f"   Client ID: {self.client_id}")
        logger.debug(f"   Client Secret: {self.client_secret}")
        logger.debug(f"   Access Token: {self.access_token}")
        
        # Send application auth request
        app_auth_req = msg.ProtoOAApplicationAuthReq()
        app_auth_req.clientId = self.client_id
        app_auth_req.clientSecret = self.client_secret
        
        # Send and handle response
        deferred = self.client.send(app_auth_req)
        deferred.addCallback(self.on_app_auth_response)
        deferred.addErrback(self.on_error)
    
    def on_app_auth_response(self, message):
        """Handle application auth response"""
        # Check for error first
        if message.payloadType == msg.ProtoOAErrorRes().payloadType:
            error = Protobuf.extract(message)
            logger.error(f"❌ Server error: {error.errorCode} - {error.description}")
            self.stop()
            return
        
        # Extract actual ProtoOA message from wrapper
        if message.payloadType == msg.ProtoOAApplicationAuthRes().payloadType:
            actual_msg = Protobuf.extract(message)
            logger.success("✅ Application authenticated!")
            logger.info("🔐 Authenticating trading account...")
            
            # Send account auth request
            acc_auth_req = msg.ProtoOAAccountAuthReq()
            acc_auth_req.ctidTraderAccountId = self.account_id
            acc_auth_req.accessToken = self.access_token
            
            deferred = self.client.send(acc_auth_req)
            deferred.addCallback(self.on_account_auth_response)
            deferred.addErrback(self.on_error)
        else:
            logger.error(f"❌ App auth failed: payloadType={message.payloadType}")
            self.stop()
    
    def on_account_auth_response(self, message):
        """Handle account auth response"""
        if message.payloadType == msg.ProtoOAAccountAuthRes().payloadType:
            actual_msg = Protobuf.extract(message)
            logger.success("✅ Trading account authenticated!")
            logger.success("🎉 FAZA 1 COMPLETĂ - READY FOR DATA & TRADING!")
            self.authenticated = True
            
            # Test getting symbols
            self.get_symbols()
        else:
            logger.error(f"❌ Account auth failed: payloadType={message.payloadType}")
            self.stop()
    
    def get_symbols(self):
        """Test getting symbols list"""
        logger.info("\n📋 Testing FAZA 2.1: Getting symbols...")
        
        symbols_req = msg.ProtoOASymbolsListReq()
        symbols_req.ctidTraderAccountId = self.account_id
        
        deferred = self.client.send(symbols_req)
        deferred.addCallback(self.on_symbols_response)
        deferred.addErrback(self.on_error)
    
    def on_symbols_response(self, message):
        """Handle symbols response"""
        if message.payloadType == msg.ProtoOASymbolsListRes().payloadType:
            actual_msg = Protobuf.extract(message)
            logger.success(f"✅ Received {len(actual_msg.symbol)} symbols!")
            
            # Show first 10
            logger.info("First 10 symbols:")
            for i, symbol in enumerate(actual_msg.symbol[:10]):
                logger.info(f"  [{i+1}] {symbol.symbolName} (ID: {symbol.symbolId})")
            
            # Check if our trading pairs exist
            our_symbols = ['GBPUSD', 'EURUSD', 'XAUUSD', 'BTCUSD']
            found = [s.symbolName for s in actual_msg.symbol if s.symbolName in our_symbols]
            
            logger.info(f"\n✅ Found {len(found)}/{len(our_symbols)} of our symbols: {', '.join(found)}")
            
            # Success - stop after 2 seconds
            reactor.callLater(2, self.stop)
        else:
            logger.error(f"❌ Symbols request failed: payloadType={message.payloadType}")
            self.stop()
    
    def on_message(self, client, message):
        """Called for every message received"""
        # Log message type
        msg_type = type(message).__name__
        if 'Error' in msg_type:
            logger.warning(f"⚠️  Received: {msg_type}")
            logger.debug(f"   Content: {message}")
    
    def on_disconnected(self, client, reason):
        """Called when WebSocket disconnects"""
        logger.warning(f"⚠️  Disconnected: {reason}")
    
    def on_error(self, failure):
        """Handle errors"""
        logger.error(f"❌ Error: {failure}")
        self.stop()
    
    def stop(self):
        """Stop client and reactor"""
        logger.info("\n👋 Stopping client...")
        
        if self.client and self.client.running:
            self.client.stopService()
        
        if reactor.running:
            reactor.stop()
        
        if self.authenticated:
            logger.info("\n" + "=" * 80)
            logger.success("✅ TEST SUCCESS - cTrader ProtoOA Working!")
            logger.info("=" * 80)

if __name__ == "__main__":
    test = cTraderTest()
    test.start()
    
    try:
        reactor.run()
    except KeyboardInterrupt:
        logger.info("\nStopped by user")
