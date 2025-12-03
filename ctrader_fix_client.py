"""
cTrader FIX API Client - Direct connection to IC Markets
Live data feed without Yahoo Finance dependency
"""

import socket
import ssl
import time
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Dict, List, Optional
import pandas as pd
from threading import Lock

class CTraderFIXClient:
    """
    FIX Protocol client for cTrader
    Connects directly to IC Markets demo server
    """
    
    def __init__(self, 
                 host: str = "h51.p.ctrader.com",
                 port: int = 5021,
                 sender_comp_id: str = "demo.icmarkets.9709773",
                 target_comp_id: str = "CSERVER",
                 password: str = None):
        
        self.host = host
        self.port = port
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id
        self.password = password
        
        self.socket = None
        self.seq_num = 1
        self.lock = Lock()
        self.connected = False
        
        print(f"🔧 cTrader FIX Client initialized for {sender_comp_id}")
    
    def _create_fix_message(self, msg_type: str, fields: Dict[str, str]) -> str:
        """Create FIX protocol message"""
        
        # Standard header
        msg = f"8=FIX.4.4\x01"  # BeginString
        msg += f"35={msg_type}\x01"  # MsgType
        msg += f"49={self.sender_comp_id}\x01"  # SenderCompID
        msg += f"56={self.target_comp_id}\x01"  # TargetCompID
        msg += f"34={self.seq_num}\x01"  # MsgSeqNum
        msg += f"52={datetime.now(timezone.utc).strftime('%Y%m%d-%H:%M:%S')}\x01"  # SendingTime
        
        # Body fields
        body = ""
        for tag, value in fields.items():
            body += f"{tag}={value}\x01"
        
        # Calculate length
        body_with_header = msg + body
        length = len(body_with_header.split("8=FIX.4.4\x01")[1])
        
        # Insert body length
        msg = f"8=FIX.4.4\x019={length}\x01" + msg.split("8=FIX.4.4\x01")[1] + body
        
        # Calculate checksum
        checksum = sum(ord(c) for c in msg) % 256
        msg += f"10={checksum:03d}\x01"
        
        self.seq_num += 1
        return msg
    
    def connect(self) -> bool:
        """Connect to cTrader FIX server"""
        
        try:
            print(f"🔌 Connecting to {self.host}:{self.port}...")
            
            # Create SSL socket
            context = ssl.create_default_context()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket = context.wrap_socket(sock, server_hostname=self.host)
            self.socket.connect((self.host, self.port))
            
            print("✅ Socket connected, sending Logon message...")
            
            # Send Logon message (MsgType=A)
            logon_fields = {
                "98": "0",  # EncryptMethod (None)
                "108": "30",  # HeartBtInt (30 seconds)
                "553": self.sender_comp_id.split('.')[-1],  # Username (account number)
                "554": self.password or "YourPasswordHere",  # Password
            }
            
            logon_msg = self._create_fix_message("A", logon_fields)
            self.socket.send(logon_msg.encode('utf-8'))
            
            # Wait for response
            response = self.socket.recv(4096).decode('utf-8')
            
            if "35=A" in response:  # Logon acknowledged
                print("✅ cTrader FIX connection established!")
                self.connected = True
                return True
            else:
                print(f"❌ Logon failed: {response}")
                return False
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def request_historical_data(self, symbol: str, timeframe: str, bars: int = 1000) -> Optional[pd.DataFrame]:
        """
        Request historical OHLCV data
        """
        
        if not self.connected:
            print("⚠️ Not connected to cTrader FIX server")
            return None
        
        try:
            # Market Data Request (MsgType=V)
            req_id = f"MD_{int(time.time())}"
            
            fields = {
                "262": req_id,  # MDReqID
                "263": "1",  # SubscriptionRequestType (Snapshot + Updates)
                "264": "0",  # MarketDepth (Full Book)
                "265": "0",  # MDUpdateType (Full Refresh)
                "146": "1",  # NoRelatedSym
                "55": symbol,  # Symbol
                "267": "2",  # NoMDEntryTypes
                "269": "0",  # MDEntryType (Bid)
                "269": "1",  # MDEntryType (Offer)
            }
            
            msg = self._create_fix_message("V", fields)
            self.socket.send(msg.encode('utf-8'))
            
            # Receive response
            response = self.socket.recv(8192).decode('utf-8')
            print(f"📊 Response: {response[:200]}...")
            
            # Parse response (simplified - needs full FIX parser)
            # For now, return placeholder
            return None
            
        except Exception as e:
            print(f"❌ Data request error: {e}")
            return None
    
    def disconnect(self):
        """Disconnect from FIX server"""
        
        if self.socket:
            try:
                # Send Logout message (MsgType=5)
                logout_msg = self._create_fix_message("5", {})
                self.socket.send(logout_msg.encode('utf-8'))
                self.socket.close()
                print("👋 Disconnected from cTrader FIX")
            except:
                pass
        
        self.connected = False


class CTraderProtoClient:
    """
    cTrader Open API via protobuf (simpler alternative)
    Using demo.icmarkets.com WebSocket connection
    """
    
    def __init__(self, account_id: str = "9709773", access_token: str = None):
        self.account_id = account_id
        self.access_token = access_token
        self.base_url = "https://api.spotware.com"
        
        print(f"🌐 cTrader Proto Client initialized for account {account_id}")
    
    def get_historical_data(self, symbol: str, timeframe: str = "H4", bars: int = 1000) -> Optional[pd.DataFrame]:
        """
        Get historical data via cTrader API
        For now, returns None - needs OAuth setup
        """
        
        print(f"⚠️ cTrader Proto API requires OAuth2 setup")
        print(f"📖 Visit: https://help.ctrader.com/open-api/")
        return None


# Singleton instance
_ctrader_client = None

def get_ctrader_client() -> CTraderFIXClient:
    """Get or create cTrader FIX client"""
    global _ctrader_client
    
    if _ctrader_client is None:
        _ctrader_client = CTraderFIXClient()
    
    return _ctrader_client


if __name__ == "__main__":
    # Test connection
    client = CTraderFIXClient()
    
    if client.connect():
        print("✅ cTrader FIX connection successful!")
        
        # Try to get data
        df = client.request_historical_data("EURUSD", "H4", 100)
        
        if df is not None:
            print(f"📊 Received {len(df)} bars")
            print(df.head())
        
        client.disconnect()
    else:
        print("❌ Connection failed")
        print("\n📋 Setup instructions:")
        print("1. Get your cTrader account password")
        print("2. Update password in .env file: CTRADER_PASSWORD=your_password")
        print("3. Or register at: https://connect.spotware.com/")
