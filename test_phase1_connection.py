"""
Test RAPID - Conexiune + Autentificare cTrader ProtoOA
Testează doar FAZA 1 (fundația necesară)
"""
import sys
import os
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ctrader_official'))

from loguru import logger
from dotenv import load_dotenv
from ctrader_open_api import Client, TcpProtocol
from ctrader_open_api.messages import OpenApiMessages_pb2 as msg

load_dotenv()

async def test_connection():
    """Test doar conexiune + autentificare (FAZA 1)"""
    logger.info("=" * 80)
    logger.info("🧪 TEST FAZA 1: CONEXIUNE + AUTENTIFICARE")
    logger.info("=" * 80)
    
    # Credentials
    client_id = os.getenv('CTRADER_CLIENT_ID')
    client_secret = os.getenv('CTRADER_CLIENT_SECRET')
    access_token = os.getenv('CTRADER_ACCESS_TOKEN')
    account_id = int(os.getenv('CTRADER_ACCOUNT_ID', '9709773'))
    
    logger.info(f"Client ID: {client_id[:20]}...")
    logger.info(f"Account: {account_id}")
    
    try:
        # Connect to WebSocket
        logger.info("🔌 Connecting to cTrader WebSocket...")
        client = Client("demo.ctraderapi.com", 5035, TcpProtocol)
        
        await client.connect()
        logger.success("✅ WebSocket connected!")
        
        # Authenticate Application
        logger.info("🔐 Authenticating application...")
        app_auth_req = msg.ProtoOAApplicationAuthReq()
        app_auth_req.clientId = client_id
        app_auth_req.clientSecret = client_secret
        
        await client.send(app_auth_req)
        app_auth_res = await client.receive()
        
        if isinstance(app_auth_res, msg.ProtoOAApplicationAuthRes):
            logger.success("✅ Application authenticated!")
        else:
            logger.error(f"❌ App auth failed: {type(app_auth_res)}")
            logger.error(f"Response: {app_auth_res}")
            await client.disconnect()
            return False
        
        # Authenticate Account
        logger.info("🔐 Authenticating trading account...")
        acc_auth_req = msg.ProtoOAAccountAuthReq()
        acc_auth_req.ctidTraderAccountId = account_id
        acc_auth_req.accessToken = access_token
        
        await client.send(acc_auth_req)
        acc_auth_res = await client.receive()
        
        if isinstance(acc_auth_res, msg.ProtoOAAccountAuthRes):
            logger.success("✅ Trading account authenticated!")
            logger.success("🎉 FAZA 1 COMPLETĂ - READY FOR DATA & TRADING!")
            
            await client.disconnect()
            return True
        else:
            logger.error(f"❌ Account auth failed: {type(acc_auth_res)}")
            logger.error(f"Response: {acc_auth_res}")
            await client.disconnect()
            return False
        
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_connection())
    
    if result:
        logger.info("\n" + "=" * 80)
        logger.success("✅ FAZA 1 SUCCESS - Foundation Ready!")
        logger.info("   Next: Implement FAZA 2 (Trendbars), FAZA 3 (Trading), etc.")
        logger.info("=" * 80)
    else:
        logger.error("\n❌ FAZA 1 FAILED - Check credentials!")
