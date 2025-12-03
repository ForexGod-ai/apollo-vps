"""
cTrader Web Login - Access account via credentials
Using cTrader Connect API with username/email
"""

import requests
from loguru import logger

def login_ctrader_web(username, email, password):
    """
    Attempt to login to cTrader Web platform
    """
    
    logger.info(f"🔐 Attempting cTrader Web login...")
    logger.info(f"   Username: {username}")
    logger.info(f"   Email: {email}")
    
    # cTrader Web endpoints
    endpoints = [
        "https://api.ctrader.com/connect/token",
        "https://connect.spotware.com/apps/token",
        "https://demo.icmarkets.com/ctrader/api/login",
        "https://id.ctrader.com/connect/token"
    ]
    
    # Try different authentication methods
    for endpoint in endpoints:
        try:
            logger.info(f"\n🔄 Trying endpoint: {endpoint}")
            
            # Method 1: Direct login
            payload = {
                "grant_type": "password",
                "username": username,
                "password": password,
                "email": email
            }
            
            response = requests.post(
                endpoint,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10
            )
            
            logger.info(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                logger.success("✅ Login successful!")
                return response.json()
            else:
                logger.debug(f"   Response: {response.text[:200]}")
                
        except Exception as e:
            logger.debug(f"   Error: {e}")
            continue
    
    # Try cTrader Mobile API endpoint
    logger.info("\n🔄 Trying cTrader Mobile API...")
    try:
        mobile_endpoint = "https://mobile.ctrader.com/api/v1/login"
        
        response = requests.post(
            mobile_endpoint,
            json={
                "email": email,
                "password": password
            },
            timeout=10
        )
        
        if response.status_code == 200:
            logger.success("✅ Mobile API login successful!")
            return response.json()
        else:
            logger.debug(f"Mobile API response: {response.text[:200]}")
            
    except Exception as e:
        logger.debug(f"Mobile API error: {e}")
    
    logger.warning("⚠️  Could not authenticate with provided credentials")
    logger.info("\n💡 Alternative approaches:")
    logger.info("1. Use cTrader desktop app - it stores data locally")
    logger.info("2. Register OAuth app at: https://connect.spotware.com/apps")
    logger.info("3. Check if IC Markets provides API credentials separately")
    
    return None


def check_ctrader_account_via_api():
    """
    Check cTrader account using stored credentials
    """
    
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    username = "pocovnicu.razvan12"
    email = "pocovnicu.razvan12@gmail.com"
    password = os.getenv('CTRADER_PASSWORD')
    account_id = os.getenv('CTRADER_ACCOUNT_ID')
    
    if not password:
        logger.error("❌ CTRADER_PASSWORD not set in .env")
        return None
    
    logger.info("🔌 Connecting to cTrader account...")
    logger.info(f"   Account ID: {account_id}")
    logger.info(f"   Username: {username}")
    logger.info(f"   Email: {email}")
    
    # Try to login
    result = login_ctrader_web(username, email, password)
    
    if result:
        logger.success("✅ Successfully connected to cTrader!")
        logger.info(f"Response: {result}")
        
        # Try to get account info
        if 'access_token' in result:
            token = result['access_token']
            
            # Query account data
            account_url = f"https://api.ctrader.com/v3/accounts/{account_id}"
            headers = {"Authorization": f"Bearer {token}"}
            
            try:
                account_response = requests.get(account_url, headers=headers, timeout=10)
                
                if account_response.status_code == 200:
                    account_data = account_response.json()
                    logger.success("✅ Account data retrieved!")
                    logger.info(f"\n{account_data}")
                    return account_data
                else:
                    logger.debug(f"Account API response: {account_response.text[:200]}")
                    
            except Exception as e:
                logger.error(f"Error fetching account data: {e}")
        
        return result
    else:
        logger.error("❌ Could not connect to cTrader")
        logger.info("\n📋 Manual verification needed:")
        logger.info("1. Open cTrader desktop/web")
        logger.info("2. Check Account History for:")
        logger.info("   - Current Balance")
        logger.info("   - Total Profit/Loss")
        logger.info("   - Number of closed trades")
        logger.info("3. Share those numbers and I'll generate the report")
        
        return None


if __name__ == "__main__":
    result = check_ctrader_account_via_api()
    
    if not result:
        print("\n" + "="*60)
        print("⚠️  DIRECT API ACCESS NOT AVAILABLE")
        print("="*60)
        print()
        print("cTrader requires OAuth2 setup for programmatic access.")
        print()
        print("📋 To get your account data, please:")
        print()
        print("1. Open cTrader (desktop or web)")
        print("2. Login with:")
        print("   - Username: pocovnicu.razvan12")
        print("   - Email: pocovnicu.razvan12@gmail.com")
        print()
        print("3. Go to 'History' tab and note:")
        print("   - Balance: $_____")
        print("   - Profit: $_____")
        print("   - Number of trades: _____")
        print()
        print("4. Share those numbers and I'll generate the report!")
        print()
        print("="*60)
