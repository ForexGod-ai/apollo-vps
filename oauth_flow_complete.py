#!/usr/bin/env python3
"""
cTrader OAuth Complete Flow
Gets proper Access + Refresh tokens
"""

import os
from dotenv import load_dotenv
from loguru import logger
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
import re

load_dotenv()

CLIENT_ID = os.getenv('CTRADER_CLIENT_ID')
CLIENT_SECRET = os.getenv('CTRADER_CLIENT_SECRET')

# OAuth URLs
AUTH_URL = "https://openapi.ctrader.com/apps/auth"
TOKEN_URL = "https://openapi.ctrader.com/apps/token"
REDIRECT_URI = "http://localhost:8080/callback"

authorization_code = None


class OAuthHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback"""
    
    def do_GET(self):
        global authorization_code
        
        # Parse URL
        parsed = urlparse(self.path)
        
        if parsed.path == '/callback':
            # Get authorization code
            params = parse_qs(parsed.query)
            
            if 'code' in params:
                authorization_code = params['code'][0]
                
                # Send success response
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                
                html = """
                <html>
                <head><title>Authorization Successful</title></head>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h1 style="color: green;">✅ Authorization Successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                    <p>Code received: <code>{}</code></p>
                </body>
                </html>
                """.format(authorization_code[:20] + "...")
                
                self.wfile.write(html.encode())
                
                logger.success(f"✅ Authorization code received: {authorization_code[:20]}...")
            else:
                # Error
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                
                html = """
                <html>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h1 style="color: red;">❌ Authorization Failed</h1>
                    <p>No code received.</p>
                </body>
                </html>
                """
                
                self.wfile.write(html.encode())
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


def exchange_code_for_token(code):
    """Exchange authorization code for access token"""
    
    logger.info("🔄 Exchanging code for tokens...")
    
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    
    try:
        response = requests.post(TOKEN_URL, data=data)
        
        logger.info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            tokens = response.json()
            
            if 'access_token' in tokens:
                access_token = tokens['access_token']
                refresh_token = tokens.get('refresh_token', 'N/A')
                expires_in = tokens.get('expires_in', 'Unknown')
                
                logger.success("✅ Tokens received!")
                logger.info(f"   Access Token: {access_token}")
                logger.info(f"   Refresh Token: {refresh_token}")
                logger.info(f"   Expires in: {expires_in} seconds")
                
                # Update .env
                logger.info("\n📝 Updating .env file...")
                
                with open('.env', 'r') as f:
                    env_content = f.read()
                
                env_content = re.sub(
                    r'CTRADER_ACCESS_TOKEN=.*',
                    f'CTRADER_ACCESS_TOKEN={access_token}',
                    env_content
                )
                
                env_content = re.sub(
                    r'CTRADER_REFRESH_TOKEN=.*',
                    f'CTRADER_REFRESH_TOKEN={refresh_token}',
                    env_content
                )
                
                with open('.env', 'w') as f:
                    f.write(env_content)
                
                logger.success("✅ .env updated!")
                
                return True
            else:
                logger.error(f"❌ No access_token in response: {response.text}")
                return False
        else:
            logger.error(f"❌ Token exchange failed: {response.status_code}")
            logger.error(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    global authorization_code
    
    logger.info("="*70)
    logger.info("🔐 cTrader OAuth Authorization Flow")
    logger.info("="*70)
    
    # Build authorization URL
    auth_url = f"{AUTH_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=trading&response_type=code"
    
    logger.info("\n📋 Starting OAuth flow...")
    logger.info("1. Browser will open with cTrader login")
    logger.info("2. Login and authorize the application")
    logger.info("3. You'll be redirected back to localhost:8080")
    logger.info("4. Tokens will be automatically saved\n")
    
    # Start local server
    logger.info("🚀 Starting local server on port 8080...")
    server = HTTPServer(('localhost', 8080), OAuthHandler)
    
    # Open browser
    logger.info("🌐 Opening browser...")
    webbrowser.open(auth_url)
    
    logger.info("⏳ Waiting for authorization...")
    
    # Handle one request (the callback)
    server.handle_request()
    
    if authorization_code:
        # Exchange code for token
        success = exchange_code_for_token(authorization_code)
        
        if success:
            logger.success("\n✅ OAuth flow complete!")
            logger.info("🚀 Ready to connect to cTrader API")
        else:
            logger.error("\n❌ Failed to get tokens")
    else:
        logger.error("\n❌ No authorization code received")
    
    logger.info("\n" + "="*70)


if __name__ == "__main__":
    main()
