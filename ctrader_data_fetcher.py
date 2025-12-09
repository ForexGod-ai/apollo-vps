"""
cTrader Data Fetcher - SIMPLIFIED VERSION
==========================================
Folosește ctrader_official library pentru a fetcha date pentru toate 21 paritatile
Fără Twisted - doar sync client pentru compatibilitate macOS
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
from dotenv import load_dotenv

# Add cTrader official library to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ctrader_official'))

from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import *
from ctrader_open_api.messages.OpenApiMessages_pb2 import *
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import *

load_dotenv()


class CTraderDataFetcher:
    """
    Simplified cTrader client pentru fetching data
    Folosește Twisted reactor în background
    """
    
    def __init__(self):
        self.client_id = os.getenv('CTRADER_CLIENT_ID')
        self.client_secret = os.getenv('CTRADER_CLIENT_SECRET')
        self.access_token = os.getenv('CTRADER_ACCESS_TOKEN')
        self.account_id = int(os.getenv('CTRADER_ACCOUNT_ID', '9709773'))
        
        # Host (demo sau live)
        self.demo = os.getenv('CTRADER_DEMO', 'True').lower() == 'true'
        self.host = EndPoints.PROTOBUF_DEMO_HOST if self.demo else EndPoints.PROTOBUF_LIVE_HOST
        self.port = EndPoints.PROTOBUF_PORT
        
        # Client instance
        self.client = None
        self.connected = False
        self.authenticated = False
        
        # Symbols mapping (symbol_name -> symbol_id)
        self.symbols = {}
        
        # Data cache
        self.trendbars_cache = {}
        
        logger.info("🚀 cTrader Data Fetcher initialized")
        logger.info(f"   Host: {self.host}:{self.port}")
        logger.info(f"   Account: {self.account_id}")
        logger.info(f"   Mode: {'DEMO' if self.demo else 'LIVE'}")
    
    def get_all_symbols(self) -> Dict[str, int]:
        """
        Fetch available symbols from cTrader
        Returns dict: {symbol_name: symbol_id}
        """
        logger.info("📋 Fetching available symbols from cTrader...")
        
        try:
            from twisted.internet import reactor
            
            # Initialize client
            self.client = Client(self.host, self.port, TcpProtocol)
            
            # Setup callbacks
            self.client.setConnectedCallback(self._on_connected)
            self.client.setDisconnectedCallback(self._on_disconnected)
            self.client.setMessageReceivedCallback(self._on_message_received)
            
            # Start connection
            self.client.startService()
            
            # Run reactor for a limited time
            reactor.callLater(15, reactor.stop)  # Stop after 15 seconds
            reactor.run()
            
            logger.success(f"✅ Fetched {len(self.symbols)} symbols")
            return self.symbols
            
        except Exception as e:
            logger.error(f"❌ Error fetching symbols: {e}")
            return {}
    
    def _on_connected(self, client):
        """Callback when connected"""
        logger.success("✅ Connected to cTrader")
        self.connected = True
        
        # Authenticate application
        request = ProtoOAApplicationAuthReq()
        request.clientId = self.client_id
        request.clientSecret = self.client_secret
        
        deferred = client.send(request)
        deferred.addErrback(self._on_error)
    
    def _on_disconnected(self, client, reason):
        """Callback when disconnected"""
        logger.warning(f"⚠️  Disconnected: {reason}")
        self.connected = False
    
    def _on_message_received(self, client, message):
        """Callback for all messages"""
        try:
            payload_type = message.payloadType
            
            # Ignore heartbeats
            if payload_type == ProtoHeartbeatEvent().payloadType:
                return
            
            # Application authentication response
            if payload_type == ProtoOAApplicationAuthRes().payloadType:
                logger.success("✅ Application authenticated")
                self.authenticated = True
                
                # Now authenticate account
                self._authenticate_account(client)
            
            # Account authentication response
            elif payload_type == ProtoOAAccountAuthRes().payloadType:
                logger.success(f"✅ Account {self.account_id} authenticated")
                
                # Request symbols list
                self._request_symbols_list(client)
            
            # Symbols list response
            elif payload_type == ProtoOASymbolsListRes().payloadType:
                response = Protobuf.extract(message)
                
                logger.info(f"📊 Received {len(response.symbol)} symbols")
                
                for symbol in response.symbol:
                    symbol_name = symbol.symbolName
                    symbol_id = symbol.symbolId
                    self.symbols[symbol_name] = symbol_id
                    
                    # Log relevant symbols
                    if any(pair in symbol_name for pair in ['BTC', 'XAU', 'XAG', 'USOIL', 'GBP', 'EUR', 'USD', 'AUD', 'NZD', 'CHF', 'JPY', 'CAD']):
                        logger.debug(f"   {symbol_name} -> ID: {symbol_id}")
                
                logger.success(f"✅ Symbols cached: {len(self.symbols)}")
                
                # Stop reactor now that we have symbols
                from twisted.internet import reactor
                reactor.callLater(1, reactor.stop)
            
            else:
                logger.debug(f"📨 Message: {payload_type}")
        
        except Exception as e:
            logger.error(f"❌ Message processing error: {e}")
    
    def _on_error(self, failure):
        """Callback for errors"""
        logger.error(f"❌ Error: {failure}")
    
    def _authenticate_account(self, client):
        """Authenticate trading account"""
        request = ProtoOAAccountAuthReq()
        request.ctidTraderAccountId = self.account_id
        request.accessToken = self.access_token
        
        deferred = client.send(request)
        deferred.addErrback(self._on_error)
    
    def _request_symbols_list(self, client):
        """Request list of available symbols"""
        request = ProtoOASymbolsListReq()
        request.ctidTraderAccountId = self.account_id
        request.includeArchivedSymbols = False
        
        deferred = client.send(request)
        deferred.addErrback(self._on_error)
    
    def check_pair_availability(self, pairs: List[str]) -> Dict[str, bool]:
        """
        Check which pairs from config are available on broker
        
        Args:
            pairs: List of symbol names (e.g., ['BTCUSD', 'XAUUSD', ...])
        
        Returns:
            Dict: {symbol_name: available (True/False)}
        """
        logger.info(f"🔍 Checking availability for {len(pairs)} pairs...")
        
        # Fetch symbols if not already done
        if not self.symbols:
            self.get_all_symbols()
        
        result = {}
        available_count = 0
        
        for pair in pairs:
            # Check exact match
            if pair in self.symbols:
                result[pair] = True
                available_count += 1
                logger.success(f"   ✅ {pair} - Available (ID: {self.symbols[pair]})")
            else:
                result[pair] = False
                logger.warning(f"   ❌ {pair} - NOT available on broker")
        
        logger.info(f"\n📊 SUMMARY: {available_count}/{len(pairs)} pairs available on IC Markets")
        
        return result


def test_data_fetcher():
    """Test cTrader data fetcher"""
    logger.info("=" * 70)
    logger.info("🧪 TESTING CTRADER DATA FETCHER")
    logger.info("=" * 70)
    
    # Load pairs from config
    with open('pairs_config.json', 'r') as f:
        config = json.load(f)
        pairs = [p['symbol'] for p in config['pairs']]
    
    logger.info(f"\n📋 Checking {len(pairs)} pairs from pairs_config.json:")
    for i, pair in enumerate(pairs, 1):
        logger.info(f"   {i:2d}. {pair}")
    
    # Create fetcher
    fetcher = CTraderDataFetcher()
    
    # Check availability
    availability = fetcher.check_pair_availability(pairs)
    
    # Save results
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_pairs": len(pairs),
        "available_pairs": sum(availability.values()),
        "availability": availability,
        "symbol_ids": {pair: fetcher.symbols.get(pair, None) for pair in pairs if availability.get(pair, False)}
    }
    
    with open('ctrader_pair_availability.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.success(f"\n✅ Results saved to: ctrader_pair_availability.json")
    logger.info("=" * 70)


if __name__ == "__main__":
    test_data_fetcher()
