#!/usr/bin/env python3
"""
Generate FRESH cTrader Access Token for ProtoOA
Opens browser for OAuth flow
"""

import os
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv('CTRADER_CLIENT_ID')
CLIENT_SECRET = os.getenv('CTRADER_CLIENT_SECRET')
REDIRECT_URI = "http://localhost:5000/callback"

# OAuth endpoints
AUTH_URL = "https://openapi.ctrader.com/apps/auth"
TOKEN_URL = "https://openapi.ctrader.com/apps/token"

authorization_code = None

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global authorization_code
        
        if '/callback' in self.path:
            # Parse authorization code
            query = urlparse(self.path).query
            params = parse_qs(query)
            
            if 'code' in params:
                authorization_code = params['code'][0]
                
                # Send success page
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                html = """
                <html>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h1 style="color: green;">Authorization Successful!</h1>
                    <p>You can close this window and return to terminal.</p>
                </body>
                </html>
                """
                self.wfile.write(html.encode('utf-8'))
                
                logger.success(f"✅ Authorization code received: {authorization_code[:20]}...")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Error: No authorization code")
    
    def log_message(self, format, *args):
        pass  # Suppress default logging

def exchange_code_for_token(code):
    """Exchange authorization code for access token"""
    try:
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }
        
        response = requests.post(
            TOKEN_URL,
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Token exchange failed: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Token exchange error: {e}")
        return None

def update_env_file(access_token, refresh_token):
    """Update .env file with new tokens"""
    try:
        env_path = '.env'
        
        with open(env_path, 'r') as f:
            lines = f.readlines()
        
        with open(env_path, 'w') as f:
            for line in lines:
                if line.startswith('CTRADER_ACCESS_TOKEN='):
                    f.write(f'CTRADER_ACCESS_TOKEN={access_token}\n')
                elif line.startswith('CTRADER_REFRESH_TOKEN='):
                    f.write(f'CTRADER_REFRESH_TOKEN={refresh_token}\n')
                else:
                    f.write(line)
        
        logger.success("✅ Updated .env with new tokens")
        
    except Exception as e:
        logger.error(f"Error updating .env: {e}")

def main():
    logger.info("="*70)
    logger.info("🔐 cTrader OAuth2 Flow - Get Fresh Access Token")
    logger.info("="*70)
    logger.info(f"Client ID: {CLIENT_ID[:20]}...")
    logger.info("")
    
    # Build authorization URL
    auth_url = (
        f"{AUTH_URL}?"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"scope=trading&"
        f"response_type=code"
    )
    
    logger.info("📋 Steps:")
    logger.info("1. Browser will open with cTrader login")
    logger.info("2. Login with your IC Markets account")
    logger.info("3. Authorize the application")
    logger.info("4. You'll be redirected to localhost:5000")
    logger.info("5. Tokens will be saved automatically")
    logger.info("")
    
    # Start local server
    logger.info("🚀 Starting local server on port 5000...")
    server = HTTPServer(('localhost', 5000), OAuthHandler)
    
    # Open browser
    logger.info("🌐 Opening browser for OAuth authorization...")
    logger.info(f"URL: {auth_url[:80]}...")
    webbrowser.open(auth_url)
    
    logger.info("⏳ Waiting for authorization...")
    
    # Handle one request (the callback)
    server.handle_request()
    
    if authorization_code:
        logger.info("")
        logger.info("🔄 Exchanging authorization code for tokens...")
        
        token_data = exchange_code_for_token(authorization_code)
        
        if token_data:
            access_token = token_data.get('access_token')
            refresh_token = token_data.get('refresh_token')
            expires_in = token_data.get('expires_in', 0)
            
            logger.success("")
            logger.success("="*70)
            logger.success("✅ SUCCESS! Tokens received")
            logger.success("="*70)
            logger.success(f"Access Token: {access_token[:30]}...")
            logger.success(f"Refresh Token: {refresh_token[:30]}...")
            logger.success(f"Expires in: {expires_in / 3600:.1f} hours")
            logger.success("="*70)
            
            # Update .env
            update_env_file(access_token, refresh_token)
            
            logger.info("")
            logger.info("🎉 Ready to test ProtoOA!")
            logger.info("Run: python3 test_protooa_simple.py")
            logger.info("")
        else:
            logger.error("❌ Failed to get tokens")
    else:
        logger.error("❌ No authorization code received")
    
    server.server_close()

if __name__ == "__main__":
    main()
